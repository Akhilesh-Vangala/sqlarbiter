import os
import tempfile
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from vdir.api import create_app


class PublicDemoTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "VDIR_PUBLIC_SHOWCASE": "1",
                "VDIR_PUBLIC_DEMO": "1",
                "VDIR_DEMO_SECRET": "local-test-secret-" + "x" * 64,
                "VDIR_LOAD_DOTENV": "0",
            },
        )
        self.env.start()
        self.app = create_app(self.directory.name)
        self.client = TestClient(self.app, base_url="https://demo.example")
        self.client.__enter__()
        response = self.client.get("/api/demo/config")
        self.assertFalse(response.json()["live_model"])
        self.assertIn("HttpOnly", response.headers["set-cookie"])

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.env.stop()
        self.directory.cleanup()

    def start(self, case="case-002"):
        r = self.client.post("/api/demo/investigate", json={"case_id": case})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_base_interpreter_can_load_only_trusted_external_dependencies(self):
        from vdir import evaluation

        # Mimic a serverless base interpreter without the parent's venv paths.
        with patch.object(evaluation.sys, "executable", sys._base_executable):
            result = self.start()
        self.assertTrue(result["grading"]["passed"])
        self.assertTrue(result["evidence"])

    def test_all_six_cases_execute_and_match_independent_grading(self):
        for case in ["case-00" + str(i) for i in range(1, 7)]:
            with self.subTest(case=case):
                result = self.start(case)
                self.assertTrue(result["grading"]["passed"], result["grading"])
                self.assertTrue(result["evidence"])
                self.assertEqual(result["engine"], "sqlite")

    def test_review_reexecutes_exact_result_and_cannot_mutate_same_branch(self):
        original = self.start()
        r = self.client.post(
            "/api/demo/review", json={"token": original["token"], "action": "approve"}
        )
        self.assertEqual(r.status_code, 200, r.text)
        reviewed = r.json()
        self.assertEqual(reviewed["stage"], "approved")
        self.assertEqual(reviewed["version"], original["version"])
        self.assertEqual(
            self.client.post(
                "/api/demo/review", json={"token": reviewed["token"], "action": "reject"}
            ).status_code,
            409,
        )

    def test_false_repair_and_unsafe_sql_fail_without_acceptance(self):
        original = self.start()
        for sql in (
            "SELECT substr(occurred_at,1,10) AS business_date, SUM(DISTINCT amount_cents) AS revenue_cents FROM event_deliveries GROUP BY business_date",
            "DELETE FROM event_deliveries",
        ):
            with self.subTest(sql=sql):
                r = self.client.post(
                    "/api/demo/verify", json={"token": original["token"], "candidate_sql": sql}
                )
                self.assertEqual(r.status_code, 200, r.text)
                revised = r.json()
                self.assertFalse(revised["grading"]["passed"])
                self.assertEqual(revised["parent_id"], original["id"])
                self.assertNotEqual(revised["id"], original["id"])
                self.assertEqual(
                    self.client.post(
                        "/api/demo/review", json={"token": revised["token"], "action": "approve"}
                    ).status_code,
                    409,
                )

    def test_unchanged_valid_candidate_reverifies_as_new_report(self):
        original = self.start()
        r = self.client.post(
            "/api/demo/verify",
            json={"token": original["token"], "candidate_sql": original["candidate_sql"]},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["grading"]["passed"])
        self.assertNotEqual(r.json()["id"], original["id"])

    def test_signed_state_blocks_tampering_other_visitors_and_expiry(self):
        token = self.start()["token"]
        changed = token[:-1] + ("1" if token[-1] != "1" else "2")
        self.assertEqual(
            self.client.post(
                "/api/demo/review", json={"token": changed, "action": "approve"}
            ).status_code,
            409,
        )
        with TestClient(self.app, base_url="https://demo.example") as other:
            other.get("/api/demo/config")
            self.assertEqual(
                other.post(
                    "/api/demo/review", json={"token": token, "action": "approve"}
                ).status_code,
                403,
            )
        with patch("vdir.demo_security.time.time", return_value=9999999999):
            self.assertEqual(
                self.client.post(
                    "/api/demo/review", json={"token": token, "action": "approve"}
                ).status_code,
                409,
            )

    def test_private_writes_live_mode_and_shared_history_are_not_exposed(self):
        self.assertEqual(self.client.post("/api/jobs", json={}).status_code, 405)
        self.assertEqual(self.client.post("/api/dbt/runs", json={}).status_code, 405)
        self.assertEqual(
            self.client.post(
                "/api/demo/investigate", json={"case_id": "case-002", "investigator": "anthropic"}
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(
                "/api/demo/investigate",
                json={"case_id": "case-002"},
                headers={"Origin": "https://untrusted.example"},
            ).status_code,
            403,
        )
        result = self.start()
        self.assertEqual(self.client.get("/api/demo/runs").json(), [])
        self.assertEqual(self.client.get("/api/demo/runs/" + result["id"]).status_code, 404)
        self.assertEqual(self.client.get("/").url.path, "/demo")
