# -*- coding: utf-8 -*-
"""
潮汐视频 · 演示数据初始化脚本

功能：
  1. 用 ffmpeg 生成 48 个测试视频（6 分类 x 8 条，竖屏 720x1280）
     —— 仅在 media/ 下缺少文件时生成，已有则跳过
  2. 重建数据库：5 个演示账号 + 48 条视频 + 约 240 条模拟行为
     （行为数据用于驱动 ItemCF 与兴趣画像）

注意：脚本会覆盖 data/app.db，正式使用请谨慎运行。
"""
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import time

random.seed(2026)

ROOT = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.join(ROOT, "media")
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "app.db")
sys.path.insert(0, ROOT)
from server import SCHEMA, hash_pw  # noqa: E402

CATEGORIES = {
    "篮球": {"color": "0xB03A2E", "tags": [["扣篮", "NBA", "集锦"], ["投篮", "教学"], ["街球", "实战"], ["联赛", "高光"], ["过人", "技巧"], ["三分", "绝杀"], ["篮板", "防守"], ["战术", "解析"]]},
    "美食": {"color": "0xCA6F1E", "tags": [["探店", "小吃"], ["家常菜", "教程"], ["烘焙", "甜点"], ["火锅", "夜宵"], ["烧烤", "路边摊"], ["面食", "早餐"], ["饮品", "咖啡"], ["减脂餐", "健康"]]},
    "音乐": {"color": "0x7D3C98", "tags": [["吉他", "弹唱"], ["钢琴", "纯音乐"], ["民谣", "现场"], ["电音", "混音"], ["翻唱", "热歌"], ["鼓", "节奏"], ["说唱", "freestyle"], ["古典", "交响"]]},
    "旅行": {"color": "0x2471A3", "tags": [["徒步", "风景"], ["城市", "游记"], ["海边", "日落"], ["雪山", "攻略"], ["古镇", "文化"], ["露营", "自驾"], ["美食街", "打卡"], ["小众", "秘境"]]},
    "科技": {"color": "0x1E8449", "tags": [["手机", "评测"], ["编程", "开发"], ["AI", "前沿"], ["数码", "开箱"], ["芯片", "半导体"], ["机器人", "智造"], ["新能源", "电池"], ["系统", "技巧"]]},
    "搞笑": {"color": "0xB7950B", "tags": [["萌宠", "日常"], ["段子", "脱口秀"], ["整活", "创意"], ["沙雕", "合集"], ["鬼畜", "名场面"], ["翻车", "瞬间"], ["模仿", "配音"], ["反转", "剧情"]]},
}

USERS = [
    # (用户名, 密码, 偏好分类, 行为量级)
    ("alice", "123456", ["美食", "音乐"], "heavy"),
    ("bob", "123456", ["篮球", "科技"], "heavy"),
    ("carol", "123456", ["旅行", "搞笑"], "heavy"),
    ("dave", "123456", ["篮球", "美食"], "heavy"),
    ("demo", "demo123", ["篮球"], "light"),   # 演示实时推荐用
]

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]


def find_font():
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return f.replace("\\", "/")
    return None


def gen_video(path, color, text, duration, freq):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("未找到 ffmpeg，无法生成测试视频")
    font = find_font()
    vf = ""
    if font:
        escaped = text.replace(":", r"\:").replace("'", "")
        vf = (
            "drawtext=fontfile='%s':text='%s':fontsize=44:fontcolor=white:"
            "x=(w-text_w)/2:y=(h-text_h)/2" % (font.replace(":", r"\:"), escaped)
        )
    cmd = [ffmpeg, "-y",
           "-f", "lavfi", "-i", "color=c=%s:s=720x1280:d=%d:r=30" % (color, duration),
           "-f", "lavfi", "-i", "sine=frequency=%d:duration=%d" % (freq, duration)]
    if vf:
        cmd += ["-vf", vf]
    cmd += ["-af", "volume=0.10",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "48k", "-shortest", path]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not os.path.isfile(path) or os.path.getsize(path) < 1000:
        raise RuntimeError("ffmpeg 生成失败: %s\n%s" % (path, r.stderr.decode("utf-8", "replace")[-500:]))


def ensure_videos():
    """生成 48 个测试视频（已存在则跳过）"""
    made, skipped = 0, 0
    for ci, (cat, cfg) in enumerate(CATEGORIES.items()):
        for i in range(1, 9):
            fname = "seed_%s_%d.mp4" % (cat, i)
            path = os.path.join(MEDIA_DIR, fname)
            if os.path.isfile(path) and os.path.getsize(path) > 1000:
                skipped += 1
                continue
            duration = 5 + (i % 4)
            freq = 220 + ci * 40 + i * 35
            title = "%s · 精选片段 %d" % (cat, i)
            gen_video(path, cfg["color"], title, duration, freq)
            made += 1
            print("  生成 %s" % fname)
    return made, skipped


def reset_db():
    for suffix in ("", "-wal", "-shm"):
        p = DB_PATH + suffix
        if os.path.exists(p):
            os.remove(p)
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def seed_users_and_videos(conn):
    now = time.time()
    cat_list = list(CATEGORIES.keys())
    video_ids = {}   # category -> [video_id,...]

    # 账号
    uid_map = {}
    for username, password, prefs, _lvl in USERS:
        salt = os.urandom(16).hex()
        cur = conn.execute(
            "INSERT INTO users(username, password_hash, salt, created_at) VALUES(?,?,?,?)",
            (username, hash_pw(password, salt), salt, now - 14 * 86400),
        )
        uid_map[username] = cur.lastrowid

    # 视频
    for ci, (cat, cfg) in enumerate(CATEGORIES.items()):
        video_ids[cat] = []
        for i in range(1, 9):
            fname = "seed_%s_%d.mp4" % (cat, i)
            cur = conn.execute(
                "INSERT INTO videos(title, category, tags, filename, uploader_id, created_at) "
                "VALUES(?,?,?,?,?,?)",
                ("%s · 精选片段 %d" % (cat, i), cat, ",".join(cfg["tags"][i - 1]),
                 fname, None, now - random.uniform(2, 10) * 86400),
            )
            video_ids[cat].append(cur.lastrowid)
    conn.commit()
    return uid_map, video_ids, cat_list


