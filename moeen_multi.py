import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, Response, current_app, jsonify, render_template, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db_connection


moeen_bp = Blueprint("moeen_multi", __name__, url_prefix="/moeen-executive")
SESSION_ACCOUNT = "moeen_account_id"
SESSION_DEVICE = "moeen_device_id"
SESSION_CSRF = "moeen_csrf"


def _account(account_id=None, phone=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if account_id:
            cursor.execute("SELECT * FROM moeen_accounts WHERE id = %s", (account_id,))
        else:
            cursor.execute("SELECT * FROM moeen_accounts WHERE phone = %s", (phone,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def _device(account_id, device_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM moeen_devices
            WHERE account_id = %s AND device_id = %s
              AND authorized = TRUE AND revoked_at IS NULL
        """, (account_id, device_id))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def _vault(account_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM moeen_vaults WHERE account_id = %s", (account_id,))
        row = cursor.fetchone()
        if not row or not row.get("wrapped_vault"):
            return None
        return {
            "salt": row["vault_salt"],
            "wrapped_vault": row["wrapped_vault"],
            "iv": row["wrap_iv"],
        }
    finally:
        cursor.close()
        conn.close()


def _client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.remote_addr or "unknown")


def _record_attempt(outcome, account_id=None, phone="", device_id="", device_name=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO moeen_login_attempts
                (account_id, phone, device_id, device_name, ip_address, outcome)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (account_id, phone, device_id, device_name, _client_ip(), outcome))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def _blocked(account_id, device_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COUNT(*) AS count
            FROM moeen_login_attempts
            WHERE created_at >= NOW() - INTERVAL '15 minutes'
              AND outcome IN ('bad_password', 'bad_pairing')
              AND (account_id = %s OR device_id = %s OR ip_address = %s)
        """, (account_id, device_id, _client_ip()))
        return cursor.fetchone()["count"] >= 5
    finally:
        cursor.close()
        conn.close()


def _subscription_valid(account):
    if not account or account["status"] != "active":
        return False
    return not account["subscription_end"] or account["subscription_end"] >= datetime.utcnow()


def require_moeen_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        account_id = session.get(SESSION_ACCOUNT)
        device_id = session.get(SESSION_DEVICE)
        if not account_id or not device_id or not _device(account_id, device_id):
            return jsonify(error="AUTH_REQUIRED"), 401
        account = _account(account_id=account_id)
        if not _subscription_valid(account):
            return jsonify(error="SUBSCRIPTION_INACTIVE"), 403
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("X-CSRF-Token") != session.get(SESSION_CSRF):
                return jsonify(error="INVALID_CSRF"), 403
        return view(*args, **kwargs)
    return wrapped


@moeen_bp.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=(self)"
    if request.path.startswith("/moeen-executive/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@moeen_bp.get("/")
def index():
    return render_template("moeen_exec.html")


@moeen_bp.get("/manifest.webmanifest")
def moeen_manifest():
    return send_from_directory(
        f"{current_app.static_folder}/moeen_exec",
        "manifest.webmanifest",
        mimetype="application/manifest+json",
    )


@moeen_bp.get("/sw.js")
def moeen_service_worker():
    response = send_from_directory(
        f"{current_app.static_folder}/moeen_exec",
        "sw.js",
        mimetype="application/javascript",
    )
    response.headers["Service-Worker-Allowed"] = "/moeen-executive/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@moeen_bp.get("/api/auth/status")
def auth_status():
    account_id = session.get(SESSION_ACCOUNT)
    device_id = session.get(SESSION_DEVICE)
    account = _account(account_id=account_id) if account_id else None
    authenticated = bool(
        account and _subscription_valid(account) and device_id and _device(account_id, device_id)
    )
    return jsonify(
        configured=True,
        authenticated=authenticated,
        must_change=bool(account["must_change_password"]) if authenticated else False,
        csrf=session.get(SESSION_CSRF) if authenticated else None,
        vault=_vault(account_id) if authenticated else None,
        profile={
            "name": account["full_name"],
            "title": account["job_title"] or "",
        } if authenticated else None,
    )


@moeen_bp.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()[:100]
    password = data.get("password", "")
    device_id = str(data.get("device_id", ""))[:120]
    device_name = str(data.get("device_name", "جهاز غير معروف"))[:120]
    account = _account(phone=phone)
    if not account:
        _record_attempt("bad_password", phone=phone, device_id=device_id, device_name=device_name)
        return jsonify(error="INVALID_CREDENTIALS"), 401
    if _blocked(account["id"], device_id):
        _record_attempt("temporarily_blocked", account["id"], phone, device_id, device_name)
        return jsonify(error="TEMPORARILY_BLOCKED"), 429
    if not check_password_hash(account["password_hash"], password):
        _record_attempt("bad_password", account["id"], phone, device_id, device_name)
        return jsonify(error="INVALID_CREDENTIALS"), 401
    if not _subscription_valid(account):
        return jsonify(error="SUBSCRIPTION_INACTIVE"), 403
    known = _device(account["id"], device_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COUNT(*) AS count FROM moeen_devices
            WHERE account_id = %s AND authorized = TRUE AND revoked_at IS NULL
        """, (account["id"],))
        count = cursor.fetchone()["count"]
        if not known and count == 0:
            cursor.execute("""
                INSERT INTO moeen_devices(account_id, device_id, device_name)
                VALUES (%s, %s, %s)
                ON CONFLICT(account_id, device_id) DO UPDATE
                SET authorized=TRUE, revoked_at=NULL, device_name=EXCLUDED.device_name, last_seen=NOW()
            """, (account["id"], device_id, device_name))
            conn.commit()
            known = True
    finally:
        cursor.close()
        conn.close()
    if not known:
        _record_attempt("unknown_device_blocked", account["id"], phone, device_id, device_name)
        return jsonify(error="DEVICE_NOT_AUTHORIZED"), 403
    session[SESSION_ACCOUNT] = account["id"]
    session[SESSION_DEVICE] = device_id
    session[SESSION_CSRF] = secrets.token_urlsafe(24)
    session.permanent = True
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE moeen_devices SET last_seen=NOW(), device_name=%s
            WHERE account_id=%s AND device_id=%s
        """, (device_name, account["id"], device_id))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    _record_attempt("success", account["id"], phone, device_id, device_name)
    return jsonify(
        ok=True, must_change=account["must_change_password"],
        csrf=session[SESSION_CSRF], vault=_vault(account["id"]),
        profile={"name": account["full_name"], "title": account["job_title"] or ""},
    )


@moeen_bp.post("/api/auth/pair")
def pair_device():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone", "")).strip()[:100]
    password = data.get("password", "")
    code = str(data.get("pairing_code", "")).replace(" ", "")
    device_id = str(data.get("device_id", ""))[:120]
    device_name = str(data.get("device_name", "جهاز جديد"))[:120]
    account = _account(phone=phone)
    if not account or not check_password_hash(account["password_hash"], password):
        _record_attempt("bad_pairing", account["id"] if account else None, phone, device_id, device_name)
        return jsonify(error="INVALID_CREDENTIALS"), 401
    digest = hashlib.sha256(code.encode()).hexdigest()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id FROM moeen_pairing_codes
            WHERE account_id=%s AND code_hash=%s AND used_at IS NULL AND expires_at>NOW()
            ORDER BY id DESC LIMIT 1
        """, (account["id"], digest))
        row = cursor.fetchone()
        if not row:
            _record_attempt("bad_pairing", account["id"], phone, device_id, device_name)
            return jsonify(error="INVALID_PAIRING_CODE"), 403
        cursor.execute("UPDATE moeen_pairing_codes SET used_at=NOW() WHERE id=%s", (row["id"],))
        cursor.execute("""
            INSERT INTO moeen_devices(account_id,device_id,device_name)
            VALUES(%s,%s,%s)
            ON CONFLICT(account_id,device_id) DO UPDATE
            SET device_name=EXCLUDED.device_name,authorized=TRUE,revoked_at=NULL,last_seen=NOW()
        """, (account["id"], device_id, device_name))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    session[SESSION_ACCOUNT] = account["id"]
    session[SESSION_DEVICE] = device_id
    session[SESSION_CSRF] = secrets.token_urlsafe(24)
    return jsonify(ok=True, csrf=session[SESSION_CSRF], vault=_vault(account["id"]))


@moeen_bp.post("/api/auth/logout")
@require_moeen_auth
def logout():
    for key in (SESSION_ACCOUNT, SESSION_DEVICE, SESSION_CSRF):
        session.pop(key, None)
    return jsonify(ok=True)


@moeen_bp.post("/api/security/vault-init")
@require_moeen_auth
def vault_init():
    data = request.get_json(silent=True) or {}
    if not all(isinstance(data.get(key), str) and data[key] for key in ("salt", "wrapped_vault", "iv")):
        return jsonify(error="INVALID_VAULT"), 400
    account_id = session[SESSION_ACCOUNT]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO moeen_vaults(account_id,vault_salt,wrapped_vault,wrap_iv)
            VALUES(%s,%s,%s,%s)
            ON CONFLICT(account_id) DO UPDATE SET
                vault_salt=EXCLUDED.vault_salt,wrapped_vault=EXCLUDED.wrapped_vault,
                wrap_iv=EXCLUDED.wrap_iv,updated_at=NOW()
            WHERE moeen_vaults.wrapped_vault IS NULL
        """, (account_id, data["salt"], data["wrapped_vault"], data["iv"]))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return jsonify(ok=True)


@moeen_bp.get("/api/sync/state")
@require_moeen_auth
def get_sync_state():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM moeen_vaults WHERE account_id=%s", (session[SESSION_ACCOUNT],))
        row = cursor.fetchone()
        if not row or not row["ciphertext"]:
            return jsonify(state=None, version=0)
        return jsonify(
            state={"ciphertext": row["ciphertext"], "iv": row["iv"]},
            version=row["version"], updated_at=row["updated_at"].isoformat(),
        )
    finally:
        cursor.close()
        conn.close()


@moeen_bp.put("/api/sync/state")
@require_moeen_auth
def put_sync_state():
    data = request.get_json(silent=True) or {}
    try:
        base_version = int(data.get("base_version", 0))
    except (TypeError, ValueError):
        return jsonify(error="INVALID_VERSION"), 400
    ciphertext, iv = data.get("ciphertext", ""), data.get("iv", "")
    if not ciphertext or not iv:
        return jsonify(error="INVALID_ENCRYPTED_STATE"), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT version FROM moeen_vaults WHERE account_id=%s FOR UPDATE", (session[SESSION_ACCOUNT],))
        row = cursor.fetchone()
        current = row["version"] if row else 0
        if base_version != current:
            conn.rollback()
            return jsonify(error="SYNC_CONFLICT", current_version=current), 409
        version = current + 1
        cursor.execute("""
            INSERT INTO moeen_vaults(account_id,ciphertext,iv,version)
            VALUES(%s,%s,%s,%s)
            ON CONFLICT(account_id) DO UPDATE SET
                ciphertext=EXCLUDED.ciphertext,iv=EXCLUDED.iv,
                version=EXCLUDED.version,updated_at=NOW()
        """, (session[SESSION_ACCOUNT], ciphertext, iv, version))
        conn.commit()
        return jsonify(ok=True, version=version)
    finally:
        cursor.close()
        conn.close()


@moeen_bp.post("/api/security/change-password")
@require_moeen_auth
def change_password():
    data = request.get_json(silent=True) or {}
    current, new = data.get("current_password", ""), data.get("new_password", "")
    account = _account(account_id=session[SESSION_ACCOUNT])
    if not check_password_hash(account["password_hash"], current):
        return jsonify(error="INVALID_CURRENT_PASSWORD"), 401
    if len(new) < 12 or new == current:
        return jsonify(error="WEAK_PASSWORD"), 400
    vault = data.get("vault") or {}
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE moeen_accounts SET password_hash=%s,must_change_password=FALSE,updated_at=NOW()
            WHERE id=%s
        """, (generate_password_hash(new, method="scrypt"), account["id"]))
        if vault.get("salt") and vault.get("wrapped_vault") and vault.get("iv"):
            cursor.execute("""
                UPDATE moeen_vaults SET vault_salt=%s,wrapped_vault=%s,wrap_iv=%s,updated_at=NOW()
                WHERE account_id=%s
            """, (vault["salt"], vault["wrapped_vault"], vault["iv"], account["id"]))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return jsonify(ok=True)


@moeen_bp.post("/api/security/pairing-code")
@require_moeen_auth
def create_pairing_code():
    code = f"{secrets.randbelow(1000000):06d}"
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO moeen_pairing_codes(account_id,code_hash,expires_at)
            VALUES(%s,%s,NOW()+INTERVAL '5 minutes')
        """, (session[SESSION_ACCOUNT], hashlib.sha256(code.encode()).hexdigest()))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return jsonify(code=code, expires_in_seconds=300)


@moeen_bp.get("/api/security/overview")
@require_moeen_auth
def security_overview():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT device_id AS id,device_name AS name,created_at,last_seen AS last_seen_at,revoked_at
            FROM moeen_devices WHERE account_id=%s ORDER BY created_at
        """, (session[SESSION_ACCOUNT],))
        devices = cursor.fetchall()
        cursor.execute("""
            SELECT id,device_name,ip_address,outcome,created_at,reviewed
            FROM moeen_login_attempts
            WHERE account_id=%s AND outcome NOT IN ('success','paired_success')
            ORDER BY id DESC LIMIT 50
        """, (session[SESSION_ACCOUNT],))
        attempts = cursor.fetchall()
        for rows in (devices, attempts):
            for row in rows:
                for key, value in list(row.items()):
                    if isinstance(value, datetime):
                        row[key] = value.isoformat()
        return jsonify(devices=devices, attempts=attempts, current_device_id=session[SESSION_DEVICE])
    finally:
        cursor.close()
        conn.close()


@moeen_bp.post("/api/security/devices/<device_id>/revoke")
@require_moeen_auth
def revoke_device(device_id):
    if device_id == session[SESSION_DEVICE]:
        return jsonify(error="CANNOT_REVOKE_CURRENT_DEVICE"), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE moeen_devices SET revoked_at=NOW(),authorized=FALSE
            WHERE account_id=%s AND device_id=%s
        """, (session[SESSION_ACCOUNT], device_id))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return jsonify(ok=True)


@moeen_bp.post("/api/security/attempts/review")
@require_moeen_auth
def review_attempts():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE moeen_login_attempts SET reviewed=TRUE WHERE account_id=%s", (session[SESSION_ACCOUNT],))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return jsonify(ok=True)


@moeen_bp.put("/api/sync/audio/<audio_id>")
@require_moeen_auth
def put_audio(audio_id):
    payload = request.get_data()
    iv = request.headers.get("X-Audio-IV", "")
    mime = request.headers.get("X-Audio-Type", "audio/webm")[:100]
    if not payload or len(payload) > 25 * 1024 * 1024 or not iv or len(audio_id) > 120:
        return jsonify(error="INVALID_AUDIO"), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO moeen_audio_blobs(account_id,audio_id,ciphertext,iv,mime_type)
            VALUES(%s,%s,%s,%s,%s)
            ON CONFLICT(account_id,audio_id) DO UPDATE SET
                ciphertext=EXCLUDED.ciphertext,iv=EXCLUDED.iv,
                mime_type=EXCLUDED.mime_type,updated_at=NOW()
        """, (session[SESSION_ACCOUNT], audio_id, payload, iv, mime))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return jsonify(ok=True)


@moeen_bp.get("/api/sync/audio/<audio_id>")
@require_moeen_auth
def get_audio(audio_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT ciphertext,iv,mime_type FROM moeen_audio_blobs
            WHERE account_id=%s AND audio_id=%s
        """, (session[SESSION_ACCOUNT], audio_id))
        row = cursor.fetchone()
        if not row:
            return jsonify(error="NOT_FOUND"), 404
        response = Response(bytes(row["ciphertext"]), mimetype="application/octet-stream")
        response.headers["X-Audio-IV"] = row["iv"]
        response.headers["X-Audio-Type"] = row["mime_type"]
        return response
    finally:
        cursor.close()
        conn.close()


@moeen_bp.delete("/api/sync/audio/<audio_id>")
@require_moeen_auth
def delete_audio(audio_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM moeen_audio_blobs WHERE account_id=%s AND audio_id=%s
        """, (session[SESSION_ACCOUNT], audio_id))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
    return jsonify(ok=True)
