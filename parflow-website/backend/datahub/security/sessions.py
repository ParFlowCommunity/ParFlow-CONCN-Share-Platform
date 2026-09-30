"""Cookie sessions and role guards shared by API modules."""

from datetime import timedelta
from functools import wraps
import secrets
from flask import g, jsonify, request, current_app
from ..common import ApiError, now, digest
from ..repositories.db import transaction, one
from ..repositories.queries import PUBLIC_USER


COOKIE = "concn_session"


def session_user():
    token = request.cookies.get(COOKIE, "")
    if not token or len(token) > 128:
        return None
    with transaction() as c:
        return one(
            c,
            f"""SELECT {",".join("u." + x for x in PUBLIC_USER.split(","))}
          FROM users u JOIN auth_sessions s ON s.user_id=u.id
          WHERE s.token_hash=%s AND s.revoked_at IS NULL AND s.expires_at>UTC_TIMESTAMP(6) AND u.status='active' """,
            (digest(token),),
        )


def require_user(fn=None, *, admin=False, download=False):
    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            g.user = session_user()
            if not g.user:
                raise ApiError("LOGIN_REQUIRED", 401)
            if admin and g.user["role"] != "admin":
                raise ApiError("FORBIDDEN", 403)
            if (
                download
                and current_app.config["REQUIRE_VERIFIED"]
                and not g.user["email_verified_at"]
            ):
                raise ApiError("EMAIL_VERIFICATION_REQUIRED", 403)
            return func(*args, **kwargs)

        return wrapper

    return decorate(fn) if fn else decorate


def login_response(c, user_id):
    token = secrets.token_urlsafe(32)
    c.execute(
        "INSERT INTO auth_sessions(user_id,token_hash,expires_at) VALUES(%s,%s,%s)",
        (user_id, digest(token), now() + timedelta(days=7)),
    )
    user = one(c, f"SELECT {PUBLIC_USER} FROM users WHERE id=%s", (user_id,))
    result = jsonify(user)
    result.set_cookie(
        COOKIE,
        token,
        max_age=7 * 86400,
        httponly=True,
        secure=current_app.config["COOKIE_SECURE"],
        samesite="Lax",
        path="/api",
    )
    return result
