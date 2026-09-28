"""Durable MySQL queue worker: python -m datahub.workers.queue [--once].

Single worker is the default. Claiming supports multiple processes; admission
limits are checked separately. Real clipping runs in a cancellable subprocess.
"""

import argparse
from datetime import timedelta
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from ..common import ApiError, now, uid
from ..repositories.db import transaction, one, all_rows, dump, decoded, audit
from ..config import BACKEND
from ..services.access import dataset, grant, release_reservation
from ..integrations.storage import job_root, scoped_file


def claim():
    with transaction() as c:
        # Global config lock serializes admission/claim, and avoids queue->user lock inversion.
        one(c, "SELECT id FROM platform_config WHERE id=1 FOR UPDATE")
        row = one(
            c,
            "SELECT j.id,j.user_id FROM download_jobs j JOIN task_outbox o ON o.job_id=j.id WHERE j.status='queued' AND o.state='pending' AND o.next_attempt_at<=UTC_TIMESTAMP(6) ORDER BY j.created_at,j.id LIMIT 1",
        )
        if not row:
            return None
        user = one(
            c, "SELECT status FROM users WHERE id=%s FOR UPDATE", (row["user_id"],)
        )
        job = one(c, "SELECT * FROM download_jobs WHERE id=%s FOR UPDATE", (row["id"],))
        if user["status"] != "active":
            c.execute(
                "UPDATE download_jobs SET status='cancelled',error_code='FORBIDDEN',finished_at=%s WHERE id=%s",
                (now(), job["id"]),
            )
            release_reservation(c, job["user_id"], job["basin_code"])
            return None
        active = one(
            c,
            "SELECT id FROM download_jobs WHERE user_id=%s AND status IN ('running','packaging','cancel_requested') LIMIT 1",
            (job["user_id"],),
        )
        if active:
            return None
        try:
            dataset(c, job["basin_code"], job["dataset_version_id"])
            if job["application_id"]:
                grant(
                    c,
                    job["application_id"],
                    job["user_id"],
                    job["basin_code"],
                    job["dataset_version_id"],
                )
        except ApiError as exc:
            c.execute(
                "UPDATE download_jobs SET status='failed',error_code=%s,finished_at=%s WHERE id=%s",
                (exc.code, now(), job["id"]),
            )
            release_reservation(c, job["user_id"], job["basin_code"])
            return None
        attempt = job["current_attempt"] + 1
        workkey = f"{job['id']}/attempt-{attempt}"
        c.execute(
            "UPDATE download_jobs SET status='running',stage_code='clipping',current_attempt=%s,heartbeat_at=%s WHERE id=%s",
            (attempt, now(), job["id"]),
        )
        c.execute(
            "INSERT INTO job_attempts(job_id,attempt_no,worker_id,lease_expires_at,work_storage_key) VALUES(%s,%s,%s,%s,%s)",
            (
                job["id"],
                attempt,
                f"{os.getpid()}-{uid()[:8]}",
                now() + timedelta(minutes=2),
                workkey,
            ),
        )
        c.execute(
            "UPDATE task_outbox SET state='published',published_at=%s WHERE job_id=%s AND state='pending'",
            (now(), job["id"]),
        )
        return {**job, "attempt": attempt, "workkey": workkey}


def heartbeat(job):
    with transaction() as c:
        row = one(
            c,
            "SELECT status,current_attempt FROM download_jobs WHERE id=%s FOR UPDATE",
            (job["id"],),
        )
        if row["current_attempt"] != job["attempt"] or row["status"] not in (
            "running",
            "packaging",
        ):
            return False
        user = one(c, "SELECT status FROM users WHERE id=%s", (job["user_id"],))
        if user["status"] != "active":
            return False
        c.execute(
            "UPDATE download_jobs SET heartbeat_at=%s WHERE id=%s", (now(), job["id"])
        )
        c.execute(
            "UPDATE job_attempts SET lease_expires_at=%s WHERE job_id=%s AND attempt_no=%s",
            (now() + timedelta(minutes=2), job["id"], job["attempt"]),
        )
    return True


