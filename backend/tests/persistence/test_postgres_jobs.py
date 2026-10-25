"""PostgreSQL adapter contract and concurrency checks."""
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from sqlarbiter.api.routes import create_app
from sqlarbiter.persistence.jobs import digest
from sqlarbiter.persistence.migrations import migrate
from sqlarbiter.persistence.postgres_jobs import PostgresJobStore
from sqlarbiter.workflows.service import process_next


DATABASE_URL = os.getenv("SQLARBITER_TEST_DATABASE_URL")


def request(case_id="case-001"):
    return {
        "kind": "investigation",
        "case_id": case_id,
        "investigator": "baseline",
        "engine": "duckdb",
        "input_version": "version-1",
    }


def result(case_id="case-001"):
    return {
        "case_id": case_id,
        "engine": "duckdb",
        "input_version": "version-1",
        "response": {"decision": {"status": "candidate", "candidate_sql": "SELECT 1"}},
        "grading": {"passed": True},
    }


@unittest.skipUnless(DATABASE_URL, "Set SQLARBITER_TEST_DATABASE_URL for PostgreSQL integration")
class PostgresJobStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        migrate(DATABASE_URL)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = PostgresJobStore(self.root, DATABASE_URL, pool_size=4)
        with self.store.connection(write=True) as connection:
            for table in ("workflow_jobs", "workflows", "graph_continuations", "events", "reviews", "jobs"):
                connection.execute("DELETE FROM " + table)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_concurrent_idempotency_claim_fencing_and_immutable_review(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            admitted = list(
                pool.map(
                    lambda _: self.store.enqueue(request(), "same-request", "operator"),
                    range(6),
                )
            )
        self.assertEqual(len({identity for identity, _ in admitted}), 1)
        self.assertEqual(sum(created for _, created in admitted), 1)

        for index in range(1, 5):
            self.store.enqueue(request("case-%03d" % index), "request-%d" % index)
        with ThreadPoolExecutor(max_workers=6) as pool:
            claims = list(pool.map(lambda _: self.store.claim(), range(6)))
        owned = [claim for claim in claims if claim]
        self.assertEqual(len(owned), 5)
        self.assertEqual(len({claim["id"] for claim in owned}), 5)

        first = owned[0]
        payload = result(first["request"]["case_id"])
        self.store.finish(first, result=payload)
        completed = self.store.get(first["id"])
        self.assertEqual(completed["result_version"], digest(payload))
        reviewed = self.store.review(
            first["id"], completed["result_version"], "approved", "reviewer", "verified"
        )
        self.assertEqual(reviewed["review"]["actor"], "reviewer")
        repeated = self.store.review(
            first["id"], completed["result_version"], "approved", "reviewer", "verified"
        )
        self.assertEqual(repeated["review"]["action"], "approved")

    def test_workflow_admission_and_expired_lease_are_persistent(self):
        workflow = {
            "name": "release checks",
            "jobs": [request("case-001"), request("case-002")],
        }
        with ThreadPoolExecutor(max_workers=4) as pool:
            values = list(
                pool.map(
                    lambda _: self.store.enqueue_workflow(workflow, "workflow-key", "operator"),
                    range(4),
                )
            )
        self.assertEqual(len({identity for identity, _ in values}), 1)
        self.assertEqual(sum(created for _, created in values), 1)
        current = self.store.get_workflow(values[0][0])
        self.assertEqual(current["counts"]["total"], 2)

        claim = self.store.claim(lease_seconds=-1)
        self.assertIsNotNone(claim)
        next_claim = self.store.claim()
        self.assertIsNotNone(next_claim)
        interrupted = self.store.get(claim["id"])
        self.assertEqual(interrupted["status"], "interrupted")
        self.assertIsNone(interrupted["result"])

    def test_api_and_worker_complete_a_verified_job_through_postgres(self):
        token = "p" * 32
        with patch.dict(os.environ, {"SQLARBITER_DATABASE_URL": DATABASE_URL, "SQLARBITER_LOAD_DOTENV": "0"}):
            app = create_app(self.root / "api", token=token)
            with TestClient(app, base_url="http://localhost") as client:
                headers = {
                    "Authorization": "Bearer " + token,
                    "Content-Type": "application/json",
                    "Idempotency-Key": "postgres-e2e-001",
                }
                created = client.post(
                    "/api/jobs",
                    headers=headers,
                    json={"case_id": "case-001", "investigator": "baseline", "engine": "duckdb"},
                )
                self.assertEqual(created.status_code, 202, created.text)
                self.assertTrue(process_next(app.state.store))
                completed = client.get(
                    "/api/jobs/" + created.json()["id"],
                    headers={"Authorization": "Bearer " + token},
                )
                self.assertEqual(completed.status_code, 200, completed.text)
                self.assertEqual(completed.json()["status"], "completed")
                self.assertTrue(completed.json()["result"]["grading"]["passed"])
                self.assertEqual(client.get("/readyz").json(), {"status": "ready"})


if __name__ == "__main__":
    unittest.main()
