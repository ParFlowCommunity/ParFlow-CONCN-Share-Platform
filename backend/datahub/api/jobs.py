from flask import Blueprint, g, jsonify
from ..security.sessions import require_user
from ..common import ApiError, body, pagination
from ..repositories.db import transaction, one, all_rows
from .helpers import idempotency
from ..services.jobs import submit_job, cancel_job
from ..repositories.queries import JOB_SELECT

bp = Blueprint("jobs", __name__)


@bp.post("/api/jobs")
@require_user(download=True)
def create_job():
    job_id, reused = submit_job(g.user["id"], body(), idempotency())
    return jsonify(id=job_id, reused=reused), 200 if reused else 202


@bp.get("/api/jobs")
@require_user
def list_jobs():
    size, offset = pagination()
    with transaction() as c:
        rows = all_rows(
            c,
            JOB_SELECT
            + " WHERE j.user_id=%s ORDER BY j.created_at DESC,j.id DESC LIMIT %s OFFSET %s",
            (g.user["id"], size, offset),
        )
        total = one(
            c, "SELECT COUNT(*) n FROM download_jobs WHERE user_id=%s", (g.user["id"],)
        )["n"]
    return jsonify(items=rows, total=total)


@bp.get("/api/jobs/<job_id>")
@require_user
def get_job(job_id):
    with transaction() as c:
        row = one(
            c, JOB_SELECT + " WHERE j.id=%s AND j.user_id=%s", (job_id, g.user["id"])
        )
    if not row:
        raise ApiError("NOT_FOUND", 404)
    return jsonify(row)


@bp.post("/api/jobs/<job_id>/cancel")
@require_user
def cancel(job_id):
    with transaction() as c:
        cancel_job(c, job_id, g.user["id"])
    return jsonify(ok=True)
