"""Integration tests against the NEW disposable concn_datahub_test MySQL database.

Never point this suite at a production database. Fixtures are synthetic and are
only inserted into the explicit test database, never the public catalog.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import os
from pathlib import Path
import re
import shutil
import sys
import unittest
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["MYSQL_DATABASE"] = "concn_datahub_test"
os.environ["CONCN_MAX_ACTIVE_JOBS"] = "10"
os.environ["CONCN_ENV"] = "development"
os.environ["CONCN_REQUIRE_VERIFIED_EMAIL"] = "0"
from datahub.repositories.db import connect, transaction, one
from datahub.cli import execute_script
from datahub.web import create_app
from datahub.services.jobs import submit_job
from datahub.common import ApiError, uid, now, digest
from datahub.workers.queue import claim, finish, maintain
from pymysql.constants import CLIENT
from werkzeug.security import generate_password_hash
import pymysql

A = "01020301040000"
B = "01020301050000"
C = "01020301060000"
LARGE = "01020301000000"
PASSWORD = "TestOnlyPass123!"
HASH = generate_password_hash(PASSWORD)


class MySQLIntegration(unittest.TestCase):
    def test_admin_user_search_is_scoped_paginated_and_literal(self):
        result=self.admin.get('/api/admin/users?q=ALICE').get_json()
        self.assertEqual(result['total'],1)
        self.assertEqual(result['items'][0]['username'],'alice')
        self.assertEqual(self.admin.get('/api/admin/users?q=bob%40example').get_json()['total'],1)
        self.assertEqual(self.admin.get('/api/admin/users?q=%25').get_json()['total'],0)
        self.assertEqual(self.client.get('/api/admin/users?q=alice').status_code,403)

    def test_notification_ownership_and_read_state(self):
        application = self.application().get_json()['id']
        self.approve(application)
        job = self.job().get_json()['id']
        self.ready(job)
        notices = self.client.get('/api/notifications').get_json()
        self.assertEqual(notices['unread'], 2)
        self.assertEqual({n['kind'] for n in notices['items']}, {'approve','ready'})
        self.assertEqual(self.other.get('/api/notifications').get_json()['total'], 0)
        self.assertEqual(self.post('/api/notifications/read',{}).status_code,200)
        self.assertEqual(self.client.get('/api/notifications').get_json()['unread'],0)
        self.assertEqual(self.app.test_client().get('/api/notifications').status_code,401)

    def test_download_access_matches_slots_and_approval(self):
        url = f'/api/watersheds/{C}/download-access?version={self.version}'
        self.assertTrue(self.client.get(url).get_json()['direct'])
        for code in (A,B): self.ready(self.job(code).get_json()['id'])
        self.assertFalse(self.client.get(url).get_json()['direct'])
        app_id=self.application(code=C).get_json()['id']
        self.approve(app_id)
        self.assertEqual(self.client.get(url).get_json()['application_id'],app_id)
        self.assertIsNone(self.other.get(url).get_json()['application_id'])

    def test_extra_small_basin_can_be_approved_without_third_slot(self):
        for code in (A, B):
            response = self.job(code)
            self.assertEqual(response.status_code, 202, response.get_json())
            self.ready(response.get_json()["id"])
        self.assertEqual(self.job(C).status_code, 403)
        application = self.application(code=C)
        self.assertEqual(application.status_code, 201, application.get_json())
        app_id = application.get_json()["id"]
        self.assertEqual(self.job(C, application_id=app_id).status_code, 403)
        self.approve(app_id)
        response = self.job(C, application_id=app_id)
        self.assertEqual(response.status_code, 202, response.get_json())
        with transaction() as c:
            self.assertEqual(one(c, "SELECT COUNT(*) n FROM small_basin_slots")["n"], 2)
        self.assertEqual(self.job(C).status_code, 403)
        self.assertLess(self.job(A).status_code, 300)

    def test_search_requires_exact_fourteen_ascii_digits(self):
        for value in ('', '0102', '测试流域', '010203010400000', '0102030104000a', '０１０２０３０１０４００００', ' ' + A):
            self.assertEqual(self.client.get('/api/watersheds', query_string={'q': value}).status_code, 400)
        response = self.client.get('/api/watersheds', query_string={'q': A})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r['basin_code'] for r in response.get_json()['items']], [A])
        self.assertEqual(self.client.get('/api/watersheds', query_string={'q': '99999999999999'}).get_json()['items'], [])

    def test_help_edit_requires_admin_and_updates_published_page(self):
        payload = dict(slug='test-help', kind='help', status='published', title_zh='说明', title_en='Help', body_zh='旧内容', body_en='Old text')
        self.assertEqual(self.post('/api/admin/content', payload, self.admin).status_code, 201)
        content_id = self.admin.get('/api/admin/content').get_json()['items'][0]['id']
        path = f'/api/admin/content/{content_id}'
        payload.update(body_zh='新内容\n第二行', body_en='Updated text')
        self.assertEqual(self.post(path, payload, method='PUT').status_code, 403)
        self.assertEqual(self.post(path, payload, self.admin, method='PUT').status_code, 200)
        page = self.client.get('/api/content?kind=help').get_json()['items'][0]
        self.assertEqual(page['body_zh'], '新内容\n第二行')
        self.assertEqual(page['body_en'], 'Updated text')
        payload['status'] = 'draft'
        self.assertEqual(self.post(path, payload, self.admin, method='PUT').status_code, 200)
        self.assertEqual(self.client.get('/api/content?kind=help').get_json()['items'], [])
        self.assertEqual(self.post('/api/admin/content/0', payload, self.admin, method='PUT').status_code, 404)

    def test_original_profile_username_updates_only_current_account(self):
        response = self.post(
            "/api/me/username",
            {"username": "alice_new", "user_id": self.other_id},
            method="PUT",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/me").get_json()["username"], "alice_new")
        self.assertEqual(self.other.get("/api/me").get_json()["username"], "bob")
        self.assertEqual(
            self.post(
                "/api/me/username", {"username": "admin"}, method="PUT"
            ).status_code,
            409,
        )
        self.assertEqual(
            self.post("/api/me/username", {"username": "x"}, method="PUT").status_code,
            400,
        )
        self.assertEqual(
            self.app.test_client()
            .put(
                "/api/me/username",
                json={"username": "outsider"},
                headers={"X-DataHub": "1"},
            )
            .status_code,
            401,
        )

    def setUp(self):
        if os.environ["MYSQL_DATABASE"] != "concn_datahub_test":
            raise RuntimeError("Refusing non-test database")
        self.root = ROOT / ".local" / "test-artifacts" / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        os.environ["CONCN_JOB_ROOT"] = str(self.root)
        with connect(client_flag=CLIENT.MULTI_STATEMENTS) as conn:
            with conn.cursor() as c:
                self.assertEqual(
                    one(c, "SELECT DATABASE() name")["name"], "concn_datahub_test"
                )
                tables = re.findall(
                    r"CREATE TABLE (\w+)",
                    (ROOT / "database/migrations/001_schema.sql").read_text(),
                )
                for table in reversed(tables):
                    c.execute(f"DELETE FROM `{table}`")
            conn.commit()
            execute_script(conn, ROOT / "database/seeds/001_defaults.sql")
            execute_script(conn, ROOT / "database/migrations/002_regions.sql")
            execute_script(conn, ROOT / "database/migrations/003_notification_reads.sql")
        self.app = create_app(testing=True)
        self.client = self.app.test_client()
        self.other = self.app.test_client()
        self.admin = self.app.test_client()
        with transaction() as c:
            for name, role in [("alice", "user"), ("bob", "user"), ("admin", "admin")]:
                c.execute(
                    "INSERT INTO users(username,email,password_hash,role,email_verified_at) VALUES(%s,%s,%s,%s,%s)",
                    (name, name + "@example.test", HASH, role, now()),
                )
            self.user_id = one(c, "SELECT id FROM users WHERE username='alice'")["id"]
            self.other_id = one(c, "SELECT id FROM users WHERE username='bob'")["id"]
            for code, level in [(A, 10), (B, 10), (C, 10), (LARGE, 8)]:
                c.execute(
                    "INSERT INTO watersheds(basin_code,pfbas_level,name_zh,name_en,status) VALUES(%s,%s,'测试流域','Test basin','available')",
                    (code, level),
                )
            c.execute(
                "INSERT INTO dataset_versions(version_code,title_zh,title_en,status,boundary_version,clip_version,manifest_sha256,grid_metadata,citation,terms_version,license_text_zh,license_text_en,published_at) VALUES('TEST-1','测试版本','Test only','published','test','test',%s,'{}','Test citation','test','仅测试','Test only',%s)",
                (b"x" * 32, now()),
            )
            self.version = c.lastrowid
            c.execute(
                "INSERT INTO dataset_files(dataset_version_id,item_code,title_zh,title_en,storage_key,file_kind,output_name_template) VALUES(%s,'test','测试','Test','test','generated','test.txt')",
                (self.version,),
            )
            for code in (A, B, C, LARGE):
                c.execute(
                    "INSERT INTO watershed_datasets(basin_code,dataset_version_id,status) VALUES(%s,%s,'available')",
                    (code, self.version),
                )
        self.login(self.client, "alice")
        self.login(self.other, "bob")
        self.login(self.admin, "admin")

    def tearDown(self):
        target = self.root.resolve()
        allowed = (ROOT / ".local" / "test-artifacts").resolve()
        if not target.is_relative_to(allowed) or target == allowed:
            raise RuntimeError("Unsafe test cleanup path")
        shutil.rmtree(target)

    def post(self, path, data, client=None, key=None, method="POST"):
        return (client or self.client).open(
            path,
            method=method,
            json=data,
            headers={"X-DataHub": "1", "Idempotency-Key": key or uid()},
        )

    def login(self, client, name, pw=PASSWORD):
        r = self.post(
            "/api/login", {"email": name + "@example.test", "password": pw}, client
        )
        self.assertEqual(r.status_code, 200, r.get_json())

    def job(self, code=A, client=None, application_id=None, key=None):
        data = {
            "basin_code": code,
            "dataset_version_id": self.version,
            "terms_accepted": True,
        }
        if application_id:
            data["application_id"] = application_id
        return self.post("/api/jobs", data, client, key)

    def test_download_purpose_is_saved_and_validated(self):
        data = {"basin_code": A, "dataset_version_id": self.version, "terms_accepted": True,
                "download_affiliation": " University ", "download_purpose": " Research "}
        for extra in ({"download_affiliation": " "}, {"download_purpose": "x" * 201}):
            self.assertEqual(self.post("/api/jobs", {**data, **extra}).status_code, 400)
        response = self.post("/api/jobs", data)
        self.assertEqual(response.status_code, 202, response.get_json())
        job_id = response.get_json()["id"]
        with transaction() as c:
            snapshot = one(c, "SELECT request_snapshot FROM download_jobs WHERE id=%s", (job_id,))["request_snapshot"]
        from datahub.repositories.db import decoded
        self.assertEqual(decoded(snapshot)["download_affiliation"], "University")
        self.assertEqual(decoded(snapshot)["download_purpose"], "Research")
        self.assertEqual(self.post("/api/jobs", data).get_json()["id"], job_id)
        changed = self.post("/api/jobs", {**data, "download_purpose": "Teaching"})
        self.assertEqual(changed.status_code, 202, changed.get_json())
        self.assertNotEqual(changed.get_json()["id"], job_id)

    def ready(self, job_id):
        folder = self.root / job_id / "attempt-1"
        folder.mkdir(parents=True)
        path = folder / "result.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("test.txt", "Synthetic integration fixture only")
        payload = path.read_bytes()
        with transaction() as c:
            c.execute(
                "UPDATE download_jobs SET status='succeeded',current_attempt=1 WHERE id=%s",
                (job_id,),
            )
            c.execute(
                "INSERT INTO job_attempts(job_id,attempt_no,worker_id,state,lease_expires_at,work_storage_key) VALUES(%s,1,'test','succeeded',%s,%s)",
                (job_id, now() + timedelta(hours=1), job_id + "/attempt-1"),
            )
            c.execute(
                "INSERT INTO result_archives(id,job_id,attempt_no,storage_key,byte_size,sha256,file_manifest,expires_at) VALUES(%s,%s,1,%s,%s,%s,%s,%s)",
                (
                    uid(),
                    job_id,
                    job_id + "/attempt-1/result.zip",
                    len(payload),
                    hashlib.sha256(payload).digest(),
                    "[]",
                    now() + timedelta(hours=1),
                ),
            )
        return payload

    def application(self, client=None, key=None, code=LARGE):
        return self.post(
            "/api/applications",
            {
                "basin_code": code,
                "dataset_version_id": self.version,
                "applicant_name": "Test Researcher",
                "affiliation": "Test Lab",
                "purpose": "Integration testing research purpose",
                "large_basin_reason": "Testing one large basin authorization",
                "project_url": "",
                "terms_accepted": True,
            },
            client,
            key,
        )

    def approve(self, app_id):
        r = self.post(
            f"/api/admin/applications/{app_id}/decision",
            {"action": "approve", "comment": "Approved for integration testing"},
            self.admin,
        )
        self.assertEqual(r.status_code, 200, r.get_json())

    def test_mysql_schema_and_defaults(self):
        with transaction() as c:
            self.assertEqual(
                one(
                    c,
                    "SELECT COUNT(*) n FROM information_schema.tables WHERE table_schema=DATABASE()",
                )["n"],
                23,
            )
            self.assertEqual(
                one(
                    c,
                    "SELECT small_min_hierarchy_level FROM access_policies WHERE id=1",
                )["small_min_hierarchy_level"],
                5,
            )
        cfg = self.client.get("/api/config").get_json()
        self.assertEqual(
            [(x["hierarchy_level"], x["pfbas_level"]) for x in cfg["levels"]],
            [(n, n * 2) for n in range(1, 8)],
        )

    def test_unique_email_case_insensitive(self):
        r = self.post(
            "/api/register",
            {"username": "alice2", "email": "ALICE@EXAMPLE.TEST", "password": PASSWORD},
        )
        self.assertEqual(r.status_code, 409, r.get_json())
        with transaction() as c:
            self.assertEqual(
                one(c, "SELECT COUNT(*) n FROM users WHERE email='alice@example.test'")[
                    "n"
                ],
                1,
            )

    def test_registration_session_is_http_only_and_no_password_leak(self):
        c = self.app.test_client()
        r = self.post(
            "/api/register",
            {"username": "newuser", "email": "new@example.test", "password": PASSWORD},
            c,
        )
        self.assertEqual(r.status_code, 201)
        self.assertNotIn("password", r.get_json())
        self.assertNotIn("Set-Cookie", r.headers)
        self.assertEqual(c.get('/api/me').status_code,401)
        logged = self.post('/api/login', {'email':'new@example.test','password':PASSWORD},c)
        self.assertIn('HttpOnly',logged.headers['Set-Cookie'])
        self.assertEqual(c.get("/api/me").get_json()["remaining_slots"], 2)

    def test_csrf_unauthorized_and_cross_origin_rejected(self):
        self.assertEqual(self.client.post("/api/jobs", json={}).status_code, 403)
        self.assertEqual(self.app.test_client().get("/api/jobs").status_code, 401)
        r = self.client.post(
            "/api/jobs",
            json={},
            headers={"X-DataHub": "1", "Origin": "https://untrusted.example"},
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get("/api/admin/users").status_code, 403)

    def test_two_distinct_codes_and_idempotency(self):
        key = uid()
        a = self.job(A, key=key)
        self.assertEqual(a.status_code, 202, a.get_json())
        again = self.job(A, key=key)
        self.assertEqual(again.get_json()["id"], a.get_json()["id"])
        self.assertEqual(self.job(B).status_code, 202)
        r = self.job(C)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["error"], "SMALL_BASIN_QUOTA_EXCEEDED")
        self.assertEqual(self.job(A).get_json()["id"], a.get_json()["id"])
        self.assertEqual(self.job(B, key=key).status_code, 409)
        with transaction() as c:
            self.assertEqual(
                one(
                    c,
                    "SELECT COUNT(*) n FROM small_basin_slots WHERE user_id=%s",
                    (self.user_id,),
                )["n"],
                2,
            )

    def test_parallel_requests_cannot_acquire_third_code(self):
        def submit(code):
            try:
                submit_job(
                    self.user_id,
                    {
                        "basin_code": code,
                        "dataset_version_id": self.version,
                        "terms_accepted": True,
                    },
                    uid(),
                )
                return "ok"
            except ApiError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(submit, [A, B, C]))
        self.assertEqual(results.count("ok"), 2, results)
        self.assertEqual(results.count("SMALL_BASIN_QUOTA_EXCEEDED"), 1)

    def test_cancel_releases_only_reserved_slots(self):
        j = self.job().get_json()["id"]
        r = self.post(f"/api/jobs/{j}/cancel", {})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self.client.get("/api/me").get_json()["remaining_slots"], 2)

    def test_large_single_basin_multiple_applications_and_review(self):
        self.assertEqual(self.job(LARGE).status_code, 403)
        ids = [self.application().get_json()["id"] for _ in range(3)]
        self.assertEqual(len(set(ids)), 3)
        self.approve(ids[0])
        r = self.job(LARGE, application_id=ids[0])
        self.assertEqual(r.status_code, 202, r.get_json())
        self.assertEqual(self.client.get("/api/me").get_json()["remaining_slots"], 2)
        self.assertEqual(self.job(LARGE, self.other, ids[0]).status_code, 403)
        self.assertEqual(self.job(A, application_id=ids[0]).status_code, 403)
        self.assertEqual(self.application(code=A).status_code, 201)

    def test_application_idempotent_withdraw_and_expiry(self):
        key = uid()
        a = self.application(key=key).get_json()["id"]
        self.assertEqual(self.application(key=key).get_json()["id"], a)
        self.assertEqual(
            self.post(f"/api/applications/{a}/withdraw", {}, self.other).status_code,
            404,
        )
        self.assertEqual(
            self.post(f"/api/applications/{a}/withdraw", {}).status_code, 200
        )
        b = self.application().get_json()["id"]
        self.approve(b)
        with transaction() as c:
            c.execute(
                "UPDATE large_basin_applications SET reviewed_at=%s,authorization_expires_at=%s WHERE id=%s",
                (now() - timedelta(days=2), now() - timedelta(days=1), b),
            )
        self.assertEqual(self.job(LARGE, application_id=b).status_code, 403)

    def test_database_constraints(self):
        with self.assertRaises(pymysql.MySQLError):
            with transaction() as c:
                c.execute(
                    "INSERT INTO small_basin_slots(user_id,slot_no,basin_code,policy_id) VALUES(%s,3,%s,1)",
                    (self.user_id, A),
                )
        a = self.application().get_json()["id"]
        self.approve(a)
        with self.assertRaises(pymysql.IntegrityError):
            with transaction() as c:
                c.execute(
                    "INSERT INTO download_jobs(id,user_id,basin_code,dataset_version_id,policy_id,access_mode,application_id,request_snapshot,idempotency_key,request_hash,terms_version,terms_accepted_at) VALUES(%s,%s,%s,%s,1,'approved_large',%s,'{}',%s,%s,'test',%s)",
                    (
                        uid(),
                        self.other_id,
                        LARGE,
                        self.version,
                        a,
                        uid(),
                        b"x" * 32,
                        now(),
                    ),
                )

    def test_full_package_only(self):
        base = {
            "basin_code": A,
            "dataset_version_id": self.version,
            "terms_accepted": True,
        }
        for extra in (
            {"package_mode": "selected"},
            {"variables": ["mask"]},
            {"geometry": {}},
            {"ids": [A, B]},
        ):
            self.assertEqual(self.post("/api/jobs", {**base, **extra}).status_code, 400)

    def test_download_range_ownership_and_repeat(self):
        j = self.job().get_json()["id"]
        payload = self.ready(j)
        session = self.post(f"/api/jobs/{j}/download-session", {})
        self.assertEqual(session.status_code, 200, session.get_json())
        url = session.get_json()["url"]
        data = self.client.get(url, headers={"Range": "bytes=0-9"})
        self.assertEqual(data.status_code, 206)
        self.assertEqual(data.data, payload[:10])
        self.assertEqual(data.headers["Content-Range"], f"bytes 0-9/{len(payload)}")
        expected_date=(now()+timedelta(hours=8)).strftime('%Y%m%d')
        self.assertIn(f'ParFlow_CONCN_Share_Platform_{A}_{expected_date}.zip',data.headers['Content-Disposition'])
        self.assertEqual(self.client.get(url).data, payload)
        self.assertEqual(self.other.get(url).status_code, 410)
        self.assertEqual(self.other.get("/api/jobs/" + j).status_code, 404)
        me = self.client.get("/api/me").get_json()
        self.assertEqual(me["remaining_slots"], 1)
        self.assertEqual(me["slots"][0]["state"], "active")
        self.assertEqual(self.job().get_json()["id"], j)
        self.assertEqual(
            self.client.get(url, headers={"Range": "bytes=99999-"}).status_code, 416
        )

    def test_revocation_stops_approved_download(self):
        a = self.application().get_json()["id"]
        self.approve(a)
        j = self.job(LARGE, application_id=a).get_json()["id"]
        self.ready(j)
        url = self.post(f"/api/jobs/{j}/download-session", {}).get_json()["url"]
        r = self.post(
            f"/api/admin/applications/{a}/decision",
            {"action": "revoke", "comment": "Test revocation"},
            self.admin,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 410)

    def test_policy_change_preserves_acquired_code(self):
        j = self.job().get_json()["id"]
        self.ready(j)
        self.assertEqual(
            self.post(f"/api/jobs/{j}/download-session", {}).status_code, 200
        )
        r = self.post(
            "/api/admin/config",
            {
                "small_min_hierarchy_level": 6,
                "result_retention_hours": 72,
                "approval_validity_hours": 168,
                "reason": "Test threshold",
                "maintenance_mode": False,
            },
            self.admin,
            method="PUT",
        )
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self.job(B).status_code, 403)
        self.assertEqual(self.job(A).status_code, 200)
        with transaction() as c:
            self.assertEqual(one(c, "SELECT COUNT(*) n FROM access_policies")["n"], 2)

    def test_worker_claim_failure_and_lease_recovery(self):
        j = self.job().get_json()["id"]
        job = claim()
        self.assertEqual(job["id"], j)
        finish(job, "CLIP_FAILED")
        self.assertEqual(
            self.client.get("/api/jobs/" + j).get_json()["status"], "failed"
        )
        self.assertEqual(self.client.get("/api/me").get_json()["remaining_slots"], 2)
        j2 = self.job().get_json()["id"]
        claim()
        with transaction() as c:
            c.execute(
                "UPDATE job_attempts SET lease_expires_at=%s WHERE job_id=%s",
                (now() - timedelta(minutes=1), j2),
            )
        maintain()
        self.assertEqual(
            self.client.get("/api/jobs/" + j2).get_json()["error_code"], "WORKER_LOST"
        )

    def test_login_lockout_persists(self):
        for _ in range(5):
            self.post(
                "/api/login",
                {"email": "alice@example.test", "password": "WrongPass123"},
            )
        r = self.post(
            "/api/login", {"email": "alice@example.test", "password": PASSWORD}
        )
        self.assertEqual(r.status_code, 429, r.get_json())

    def test_reset_token_consumed_and_sessions_revoked(self):
        token = uid() + uid()
        with transaction() as c:
            c.execute(
                "INSERT INTO email_actions(user_id,purpose,target_email,token_hash,expires_at) VALUES(%s,'reset_password','alice@example.test',%s,%s)",
                (self.user_id, digest(token), now() + timedelta(minutes=30)),
            )
        response = self.post(
            "/api/email-action", {"token": token, "new_password": "ChangedTestPass123"}
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        self.assertEqual(
            self.post(
                "/api/email-action", {"token": token, "new_password": "AgainTest123"}
            ).status_code,
            400,
        )
        self.login(self.client, "alice", "ChangedTestPass123")

    def test_locale_and_public_content(self):
        r = self.post("/api/me/locale", {"locale": "en"}, method="PUT")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            self.client.get("/api/me").get_json()["preferred_locale"], "en"
        )
        r = self.post(
            "/api/admin/content",
            {
                "slug": "test-help",
                "kind": "help",
                "title_zh": "帮助",
                "title_en": "Help",
                "body_zh": "仅供测试",
                "body_en": "Test only",
                "status": "published",
            },
            self.admin,
        )
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertEqual(
            self.app.test_client()
            .get("/api/content")
            .get_json()["items"][0]["title_en"],
            "Help",
        )


if __name__ == "__main__":
    unittest.main()
