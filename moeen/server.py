import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.environ.get("MOEEN_DB_PATH", DATA_DIR / "moeen.db"))
SECRET_PATH = DATA_DIR / "session-secret.key"


def load_secret():
    configured = os.environ.get("MOEEN_SECRET_KEY")
    if configured:
        return configured
    if SECRET_PATH.exists():
        return SECRET_PATH.read_text(encoding="ascii").strip()
    value = secrets.token_urlsafe(48)
    SECRET_PATH.write_text(value, encoding="ascii")
    return value


app = Flask(__name__, static_folder=None)
app.secret_key = load_secret()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=os.environ.get("MOEEN_COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS account (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              password_hash TEXT NOT NULL,
              must_change INTEGER NOT NULL DEFAULT 1,
              vault_salt TEXT,
              wrapped_vault TEXT,
              wrap_iv TEXT,
              password_changed_at TEXT,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS devices (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              user_agent TEXT,
              created_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL,
              revoked_at TEXT
            );
            CREATE TABLE IF NOT EXISTS login_attempts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              device_id TEXT,
              device_name TEXT,
              ip_address TEXT,
              user_agent TEXT,
              outcome TEXT NOT NULL,
              created_at TEXT NOT NULL,
              reviewed INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS pairing_codes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              code_hash TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              used_at TEXT,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sync_state (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              ciphertext TEXT NOT NULL,
              iv TEXT NOT NULL,
              version INTEGER NOT NULL DEFAULT 1,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audio_blobs (
              id TEXT PRIMARY KEY,
              ciphertext BLOB NOT NULL,
              iv TEXT NOT NULL,
              mime_type TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(account)").fetchall()}
        for name in ("vault_salt", "wrapped_vault", "wrap_iv"):
            if name not in columns:
                conn.execute(f"ALTER TABLE account ADD COLUMN {name} TEXT")
        initial = os.environ.get("MOEEN_INITIAL_PASSWORD")
        exists = conn.execute("SELECT 1 FROM account WHERE id=1").fetchone()
        if initial and not exists:
            conn.execute(
                "INSERT INTO account(id,password_hash,must_change,created_at) VALUES(1,?,?,?)",
                (generate_password_hash(initial, method="scrypt"), 1, now_iso()),
            )


init_db()


def client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.remote_addr or "unknown")


def record_attempt(outcome, device_id="", device_name=""):
    with db() as conn:
        conn.execute(
            """INSERT INTO login_attempts
               (device_id,device_name,ip_address,user_agent,outcome,created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                device_id[:120],
                device_name[:120],
                client_ip()[:80],
                request.headers.get("User-Agent", "")[:500],
                outcome,
                now_iso(),
            ),
        )


def is_blocked(device_id):
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    with db() as conn:
        count = conn.execute(
            """SELECT COUNT(*) FROM login_attempts
               WHERE created_at >= ? AND outcome IN ('bad_password','bad_pairing')
               AND (device_id = ? OR ip_address = ?)""",
            (cutoff, device_id, client_ip()),
        ).fetchone()[0]
    return count >= 5


def account_row():
    with db() as conn:
        return conn.execute("SELECT * FROM account WHERE id=1").fetchone()


def vault_payload(account):
    if not account or not account["wrapped_vault"]:
        return None
    return {
        "salt": account["vault_salt"],
        "wrapped_vault": account["wrapped_vault"],
        "iv": account["wrap_iv"],
    }


def valid_crypto_field(value, max_length=20000000):
    return isinstance(value, str) and 1 <= len(value) <= max_length


def device_row(device_id):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM devices WHERE id=? AND revoked_at IS NULL", (device_id,)
        ).fetchone()


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def require_auth(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        device_id = session.get("device_id")
        if not session.get("authenticated") or not device_id or not device_row(device_id):
            session.clear()
            return jsonify(error="AUTH_REQUIRED"), 401
        if request.method not in ("GET", "HEAD"):
            if not secrets.compare_digest(
                request.headers.get("X-CSRF-Token", ""), session.get("csrf", "")
            ):
                return jsonify(error="CSRF_FAILED"), 403
        session.permanent = True
        with db() as conn:
            conn.execute(
                "UPDATE devices SET last_seen_at=? WHERE id=?", (now_iso(), device_id)
            )
        return fn(*args, **kwargs)

    return wrapped


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=(self)"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'"
    )
    response.headers["Cache-Control"] = "no-store" if request.path.startswith("/api/") else "no-cache"
    return response


@app.get("/api/auth/status")
def auth_status():
    account = account_row()
    authenticated = bool(session.get("authenticated") and device_row(session.get("device_id", "")))
    return jsonify(
        configured=bool(account),
        authenticated=authenticated,
        must_change=bool(account["must_change"]) if account and authenticated else False,
        csrf=csrf_token() if authenticated else None,
        vault=vault_payload(account) if authenticated else None,
    )


@app.post("/api/setup")
def setup():
    if account_row():
        return jsonify(error="ALREADY_CONFIGURED"), 409
    if client_ip() not in ("127.0.0.1", "::1"):
        return jsonify(error="LOCAL_SETUP_ONLY"), 403
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    vault = data.get("vault") or {}
    if len(password) < 10:
        return jsonify(error="WEAK_PASSWORD"), 400
    with db() as conn:
        conn.execute(
            """INSERT INTO account
               (id,password_hash,must_change,vault_salt,wrapped_vault,wrap_iv,password_changed_at,created_at)
               VALUES(1,?,0,?,?,?,?,?)""",
            (
                generate_password_hash(password, method="scrypt"),
                vault.get("salt") if valid_crypto_field(vault.get("salt", ""), 500) else None,
                vault.get("wrapped_vault") if valid_crypto_field(vault.get("wrapped_vault", ""), 1000) else None,
                vault.get("iv") if valid_crypto_field(vault.get("iv", ""), 500) else None,
                now_iso(),
                now_iso(),
            ),
        )
    return jsonify(ok=True)


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    device_id = str(data.get("device_id", ""))[:120]
    device_name = str(data.get("device_name", "جهاز غير معروف"))[:120]
    if not device_id:
        return jsonify(error="DEVICE_ID_REQUIRED"), 400
    if is_blocked(device_id):
        record_attempt("temporarily_blocked", device_id, device_name)
        return jsonify(error="TEMPORARILY_BLOCKED"), 429
    account = account_row()
    if not account:
        return jsonify(error="SETUP_REQUIRED"), 428
    if not check_password_hash(account["password_hash"], password):
        record_attempt("bad_password", device_id, device_name)
        return jsonify(error="INVALID_CREDENTIALS"), 401
    known = device_row(device_id)
    with db() as conn:
        device_count = conn.execute(
            "SELECT COUNT(*) FROM devices WHERE revoked_at IS NULL"
        ).fetchone()[0]
        if not known and device_count == 0:
            conn.execute(
                "INSERT INTO devices(id,name,user_agent,created_at,last_seen_at) VALUES(?,?,?,?,?)",
                (device_id, device_name, request.headers.get("User-Agent", "")[:500], now_iso(), now_iso()),
            )
            known = True
    if not known:
        record_attempt("unknown_device_blocked", device_id, device_name)
        return jsonify(error="DEVICE_NOT_AUTHORIZED"), 403
    session.clear()
    session.update(authenticated=True, device_id=device_id, csrf=secrets.token_urlsafe(24))
    session.permanent = True
    record_attempt("success", device_id, device_name)
    return jsonify(
        ok=True,
        must_change=bool(account["must_change"]),
        csrf=session["csrf"],
        vault=vault_payload(account),
    )


@app.post("/api/auth/pair")
def pair_device():
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    code = str(data.get("pairing_code", "")).replace(" ", "")
    device_id = str(data.get("device_id", ""))[:120]
    device_name = str(data.get("device_name", "جهاز جديد"))[:120]
    account = account_row()
    if not account or not check_password_hash(account["password_hash"], password):
        record_attempt("bad_pairing", device_id, device_name)
        return jsonify(error="INVALID_CREDENTIALS"), 401
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    with db() as conn:
        row = conn.execute(
            """SELECT * FROM pairing_codes
               WHERE code_hash=? AND used_at IS NULL AND expires_at>? ORDER BY id DESC LIMIT 1""",
            (digest, now_iso()),
        ).fetchone()
        if not row:
            record_attempt("bad_pairing", device_id, device_name)
            return jsonify(error="INVALID_PAIRING_CODE"), 403
        conn.execute("UPDATE pairing_codes SET used_at=? WHERE id=?", (now_iso(), row["id"]))
        conn.execute(
            """INSERT INTO devices(id,name,user_agent,created_at,last_seen_at,revoked_at)
               VALUES(?,?,?,?,?,NULL)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name,user_agent=excluded.user_agent,
               last_seen_at=excluded.last_seen_at,revoked_at=NULL""",
            (device_id, device_name, request.headers.get("User-Agent", "")[:500], now_iso(), now_iso()),
        )
    session.clear()
    session.update(authenticated=True, device_id=device_id, csrf=secrets.token_urlsafe(24))
    session.permanent = True
    record_attempt("paired_success", device_id, device_name)
    return jsonify(ok=True, csrf=session["csrf"], vault=vault_payload(account))


@app.post("/api/auth/logout")
@require_auth
def logout():
    session.clear()
    return jsonify(ok=True)


@app.post("/api/security/change-password")
@require_auth
def change_password():
    data = request.get_json(silent=True) or {}
    current = data.get("current_password", "")
    new = data.get("new_password", "")
    vault = data.get("vault") or {}
    account = account_row()
    if not check_password_hash(account["password_hash"], current):
        return jsonify(error="INVALID_CURRENT_PASSWORD"), 401
    if len(new) < 12 or new == current:
        return jsonify(error="WEAK_PASSWORD"), 400
    if account["wrapped_vault"] and not all(
        valid_crypto_field(vault.get(k, ""), 2000) for k in ("salt", "wrapped_vault", "iv")
    ):
        return jsonify(error="VAULT_REWRAP_REQUIRED"), 400
    with db() as conn:
        conn.execute(
            """UPDATE account SET password_hash=?,must_change=0,password_changed_at=?,
               vault_salt=COALESCE(?,vault_salt),wrapped_vault=COALESCE(?,wrapped_vault),
               wrap_iv=COALESCE(?,wrap_iv) WHERE id=1""",
            (
                generate_password_hash(new, method="scrypt"),
                now_iso(),
                vault.get("salt"),
                vault.get("wrapped_vault"),
                vault.get("iv"),
            ),
        )
    return jsonify(ok=True)


@app.post("/api/security/vault-init")
@require_auth
def vault_init():
    data = request.get_json(silent=True) or {}
    if not all(valid_crypto_field(data.get(k, ""), 2000) for k in ("salt", "wrapped_vault", "iv")):
        return jsonify(error="INVALID_VAULT"), 400
    account = account_row()
    if account["wrapped_vault"]:
        return jsonify(error="VAULT_ALREADY_EXISTS"), 409
    with db() as conn:
        conn.execute(
            "UPDATE account SET vault_salt=?,wrapped_vault=?,wrap_iv=? WHERE id=1",
            (data["salt"], data["wrapped_vault"], data["iv"]),
        )
    return jsonify(ok=True)


@app.get("/api/sync/state")
@require_auth
def get_sync_state():
    with db() as conn:
        row = conn.execute("SELECT * FROM sync_state WHERE id=1").fetchone()
    if not row:
        return jsonify(state=None, version=0)
    return jsonify(
        state={"ciphertext": row["ciphertext"], "iv": row["iv"]},
        version=row["version"],
        updated_at=row["updated_at"],
    )


@app.put("/api/sync/state")
@require_auth
def put_sync_state():
    data = request.get_json(silent=True) or {}
    base_version = int(data.get("base_version", 0))
    ciphertext = data.get("ciphertext", "")
    iv = data.get("iv", "")
    if not valid_crypto_field(ciphertext) or not valid_crypto_field(iv, 500):
        return jsonify(error="INVALID_ENCRYPTED_STATE"), 400
    with db() as conn:
        row = conn.execute("SELECT version FROM sync_state WHERE id=1").fetchone()
        current = row["version"] if row else 0
        if base_version != current:
            return jsonify(error="SYNC_CONFLICT", current_version=current), 409
        new_version = current + 1
        conn.execute(
            """INSERT INTO sync_state(id,ciphertext,iv,version,updated_at)
               VALUES(1,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET ciphertext=excluded.ciphertext,iv=excluded.iv,
               version=excluded.version,updated_at=excluded.updated_at""",
            (ciphertext, iv, new_version, now_iso()),
        )
    return jsonify(ok=True, version=new_version)


@app.put("/api/sync/audio/<audio_id>")
@require_auth
def put_audio(audio_id):
    if not audio_id or len(audio_id) > 120:
        return jsonify(error="INVALID_AUDIO_ID"), 400
    data = request.get_data()
    iv = request.headers.get("X-Audio-IV", "")
    mime = request.headers.get("X-Audio-Type", "audio/webm")[:100]
    if not data or len(data) > 25 * 1024 * 1024 or not valid_crypto_field(iv, 500):
        return jsonify(error="INVALID_AUDIO"), 400
    with db() as conn:
        conn.execute(
            """INSERT INTO audio_blobs(id,ciphertext,iv,mime_type,updated_at) VALUES(?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET ciphertext=excluded.ciphertext,iv=excluded.iv,
               mime_type=excluded.mime_type,updated_at=excluded.updated_at""",
            (audio_id, data, iv, mime, now_iso()),
        )
    return jsonify(ok=True)


@app.get("/api/sync/audio/<audio_id>")
@require_auth
def get_audio(audio_id):
    with db() as conn:
        row = conn.execute(
            "SELECT ciphertext,iv,mime_type FROM audio_blobs WHERE id=?", (audio_id,)
        ).fetchone()
    if not row:
        return jsonify(error="NOT_FOUND"), 404
    response = app.response_class(row["ciphertext"], mimetype="application/octet-stream")
    response.headers["X-Audio-IV"] = row["iv"]
    response.headers["X-Audio-Type"] = row["mime_type"]
    return response


@app.delete("/api/sync/audio/<audio_id>")
@require_auth
def delete_audio(audio_id):
    with db() as conn:
        conn.execute("DELETE FROM audio_blobs WHERE id=?", (audio_id,))
    return jsonify(ok=True)


@app.post("/api/security/pairing-code")
@require_auth
def create_pairing_code():
    code = f"{secrets.randbelow(1000000):06d}"
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    with db() as conn:
        conn.execute(
            "INSERT INTO pairing_codes(code_hash,expires_at,created_at) VALUES(?,?,?)",
            (digest, expires, now_iso()),
        )
    return jsonify(code=code, expires_in_seconds=300)


@app.get("/api/security/overview")
@require_auth
def security_overview():
    with db() as conn:
        devices = [
            dict(row)
            for row in conn.execute(
                "SELECT id,name,created_at,last_seen_at,revoked_at FROM devices ORDER BY created_at"
            ).fetchall()
        ]
        attempts = [
            dict(row)
            for row in conn.execute(
                """SELECT id,device_name,ip_address,outcome,created_at,reviewed
                   FROM login_attempts WHERE outcome!='success' AND outcome!='paired_success'
                   ORDER BY id DESC LIMIT 50"""
            ).fetchall()
        ]
    return jsonify(devices=devices, attempts=attempts, current_device_id=session["device_id"])


@app.post("/api/security/devices/<device_id>/revoke")
@require_auth
def revoke_device(device_id):
    if device_id == session.get("device_id"):
        return jsonify(error="CANNOT_REVOKE_CURRENT_DEVICE"), 400
    with db() as conn:
        conn.execute("UPDATE devices SET revoked_at=? WHERE id=?", (now_iso(), device_id))
    return jsonify(ok=True)


@app.post("/api/security/attempts/review")
@require_auth
def review_attempts():
    with db() as conn:
        conn.execute("UPDATE login_attempts SET reviewed=1")
    return jsonify(ok=True)


@app.get("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.get("/<path:path>")
def assets(path):
    if path.startswith("api/") or path.startswith("data/"):
        return jsonify(error="NOT_FOUND"), 404
    return send_from_directory(ROOT, path)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8792")), debug=False)
