from flask import Blueprint, g, jsonify, request
from ..security.sessions import require_user
from ..common import ApiError, body, field, pagination
from ..repositories.db import transaction, one, all_rows, decoded, audit
from ..services.jobs import cancel_job
from ..repositories.queries import PUBLIC_USER

bp = Blueprint("admin", __name__)


@bp.get("/api/admin/overview")
@require_user(admin=True)
def overview():
    with transaction() as c:
        counts = {}
        for key, sql in {
            "users": "SELECT COUNT(*) n FROM users",
            "pending": "SELECT COUNT(*) n FROM large_basin_applications WHERE status='pending'",
            "queued": "SELECT COUNT(*) n FROM download_jobs WHERE status='queued'",
            "failed": "SELECT COUNT(*) n FROM download_jobs WHERE status='failed'",
        }.items():
            counts[key] = one(c, sql)["n"]
        counts["jobs"] = all_rows(
            c, "SELECT status,COUNT(*) count FROM download_jobs GROUP BY status"
        )
        counts["last_worker_heartbeat"] = one(
            c, "SELECT MAX(heartbeat_at) heartbeat FROM download_jobs"
        )["heartbeat"]
        counts["transfer_bytes"] = one(
            c, "SELECT COALESCE(SUM(transferred_bytes),0) n FROM usage_daily"
        )["n"]
    from ..integrations.storage import job_root
    import shutil

    job_root().mkdir(parents=True, exist_ok=True)
    counts["free_disk_bytes"] = shutil.disk_usage(job_root()).free
    return jsonify(counts)


@bp.put("/api/admin/config")
@require_user(admin=True)
def edit_config():
    data = body()
    level = data.get("small_min_hierarchy_level")
    reason = field(data, "reason", 3, 1000)
    retention = data.get("result_retention_hours", 72)
    validity = data.get("approval_validity_hours", 168)
    if (
        type(level) is not int
        or not 1 <= level <= 7
        or type(retention) is not int
        or not 1 <= retention <= 720
        or type(validity) is not int
        or not 1 <= validity <= 8760
        or type(data.get("maintenance_mode", False)) is not bool
    ):
        raise ApiError("INVALID_INPUT")
    with transaction() as c:
        old = one(c, "SELECT * FROM platform_config WHERE id=1 FOR UPDATE")
        c.execute(
            "INSERT INTO access_policies(small_min_hierarchy_level,reason,created_by) VALUES(%s,%s,%s)",
            (level, reason, g.user["id"]),
        )
        policy_id = c.lastrowid
        c.execute(
            "UPDATE platform_config SET current_policy_id=%s,result_retention_hours=%s,approval_validity_hours=%s,maintenance_mode=%s,updated_by=%s WHERE id=1",
            (
                policy_id,
                retention,
                validity,
                data.get("maintenance_mode", False),
                g.user["id"],
            ),
        )
        audit(
            c,
            g.user["id"],
            "config.update",
            "policy",
            policy_id,
            {
                "previous_policy": old["current_policy_id"],
                "minimum_level": level,
                "reason": reason,
            },
        )
    return jsonify(ok=True)


@bp.get("/api/admin/users")
@require_user(admin=True)
def users():
    size, offset = pagination()
    query = request.args.get('q', '').strip()
    if len(query) > 254:
        raise ApiError('INVALID_INPUT')
    clause = " WHERE LOCATE(%s,username)>0 OR LOCATE(%s,email)>0" if query else ""
    args = (query, query) if query else ()
    with transaction() as c:
        rows = all_rows(
            c,
            f"SELECT {PUBLIC_USER} FROM users" + clause + " ORDER BY id DESC LIMIT %s OFFSET %s",
            (*args, size, offset),
        )
        total = one(c, "SELECT COUNT(*) n FROM users" + clause, args)["n"]
    return jsonify(items=rows, total=total)


@bp.put("/api/admin/users/<int:user_id>/status")
@require_user(admin=True)
def user_status(user_id):
    status = body().get("status")
    if status not in ("active", "disabled") or user_id == g.user["id"]:
        raise ApiError("INVALID_INPUT")
    with transaction() as c:
        target = one(c, "SELECT role FROM users WHERE id=%s FOR UPDATE", (user_id,))
        if not target:
            raise ApiError("NOT_FOUND", 404)
        if target["role"] == "admin":
            raise ApiError("FORBIDDEN", 403)
        c.execute("UPDATE users SET status=%s WHERE id=%s", (status, user_id))
        if status == "disabled":
            c.execute(
                "UPDATE auth_sessions SET revoked_at=UTC_TIMESTAMP(6) WHERE user_id=%s",
                (user_id,),
            )
            c.execute(
                "UPDATE download_sessions SET status='revoked' WHERE user_id=%s",
                (user_id,),
            )
        audit(c, g.user["id"], "user.status", "user", user_id, {"status": status})
    return jsonify(ok=True)


@bp.get("/api/admin/jobs")
@require_user(admin=True)
def admin_jobs():
    from ..repositories.queries import JOB_SELECT

    size, offset = pagination()
    with transaction() as c:
        rows = all_rows(
            c,
            JOB_SELECT + " ORDER BY j.created_at DESC LIMIT %s OFFSET %s",
            (size, offset),
        )
        total = one(c, "SELECT COUNT(*) n FROM download_jobs")["n"]
    return jsonify(items=rows, total=total)


@bp.post("/api/admin/jobs/<job_id>/cancel")
@require_user(admin=True)
def admin_cancel(job_id):
    with transaction() as c:
        cancel_job(c, job_id, g.user["id"], admin=True)
    return jsonify(ok=True)


@bp.get("/api/admin/audit")
@require_user(admin=True)
def audit_list():
    size, offset = pagination()
    with transaction() as c:
        rows = all_rows(
            c,
            "SELECT * FROM audit_logs ORDER BY id DESC LIMIT %s OFFSET %s",
            (size, offset),
        )
    for row in rows:
        row["details"] = decoded(row["details"])
    return jsonify(items=rows)


@bp.get("/api/admin/datasets")
@require_user(admin=True)
def admin_datasets():
    with transaction() as c:
        rows = all_rows(
            c,
            "SELECT id,version_code,title_zh,title_en,status,published_at FROM dataset_versions ORDER BY id DESC",
        )
    return jsonify(items=rows)


@bp.post("/api/admin/datasets/<int:version>/withdraw")
@require_user(admin=True)
def withdraw_dataset(version):
    with transaction() as c:
        c.execute(
            "UPDATE dataset_versions SET status='withdrawn' WHERE id=%s AND status='published'",
            (version,),
        )
        if not c.rowcount:
            raise ApiError("INVALID_STATE", 409)
        c.execute(
            "UPDATE download_sessions s JOIN download_jobs j ON j.id=s.job_id SET s.status='revoked' WHERE j.dataset_version_id=%s",
            (version,),
        )
        audit(c, g.user["id"], "dataset.withdraw", "dataset", version, {})
    return jsonify(ok=True)
