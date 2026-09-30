# -*- coding: utf-8 -*-
"""
潮汐视频 · 混合推荐引擎 v0.1

三路召回/打分通道：
  1. 热门通道    —— 播放/点赞加权 + 时间衰减（Hacker News 风格）
  2. ItemCF 通道 —— 基于物品的协同过滤（共现余弦相似度 + 行为近因加权）
  3. 兴趣通道    —— 用户分类/标签画像 + 最近浏览实时加权（“实时特征”雏形）

融合：total = W_HOT*hot + W_CONTENT*content + W_CF*itemcf
      （当前权重 W_HOT=0.20 / W_CONTENT=0.50 / W_CF=0.30，见下方常量）
输出：候选列表 + 可解释推荐理由 + 分数构成（debug）
"""
import math
import time

W_HOT = 0.20
W_CONTENT = 0.50
W_CF = 0.30
REALTIME_BOOST = 1.7                # 最近浏览类目的推荐乘性加成
RECENCY_HALF_LIFE = 7.0 * 86400.0   # 行为权重按一周半衰期衰减
RECENT_WINDOW = 5                   # 最近 5 次观看视为“实时兴趣”


class Recommender(object):

    def __init__(self, conn):
        self.videos = {}
        for r in conn.execute("SELECT * FROM videos"):
            v = dict(r)
            v["tags"] = [t.strip() for t in (v.get("tags") or "").split(",") if t.strip()]
            self.videos[v["id"]] = v
        self.events = [
            dict(r)
            for r in conn.execute(
                "SELECT user_id, video_id, event, watch_ratio, created_at "
                "FROM behaviors ORDER BY created_at"
            )
        ]

    @classmethod
    def from_data(cls, videos, behaviors):
        """从内存数据构建（供无状态推荐接口 /api/recommend 使用）"""
        obj = cls.__new__(cls)
        obj.videos = {}
        for v in videos:
            tags = v.get("tags")
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            elif isinstance(tags, list):
                tags = [str(t).strip() for t in tags if str(t).strip()]
            else:
                tags = []
            obj.videos[int(v["id"])] = {
                "id": int(v["id"]),
                "title": v.get("title", ""),
                "category": v.get("category", ""),
                "tags": tags,
                "filename": v.get("filename", ""),
                "uploader_id": v.get("uploader_id"),
                "created_at": float(v.get("created_at", 0)),
                "views": int(v.get("views", 0)),
                "likes": int(v.get("likes", 0)),
            }
        obj.events = sorted(
            [
                {
                    "user_id": int(b.get("user_id")),
                    "video_id": int(b.get("video_id")),
                    "event": b.get("event"),
                    "watch_ratio": float(b.get("watch_ratio", 0)),
                    "created_at": float(b.get("created_at", 0)),
                }
                for b in behaviors
            ],
            key=lambda e: e["created_at"],
        )
        return obj

    # ------------------------------------------------------------ 工具
    @staticmethod
    def _norm(scores):
        if not scores:
            return {}
        mx = max(scores.values())
        if mx <= 0:
            return {k: 0.0 for k in scores}
        return {k: v / mx for k, v in scores.items()}

    @staticmethod
    def _recency(ts, now):
        return 0.5 ** (max(now - ts, 0.0) / RECENCY_HALF_LIFE)

    def _positive(self, user_id):
        """用户正向行为序列 [(video_id, weight, ts), ...]"""
        out = []
        for e in self.events:
            if e["user_id"] != user_id:
                continue
            ratio = e["watch_ratio"] or 0.0
            if e["event"] == "like":
                w = 3.0
            elif e["event"] == "finish":
                w = 2.0
            elif e["event"] == "progress" and ratio >= 0.5:
                w = 1.0
            elif e["event"] == "view" and ratio >= 0.5:
                w = 0.8
            else:
                continue
            out.append((e["video_id"], w, e["created_at"]))
        return out

    # ------------------------------------------------------------ 通道 1：热门
    def hot_scores(self, now):
        s = {}
        for v in self.videos.values():
            age_h = max((now - v["created_at"]) / 3600.0, 1.0)
            raw = v["views"] + 3.0 * v["likes"]
            s[v["id"]] = raw / math.pow(age_h + 2.0, 0.3)
        return self._norm(s)

    # ------------------------------------------------------------ 通道 2：ItemCF
    def cf_scores(self, user_id):
        """返回 (归一化分数, 每个候选的最高分来源视频)"""
        user_pos = {}
        for e in self.events:
            ratio = e["watch_ratio"] or 0.0
            positive = (
                e["event"] in ("like", "finish")
                or (e["event"] in ("progress", "view") and ratio >= 0.5)
            )
            if positive:
                user_pos.setdefault(e["user_id"], set()).add(e["video_id"])

        co, pop = {}, {}
        for items in user_pos.values():
            ids = sorted(items)
            for i in range(len(ids)):
                pop[ids[i]] = pop.get(ids[i], 0) + 1
                for j in range(i + 1, len(ids)):
                    co[(ids[i], ids[j])] = co.get((ids[i], ids[j]), 0) + 1

        def sim(a, b):
            c = co.get((min(a, b), max(a, b)), 0)
            if c == 0:
                return 0.0
            return c / math.sqrt(pop.get(a, 1) * pop.get(b, 1))

        now = time.time()
        s, src = {}, {}
        for vid, w, ts in self._positive(user_id):
            if vid not in self.videos:
                continue
            rec = self._recency(ts, now)
            for cand in self.videos:
                if cand == vid:
                    continue
                sc = sim(vid, cand) * w * rec
                if sc > 0:
                    s[cand] = s.get(cand, 0.0) + sc
                    if sc > src.get(cand, (0.0, None))[0]:
                        src[cand] = (sc, vid)
        return self._norm(s), src

    # ------------------------------------------------------------ 通道 3：兴趣 + 实时
    def content_scores(self, user_id, now):
        cat_aff, tag_aff = {}, {}
        my_views = [
            e for e in self.events
            if e["user_id"] == user_id and e["event"] == "view"
        ]
        recent_cats = set()
        for e in my_views[-RECENT_WINDOW:]:
            v = self.videos.get(e["video_id"])
            if v:
                recent_cats.add(v["category"])

        for e in self.events:
            if e["user_id"] != user_id:
                continue
            ratio = e["watch_ratio"] or 0.0
            if e["event"] == "like":
                w = 3.0
            elif e["event"] == "finish":
                w = 2.0
            elif e["event"] in ("progress", "view") and ratio >= 0.3:
                w = 1.0
            elif e["event"] == "view":
                w = 0.4
            else:
                continue
            v = self.videos.get(e["video_id"])
            if not v:
                continue
            w *= self._recency(e["created_at"], now)
            if v["category"] in recent_cats:
                w *= 2.0   # 实时兴趣通道：最近看过的分类翻倍加权
            cat_aff[v["category"]] = cat_aff.get(v["category"], 0.0) + w
            for t in v["tags"]:
                tag_aff[t] = tag_aff.get(t, 0.0) + w * 0.5

        if not cat_aff:
            return {}, {}, recent_cats
        mx = max(cat_aff.values()) or 1.0
        s = {}
        for vid, v in self.videos.items():
            sc = 0.7 * (cat_aff.get(v["category"], 0.0) / mx)
            if v["tags"]:
                hit = sum(1.0 for t in v["tags"] if t in tag_aff)
                sc += 0.3 * (hit / len(v["tags"]))
            s[vid] = sc
        return s, cat_aff, recent_cats

    # ------------------------------------------------------------ 融合与理由
    def recommend(self, user_id, count=12):
        now = time.time()
        hot = self.hot_scores(now)

        has_history = user_id is not None and any(
            e["user_id"] == user_id for e in self.events
        )
        if not has_history:
            ranked = sorted(
                self.videos.values(),
                key=lambda v: hot.get(v["id"], 0.0),
                reverse=True,
            )
            return [
                self._pack(v, "🔥 热门视频", hot.get(v["id"], 0.0), 0.0, 0.0)
                for v in ranked[:count]
            ]

        cf, cf_src = self.cf_scores(user_id)
        content, cat_aff, recent_cats = self.content_scores(user_id, now)
        seen = {
            e["video_id"]
            for e in self.events
            if e["user_id"] == user_id and e["event"] in ("view", "progress", "finish")
        }

        ranked = []
        for vid, v in self.videos.items():
            h = hot.get(vid, 0.0)
            c = content.get(vid, 0.0)
            f = cf.get(vid, 0.0)
            total = W_HOT * h + W_CONTENT * c + W_CF * f
            # 实时兴趣通道：最近浏览过的分类直接乘性加权，
            # 保证“连续刷同类视频后，推荐流立刻倾斜”的可感知效果
            if v["category"] in recent_cats:
                total *= REALTIME_BOOST
            reason = self._reason(v, c, f, cf_src.get(vid), cat_aff, recent_cats)
            ranked.append({"total": total, "v": v, "h": h, "c": c, "f": f, "reason": reason})
        ranked.sort(key=lambda x: x["total"], reverse=True)

        fresh = [x for x in ranked if x["v"]["id"] not in seen]
        refill = [x for x in ranked if x["v"]["id"] in seen]
        picked = fresh[:count]
        for x in refill:
            if len(picked) >= count:
                break
            picked.append(dict(x, reason="🔁 再看一遍 · " + x["reason"]))

        return [
            self._pack(x["v"], x["reason"], x["h"], x["c"], x["f"], x["total"])
            for x in picked
        ]

    def _reason(self, v, c, f, cf_src, cat_aff, recent_cats):
        # 实时兴趣信号优先展示，直观呈现“越刷越懂你”
        if v["category"] in recent_cats and c > 0.05:
            return "⚡ 看你最近在看「%s」" % v["category"]
        if c >= f and c > 0.05:
            if cat_aff.get(v["category"], 0.0) > 0:
                return "🎯 匹配你的「%s」兴趣" % v["category"]
        if f > 0.05 and cf_src and cf_src[1] is not None:
            src_v = self.videos.get(cf_src[1])
            if src_v:
                return "👤 看过《%s》的人也再看" % src_v["title"]
        return "🔥 热门视频"

    def _pack(self, v, reason, h, c, f, total=None):
        return {
            "id": v["id"],
            "title": v["title"],
            "category": v["category"],
            "tags": v["tags"],
            "url": "/media/" + v["filename"],
            "views": v["views"],
            "likes": v["likes"],
            "uploader_id": v.get("uploader_id"),
            "created_at": v["created_at"],
            "reason": reason,
            "debug": {
                "hot": round(h, 4),
                "content": round(c, 4),
                "itemcf": round(f, 4),
                "total": round(total if total is not None else h, 4),
            },
        }



