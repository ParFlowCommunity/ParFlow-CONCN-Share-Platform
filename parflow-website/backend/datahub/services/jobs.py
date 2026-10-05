"""Submit and cancel jobs. Transaction boundaries and lock order are unchanged."""

from datetime import timedelta
import os
from ..common import ApiError, field, now, uid, digest
from ..repositories.db import transaction, one, all_rows, dump, decoded, audit
from .access import lock_context, dataset, grant, release_reservation
from ..package_content import package_revision


ACTIVE = ("queued", "running", "packaging", "cancel_requested")


def request_spec(data):
    import re

    allowed = {
        "basin_code",
        "dataset_version_id",
        "application_id",
        "terms_accepted",
        "package_mode",
        "download_affiliation",
        "download_purpose",
    }
    if set(data) - allowed or data.get("package_mode", "full") != "full":
        raise ApiError("FULL_PACKAGE_ONLY")
    code = field(data, "basin_code", 14, 14)
    if not re.fullmatch("[0-9]{14}", code):
        raise ApiError("INVALID_INPUT")
    version = data.get("dataset_version_id")
    if type(version) is not int or version < 1:
        raise ApiError("INVALID_INPUT")
    if data.get("terms_accepted") is not True:
        raise ApiError("TERMS_REQUIRED")
    app_id = data.get("application_id")
    if "download_affiliation" in data or "download_purpose" in data:
        field(data, "download_affiliation", 1, 100)
        field(data, "download_purpose", 1, 200)
    if app_id is not None and (
        not isinstance(app_id, str) or not re.fullmatch("[a-f0-9]{32}", app_id)
    ):
        raise ApiError("INVALID_INPUT")
    return code, version, app_id


