from datetime import timedelta
from flask import Blueprint, g, jsonify, request
from ..security.sessions import require_user
from ..common import ApiError, body, field, now, uid, digest, pagination
from ..repositories.db import transaction, one, all_rows, dump, audit
from ..services.access import lock_context, dataset
from .helpers import idempotency
from ..repositories.queries import APP_SELECT

bp = Blueprint("applications", __name__)


@bp.post("/api/applications")
@require_user(download=True)
def apply():
    data = body()
    key = idempotency()
    fingerprint = digest(dump(data))
    allowed = {
        "basin_code",
        "dataset_version_id",
        "applicant_name",
        "affiliation",
        "purpose",
        "large_basin_reason",
        "project_url",
        "terms_accepted",
    }
    if set(data) - allowed or data.get("terms_accepted") is not True:
        raise ApiError("INVALID_INPUT")
    code = field(data, "basin_code", 14, 14)
    version = data.get("dataset_version_id")
    if type(version) is not int or version < 1:
        raise ApiError("INVALID_INPUT")
    name = field(data, "applicant_name", 1, 100)
    affiliation = field(data, "affiliation", 1, 255)
    purpose = field(data, "purpose", 10, 5000)
    reason = field(data, "large_basin_reason", 10, 5000)
    url = data.get("project_url", "")
    if (
        not isinstance(url, str)
        or len(url) > 2000
        or (url and not url.startswith(("https://", "http://")))
    ):
        raise ApiError("INVALID_FIELD", field="project_url")
    with transaction() as c:
        cfg = lock_context(c, g.user["id"])
        old = one(
            c,
            "SELECT id,request_hash FROM large_basin_applications WHERE user_id=%s AND idempotency_key=%s",
            (g.user["id"], key),
        )
        if old:
            if old["request_hash"] != fingerprint:
                raise ApiError("IDEMPOTENCY_CONFLICT", 409)
            return jsonify(id=old["id"], reused=True)
        if cfg["maintenance_mode"]:
            raise ApiError("MAINTENANCE", 503)
        v = dataset(c, code, version)
        app_id = uid()
        c.execute(
            """INSERT INTO large_basin_applications(id,user_id,basin_code,dataset_version_id,policy_id,applicant_name,
        affiliation,contact_email,purpose,large_basin_reason,project_url,terms_version,terms_accepted_at,request_snapshot,idempotency_key,request_hash)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                app_id,
                g.user["id"],
                code,
                version,
                cfg["current_policy_id"],
                name,
                affiliation,
                g.user["email"],
                purpose,
                reason,
                url,
                v["terms_version"],
                now(),
                dump(
                    {
                        "version_code": v["version_code"],
                        "manifest_sha256": v["manifest_sha256"],
                        "package_mode": "full",
                        "pfbas_level": v["pfbas_level"],
                    }
                ),
                key,
                fingerprint,
            ),
        )
        audit(
            c,
            g.user["id"],
            "application.submit",
            "application",
            app_id,
            {"basin_code": code},
        )
    return jsonify(id=app_id), 201


@bp.get("/api/applications")
@require_user
def applications():
    size, offset = pagination()
    with transaction() as c:
        rows = all_rows(
            c,
            APP_SELECT
            + " WHERE a.user_id=%s ORDER BY a.submitted_at DESC,a.id DESC LIMIT %s OFFSET %s",
            (g.user["id"], size, offset),
        )
        total = one(
            c,
            "SELECT COUNT(*) n FROM large_basin_applications WHERE user_id=%s",
            (g.user["id"],),
        )["n"]
    return jsonify(items=rows, total=total)


@bp.post("/api/applications/<app_id>/withdraw")
@require_user
def withdraw(app_id):
    with transaction() as c:
        lock_context(c, g.user["id"])
        a = one(
            c,
            "SELECT status FROM large_basin_applications WHERE id=%s AND user_id=%s FOR UPDATE",
            (app_id, g.user["id"]),
        )
        if not a:
            raise ApiError("NOT_FOUND", 404)
        if a["status"] != "pending":
            raise ApiError("INVALID_STATE", 409)
        c.execute(
            "UPDATE large_basin_applications SET status='withdrawn' WHERE id=%s",
            (app_id,),
        )
        c.execute(
            "INSERT INTO application_reviews(application_id,actor_user_id,action,comment) VALUES(%s,%s,'withdraw','Withdrawn by applicant')",
            (app_id, g.user["id"]),
        )
    return jsonify(ok=True)


@bp.get("/api/admin/applications")
@require_user(admin=True)
def admin_apps():
    size, offset = pagination()
    status = request.args.get("status", "pending")
    clause = " WHERE a.status=%s" if status else ""
    args = [status] if status else []
    with transaction() as c:
        rows = all_rows(
            c,
            APP_SELECT
            + clause
            + " ORDER BY a.submitted_at DESC,a.id DESC LIMIT %s OFFSET %s",
            [*args, size, offset],
        )
        total = one(
            c, "SELECT COUNT(*) n FROM large_basin_applications a" + clause, args
        )["n"]
    return jsonify(items=rows, total=total)


@bp.post("/api/admin/applications/<app_id>/decision")
@require_user(admin=True)
def decide(app_id):
    data = body()
    action = data.get("action")
    comment = field(data, "comment", 1, 5000)
    if action not in ("approve", "reject", "revoke"):
        raise ApiError("INVALID_INPUT")
    with transaction() as c:
        cfg = one(
            c,
            "SELECT c.*,p.small_min_hierarchy_level FROM platform_config c JOIN access_policies p ON p.id=c.current_policy_id WHERE c.id=1 FOR UPDATE",
        )
        a = one(c, "SELECT * FROM large_basin_applications WHERE id=%s", (app_id,))
        if not a:
            raise ApiError("NOT_FOUND", 404)
        one(c, "SELECT id FROM users WHERE id=%s FOR UPDATE", (a["user_id"],))
        a = one(
            c,
            "SELECT * FROM large_basin_applications WHERE id=%s FOR UPDATE",
            (app_id,),
        )
        if (action in ("approve", "reject") and a["status"] != "pending") or (
            action == "revoke" and a["status"] != "approved"
        ):
            raise ApiError("INVALID_STATE", 409)
        if action == "approve":
            v = dataset(c, a["basin_code"], a["dataset_version_id"])
            c.execute(
                "UPDATE large_basin_applications SET status='approved',reviewed_by=%s,reviewed_at=%s,review_comment=%s,authorization_expires_at=%s WHERE id=%s",
                (
                    g.user["id"],
                    now(),
                    comment,
                    now() + timedelta(hours=cfg["approval_validity_hours"]),
                    app_id,
                ),
            )
        elif action == "reject":
            c.execute(
                "UPDATE large_basin_applications SET status='rejected',reviewed_by=%s,reviewed_at=%s,review_comment=%s WHERE id=%s",
                (g.user["id"], now(), comment, app_id),
            )
        else:
            c.execute(
                "UPDATE large_basin_applications SET status='revoked',revoked_at=%s WHERE id=%s",
                (now(), app_id),
            )
            c.execute(
                "UPDATE download_sessions s JOIN download_jobs j ON j.id=s.job_id SET s.status='revoked' WHERE j.application_id=%s",
                (app_id,),
            )
            c.execute(
                "UPDATE download_jobs SET status=IF(status='queued','cancelled','cancel_requested') WHERE application_id=%s AND status IN ('queued','running','packaging')",
                (app_id,),
            )
        c.execute(
            "INSERT INTO application_reviews(application_id,actor_user_id,action,comment) VALUES(%s,%s,%s,%s)",
            (app_id, g.user["id"], action, comment),
        )
        audit(
            c,
            g.user["id"],
            "application." + action,
            "application",
            app_id,
            {"comment": comment},
        )
    return jsonify(ok=True)
