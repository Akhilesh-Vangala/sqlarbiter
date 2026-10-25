"""Actual public API/SSE and private worker provenance, without provider requests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from sqlarbiter.persistence.jobs import JobStore
from sqlarbiter.platform.run_contract import RunRecord
from sqlarbiter.uploads.api import attach
from sqlarbiter.workflows.service import case_version, find_case, process_next

ROOT = Path(__file__).resolve().parents[3]
UPLOAD = {"csv": "id,amount\na,12.34\nb,12.34\n", "mapping": {"key": "c0", "amount": "c1"}, "options": {}}


class RunContractTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        attach(app, "SQLArbiter", ROOT)
        self.client = TestClient(app)

    def test_public_run_identity_contract_binding_and_tamper_rejection(self):
        first = self.client.post("/api/uploads/analyze", json=UPLOAD)
        report = first.json()
        run = RunRecord.model_validate(report["run_record"])
        self.assertEqual(first.headers["x-run-id"], run.run_id)
        self.assertEqual(run.owner_scope, "request-local")
        self.assertEqual(run.billing, "not-used")
        other = self.client.post("/api/uploads/analyze", json=UPLOAD).json()["run_record"]
        self.assertNotEqual(run.run_id, other["run_id"])
        self.assertEqual(run.input_sha256, other["input_sha256"])
        changed = copy.deepcopy(UPLOAD)
        changed["options"]["unit"] = "cents"
        changed["csv"] = "id,amount\na,12\nb,12\n"
        second = self.client.post("/api/uploads/analyze", json=changed).json()["run_record"]
        self.assertNotEqual(run.input_sha256, second["input_sha256"])
        self.assertNotEqual(run.contract_sha256, second["contract_sha256"])
        report["run_record"]["verification_passed"] = False
        self.assertFalse(self.client.post("/api/uploads/check-report", json={"report": report}).json()["verified"])

    def test_stream_stages_and_final_report_have_one_correlation_id(self):
        response = self.client.post("/api/uploads/analyze-stream", json=UPLOAD)
        events = []
        for block in response.text.strip().split("\n\n"):
            if block.startswith("event:"):
                lines = block.splitlines()
                events.append((lines[0][7:], json.loads(lines[1][6:])))
        run = events[-1][1]["run_record"]
        self.assertTrue(all(e[1]["run_id"] == run["run_id"] for e in events if e[0] == "stage"))

    def test_public_record_cannot_claim_live_provider_verification(self):
        value = self.client.post("/api/uploads/analyze", json=UPLOAD).json()["run_record"]
        for changes in ({"mode": "langgraph"}, {"billing": "provider-reported"}, {"private_source": "secret"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                RunRecord.model_validate({**value, **changes})

    def test_private_queue_worker_and_independent_grade_share_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp))
            case = find_case("case-005")
            run_id, _ = store.enqueue({"kind": "investigation", "case_id": case.case_id, "investigator": "baseline",
                                       "engine": "sqlite", "input_version": case_version(case, "sqlite")}, "provenance-test")
            process_next(store)
            result = store.get(run_id)["result"]
            provenance = RunRecord.model_validate(result["run_record"])
            self.assertEqual(provenance.run_id, run_id)
            self.assertEqual(provenance.budget_run_id, run_id)
            self.assertTrue(provenance.verification_passed)
            self.assertEqual(provenance.verification_scope, "independent-regression")
            self.assertNotIn("candidate_sql", provenance.model_dump_json())