def seed_behaviors(conn, uid_map, video_ids, cat_list):
    now = time.time()
    n = 0
    for username, _pw, prefs, level in USERS:
        uid = uid_map[username]
        if username == "demo":
            continue  # demo 由下方专用逻辑只种 3 条，便于演示实时倾斜
        heavy = level == "heavy"
        # 偏好分类：看 2~3 遍，高完播率，多数点赞
        for cat in prefs:
            for vid in video_ids[cat]:
                rounds = 3 if heavy else 1
                for r in range(rounds):
                    ratio = random.uniform(0.7, 1.0)
                    ts = now - random.uniform(3600, 6.5 * 86400)
                    conn.execute(
                        "INSERT INTO behaviors(user_id,video_id,event,watch_ratio,created_at) VALUES(?,?,?,?,?)",
                        (uid, vid, "view", 0, ts))
                    conn.execute(
                        "INSERT INTO behaviors(user_id,video_id,event,watch_ratio,created_at) VALUES(?,?,?,?,?)",
                        (uid, vid, "progress", ratio, ts + 30))
                    if ratio >= 0.9:
                        conn.execute(
                            "INSERT INTO behaviors(user_id,video_id,event,watch_ratio,created_at) VALUES(?,?,?,?,?)",
                            (uid, vid, "finish", 1, ts + 60))
                    if random.random() < 0.65:
                        conn.execute(
                            "INSERT INTO behaviors(user_id,video_id,event,watch_ratio,created_at) VALUES(?,?,?,?,?)",
                            (uid, vid, "like", 0, ts + 90))
                    n += 3
        # 非偏好分类：少量低完播“刷到划走”
        others = [c for c in cat_list if c not in prefs]
        for cat in random.sample(others, 2):
            vid = random.choice(video_ids[cat])
            ts = now - random.uniform(3600, 6 * 86400)
            conn.execute(
                "INSERT INTO behaviors(user_id,video_id,event,watch_ratio,created_at) VALUES(?,?,?,?,?)",
                (uid, vid, "view", 0, ts))
            conn.execute(
                "INSERT INTO behaviors(user_id,video_id,event,watch_ratio,created_at) VALUES(?,?,?,?,?)",
                (uid, vid, "progress", random.uniform(0.05, 0.25), ts + 20))
            n += 2

    # demo 账号：最近 2 小时连续看了 3 条篮球 → 演示“实时兴趣”倾斜
    demo_uid = uid_map["demo"]
    for vid in video_ids["篮球"][:3]:
        ts = now - random.uniform(1800, 7200)
        conn.execute(
            "INSERT INTO behaviors(user_id,video_id,event,watch_ratio,created_at) VALUES(?,?,?,?,?)",
            (demo_uid, vid, "view", 0, ts))
        conn.execute(
            "INSERT INTO behaviors(user_id,video_id,event,watch_ratio,created_at) VALUES(?,?,?,?,?)",
            (demo_uid, vid, "progress", random.uniform(0.6, 1.0), ts + 30))
        n += 2
    conn.execute(
        "INSERT INTO behaviors(user_id,video_id,event,watch_ratio,created_at) VALUES(?,?,?,?,?)",
        (demo_uid, video_ids["篮球"][0], "like", 0, now - 1500))
    n += 1

    # 用行为数据回填视频的 views/likes 计数
    conn.execute(
        "UPDATE videos SET views = "
        "(SELECT COUNT(*) FROM behaviors WHERE video_id = videos.id AND event = 'view')")
    conn.execute(
        "UPDATE videos SET likes = "
        "(SELECT COUNT(*) FROM behaviors WHERE video_id = videos.id AND event = 'like')")
    conn.commit()
    return n


def main():
    print("== 潮汐视频 · 演示数据初始化 ==")
    print("[1/3] 生成测试视频（需 ffmpeg，仅首次）")
    made, skipped = ensure_videos()
    print("  本次生成 %d 个，已存在跳过 %d 个" % (made, skipped))

    print("[2/3] 重建数据库")
    conn = reset_db()
    uid_map, video_ids, cat_list = seed_users_and_videos(conn)
    print("  账号 %d 个，视频 %d 条" % (len(uid_map), sum(len(v) for v in video_ids.values())))

    print("[3/3] 写入模拟行为数据")
    n = seed_behaviors(conn, uid_map, video_ids, cat_list)
    conn.close()
    print("  行为事件 %d 条" % n)

    print()
    print("完成！启动方式：")
    print("    python server.py")
    print("然后访问 http://localhost:8000")
    print()
    print("演示账号：")
    for username, password, prefs, _ in USERS:
        print("    %-8s / %-8s 偏好：%s" % (username, password, "、".join(prefs)))
    print()
    print("推荐演示剧本：")
    print("    1. 注册一个新账号（或用 demo 登录）")
    print("    2. 连续看完 3 条篮球视频（让它播完或点赞）")
    print("    3. 点击右上角「换一批」→ 推荐流立刻向篮球倾斜")
    print("    4. 观察每个视频上的推荐理由标签（热门/兴趣匹配/实时兴趣/看过X的人也看）")


if __name__ == "__main__":
    main()



