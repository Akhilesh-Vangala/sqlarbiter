import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlarbiter.api.routes import create_app
from sqlarbiter.workflows.dbt_service import CASE_ID
from sqlarbiter.persistence.jobs import digest
from sqlarbiter.persistence.jobs import Conflict
from sqlarbiter.persistence.jobs import JobCancelled
from sqlarbiter.workflows.service import process_next


def result_for(request, passed=True):
    model = "SELECT DISTINCT event_id, customer_id, occurred_at, status, amount_cents FROM stg_payment_deliveries"
    diff = "--- a/models/int_payment_events.sql\n+++ b/models/int_payment_events.sql\n+" + model
    report = {
        "passed": passed,
        "patch_sha256": hashlib.sha256(diff.encode()).hexdigest(),
        "model_sha256": hashlib.sha256(model.encode()).hexdigest(),
        "verification": [],
    }
    report["version"] = digest(report)
    return {
        "case_id": CASE_ID,
        "input_version": request["input_version"],
        "engine": "duckdb",
        "current_sql": "SELECT * FROM stg_payment_deliveries",
        "contract": {},
        "response": {
            "decision": {
                "status": "candidate",
                "candidate_sql": model,
                "explanation": "Test transport",
                "evidence_ids": [],
            },
            "trace": [],
        },
        "grading": {"passed": passed, "checks": []},
        "dbt": report,
        "patch": diff,
        "model_sql": model,
    }


class DbtAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tool = self.root / "dbt"
        self.tool.write_text("test-only executable marker")
        self.available = patch(
            "sqlarbiter.workflows.dbt_service.executable", return_value=self.tool
        )
        self.available.start()
        self.app = create_app(self.root / "state", token="")
        self.client = TestClient(self.app, base_url="http://localhost", client=("127.0.0.1", 1))
        self.store = self.app.state.store

    def tearDown(self):
        self.client.close()
        self.available.stop()
        self.temp.cleanup()

    def enqueue(self, key="dbt-request-001", **fields):
        return self.client.post(
            "/api/dbt/runs",
            json={"project_id": "payment-revenue", **fields},
            headers={"Idempotency-Key": key},
        )

    def completed(self, passed=True):
        value = self.enqueue().json()
        with patch(
            "sqlarbiter.workflows.dbt_service.execute",
            side_effect=lambda store, job: result_for(job["request"], passed),
        ):
            self.assertTrue(process_next(self.store))
        return self.store.get(value["id"])

    def test_admission_is_idempotent_and_cannot_upload_arbitrary_project_or_code(self):
        first, second = self.enqueue(), self.enqueue()
        self.assertEqual((first.status_code, second.status_code), (202, 200))
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(self.enqueue(project_path="/tmp/untrusted").status_code, 422)
        self.assertEqual(
            self.client.post(
                "/api/dbt/runs",
                json={"project_id": "../../private"},
                headers={"Idempotency-Key": "other-project"},
            ).status_code,
            422,
        )
        self.assertEqual(self.enqueue(investigator="langgraph").status_code, 503)
        self.assertEqual(len(self.store.list()), 1)

    def test_missing_tooling_is_visible_without_enqueuing_and_paths_are_private(self):
        with patch(
            "sqlarbiter.workflows.dbt_service.executable", return_value=self.root / "missing"
        ):
            response = self.client.get("/api/dbt/projects")
            self.assertFalse(response.json()[0]["available"])
            self.assertNotIn(str(self.root), response.text)
            self.assertEqual(self.enqueue().status_code, 503)
        self.assertEqual(self.store.list(), [])

    def test_progress_is_owner_fenced_and_cancelled_work_cannot_publish_progress(self):
        identity = self.enqueue().json()["id"]
        job = self.store.claim()
        self.store.progress(job, "verification", "running", {"fixtures_completed": 1})
        self.assertEqual(self.store.get(identity)["events"][-1]["payload"]["fixtures_completed"], 1)
        with self.assertRaises(Conflict):
            self.store.progress(dict(job, owner="lost-owner"), "verification", "completed")
        self.store.cancel(identity)
        with self.assertRaises(JobCancelled):
            self.store.progress(job, "verification", "completed")

    def test_verified_patch_download_and_exact_version_immutable_review(self):
        job = self.completed()
        path = "/api/jobs/" + job["id"] + "/review"
        self.assertEqual(
            self.client.post(path, json={"version": "0" * 64, "action": "approved"}).status_code,
            409,
        )
        download = self.client.get("/api/dbt/runs/" + job["id"] + "/patch")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.text, job["result"]["patch"])
        body = {"version": job["result_version"], "action": "approved", "note": "test review"}
        self.assertEqual(self.client.post(path, json=body).status_code, 200)
        self.assertEqual(self.client.post(path, json=body).status_code, 200)
        self.assertEqual(
            self.client.post(path, json=dict(body, action="rejected")).status_code, 409
        )

    def test_failed_patch_cannot_be_approved_or_downloaded(self):
        job = self.completed(False)
        self.assertEqual(self.client.get("/api/dbt/runs/" + job["id"] + "/patch").status_code, 409)
        self.assertEqual(
            self.client.post(
                "/api/jobs/" + job["id"] + "/review",
                json={"version": job["result_version"], "action": "approved"},
            ).status_code,
            409,
        )

    def test_tampered_patch_is_blocked_even_if_stored_grading_and_version_still_pass(self):
        job = self.completed()
        result = job["result"]
        result["patch"] += "\nchanged artifact"
        with self.store.connection(write=True) as db:
            db.execute("UPDATE jobs SET result_json=? WHERE id=?", (json.dumps(result), job["id"]))
        self.assertEqual(
            self.client.post(
                "/api/jobs/" + job["id"] + "/review",
                json={"version": job["result_version"], "action": "approved"},
            ).status_code,
            409,
        )
        self.assertEqual(self.client.get("/api/dbt/runs/" + job["id"] + "/patch").status_code, 409)

    def test_revisions_are_new_jobs_with_same_source_and_stale_or_cross_type_requests_fail(self):
        job = self.completed()
        body = {"parent_version": job["result_version"], "candidate_sql": "SELECT 1"}
        response = self.client.post(
            "/api/dbt/runs/" + job["id"] + "/revisions",
            json=body,
            headers={"Idempotency-Key": "revision-001"},
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["request"]["investigator"], "baseline")
        self.assertEqual(
            response.json()["request"]["input_version"], job["request"]["input_version"]
        )
        self.assertEqual(self.store.get(job["id"])["result_version"], job["result_version"])
        self.assertEqual(
            self.client.post(
                "/api/dbt/runs/" + job["id"] + "/revisions",
                json=dict(body, parent_version="0" * 64),
                headers={"Idempotency-Key": "stale-revision"},
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.post(
                "/api/jobs/" + job["id"] + "/candidates",
                json=body,
                headers={"Idempotency-Key": "wrong-route"},
            ).status_code,
            409,
        )

    def test_new_routes_require_access_and_deep_links_have_security_headers(self):
        token = "operator-secret-" + "x" * 32
        with TestClient(
            create_app(self.root / "state", token=token), base_url="http://localhost"
        ) as protected:
            self.assertEqual(protected.get("/api/dbt/projects").status_code, 401)
            self.assertEqual(protected.get("/api/dbt/runs/" + "0" * 32 + "/patch").status_code, 401)
        for path in ("/dbt", "/dbt/new", "/dbt/runs/" + "0" * 32):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
