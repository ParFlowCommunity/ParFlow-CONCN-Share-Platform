from datetime import timedelta
import os
import secrets
from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash
from ..repositories.db import transaction, one, all_rows, audit
from ..common import ApiError, body, field, email, password, now, digest
from ..security.sessions import COOKIE, require_user, login_response
from ..integrations.email import issue_email_action

bp = Blueprint("auth", __name__)


DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(24))


@bp.put("/api/me/username")
@require_user
def change_username():
    name = field(body(), "username", 4, 64)
    with transaction() as c:
        one(c, "SELECT id FROM users WHERE id=%s FOR UPDATE", (g.user["id"],))
        c.execute("UPDATE users SET username=%s WHERE id=%s", (name, g.user["id"]))
        audit(c, g.user["id"], "user.username", "user", g.user["id"], {})
    return jsonify(ok=True)


@bp.post("/api/register")
def register():
    data = body()
    name, address = field(data, "username", 4, 64), email(data.get("email"))
    hashed = generate_password_hash(password(data.get("password")))
    with transaction() as c:
        c.execute(
            "INSERT INTO users(username,email,password_hash) VALUES(%s,%s,%s)",
            (name, address, hashed),
        )
    return jsonify(ok=True), 201


@bp.post("/api/login")
def login():
    data = body()
    address = email(data.get("email"))
    supplied = data.get("password", "")
    if not isinstance(supplied, str) or len(supplied) > 128:
        raise ApiError("INVALID_CREDENTIALS", 401)
    error = None
    with transaction() as c:
        user = one(c, "SELECT * FROM users WHERE email=%s FOR UPDATE", (address,))
        if user and user["locked_until"] and user["locked_until"] > now():
            error = ApiError("LOGIN_LOCKED", 429)
        elif not check_password_hash(
            user["password_hash"] if user else DUMMY_HASH, supplied
        ) or (user and user["status"] != "active"):
            if user:
                count = user["failed_login_count"] + 1
                c.execute(
                    "UPDATE users SET failed_login_count=%s,locked_until=%s WHERE id=%s",
                    (
                        0 if count >= 5 else count,
                        now() + timedelta(minutes=15) if count >= 5 else None,
                        user["id"],
                    ),
                )
            error = ApiError("INVALID_CREDENTIALS", 401)
        else:
            c.execute(
                "UPDATE users SET failed_login_count=0,locked_until=NULL WHERE id=%s",
                (user["id"],),
            )
            result = login_response(c, user["id"])
    if error:
        raise error
    return result


@bp.get("/api/me")
@require_user
def me():
    with transaction() as c:
        slots = all_rows(
            c,
            "SELECT s.slot_no,s.basin_code,s.state,w.name_zh,w.name_en,w.pfbas_level FROM small_basin_slots s JOIN watersheds w ON s.basin_code=w.basin_code WHERE s.user_id=%s ORDER BY slot_no",
            (g.user["id"],),
        )
    return jsonify({**g.user, "slots": slots, "remaining_slots": 2 - len(slots)})


@bp.post("/api/logout")
def logout():
    with transaction() as c:
        c.execute(
            "UPDATE auth_sessions SET revoked_at=UTC_TIMESTAMP(6) WHERE token_hash=%s",
            (digest(request.cookies.get(COOKIE, "")),),
        )
    result = jsonify(ok=True)
    result.delete_cookie(COOKIE, path="/api")
    return result


@bp.put("/api/me/locale")
@require_user
def locale():
    value = body().get("locale")
    if value not in ("zh-CN", "en"):
        raise ApiError("INVALID_INPUT")
    with transaction() as c:
        c.execute(
            "UPDATE users SET preferred_locale=%s WHERE id=%s", (value, g.user["id"])
        )
    return jsonify(ok=True)


