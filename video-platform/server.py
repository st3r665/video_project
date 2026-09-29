# -*- coding: utf-8 -*-
"""
潮汐视频 —— 短视频推荐平台 MVP v0.1
零第三方依赖（Python 3.8+ 标准库实现）。

快速开始：
    python seed.py     # 首次运行：初始化演示数据与测试视频
    python server.py   # 启动服务 → http://localhost:8000

架构说明：
    v0.1 为单机可运行原型：http.server + SQLite。
    推荐引擎独立于 recommender.py，接口与毕业设计正式架构
    （Spring Boot 业务后端 + FastAPI 推荐服务）保持兼容，便于后续迁移。
"""
import hashlib
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

from recommender import Recommender

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(ROOT, "static")
MEDIA_DIR = os.path.join(ROOT, "media")
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "app.db")
MAX_UPLOAD = 200 * 1024 * 1024
ALLOWED_EXT = {".mp4", ".webm", ".mov", ".m4v"}
EVENTS = ("view", "progress", "finish", "like", "unlike")

for d in (STATIC_DIR, MEDIA_DIR, DATA_DIR):
    os.makedirs(d, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tokens(
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS videos(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    filename TEXT NOT NULL,
    uploader_id INTEGER,
    created_at REAL NOT NULL,
    views INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS behaviors(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    video_id INTEGER NOT NULL,
    event TEXT NOT NULL,
    watch_ratio REAL NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_beh_user ON behaviors(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_beh_video ON behaviors(video_id, event);
"""


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def hash_pw(password, salt_hex):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 100000
    ).hex()


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------- 路由与上下文
ROUTES = []


def route(method, pattern):
    def deco(fn):
        ROUTES.append((method, re.compile(pattern), fn))
        return fn
    return deco


class Ctx(object):
    """单次请求上下文：惰性数据库连接 + 登录用户解析"""

    def __init__(self, handler, qs, body):
        self.h = handler
        self.qs = qs
        self.body = body
        self._db = None
        self._user = None
        self._auth_resolved = False

    def conn(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    def close(self):
        if self._db is not None:
            try:
                self._db.close()
            except Exception:
                pass
            self._db = None

    def json(self):
        try:
            return json.loads(self.body.decode("utf-8")) if self.body else {}
        except Exception:
            raise ApiError(400, "请求体不是合法 JSON")

    def user(self):
        if not self._auth_resolved:
            self._auth_resolved = True
            h = self.h.headers.get("Authorization", "")
            m = re.match(r"^Bearer\s+([0-9a-f]{32,})$", h.strip())
            if m:
                row = self.conn().execute(
                    "SELECT u.id, u.username FROM tokens t "
                    "JOIN users u ON u.id = t.user_id WHERE t.token = ?",
                    (m.group(1),),
                ).fetchone()
                self._user = dict(row) if row else None
        return self._user

    def require_user(self):
        u = self.user()
        if not u:
            raise ApiError(401, "请先登录")
        return u


def serialize_video(v):
    return {
        "id": v["id"],
        "title": v["title"],
        "category": v["category"],
        "tags": [t for t in (v["tags"] or "").split(",") if t],
        "url": "/media/" + v["filename"],
        "views": v["views"],
        "likes": v["likes"],
        "uploader_id": v["uploader_id"],
        "created_at": v["created_at"],
    }


# ---------------------------------------------------------------- API 实现
@route("POST", r"^/api/register$")
def api_register(ctx):
    d = ctx.json()
    username = str(d.get("username", "")).strip()
    password = str(d.get("password", ""))
    if not re.match(r"^[\w\u4e00-\u9fa5]{2,20}$", username):
        raise ApiError(400, "用户名需为 2~20 位字母/数字/下划线/中文")
    if len(password) < 6:
        raise ApiError(400, "密码至少 6 位")
    salt = secrets.token_hex(16)
    try:
        cur = ctx.conn().execute(
            "INSERT INTO users(username, password_hash, salt, created_at) VALUES(?,?,?,?)",
            (username, hash_pw(password, salt), salt, time.time()),
        )
    except sqlite3.IntegrityError:
        raise ApiError(409, "用户名已被占用")
    uid = cur.lastrowid
    token = secrets.token_hex(24)
    ctx.conn().execute(
        "INSERT INTO tokens(token, user_id, created_at) VALUES(?,?,?)",
        (token, uid, time.time()),
    )
    ctx.conn().commit()
    return {"token": token, "user": {"id": uid, "username": username}}


@route("POST", r"^/api/login$")
def api_login(ctx):
    d = ctx.json()
    username = str(d.get("username", "")).strip()
    password = str(d.get("password", ""))
    row = ctx.conn().execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    if not row or hash_pw(password, row["salt"]) != row["password_hash"]:
        raise ApiError(401, "用户名或密码错误")
    token = secrets.token_hex(24)
    ctx.conn().execute(
        "INSERT INTO tokens(token, user_id, created_at) VALUES(?,?,?)",
        (token, row["id"], time.time()),
    )
    ctx.conn().commit()
    return {"token": token, "user": {"id": row["id"], "username": row["username"]}}


@route("POST", r"^/api/logout$")
def api_logout(ctx):
    h = ctx.h.headers.get("Authorization", "")
    m = re.match(r"^Bearer\s+([0-9a-f]{32,})$", h.strip())
    if m:
        ctx.conn().execute("DELETE FROM tokens WHERE token = ?", (m.group(1),))
        ctx.conn().commit()
    return {"ok": True}


@route("POST", r"^/api/recommend$")
def api_recommend(ctx):
    """无状态推荐接口：Java 业务后端传入视频与行为数据，返回排序结果"""
    if os.environ.get("REC_LOG"):
        try:
            with open(os.path.join(DATA_DIR, "access.log"), "a", encoding="utf-8") as f:
                f.write("[recommend-req] body_len=%d content_length=%s transfer_encoding=%s content_type=%s\n"
                        % (len(ctx.body), ctx.h.headers.get("Content-Length"),
                           ctx.h.headers.get("Transfer-Encoding"), ctx.h.headers.get("Content-Type")))
        except Exception:
            pass
    d = ctx.json()
    user_id = d.get("user_id")
    try:
        count = max(1, min(int(d.get("count") or 12), 30))
    except Exception:
        count = 12
    videos = d.get("videos") or []
    behaviors = d.get("behaviors") or []
    rec = Recommender.from_data(videos, behaviors)
    items = rec.recommend(user_id, count=count)
    slim = [
        {
            "video_id": it["id"],
            "reason": it["reason"],
            "score": it["debug"].get("total", 0.0),
        }
        for it in items
    ]
    if os.environ.get("REC_LOG"):
        try:
            with open(os.path.join(DATA_DIR, "access.log"), "a", encoding="utf-8") as f:
                f.write("[recommend] user_id=%s videos=%d behaviors=%d -> items=%d\n"
                        % (user_id, len(videos), len(behaviors), len(slim)))
        except Exception:
            pass
    return {"items": slim}


@route("GET", r"^/api/me$")
def api_me(ctx):
    u = ctx.user()
    return {"user": u}


@route("GET", r"^/api/feed$")
def api_feed(ctx):
    count = 12
    try:
        count = max(1, min(int(ctx.qs.get("count", ["12"])[0]), 30))
    except Exception:
        pass
    user = ctx.user()
    rec = Recommender(ctx.conn())
    items = rec.recommend(user["id"] if user else None, count=count)
    names = {r["id"]: r["username"] for r in ctx.conn().execute("SELECT id, username FROM users")}
    for it in items:
        it["uploader"] = names.get(it.get("uploader_id")) or "潮汐官方"
    return {"items": items, "personalized": bool(user)}


@route("POST", r"^/api/behavior$")
def api_behavior(ctx):
    user = ctx.require_user()
    d = ctx.json()
    try:
        vid = int(d.get("video_id"))
    except Exception:
        raise ApiError(400, "video_id 不合法")
    event = str(d.get("event", ""))
    if event not in EVENTS:
        raise ApiError(400, "event 不合法")
    try:
        ratio = max(0.0, min(float(d.get("watch_ratio") or 0.0), 1.0))
    except Exception:
        ratio = 0.0
    if not ctx.conn().execute("SELECT 1 FROM videos WHERE id = ?", (vid,)).fetchone():
        raise ApiError(404, "视频不存在")
    ctx.conn().execute(
        "INSERT INTO behaviors(user_id, video_id, event, watch_ratio, created_at) "
        "VALUES(?,?,?,?,?)",
        (user["id"], vid, event, ratio, time.time()),
    )
    if event == "view":
        ctx.conn().execute("UPDATE videos SET views = views + 1 WHERE id = ?", (vid,))
    elif event == "like":
        ctx.conn().execute("UPDATE videos SET likes = likes + 1 WHERE id = ?", (vid,))
    elif event == "unlike":
        ctx.conn().execute(
            "UPDATE videos SET likes = MAX(0, likes - 1) WHERE id = ?", (vid,)
        )
    ctx.conn().commit()
    return {"ok": True}


@route("GET", r"^/api/videos/mine$")
def api_videos_mine(ctx):
    user = ctx.require_user()
    rows = ctx.conn().execute(
        "SELECT * FROM videos WHERE uploader_id = ? ORDER BY created_at DESC",
        (user["id"],),
    ).fetchall()
    return {"items": [serialize_video(r) for r in rows]}


def parse_multipart(body, content_type):
    """解析 multipart/form-data（标准库无内置支持，手动实现）"""
    m = re.search(r'boundary="?([^";]+)"?', content_type)
    if not m:
        raise ApiError(400, "缺少 multipart boundary")
    boundary = m.group(1).encode("utf-8")
    fields, files = {}, {}
    for chunk in body.split(b"--" + boundary)[1:]:
        if chunk.strip(b"\r\n-") == b"":
            continue
        head, sep, content = chunk.partition(b"\r\n\r\n")
        if not sep:
            continue
        if content.endswith(b"\r\n"):
            content = content[:-2]
        headers = head.decode("utf-8", "replace")
        nm = re.search(r'name="([^"]*)"', headers)
        if not nm:
            continue
        fm = re.search(r'filename="([^"]*)"', headers)
        if fm:
            files[nm.group(1)] = {"filename": fm.group(1), "data": content}
        else:
            fields[nm.group(1)] = content.decode("utf-8", "replace").strip()
    return fields, files


@route("POST", r"^/api/upload$")
def api_upload(ctx):
    user = ctx.require_user()
    ctype = ctx.h.headers.get("Content-Type", "")
    if "multipart/form-data" not in ctype:
        raise ApiError(400, "上传需使用 multipart/form-data 表单")
    fields, files = parse_multipart(ctx.body, ctype)
    f = files.get("file")
    if not f or not f["data"]:
        raise ApiError(400, "缺少视频文件")
    if len(f["data"]) > MAX_UPLOAD:
        raise ApiError(413, "文件过大（上限 200MB）")
    title = (fields.get("title") or "").strip()[:80] or "未命名作品"
    category = (fields.get("category") or "其他").strip()[:20]
    tags = ",".join(
        t.strip()[:20] for t in (fields.get("tags") or "").split(",") if t.strip()
    )[:200]
    ext = os.path.splitext(f["filename"])[1].lower()
    if ext not in ALLOWED_EXT:
        raise ApiError(400, "仅支持 mp4 / webm / mov / m4v 格式")
    fname = uuid.uuid4().hex + ext
    with open(os.path.join(MEDIA_DIR, fname), "wb") as fp:
        fp.write(f["data"])
    cur = ctx.conn().execute(
        "INSERT INTO videos(title, category, tags, filename, uploader_id, created_at) "
        "VALUES(?,?,?,?,?,?)",
        (title, category, tags, fname, user["id"], time.time()),
    )
    ctx.conn().commit()
    return {"id": cur.lastrowid, "url": "/media/" + fname}


# ---------------------------------------------------------------- HTTP 服务
STATIC_PAGES = {"/": "index.html", "/login": "login.html", "/upload": "upload.html"}


class Handler(BaseHTTPRequestHandler):
    server_version = "TideVideo/0.1"

    def log_message(self, fmt, *args):
        if os.environ.get("REC_LOG"):
            try:
                with open(os.path.join(DATA_DIR, "access.log"), "a", encoding="utf-8") as f:
                    f.write("%s - %s\n" % (self.address_string(), fmt % args))
            except Exception:
                pass

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def _read_body(self):
        # 支持两种请求体传输方式：
        #   1. Content-Length（浏览器/curl 常用）
        #   2. Transfer-Encoding: chunked（Java HttpURLConnection/RestTemplate 默认）
        te = (self.headers.get("Transfer-Encoding") or "").lower()
        if "chunked" in te:
            return self._read_chunked()
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length < 0 or length > MAX_UPLOAD + 1024 * 1024:
            raise ApiError(413, "请求体过大")
        return self.rfile.read(length) if length else b""

    def _read_chunked(self):
        chunks = []
        total = 0
        while True:
            line = self.rfile.readline(65536).strip()
            if not line:
                break
            try:
                size = int(line.split(b";")[0], 16)
            except ValueError:
                raise ApiError(400, "分块传输编码格式错误")
            if size == 0:
                while True:
                    trailer = self.rfile.readline(65536)
                    if trailer in (b"\r\n", b"\n", b""):
                        break
                break
            total += size
            if total > MAX_UPLOAD + 1024 * 1024:
                raise ApiError(413, "请求体过大")
            chunks.append(self.rfile.read(size))
            self.rfile.read(2)  # 丢弃块尾的 CRLF
        return b"".join(chunks)

    def _dispatch(self, method):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        qs = parse_qs(parsed.query)
        try:
            if path.startswith("/api/"):
                self._handle_api(method, path, qs)
            elif path.startswith("/media/"):
                self._serve_media(path)
            else:
                self._serve_static(path)
        except ApiError as e:
            self._send_json(e.status, {"error": e.message})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try:
                self._send_json(500, {"error": "服务器内部错误: %s" % e})
            except Exception:
                pass

    def _handle_api(self, method, path, qs):
        for m, rx, fn in ROUTES:
            if m == method and rx.match(path):
                body = self._read_body() if method == "POST" else b""
                ctx = Ctx(self, qs, body)
                try:
                    result = fn(ctx)
                finally:
                    ctx.close()
                self._send_json(200, result)
                return
        raise ApiError(404, "接口不存在: %s" % path)

    def _serve_static(self, path):
        name = STATIC_PAGES.get(path)
        if name is None:
            if path.startswith("/static/"):
                name = os.path.normpath(path[len("/static/"):]).lstrip("\\/")
            else:
                raise ApiError(404, "页面不存在")
        fpath = os.path.normpath(os.path.join(STATIC_DIR, name))
        if not fpath.startswith(STATIC_DIR) or not os.path.isfile(fpath):
            raise ApiError(404, "文件不存在")
        self._send_file(fpath)

    def _serve_media(self, path):
        name = os.path.basename(unquote(path))  # 仅取文件名，防目录穿越
        fpath = os.path.join(MEDIA_DIR, name)
        if not os.path.isfile(fpath):
            raise ApiError(404, "视频不存在")
        self._send_file(fpath, allow_range=True)

    def _send_json(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, fpath, allow_range=False):
        size = os.path.getsize(fpath)
        ctype = mimetypes.guess_type(fpath)[0] or "application/octet-stream"
        start, end, status = 0, size - 1, 200
        if allow_range:
            rng = self.headers.get("Range")
            if rng:
                m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
                if m:
                    status = 206
                    if m.group(1):
                        start = int(m.group(1))
                    if m.group(2):
                        end = min(int(m.group(2)), size - 1)
                    if start > end or start >= size:
                        self.send_response(416)
                        self.send_header("Content-Range", "bytes */%d" % size)
                        self.end_headers()
                        return
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if status == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.end_headers()
        with open(fpath, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def main():
    init_db()
    port = int(os.environ.get("PORT", "8000"))
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        print("启动失败：端口 %d 可能被占用（%s）" % (port, e))
        print("可设置其他端口后重试，例如：set PORT=8001 && python server.py")
        return
    print("=" * 50)
    print("  潮汐视频 MVP v0.1 已启动")
    print("  访问地址:  http://localhost:%d" % port)
    print("  演示账号:  demo / demo123（更多账号见 README）")
    print("  退出服务:  Ctrl + C")
    print("=" * 50)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")


if __name__ == "__main__":
    main()
