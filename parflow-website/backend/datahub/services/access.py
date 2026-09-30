"""Shared access checks and quota reservation cleanup, using caller-owned transactions."""

from ..common import ApiError, now
from ..repositories.db import one, audit


def lock_context(c, user_id):
    cfg = one(
        c,
        "SELECT c.*,p.small_min_hierarchy_level FROM platform_config c JOIN access_policies p ON p.id=c.current_policy_id WHERE c.id=1 FOR UPDATE",
    )
    user = one(c, "SELECT id,status FROM users WHERE id=%s FOR UPDATE", (user_id,))
    if not user or user["status"] != "active":
        raise ApiError("FORBIDDEN", 403)
    return cfg


def dataset(c, code, version):
    row = one(
        c,
        """SELECT w.basin_code,w.pfbas_level, v.*,d.estimated_zip_bytes
      FROM watershed_datasets d JOIN watersheds w ON w.basin_code=d.basin_code JOIN dataset_versions v ON v.id=d.dataset_version_id
      WHERE d.basin_code=%s AND d.dataset_version_id=%s AND d.status='available' AND w.status='available' AND v.status='published' """,
        (code, version),
    )
    if not row:
        raise ApiError("DATA_UNAVAILABLE", 409)
    return row


def grant(c, app_id, user_id, code, version):
    a = one(
        c,
        "SELECT * FROM large_basin_applications WHERE id=%s AND user_id=%s AND basin_code=%s AND dataset_version_id=%s FOR UPDATE",
        (app_id, user_id, code, version),
    )
    if (
        not a
        or a["status"] != "approved"
        or not a["authorization_expires_at"]
        or a["authorization_expires_at"] <= now()
    ):
        raise ApiError("APPROVAL_REQUIRED", 403)
    return a


def release_reservation(c, user_id, code):
    """Caller owns user lock; terminal work must not release another live reference."""
    live = one(
        c,
        """SELECT j.id FROM download_jobs j LEFT JOIN result_archives a ON a.job_id=j.id
      WHERE j.user_id=%s AND j.basin_code=%s AND j.access_mode='small' AND
      (j.status IN ('queued','running','packaging','cancel_requested') OR (a.state='available' AND a.expires_at>UTC_TIMESTAMP(6))) LIMIT 1""",
        (user_id, code),
    )
    if not live:
        c.execute(
            "DELETE FROM small_basin_slots WHERE user_id=%s AND basin_code=%s AND state='reserved'",
            (user_id, code),
        )
        if c.rowcount:
            audit(
                c,
                user_id,
                "slot.release",
                "basin",
                code,
                {"reason": "no_active_result_or_task"},
            )