@bp.put("/api/me/password")
@require_user
def change_password():
    data = body()
    hashed = generate_password_hash(password(data.get("new_password")))
    with transaction() as c:
        user = one(c, "SELECT * FROM users WHERE id=%s FOR UPDATE", (g.user["id"],))
        if not check_password_hash(
            user["password_hash"], str(data.get("old_password", ""))
        ):
            raise ApiError("INVALID_CREDENTIALS", 401)
        c.execute(
            "UPDATE users SET password_hash=%s WHERE id=%s", (hashed, g.user["id"])
        )
        c.execute(
            "UPDATE auth_sessions SET revoked_at=UTC_TIMESTAMP(6) WHERE user_id=%s",
            (g.user["id"],),
        )
        c.execute(
            "UPDATE email_actions SET revoked_at=UTC_TIMESTAMP(6) WHERE user_id=%s AND consumed_at IS NULL",
            (g.user["id"],),
        )
    result = jsonify(ok=True)
    result.delete_cookie(COOKIE, path="/api")
    return result


@bp.post("/api/me/verify-email")
@require_user
def verify_email():
    issue_email_action(g.user["id"], g.user["email"], "verify_email")
    return jsonify(ok=True), 202


@bp.post("/api/me/change-email")
@require_user
def change_email():
    data = body()
    address = email(data.get("email"))
    with transaction() as c:
        user = one(c, "SELECT password_hash FROM users WHERE id=%s", (g.user["id"],))
        if not check_password_hash(
            user["password_hash"], str(data.get("password", ""))
        ):
            raise ApiError("INVALID_CREDENTIALS", 401)
        if one(c, "SELECT id FROM users WHERE email=%s", (address,)):
            raise ApiError("ACCOUNT_EXISTS", 409)
    issue_email_action(g.user["id"], address, "change_email")
    return jsonify(ok=True), 202


@bp.post("/api/forgot-password")
def forgot_password():
    address = email(body().get("email"))
    if not os.getenv("SMTP_HOST"):
        raise ApiError("EMAIL_SERVICE_UNAVAILABLE", 503)
    with transaction() as c:
        user = one(
            c,
            "SELECT id FROM users WHERE email=%s AND email_verified_at IS NOT NULL AND status='active'",
            (address,),
        )
    if user:
        issue_email_action(user["id"], address, "reset_password")
    return jsonify(ok=True), 202


@bp.post("/api/email-action")
def email_action():
    data = body()
    token = field(data, "token", 20, 128)
    # Resolve owner, then always lock user before action to agree with issuance.
    with transaction() as c:
        action = one(
            c, "SELECT * FROM email_actions WHERE token_hash=%s", (digest(token),)
        )
        if not action:
            raise ApiError("INVALID_TOKEN")
        user = one(
            c, "SELECT * FROM users WHERE id=%s FOR UPDATE", (action["user_id"],)
        )
        action = one(
            c,
            "SELECT * FROM email_actions WHERE token_hash=%s FOR UPDATE",
            (digest(token),),
        )
        if (
            user["status"] != "active"
            or action["consumed_at"]
            or action["revoked_at"]
            or action["expires_at"] <= now()
        ):
            raise ApiError("INVALID_TOKEN")
        if action["purpose"] == "reset_password":
            hashed = generate_password_hash(password(data.get("new_password")))
            c.execute(
                "UPDATE users SET password_hash=%s,failed_login_count=0,locked_until=NULL WHERE id=%s",
                (hashed, user["id"]),
            )
        elif action["purpose"] == "verify_email":
            if user["email"] != action["target_email"]:
                raise ApiError("INVALID_TOKEN")
            c.execute(
                "UPDATE users SET email_verified_at=UTC_TIMESTAMP(6) WHERE id=%s",
                (user["id"],),
            )
        else:
            c.execute(
                "UPDATE users SET email=%s,email_verified_at=UTC_TIMESTAMP(6) WHERE id=%s",
                (action["target_email"], user["id"]),
            )
        c.execute(
            "UPDATE email_actions SET consumed_at=UTC_TIMESTAMP(6) WHERE id=%s",
            (action["id"],),
        )
        c.execute(
            "UPDATE auth_sessions SET revoked_at=UTC_TIMESTAMP(6) WHERE user_id=%s",
            (user["id"],),
        )
    result = jsonify(ok=True)
    result.delete_cookie(COOKIE, path="/api")
    return result
