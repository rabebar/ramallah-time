"""Al-Mizan Political Foundation hosted inside the RT Studio service.

The public site keeps its own host and UI while sharing RT Studio's PostgreSQL
instance.  Tables are deliberately prefixed with ``mizan_`` so the two
applications remain logically separated.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import mimetypes
import os
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import quote, urljoin

import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from flask import Blueprint, Response, jsonify, request, send_from_directory

from database import get_db_connection


LOGGER = logging.getLogger(__name__)
MIZAN_HOST = os.environ.get("MIZAN_PUBLIC_HOST", "mizan.rtstudio.store").strip().lower()
MIZAN_PUBLIC_URL = os.environ.get(
    "MIZAN_PUBLIC_SITE_URL", f"https://{MIZAN_HOST}"
).rstrip("/")
MIZAN_ADMIN_USERNAME = os.environ.get("MIZAN_ADMIN_USERNAME", "").strip()
MIZAN_ADMIN_PASSWORD = os.environ.get("MIZAN_ADMIN_PASSWORD", "")
MIZAN_SUPER_ADMIN_USERNAME = os.environ.get(
    "MIZAN_SUPER_ADMIN_USERNAME", MIZAN_ADMIN_USERNAME
).strip()
MIZAN_SOURCE_DATABASE_URL = os.environ.get("MIZAN_SOURCE_DATABASE_URL", "").strip()
MIZAN_TELEGRAM_BOT_TOKEN = os.environ.get("MIZAN_TELEGRAM_BOT_TOKEN", "").strip()
MIZAN_TELEGRAM_CHAT_ID = os.environ.get("MIZAN_TELEGRAM_CHAT_ID", "").strip()
MIZAN_MAX_BODY_SIZE = int(os.environ.get("MIZAN_MAX_BODY_SIZE", 25 * 1024 * 1024))

MIZAN_ROOT = Path(__file__).resolve().parent / "static" / "mizan"
RABEE_AUTHOR_IMAGE = "/mizan-political/rabee-albarghouti-author.png"
_storage_lock = threading.Lock()
_storage_ready = False

mizan_bp = Blueprint("mizan", __name__, url_prefix="/mizan-political")


class MizanHostMiddleware:
    """Internally mount the Mizan blueprint at `/` on its dedicated host."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        host = (environ.get("HTTP_HOST") or "").split(":", 1)[0].lower()
        path = environ.get("PATH_INFO") or "/"
        if host == MIZAN_HOST and not path.startswith("/mizan-political"):
            environ["MIZAN_ORIGINAL_PATH"] = path
            environ["PATH_INFO"] = "/mizan-political" + (
                path if path.startswith("/") else f"/{path}"
            )
        return self.app(environ, start_response)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _normalize_item(item: dict) -> dict:
    return {
        "id": item.get("id") or str(uuid.uuid4()),
        "title": str(item.get("title") or "").strip(),
        "category": item.get("category") or "palestine",
        "placement": item.get("placement") or "normal",
        "image": item.get("image") or "",
        "authorName": str(item.get("authorName") or "").strip(),
        "authorImage": item.get("authorImage") or "",
        "summary": str(item.get("summary") or "").strip(),
        "body": str(item.get("body") or "").strip(),
        "createdAt": int(item.get("createdAt") or _now_ms()),
    }


def _row_to_item(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "category": row["category"],
        "placement": row["placement"],
        "image": row.get("image") or "",
        "authorName": row.get("author_name") or "",
        "authorImage": row.get("author_image") or "",
        "summary": row["summary"],
        "body": row.get("body") or "",
        "createdAt": int(row["created_at"]),
    }


def _public_item(item: dict) -> dict:
    public = dict(item)
    if str(public.get("image") or "").startswith("data:"):
        public["image"] = ""
    if str(public.get("authorImage") or "").startswith("data:"):
        public["authorImage"] = ""
    return public