def submit_job(user_id, data, key):
    code, version, app_id = request_spec(data)
    fingerprint = digest(dump(data))
    revision = package_revision()
    affiliation = data.get("download_affiliation", "").strip()
    purpose = data.get("download_purpose", "").strip()
    with transaction() as c:
        cfg = lock_context(c, user_id)
        old = one(
            c,
            "SELECT id,request_hash FROM download_jobs WHERE user_id=%s AND idempotency_key=%s",
            (user_id, key),
        )
        if old:
            if old["request_hash"] != fingerprint:
                raise ApiError("IDEMPOTENCY_CONFLICT", 409)
            return old["id"], True
        if cfg["maintenance_mode"]:
            raise ApiError("MAINTENANCE", 503)
        v = dataset(c, code, version)
        slots = all_rows(
            c, "SELECT * FROM small_basin_slots WHERE user_id=%s FOR UPDATE", (user_id,)
        )
        slot = next((s for s in slots if s["basin_code"] == code), None)
        if app_id:
            grant(c, app_id, user_id, code, version)
            mode = "approved_large"
        elif slot or v["pfbas_level"] // 2 >= cfg["small_min_hierarchy_level"]:
            mode = "small"
        else:
            raise ApiError("APPROVAL_REQUIRED", 403)
        old = one(
            c,
            """SELECT j.id FROM download_jobs j LEFT JOIN result_archives a ON a.job_id=j.id
            WHERE j.user_id=%s AND j.basin_code=%s AND j.dataset_version_id=%s AND j.access_mode=%s
            AND (j.application_id <=> %s) AND JSON_UNQUOTE(JSON_EXTRACT(j.request_snapshot,'$.package_revision'))=%s
            AND COALESCE(JSON_UNQUOTE(JSON_EXTRACT(j.request_snapshot,'$.download_affiliation')),'')=%s
            AND COALESCE(JSON_UNQUOTE(JSON_EXTRACT(j.request_snapshot,'$.download_purpose')),'')=%s AND (j.status IN ('queued','running','packaging') OR
              (j.status='succeeded' AND a.state='available' AND a.expires_at>UTC_TIMESTAMP(6))) ORDER BY j.created_at DESC LIMIT 1""",
            (user_id, code, version, mode, app_id, revision, affiliation, purpose),
        )
        if old:
            return old["id"], True
        if one(
            c,
            "SELECT COUNT(*) n FROM download_jobs WHERE user_id=%s AND status IN ('queued','running','packaging','cancel_requested')",
            (user_id,),
        )["n"] >= int(os.getenv("CONCN_MAX_ACTIVE_JOBS", "2")):
            raise ApiError("ACTIVE_JOB_LIMIT", 429)
        if one(c, "SELECT COUNT(*) n FROM download_jobs WHERE status='queued'")[
            "n"
        ] >= int(os.getenv("CONCN_MAX_QUEUE", "50")):
            raise ApiError("QUEUE_FULL", 429)
        if mode == "small" and not slot:
            if len(slots) >= 2:
                raise ApiError("SMALL_BASIN_QUOTA_EXCEEDED", 403, limit=2)
            number = next(i for i in (1, 2) if i not in [s["slot_no"] for s in slots])
            c.execute(
                "INSERT INTO small_basin_slots(user_id,slot_no,basin_code,policy_id) VALUES(%s,%s,%s,%s)",
                (user_id, number, code, cfg["current_policy_id"]),
            )
        files = all_rows(
            c,
            "SELECT item_code,file_kind,storage_key,source_sha256,output_name_template,metadata FROM dataset_files WHERE dataset_version_id=%s ORDER BY item_code",
            (version,),
        )
        if not files:
            raise ApiError("DATA_UNAVAILABLE", 409)
        snapshot = {
            "download_affiliation": affiliation,
            "download_purpose": purpose,
            "package_revision": revision,
            "basin_code": code,
            "pfbas_level": v["pfbas_level"],
            "version_code": v["version_code"],
            "manifest_sha256": v["manifest_sha256"],
            "boundary_version": v["boundary_version"],
            "clip_version": v["clip_version"],
            "grid": decoded(v["grid_metadata"]),
            "files": files,
            "citation": v["citation"],
            "license_zh": v["license_text_zh"],
            "license_en": v["license_text_en"],
        }
        job_id = uid()
        c.execute(
            """INSERT INTO download_jobs(id,user_id,basin_code,dataset_version_id,policy_id,access_mode,application_id,
          request_snapshot,idempotency_key,request_hash,terms_version,terms_accepted_at)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                job_id,
                user_id,
                code,
                version,
                cfg["current_policy_id"],
                mode,
                app_id,
                dump(snapshot),
                key,
                fingerprint,
                v["terms_version"],
                now(),
            ),
        )
        c.execute("INSERT INTO task_outbox(job_id) VALUES(%s)", (job_id,))
        c.execute(
            "INSERT INTO usage_daily(user_id,usage_date,accepted_jobs) VALUES(%s,%s,1) ON DUPLICATE KEY UPDATE accepted_jobs=accepted_jobs+1",
            (user_id, (now() + timedelta(hours=8)).date()),
        )
        audit(
            c, user_id, "job.create", "job", job_id, {"basin_code": code, "mode": mode}
        )
        return job_id, False


def cancel_job(c, job_id, actor, admin=False):
    row = one(c, "SELECT * FROM download_jobs WHERE id=%s", (job_id,))
    if not row or (not admin and row["user_id"] != actor):
        raise ApiError("NOT_FOUND", 404)
    lock_context(c, row["user_id"])
    row = one(c, "SELECT * FROM download_jobs WHERE id=%s FOR UPDATE", (job_id,))
    if row["status"] not in ACTIVE:
        raise ApiError("INVALID_STATE", 409)
    status = "cancelled" if row["status"] == "queued" else "cancel_requested"
    c.execute("UPDATE download_jobs SET status=%s WHERE id=%s", (status, job_id))
    release_reservation(c, row["user_id"], row["basin_code"])
    audit(c, actor, "job.cancel", "job", job_id, {})
