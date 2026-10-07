import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    AVAILABLE = True
except ImportError:
    AVAILABLE = False

if AVAILABLE:
    from vdir.api import create_app

from vdir.cases import JOIN_SQL
from vdir.jobs import JobStore
from vdir.service import process_next


@unittest.skipUnless(AVAILABLE, "Install web/test dependencies for API checks")
class WorkbenchAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = create_app(self.root, token="", operator="test-operator")
        self.client = TestClient(self.app, base_url="http://localhost", client=("127.0.0.1", 32100))
        self.store = self.app.state.store

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def enqueue(self, case_id="case-001", key="request-001"):
        return self.client.post("/api/jobs", json={"case_id": case_id}, headers={"Idempotency-Key": key})

    def completed(self, case_id="case-001"):
        response = self.enqueue(case_id)
        self.assertEqual(response.status_code, 202)
        job_id = response.json()["id"]
        self.assertTrue(process_next(self.store))
        return self.client.get("/api/jobs/" + job_id).json()

    def test_idempotency_returns_same_job_and_conflicting_body_is_rejected(self):
        first, second = self.enqueue(), self.enqueue()
        self.assertEqual((first.status_code, second.status_code), (202, 200))
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(self.enqueue("case-002").status_code, 409)
        self.assertEqual(len(self.client.get("/api/jobs").json()), 1)

    def test_persistent_completion_trace_and_export(self):
        job = self.completed()
        self.assertEqual(job["status"], "completed")
        self.assertTrue(job["result"]["grading"]["passed"])
        self.assertEqual(len(job["result"]["response"]["trace"]), 8)
        self.assertEqual([event["name"] for event in job["events"]], ["queued", "running", "completed"])
        restored = TestClient(create_app(self.root, token=""), base_url="http://localhost", client=("127.0.0.1", 1))
        self.assertEqual(restored.get("/api/jobs/" + job["id"]).json()["result_version"], job["result_version"])
        restored.close()
        exported = self.client.get("/api/jobs/" + job["id"] + "/report")
        self.assertIn("attachment", exported.headers["content-disposition"])
        self.assertEqual(exported.json()["result"], job["result"])
        self.assertNotIn("owner", job)
        self.assertNotIn("idempotency_key", job)
        self.assertEqual(self.client.get("/api/stats").json(), {"completed": 1, "verified_candidates": 1})

    def test_review_binds_exact_version_and_is_immutable(self):
        job = self.completed()
        path = "/api/jobs/" + job["id"] + "/review"
        wrong = self.client.post(path, json={"version": "0" * 64, "action": "approved"})
        self.assertEqual(wrong.status_code, 409)
        body = {"version": job["result_version"], "action": "approved", "note": "Checked contract and snapshots"}
        accepted = self.client.post(path, json=body)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["review"]["actor"], "test-operator")
        self.assertEqual(self.client.post(path, json=body).status_code, 200)
        self.assertEqual(self.client.post(path, json=dict(body, action="rejected")).status_code, 409)
        events = self.client.get("/api/jobs/" + job["id"]).json()["events"]
        self.assertEqual(sum(event["name"] == "review_approved" for event in events), 1)

    def test_modified_candidate_requires_new_verification_and_failed_candidate_cannot_be_approved(self):
        original = self.completed()
        path = "/api/jobs/" + original["id"] + "/candidates"
        stale = self.client.post(path, json={"parent_version": "0" * 64, "candidate_sql": JOIN_SQL},
                                 headers={"Idempotency-Key": "stale-revision"})
        self.assertEqual(stale.status_code, 409)
        created = self.client.post(path, json={"parent_version": original["result_version"], "candidate_sql": JOIN_SQL},
                                   headers={"Idempotency-Key": "new-revision"})
        self.assertEqual(created.status_code, 202)
        process_next(self.store)
        revision = self.client.get("/api/jobs/" + created.json()["id"]).json()
        self.assertFalse(revision["result"]["grading"]["passed"])
        self.assertNotEqual(revision["result_version"], original["result_version"])
        approval = self.client.post("/api/jobs/" + revision["id"] + "/review",
                                    json={"version": revision["result_version"], "action": "approved"})
        self.assertEqual(approval.status_code, 409)
        self.assertEqual(self.client.get("/api/jobs/" + original["id"]).json()["result_version"], original["result_version"])

    def test_mutating_sql_is_rejected_by_verification_not_executed(self):
        original = self.completed()
        response = self.client.post("/api/jobs/" + original["id"] + "/candidates",
                                    json={"parent_version": original["result_version"], "candidate_sql": "DELETE FROM orders"},
                                    headers={"Idempotency-Key": "unsafe-revision"})
        process_next(self.store)
        revision = self.client.get("/api/jobs/" + response.json()["id"]).json()
        self.assertEqual(revision["status"], "completed")
        self.assertFalse(revision["result"]["grading"]["passed"])

    def test_no_change_is_not_a_repair_approval(self):
        job = self.completed("case-005")
        self.assertEqual(job["result"]["response"]["decision"]["status"], "no_change")
        response = self.client.post("/api/jobs/" + job["id"] + "/review",
                                    json={"version": job["result_version"], "action": "approved"})
        self.assertEqual(response.status_code, 409)

    def test_access_code_protects_data_and_is_not_exposed(self):
        token = "operator-secret-" + "x" * 32
        with TestClient(create_app(self.root, token=token), base_url="http://localhost") as client:
            self.assertEqual(client.get("/api/jobs").status_code, 401)
            self.assertEqual(client.get("/healthz").status_code, 200)
            response = client.get("/api/config", headers={"Authorization": "Bearer " + token})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(token, response.text)

    def test_local_origin_host_and_body_boundaries(self):
        remote = TestClient(self.app, base_url="http://localhost", client=("192.0.2.1", 1))
        self.assertEqual(remote.get("/api/jobs").status_code, 403)
        remote.close()
        self.assertEqual(self.client.get("/healthz", headers={"Host": "hostile.example"}).status_code, 400)
        self.assertEqual(self.client.post("/api/jobs", json={"case_id": "case-001"},
                                         headers={"Origin": "https://hostile.example"}).status_code, 403)
        self.assertEqual(self.client.post("/api/jobs", content="case_id=case-001").status_code, 415)
        self.assertEqual(self.client.post("/api/jobs", content="x" * 75001,
                                         headers={"Content-Type": "application/json"}).status_code, 413)

    def test_invalid_cases_extra_fields_and_missing_hosted_configuration(self):
        self.assertEqual(self.enqueue("unknown").status_code, 404)
        self.assertEqual(self.client.post("/api/jobs", json={"case_id": "case-001", "actor": "pretend-admin"}).status_code, 422)
        self.assertEqual(self.client.get("/api/jobs/missing").status_code, 404)
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post("/api/jobs", json={"case_id": "case-001", "investigator": "anthropic"},
                                        headers={"Idempotency-Key": "hosted-unavailable"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(len(self.store.list()), 0)

    def test_static_page_has_csp_and_public_deployment_requires_access(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Prove the repair", response.text)
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        self.assertEqual(self.client.get("/assets/app.js").status_code, 200)
        with self.assertRaises(ValueError):
            create_app(self.root, token="", public_origin="https://workbench.example")


if __name__ == "__main__":
    unittest.main()