def finish(job, error=None):
    result = None
    if error is None:
        result = json.loads(scoped_file(job["workkey"] + "/result.json").read_text())
        if result["byte_size"] > int(os.getenv("CONCN_MAX_ZIP_BYTES", "2147483648")):
            error = "OUTPUT_TOO_LARGE"
    with transaction() as c:
        # Allow cancellation/failure cleanup even when the user has been disabled.
        cfg = one(c, "SELECT * FROM platform_config WHERE id=1 FOR UPDATE")
        one(c, "SELECT id FROM users WHERE id=%s FOR UPDATE", (job["user_id"],))
        if error is None:
            try:
                dataset(c, job["basin_code"], job["dataset_version_id"])
                if job["application_id"]:
                    grant(
                        c,
                        job["application_id"],
                        job["user_id"],
                        job["basin_code"],
                        job["dataset_version_id"],
                    )
            except ApiError as exc:
                error = exc.code
        j = one(c, "SELECT * FROM download_jobs WHERE id=%s FOR UPDATE", (job["id"],))
        if j["current_attempt"] != job["attempt"] or j["status"] not in (
            "running",
            "packaging",
            "cancel_requested",
        ):
            return
        if j["status"] == "cancel_requested":
            error = "CANCELLED"
        status = (
            "cancelled"
            if error == "CANCELLED"
            else ("failed" if error else "succeeded")
        )
        if not error:
            c.execute(
                "INSERT INTO result_archives(id,job_id,attempt_no,storage_key,byte_size,sha256,file_manifest,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    uid(),
                    job["id"],
                    job["attempt"],
                    job["workkey"] + "/result.zip",
                    result["byte_size"],
                    bytes.fromhex(result["sha256"]),
                    dump(result["files"]),
                    now() + timedelta(hours=cfg["result_retention_hours"]),
                ),
            )
        c.execute(
            "UPDATE download_jobs SET status=%s,stage_code=%s,error_code=%s,finished_at=%s WHERE id=%s",
            (status, "complete" if not error else None, error, now(), job["id"]),
        )
        c.execute(
            "UPDATE job_attempts SET state=%s,error_code=%s,finished_at=%s WHERE job_id=%s AND attempt_no=%s",
            (status, error, now(), job["id"], job["attempt"]),
        )
        if error:
            release_reservation(c, job["user_id"], job["basin_code"])
        audit(c, None, "job." + status, "job", job["id"], {"error_code": error})


def kill_tree(process):
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.kill()
        process.wait()


def execute(job):
    work = scoped_file(job["workkey"])
    work.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(work).free < int(
        os.getenv("CONCN_MIN_FREE_BYTES", "1073741824")
    ):
        finish(job, "DISK_FULL")
        return
    snapshot = work / "snapshot.json"
    snapshot.write_text(dump(decoded(job["request_snapshot"])), encoding="utf-8")
    error = None
    process = None
    try:
        with (work / "worker.log").open("wb") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "datahub.workers.clip", str(snapshot)],
                cwd=BACKEND,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
            )
            started = time.monotonic()
            while process.poll() is None:
                if not heartbeat(job):
                    error = "CANCELLED"
                    break
                if time.monotonic() - started > int(
                    os.getenv("CONCN_TASK_TIMEOUT", "3600")
                ):
                    error = "TASK_TIMEOUT"
                    break
                if shutil.disk_usage(work).free < int(
                    os.getenv("CONCN_MIN_FREE_BYTES", "1073741824")
                ):
                    error = "DISK_FULL"
                    break
                time.sleep(2)
            if error:
                kill_tree(process)
            elif process.returncode:
                error = "CLIP_FAILED"
        finish(job, error)
    except Exception:
        if process and process.poll() is None:
            kill_tree(process)
        finish(job, "CLIP_FAILED")


def maintain():
    with transaction() as c:
        stale = all_rows(
            c,
            "SELECT j.* FROM download_jobs j JOIN job_attempts a ON j.id=a.job_id AND j.current_attempt=a.attempt_no WHERE a.lease_expires_at<UTC_TIMESTAMP(6) AND j.status IN ('running','packaging','cancel_requested') LIMIT 100",
        )
    for job in stale:
        finish({**job, "attempt": job["current_attempt"]}, "WORKER_LOST")
    with transaction() as c:
        expired = all_rows(
            c,
            "SELECT a.id,j.id AS job_id,j.user_id,j.basin_code,a.storage_key FROM result_archives a JOIN download_jobs j ON a.job_id=j.id WHERE (a.expires_at<UTC_TIMESTAMP(6) AND a.state='available') OR a.state='deleting' LIMIT 100",
        )
    for item in expired:
        with transaction() as c:
            one(c, "SELECT id FROM users WHERE id=%s FOR UPDATE", (item["user_id"],))
            one(
                c,
                "SELECT id FROM result_archives WHERE id=%s FOR UPDATE",
                (item["id"],),
            )
            live = one(
                c,
                "SELECT id FROM download_sessions WHERE archive_id=%s AND ((status='active' AND expires_at>UTC_TIMESTAMP(6)) OR transfer_lease_until>UTC_TIMESTAMP(6)) LIMIT 1",
                (item["id"],),
            )
            if live:
                continue
            c.execute(
                "UPDATE result_archives SET state='deleting' WHERE id=%s", (item["id"],)
            )
        # Delete only the exact archive; preserve logs and scientific inputs. Working dirs are retained for diagnosis.
        scoped_file(item["storage_key"]).unlink(missing_ok=True)
        with transaction() as c:
            one(c, "SELECT id FROM users WHERE id=%s FOR UPDATE", (item["user_id"],))
            c.execute(
                "UPDATE result_archives SET state='deleted',deleted_at=%s WHERE id=%s",
                (now(), item["id"]),
            )
            c.execute(
                "UPDATE download_jobs SET status='expired' WHERE id=%s AND status='succeeded'",
                (item["job_id"],),
            )
            release_reservation(c, item["user_id"], item["basin_code"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    args = p.parse_args()
    job_root().mkdir(parents=True, exist_ok=True)
    while True:
        try:
            maintain()
            job = claim()
            if job:
                execute(job)
        except Exception as exc:
            print("Worker iteration failed:", type(exc).__name__, flush=True)
        if args.once:
            break
        time.sleep(2)


if __name__ == "__main__":
    main()
