"""Cookie-authorized ZIP delivery, including Range and transfer accounting."""

from datetime import timedelta
from flask import Blueprint, g, jsonify, request, current_app, Response
from ..security.sessions import require_user
from ..common import ApiError, now, uid, digest
from ..repositories.db import transaction, one
from ..services.access import lock_context, dataset, grant
from ..integrations.storage import scoped_file

bp = Blueprint("downloads", __name__)


@bp.post("/api/jobs/<job_id>/download-session")
@require_user(download=True)
def download_session(job_id):
    import secrets

    with transaction() as c:
        lock_context(c, g.user["id"])
        j = one(
            c,
            "SELECT * FROM download_jobs WHERE id=%s AND user_id=%s",
            (job_id, g.user["id"]),
        )
        if not j:
            raise ApiError("NOT_FOUND", 404)
        dataset(c, j["basin_code"], j["dataset_version_id"])
        if j["application_id"]:
            grant(
                c,
                j["application_id"],
                g.user["id"],
                j["basin_code"],
                j["dataset_version_id"],
            )
        one(c, "SELECT id FROM download_jobs WHERE id=%s FOR UPDATE", (job_id,))
        a = one(
            c,
            "SELECT * FROM result_archives WHERE job_id=%s AND state='available' AND expires_at>UTC_TIMESTAMP(6) FOR UPDATE",
            (job_id,),
        )
        if (
            j["status"] != "succeeded"
            or not a
            or not scoped_file(a["storage_key"]).is_file()
        ):
            raise ApiError("FILE_UNAVAILABLE", 410)
        if j["access_mode"] == "small":
            slot = one(
                c,
                "SELECT state FROM small_basin_slots WHERE user_id=%s AND basin_code=%s",
                (g.user["id"], j["basin_code"]),
            )
            if not slot:
                raise ApiError("FORBIDDEN", 403)
            c.execute(
                "UPDATE small_basin_slots SET state='active',activated_at=COALESCE(activated_at,UTC_TIMESTAMP(6)) WHERE user_id=%s AND basin_code=%s",
                (g.user["id"], j["basin_code"]),
            )
        token = secrets.token_urlsafe(32)
        session_id = uid()
        expiry = min(now() + timedelta(hours=1), a["expires_at"])
        if j["application_id"]:
            app = one(
                c,
                "SELECT authorization_expires_at FROM large_basin_applications WHERE id=%s",
                (j["application_id"],),
            )
            expiry = min(expiry, app["authorization_expires_at"])
        day = (now() + timedelta(hours=8)).date()
        c.execute(
            "INSERT INTO download_sessions(id,user_id,job_id,archive_id,token_hash,authorized_bytes,usage_date,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                session_id,
                g.user["id"],
                job_id,
                a["id"],
                digest(token),
                a["byte_size"],
                day,
                expiry,
            ),
        )
        c.execute(
            "INSERT INTO usage_daily(user_id,usage_date,authorized_bytes) VALUES(%s,%s,%s) ON DUPLICATE KEY UPDATE authorized_bytes=authorized_bytes+%s",
            (g.user["id"], day, a["byte_size"], a["byte_size"]),
        )
    # Secret lives in an HttpOnly cookie, not URL/history/access logs. Browser keeps it for Range retries.
    result = jsonify(url="/api/files/" + session_id, expires_at=expiry)
    result.set_cookie(
        "download_" + session_id,
        token,
        max_age=3600,
        httponly=True,
        secure=current_app.config["COOKIE_SECURE"],
        samesite="Lax",
        path="/api/files/" + session_id,
    )
    return result


@bp.route("/api/files/<session_id>", methods=["GET", "HEAD"])
@require_user(download=True)
def transfer(session_id):
    import re

    token = request.cookies.get("download_" + session_id, "")
    with transaction() as c:
        lock_context(c, g.user["id"])
        s = one(
            c,
            "SELECT * FROM download_sessions WHERE id=%s AND user_id=%s AND token_hash=%s",
            (session_id, g.user["id"], digest(token)),
        )
        if not s or s["status"] != "active" or s["expires_at"] <= now():
            raise ApiError("FILE_UNAVAILABLE", 410)
        j = one(c, "SELECT * FROM download_jobs WHERE id=%s", (s["job_id"],))
        dataset(c, j["basin_code"], j["dataset_version_id"])
        if j["application_id"]:
            grant(
                c,
                j["application_id"],
                g.user["id"],
                j["basin_code"],
                j["dataset_version_id"],
            )
        a = one(
            c,
            "SELECT * FROM result_archives WHERE id=%s FOR UPDATE",
            (s["archive_id"],),
        )
        if a["state"] != "available" or a["expires_at"] <= now():
            raise ApiError("FILE_UNAVAILABLE", 410)
        path = scoped_file(a["storage_key"])
        if not path.is_file():
            raise ApiError("FILE_UNAVAILABLE", 410)
        size = a["byte_size"]
        start, end = 0, size - 1
        status = 200
        range_header = request.headers.get("Range")
        etag = '"' + a["sha256"].hex() + '"'
        if range_header and request.headers.get("If-Range", etag) == etag:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
            if not match or not any(match.groups()):
                return Response(
                    status=416, headers={"Content-Range": f"bytes */{size}"}
                )
            left, right = match.groups()
            if left:
                start = int(left)
                end = min(int(right), size - 1) if right else size - 1
            else:
                start = max(0, size - int(right))
            if start > end or start >= size:
                return Response(
                    status=416, headers={"Content-Range": f"bytes */{size}"}
                )
            status = 206
        c.execute(
            "UPDATE download_sessions SET transfer_lease_until=%s WHERE id=%s",
            (now() + timedelta(minutes=5), session_id),
        )

    def stream():
        import time

        sent = 0
        last = time.monotonic()
        try:
            with path.open("rb") as file:
                file.seek(start)
                remaining = end - start + 1
                while remaining:
                    if time.monotonic() - last > 15:
                        with transaction() as c:
                            check = one(
                                c,
                                "SELECT s.status,u.status AS user_status FROM download_sessions s JOIN users u ON u.id=s.user_id WHERE s.id=%s",
                                (session_id,),
                            )
                            if (
                                not check
                                or check["status"] != "active"
                                or check["user_status"] != "active"
                            ):
                                break
                            if j["application_id"]:
                                grant(
                                    c,
                                    j["application_id"],
                                    s["user_id"],
                                    j["basin_code"],
                                    j["dataset_version_id"],
                                )
                            c.execute(
                                "UPDATE download_sessions SET transfer_lease_until=%s WHERE id=%s",
                                (now() + timedelta(minutes=5), session_id),
                            )
                        last = time.monotonic()
                    chunk = file.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    sent += len(chunk)
                    yield chunk
        finally:
            with transaction() as c:
                c.execute(
                    "UPDATE download_sessions SET transferred_bytes=transferred_bytes+%s WHERE id=%s",
                    (sent, session_id),
                )
                c.execute(
                    "UPDATE usage_daily SET transferred_bytes=transferred_bytes+%s WHERE user_id=%s AND usage_date=%s",
                    (sent, s["user_id"], s["usage_date"]),
                )

    headers = {
        "Content-Length": str(end - start + 1),
        "Accept-Ranges": "bytes",
        "ETag": etag,
        "Content-Disposition": f'attachment; filename="ParFlow_CONCN_Share_Platform_{j["basin_code"]}_{(now() + timedelta(hours=8)).strftime("%Y%m%d")}.zip"',
        "Cache-Control": "private, no-store",
    }
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return Response(
        None if request.method == "HEAD" else stream(),
        status=status,
        headers=headers,
        mimetype="application/zip",
    )