def _ensure_storage() -> None:
    global _storage_ready
    if _storage_ready:
        return

    with _storage_lock:
        if _storage_ready:
            return

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS mizan_news_items (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    placement TEXT NOT NULL,
                    image TEXT,
                    author_name TEXT,
                    author_image TEXT,
                    summary TEXT NOT NULL,
                    body TEXT,
                    created_at BIGINT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS mizan_admin_users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'admin',
                    created_at BIGINT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS mizan_visit_events (
                    id TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    post_id TEXT,
                    category TEXT,
                    visitor_hash TEXT NOT NULL,
                    user_agent_hash TEXT NOT NULL,
                    created_at BIGINT NOT NULL
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS mizan_visits_created_idx "
                "ON mizan_visit_events(created_at)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS mizan_visits_post_idx "
                "ON mizan_visit_events(post_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS mizan_visits_recent_idx "
                "ON mizan_visit_events(visitor_hash, user_agent_hash, path, created_at)"
            )
            cur.execute(
                """
                UPDATE mizan_news_items
                SET author_image = %s
                WHERE TRIM(author_name) = %s
                  AND author_image IS DISTINCT FROM %s
                """,
                (RABEE_AUTHOR_IMAGE, "ربيع البرغوثي", RABEE_AUTHOR_IMAGE),
            )
            conn.commit()
        finally:
            conn.close()

        if MIZAN_SOURCE_DATABASE_URL:
            _copy_source_database()

        _storage_ready = True


def _copy_source_database() -> None:
    """Copy the old Mizan database into the RT Studio database.

    The operation is idempotent. It can safely run on consecutive deploys
    during cutover and preserves the newest source content.
    """

    source = psycopg2.connect(
        MIZAN_SOURCE_DATABASE_URL, cursor_factory=RealDictCursor
    )
    destination = get_db_connection()
    try:
        src = source.cursor()
        dst = destination.cursor()

        src.execute("SELECT * FROM news_items")
        news_rows = src.fetchall()
        for row in news_rows:
            dst.execute(
                """
                INSERT INTO mizan_news_items (
                    id, title, category, placement, image, author_name,
                    author_image, summary, body, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    category = EXCLUDED.category,
                    placement = EXCLUDED.placement,
                    image = EXCLUDED.image,
                    author_name = EXCLUDED.author_name,
                    author_image = EXCLUDED.author_image,
                    summary = EXCLUDED.summary,
                    body = EXCLUDED.body,
                    created_at = EXCLUDED.created_at
                """,
                (
                    row["id"],
                    row["title"],
                    row["category"],
                    row["placement"],
                    row.get("image"),
                    row.get("author_name"),
                    row.get("author_image"),
                    row["summary"],
                    row.get("body"),
                    row["created_at"],
                ),
            )

        src.execute("SELECT * FROM admin_users")
        admin_rows = src.fetchall()
        for row in admin_rows:
            dst.execute(
                """
                INSERT INTO mizan_admin_users (
                    username, password_hash, role, created_at
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    role = EXCLUDED.role,
                    created_at = EXCLUDED.created_at
                """,
                (
                    row["username"],
                    row["password_hash"],
                    row["role"],
                    row["created_at"],
                ),
            )

        src.execute("SELECT * FROM visit_events")
        visit_rows = src.fetchall()
        for row in visit_rows:
            dst.execute(
                """
                INSERT INTO mizan_visit_events (
                    id, path, post_id, category, visitor_hash,
                    user_agent_hash, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    row["id"],
                    row["path"],
                    row.get("post_id"),
                    row.get("category"),
                    row["visitor_hash"],
                    row["user_agent_hash"],
                    row["created_at"],
                ),
            )

        destination.commit()
        LOGGER.info(
            "Mizan migration copied %s news items, %s admins and %s visits",
            len(news_rows),
            len(admin_rows),
            len(visit_rows),
        )
    except Exception:
        destination.rollback()
        LOGGER.exception("Mizan source database migration failed")
        raise
    finally:
        source.close()
        destination.close()


def _get_news() -> list[dict]:
    _ensure_storage()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM mizan_news_items ORDER BY created_at DESC")
        return [_row_to_item(dict(row)) for row in cur.fetchall()]
    finally:
        conn.close()


def _get_news_item(item_id: str) -> dict | None:
    _ensure_storage()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM mizan_news_items WHERE id = %s", (item_id,))
        row = cur.fetchone()
        return _row_to_item(dict(row)) if row else None
    finally:
        conn.close()


def _save_news(item: dict) -> None:
    _ensure_storage()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT created_at FROM mizan_news_items WHERE id = %s", (item["id"],)
        )
        existing = cur.fetchone()
        created_at = int(existing["created_at"]) if existing else item["createdAt"]
        cur.execute(
            """
            INSERT INTO mizan_news_items (
                id, title, category, placement, image, author_name,
                author_image, summary, body, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                category = EXCLUDED.category,
                placement = EXCLUDED.placement,
                image = EXCLUDED.image,
                author_name = EXCLUDED.author_name,
                author_image = EXCLUDED.author_image,
                summary = EXCLUDED.summary,
                body = EXCLUDED.body
            """,
            (
                item["id"],
                item["title"],
                item["category"],
                item["placement"],
                item["image"],
                item["authorName"],
                item["authorImage"],
                item["summary"],
                item["body"],
                created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _stored_admins() -> list[dict]:
    _ensure_storage()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT username, password_hash, role, created_at "
            "FROM mizan_admin_users ORDER BY created_at DESC"
        )
        return [
            {
                "username": row["username"],
                "passwordHash": row["password_hash"],
                "role": row["role"],
                "createdAt": int(row["created_at"]),
                "source": "stored",
            }
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def _all_admins() -> list[dict]:
    admins = []
    if MIZAN_ADMIN_USERNAME and MIZAN_ADMIN_PASSWORD:
        admins.append(
            {
                "username": MIZAN_ADMIN_USERNAME,
                "passwordHash": _hash_password(MIZAN_ADMIN_PASSWORD),
                "role": "super_admin",
                "source": "env",
                "createdAt": None,
            }
        )
    for admin in _stored_admins():
        if (
            admin["role"] == "super_admin"
            or admin["username"] == MIZAN_SUPER_ADMIN_USERNAME
        ):
            admin["role"] = "super_admin"
        else:
            admin["role"] = "admin"
        admins.append(admin)
    return admins


def _public_admin(admin: dict) -> dict:
    return {
        "username": admin["username"],
        "role": "super_admin" if admin["role"] == "super_admin" else "admin",
        "source": admin.get("source", "stored"),
        "createdAt": admin.get("createdAt"),
    }


def _require_admin(super_admin: bool = False) -> dict:
    username = request.headers.get("x-admin-user", "")
    password = request.headers.get("x-admin-pass", "")
    found = next(
        (
            admin
            for admin in _all_admins()
            if admin["username"] == username
            and admin["passwordHash"] == _hash_password(password)
        ),
        None,
    )
    if not found:
        return {}
    if super_admin and found["role"] != "super_admin":
        return {"_forbidden": True}
    return found


def _request_json() -> dict:
    if (request.content_length or 0) > MIZAN_MAX_BODY_SIZE:
        raise ValueError("Payload too large")
    return request.get_json(silent=True) or {}


def _client_ip() -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or request.remote_addr or "unknown"


def _is_bot() -> bool:
    agent = request.headers.get("user-agent", "").lower()
    return any(
        marker in agent
        for marker in (
            "bot",
            "crawler",
            "spider",
            "preview",
            "facebookexternalhit",
            "whatsapp",
            "telegrambot",
            "twitterbot",
            "slackbot",
            "discordbot",
            "linkedinbot",
        )
    )


def _record_visit(original_path: str, item: dict | None = None) -> None:
    if request.method != "GET" or _is_bot():
        return
    is_post = original_path.startswith("/post/")
    if is_post and not item:
        return

    salt = os.environ.get("MIZAN_VISIT_HASH_SALT") or MIZAN_ADMIN_PASSWORD or "mizan-political"
    visitor_hash = hashlib.sha256(
        f"{salt}:{_client_ip()}".encode("utf-8")
    ).hexdigest()
    agent_hash = hashlib.sha256(
        request.headers.get("user-agent", "").encode("utf-8")
    ).hexdigest()
    path = original_path if is_post else "/"
    recent = _now_ms() - 30 * 60 * 1000

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id FROM mizan_visit_events
            WHERE visitor_hash = %s AND user_agent_hash = %s
              AND path = %s AND created_at >= %s
            LIMIT 1
            """,
            (visitor_hash, agent_hash, path, recent),
        )
        if cur.fetchone():
            return
        cur.execute(
            """
            INSERT INTO mizan_visit_events (
                id, path, post_id, category, visitor_hash,
                user_agent_hash, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                path,
                item.get("id") if item else None,
                item.get("category") if item else ("home" if path == "/" else None),
                visitor_hash,
                agent_hash,
                _now_ms(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _analytics() -> dict:
    _ensure_storage()
    now = _now_ms()
    day = 24 * 60 * 60 * 1000
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              COUNT(*)::int AS total,
              COUNT(*) FILTER (WHERE created_at >= %s)::int AS last24h,
              COUNT(*) FILTER (WHERE created_at >= %s)::int AS last7d,
              COUNT(*) FILTER (WHERE created_at >= %s)::int AS last30d
            FROM mizan_visit_events
            """,
            (now - day, now - 7 * day, now - 30 * day),
        )
        totals = dict(cur.fetchone())
        cur.execute(
            """
            SELECT v.post_id AS id,
              COALESCE(n.title, v.post_id) AS title,
              COALESCE(n.category, v.category) AS category,
              COUNT(*)::int AS visits
            FROM mizan_visit_events v
            LEFT JOIN mizan_news_items n ON n.id = v.post_id
            WHERE v.post_id IS NOT NULL
            GROUP BY v.post_id, n.title, n.category, v.category
            ORDER BY visits DESC LIMIT 8
            """
        )
        top_posts = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            SELECT COALESCE(n.category, v.category, 'home') AS category,
              COUNT(*)::int AS visits
            FROM mizan_visit_events v
            LEFT JOIN mizan_news_items n ON n.id = v.post_id
            GROUP BY COALESCE(n.category, v.category, 'home')
            ORDER BY visits DESC
            """
        )
        categories = [dict(row) for row in cur.fetchall()]
        return {"totals": totals, "topPosts": top_posts, "categories": categories}
    finally:
        conn.close()


def _send_telegram_photo(item: dict, image_url: str, caption: str) -> bool:
    try:
        image_response = requests.get(
            image_url,
            headers={"User-Agent": "MizanPoliticalBot/1.0"},
            timeout=20,
        )
        image_response.raise_for_status()
        content_type = image_response.headers.get("content-type", "").split(";", 1)[0]
        if content_type not in {"image/jpeg", "image/png", "image/gif"}:
            raise ValueError(f"Unsupported Telegram image type: {content_type}")
        if len(image_response.content) > 10 * 1024 * 1024:
            raise ValueError("Telegram image exceeds 10 MB")
        extension = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
        }[content_type]
        response = requests.post(
            f"https://api.telegram.org/bot{MIZAN_TELEGRAM_BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": MIZAN_TELEGRAM_CHAT_ID,
                "caption": caption,
                "parse_mode": "HTML",
            },
            files={
                "photo": (
                    f"mizan-{item['id']}.{extension}",
                    image_response.content,
                    content_type,
                )
            },
            timeout=30,
        )
        if response.ok:
            return True
        LOGGER.warning("Mizan Telegram photo notification failed: %s", response.text)
    except Exception:
        LOGGER.exception("Mizan Telegram photo upload failed")
    return False


def _notify_telegram(item: dict, *, allow_text_fallback: bool = True) -> bool:
    if not MIZAN_TELEGRAM_BOT_TOKEN or not MIZAN_TELEGRAM_CHAT_ID:
        return False
    request_host = request.host.split(":", 1)[0].lower()
    if request_host == MIZAN_HOST:
        public_url = request.host_url.rstrip("/")
    else:
        public_url = f"{request.host_url.rstrip('/')}/mizan-political"
    post_url = f"{public_url}/post/{quote(item['id'])}"
    category = f"\nالقسم: {html.escape(item['category'])}" if item.get("category") else ""
    raw_summary = str(item.get("summary") or "")
    summary = f"\n\n{html.escape(raw_summary)}" if raw_summary else ""
    text = (
        f"<b>{html.escape(item['title'])}</b>{category}{summary}"
        f'\n\n<a href="{html.escape(post_url)}">قراءة المادة كاملة</a>'
    )
    try:
        image = str(item.get("image") or "").strip()
        if image and not image.startswith("data:"):
            image_url = urljoin(f"{public_url}/", image)
            # Telegram photo captions are limited to 1024 characters. Keep the
            # useful article context while leaving room for the link and markup.
            caption_summary = raw_summary[:700]
            caption = (
                f"<b>{html.escape(item['title'])}</b>{category}"
                + (f"\n\n{html.escape(caption_summary)}" if caption_summary else "")
                + f'\n\n<a href="{html.escape(post_url)}">قراءة المادة كاملة</a>'
            )
            if _send_telegram_photo(item, image_url, caption):
                return True

            if not allow_text_fallback:
                return False

        elif not allow_text_fallback:
            return False

        response = requests.post(
            f"https://api.telegram.org/bot{MIZAN_TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": MIZAN_TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=10,
        )
        response.raise_for_status()
        return True
    except Exception:
        LOGGER.exception("Mizan Telegram notification failed")
        return False


@mizan_bp.get("/api/news")
def api_news_get():
    news = _get_news()
    if request.headers.get("x-admin-user") or request.headers.get("x-admin-pass"):
        if not _require_admin():
            return jsonify(error="Unauthorized"), 401
        return jsonify(news)
    return jsonify([_public_item(item) for item in news])


@mizan_bp.post("/api/news")
def api_news_post():
    if not _require_admin():
        return jsonify(error="Unauthorized"), 401
    try:
        item = _normalize_item(_request_json())
    except ValueError as exc:
        return jsonify(error=str(exc)), 413
    if not item["title"] or not item["summary"]:
        return jsonify(error="Missing title or summary"), 400
    existing = _get_news_item(item["id"])
    _save_news(item)
    if not existing:
        _notify_telegram(item)
    return jsonify(item)


@mizan_bp.delete("/api/news/<path:item_id>")
def api_news_delete(item_id: str):
    if not _require_admin():
        return jsonify(error="Unauthorized"), 401
    _ensure_storage()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM mizan_news_items WHERE id = %s", (item_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@mizan_bp.post("/api/news/<path:item_id>/telegram")
def api_news_telegram(item_id: str):
    if not _require_admin():
        return jsonify(error="Unauthorized"), 401
    item = _get_news_item(item_id)
    if not item:
        return jsonify(error="Article not found"), 404
    if not _notify_telegram(item, allow_text_fallback=False):
        return jsonify(error="Telegram publishing failed"), 502
    return jsonify(ok=True)


@mizan_bp.post("/api/admins/login")
def api_admin_login():
    body = _request_json()
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    found = next(
        (
            admin
            for admin in _all_admins()
            if admin["username"] == username
            and admin["passwordHash"] == _hash_password(password)
        ),
        None,
    )
    if not found:
        return jsonify(error="Invalid login"), 401
    return jsonify(_public_admin(found))


@mizan_bp.get("/api/admins")
def api_admins_get():
    admin = _require_admin(super_admin=True)
    if not admin:
        return jsonify(error="Unauthorized"), 401
    if admin.get("_forbidden"):
        return jsonify(error="Super admin required"), 403
    return jsonify([_public_admin(item) for item in _all_admins()])


@mizan_bp.post("/api/admins")
def api_admins_post():
    requester = _require_admin(super_admin=True)
    if not requester:
        return jsonify(error="Unauthorized"), 401
    if requester.get("_forbidden"):
        return jsonify(error="Super admin required"), 403
    body = _request_json()
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    role = "super_admin" if body.get("role") == "super_admin" else "admin"
    if len(username) < 3 or len(password) < 8:
        return jsonify(error="Invalid username or password"), 400
    if any(item["username"].lower() == username.lower() for item in _all_admins()):
        return jsonify(error="Admin already exists"), 409

    created_at = _now_ms()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO mizan_admin_users (
                username, password_hash, role, created_at
            ) VALUES (%s, %s, %s, %s)
            """,
            (username, _hash_password(password), role, created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return (
        jsonify(
            username=username,
            role=role,
            source="stored",
            createdAt=created_at,
        ),
        201,
    )


@mizan_bp.delete("/api/admins/<path:username>")
def api_admins_delete(username: str):
    requester = _require_admin(super_admin=True)
    if not requester:
        return jsonify(error="Unauthorized"), 401
    if requester.get("_forbidden"):
        return jsonify(error="Super admin required"), 403
    if username == MIZAN_ADMIN_USERNAME:
        return jsonify(error="Cannot delete environment super admin"), 400
    if username == requester["username"]:
        return jsonify(error="Cannot delete current admin"), 400
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM mizan_admin_users WHERE username = %s", (username,))
        conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@mizan_bp.get("/api/analytics")
def api_analytics():
    admin = _require_admin(super_admin=True)
    if not admin:
        return jsonify(error="Unauthorized"), 401
    if admin.get("_forbidden"):
        return jsonify(error="Super admin required"), 403
    return jsonify(_analytics())


@mizan_bp.get("/api/health")
def api_health():
    _ensure_storage()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        counts = {}
        for label, table in (
            ("news", "mizan_news_items"),
            ("admins", "mizan_admin_users"),
            ("visits", "mizan_visit_events"),
        ):
            cur.execute(f"SELECT COUNT(*)::int AS count FROM {table}")
            counts[label] = int(cur.fetchone()["count"])
        return jsonify(ok=True, **counts)
    finally:
        conn.close()


def _original_path() -> str:
    original = request.environ.get("MIZAN_ORIGINAL_PATH")
    if original:
        return original
    path = request.path
    if path.startswith("/mizan-political"):
        path = path[len("/mizan-political") :]
    return path or "/"


def _render_index(item_id: str | None = None) -> Response:
    news = _get_news()
    item = next((entry for entry in news if entry["id"] == item_id), None)
    original_path = _original_path()

    index_path = MIZAN_ROOT / "index.html"
    page = index_path.read_text(encoding="utf-8")
    host = (request.host or "").split(":", 1)[0].lower()
    base_path = "" if host == MIZAN_HOST else "/mizan-political"
    initial_news_json = json.dumps(
        [_public_item(entry) for entry in news], ensure_ascii=False
    )
    initial_news_json = (
        initial_news_json.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    page = page.replace(
        "<script src=\"/app.js\"></script>",
        (
            f'<script>window.MIZAN_BASE_PATH={json.dumps(base_path)};</script>\n'
            f'<script id="initialNewsData" type="application/json">'
            f"{initial_news_json}"
            f"</script>\n"
            f'<script src="{base_path}/app.js"></script>'
        ),
    )
    page = page.replace('href="/styles.css"', f'href="{base_path}/styles.css"')
    page = page.replace('src="/logo.svg"', f'src="{base_path}/logo.svg"')

    site_title = (
        "مؤسسة الميزان السياسي للأبحاث والترجمة الإعلامية"
    )
    if item:
        title = f"{item['title']} | مؤسسة الميزان السياسي"
        description = item.get("summary") or ""
        canonical = f"{MIZAN_PUBLIC_URL}/post/{quote(item['id'])}"
        image = item.get("image") or ""
        page = page.replace(
            page[page.find("<title>") : page.find("</title>") + len("</title>")],
            f"<title>{html.escape(title)}</title>",
        )
        meta = (
            f'<link rel="canonical" href="{html.escape(canonical)}">\n'
            '<meta property="og:type" content="article">\n'
            f'<meta property="og:site_name" content="{html.escape(site_title)}">\n'
            f'<meta property="og:title" content="{html.escape(title)}">\n'
            f'<meta property="og:description" content="{html.escape(description)}">\n'
            f'<meta property="og:url" content="{html.escape(canonical)}">\n'
        )
        if image and not image.startswith("data:"):
            absolute_image = urljoin(f"{MIZAN_PUBLIC_URL}/", image)
            meta += (
                f'<meta property="og:image" content="{html.escape(absolute_image)}">\n'
                '<meta name="twitter:card" content="summary_large_image">\n'
                f'<meta name="twitter:image" content="{html.escape(absolute_image)}">\n'
            )
        page = page.replace("</head>", meta + "</head>")

    try:
        _record_visit(original_path, item)
    except Exception:
        LOGGER.exception("Mizan visit tracking failed")

    return Response(page, mimetype="text/html")


@mizan_bp.get("/")
def mizan_home():
    return _render_index()


@mizan_bp.get("/post/<path:item_id>")
def mizan_post(item_id: str):
    return _render_index(item_id)


@mizan_bp.get("/<path:filename>")
def mizan_static(filename: str):
    target = (MIZAN_ROOT / filename).resolve()
    if target.is_file() and MIZAN_ROOT.resolve() in target.parents:
        return send_from_directory(MIZAN_ROOT, filename)
    return _render_index()


def register_mizan(app) -> None:
    app.register_blueprint(mizan_bp)
    if not isinstance(app.wsgi_app, MizanHostMiddleware):
        app.wsgi_app = MizanHostMiddleware(app.wsgi_app)
