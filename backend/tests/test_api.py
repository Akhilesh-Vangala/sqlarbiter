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

    def test_liveness_and_database_readiness_are_separate(self):
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/readyz").json(), {"status": "ready"})

    def test_metric_definition_exposes_only_current_public_metadata_and_requires_access(self):
        from vdir.cases import incidents
        case = incidents()[0]
        response = self.client.get("/api/incidents/" + case.case_id)
        value = response.json()
        self.assertEqual(value["contract"], case.contract)
        self.assertEqual(value["current_sql"], case.current_sql)
        self.assertEqual(value["snapshot_id"], case.sources[0].snapshot_id)
        self.assertEqual(value["schema"], {table: list(definitions) for table, (definitions, rows) in case.sources[0].tables.items()})
        self.assertEqual(set(value), {"id", "title", "description", "contract", "current_sql", "lineage", "schema", "snapshot_id", "input_version"})
        for source in case.sources[1:]:
            if source.snapshot_id != case.sources[0].snapshot_id:
                self.assertNotIn(source.snapshot_id, response.text)
        self.assertEqual(self.client.get("/api/incidents/missing").status_code, 404)
        with TestClient(create_app(self.root, token="test-access-" + "x" * 32), base_url="http://localhost") as protected:
            self.assertEqual(protected.get("/api/incidents/" + case.case_id).status_code, 401)
            self.assertEqual(protected.get("/api/config").status_code, 401)

    def test_deep_investigation_pages_validate_section_and_keep_security_headers(self):
        for section in ("evidence", "sql", "activity", "definition"):
            response = self.client.get("/investigations/" + "1" * 32 + "/" + section)
            self.assertEqual(response.status_code, 200)
            self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
        self.assertEqual(self.client.get("/investigations/" + "1" * 32 + "/unknown").status_code, 404)

    def test_spend_status_is_authenticated_and_hides_ledger_paths(self):
        response = self.client.get("/api/spend")
        self.assertEqual(response.status_code, 200)
        value = response.json()
        self.assertEqual((value["run_limit_usd"], value["total_limit_usd"], value["accounted_usd"]), (1, 5, 0))
        self.assertNotIn(str(self.root), response.text)
        token = "test-access-" + "x" * 32
        with TestClient(create_app(self.root, token=token), base_url="http://localhost") as client:
            self.assertEqual(client.get("/api/spend").status_code, 401)

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
        self.assertIn("New investigation", response.text)
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        self.assertEqual(self.client.get("/assets/app.js").status_code, 200)
        with self.assertRaises(ValueError):
            create_app(self.root, token="", public_origin="https://workbench.example")

    def test_public_showcase_allows_remote_reads_and_blocks_changes(self):
        with patch.dict(os.environ, {"VDIR_PUBLIC_SHOWCASE": "1"}):
            public_app = create_app(self.root / "public", token="", operator="public-showcase")
        with TestClient(public_app, base_url="https://verifyops.example", client=("203.0.113.10", 1)) as public:
            self.assertEqual(public.get("/").status_code, 200)
            config = public.get("/api/config")
            self.assertEqual(config.status_code, 200)
            self.assertTrue(config.json()["public_showcase"])
            self.assertEqual(config.json()["access_mode"], "public_read_only")
            blocked = public.post("/api/jobs", json={"case_id": "case-001"})
            self.assertEqual(blocked.status_code, 405)
            self.assertEqual(blocked.json()["detail"], "Public showcase is read-only")

    def test_page_routes_reload_without_exposing_protected_job_data(self):
        token = "private-operator-" + "x" * 32
        with TestClient(create_app(self.root, token=token), base_url="http://localhost") as client:
            for path in ("/", "/investigations", "/runs", "/investigations/" + "a" * 32):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn('id="home-view"', response.text)
                self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
                self.assertNotIn(token, response.text)
            self.assertEqual(client.get("/api/jobs/" + "a" * 32).status_code, 401)
            self.assertEqual(client.get("/api/missing").status_code, 401)
            self.assertEqual(client.get("/unrelated-path").status_code, 404)

    def test_graph_selection_requires_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post("/api/jobs", json={"case_id": "case-003", "investigator": "langgraph"},
                headers={"Idempotency-Key": "graph-not-configured"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(len(self.store.list()), 0)
        self.assertIn("LangGraph AI", self.client.get("/").text)

    def test_graph_api_service_pause_resume_keeps_original_and_verifies_continuation(self):
        import asyncio
        from graph import investigate as graph_investigate
        from tools import EvidenceTools
        from model_fixtures import ScriptedClient, completion, call
        from vdir import evaluation
        original_worker = evaluation.run_worker
        def provider(workspace, *, mode="baseline", requests=None, continuation=None, spend_root=None):
            if mode != "langgraph":
                return original_worker(workspace, mode=mode, requests=requests)
            def clarify(messages):
                import json
                if continuation:
                    self.assertIn("operator_guidance", messages[-1]["content"][0]["content"])
                    evidence = parent["result"]["response"]["trace"][0]["evidence_id"]
                else:
                    evidence = json.loads(messages[-1]["content"][0]["content"])["evidence_id"]
                return completion([call("finish", {"status": "needs_information", "explanation": "Offsets missing.",
                    "evidence_ids": [evidence], "affected_ids": ["t1", "t2"], "required_fields": ["utc_offset_minutes"]})])
            steps = [clarify] if continuation else [completion([call("contract", {})]), clarify]
            return asyncio.run(graph_investigate(EvidenceTools(workspace), ScriptedClient(steps), **(continuation or {})))
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-only", "VDIR_ANTHROPIC_MODEL": "test-only"}), \
                patch("vdir.evaluation.run_worker", side_effect=provider):
            response = self.client.post("/api/jobs", json={"case_id": "case-003", "investigator": "langgraph"},
                headers={"Idempotency-Key": "graph-pausing"})
            self.assertEqual(response.status_code, 202)
            process_next(self.store)
            parent = self.client.get("/api/jobs/" + response.json()["id"]).json()
            self.assertEqual(parent["status"], "paused")
            self.assertTrue(parent["result"]["grading"]["passed"])
            url = "/api/jobs/" + parent["id"] + "/resume"
            body = {"parent_version": parent["result_version"], "guidance": "Keep asking for source offsets."}
            self.assertEqual(self.client.post(url, json=dict(body, parent_version="0" * 64),
                headers={"Idempotency-Key": "stale-graph"}).status_code, 409)
            child = self.client.post(url, json=body, headers={"Idempotency-Key": "graph-continuation"})
            self.assertEqual(child.status_code, 202)
            self.assertEqual(self.client.post(url, json=body, headers={"Idempotency-Key": "graph-continuation"}).status_code, 200)
            self.assertEqual(self.client.post(url, json=body, headers={"Idempotency-Key": "duplicate-graph"}).status_code, 409)
            process_next(self.store)
            resumed = self.client.get("/api/jobs/" + child.json()["id"]).json()
            self.assertEqual(resumed["status"], "paused")
            self.assertEqual(resumed["result"]["response"]["model_run"]["rounds"], 3)
            self.assertEqual(len(resumed["result"]["response"]["trace"]), 1)
            self.assertTrue(resumed["result"]["grading"]["passed"])
            unchanged = self.client.get("/api/jobs/" + parent["id"]).json()
            self.assertEqual(unchanged["result_version"], parent["result_version"])
            self.assertEqual(unchanged["result"], parent["result"])


if __name__ == "__main__":
    unittest.main()
