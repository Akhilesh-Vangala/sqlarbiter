"""Workflow admission, cancellation races and actual subprocess supervision."""

import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlarbiter.api.routes import create_app
from sqlarbiter.persistence.jobs import Conflict
from sqlarbiter.persistence.jobs import JobCancelled
from sqlarbiter.persistence.jobs import JobStore
from sqlarbiter.workflows.service import process_next
from sqlarbiter.workflows.service import case_version
from sqlarbiter.workflows.service import find_case
from sqlarbiter.evaluation.evaluation import run_worker
from sqlarbiter.evaluation.evaluation import execution_scope
from sqlarbiter.evaluation.evaluation import ExecutionInterrupted
from sqlarbiter.evaluation.evaluation import InvestigatorError


def request(case="case-001"):
    return {
        "kind": "investigation",
        "case_id": case,
        "engine": "duckdb",
        "investigator": "baseline",
        "input_version": case_version(find_case(case), "duckdb"),
    }


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = create_app(self.root, token="")
        self.client = TestClient(self.app, base_url="http://localhost", client=("127.0.0.1", 1))
        self.store = self.app.state.store

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_queued_cancel_is_idempotent_and_never_claimed(self):
        identity, _ = self.store.enqueue(request(), "cancel-queued")
        self.assertEqual(self.store.cancel(identity)["status"], "cancelled")
        self.store.cancel(identity)
        self.assertIsNone(self.store.claim())
        value = self.store.get(identity)
        self.assertEqual([e["name"] for e in value["events"]], ["queued", "cancelled"])
        self.assertIsNone(value["result"])

    def test_running_cancel_fences_publication_and_requires_owner_ack(self):
        identity, _ = self.store.enqueue(request(), "cancel-running")
        job = self.store.claim()
        self.assertEqual(self.store.cancel(identity)["status"], "cancelling")
        self.store.heartbeat(job)
        with self.assertRaises(JobCancelled):
            self.store.ensure_active(job)
        with self.assertRaises(Conflict):
            self.store.finish(job, result={})
        with self.assertRaises(Conflict):
            self.store.acknowledge_cancel(dict(job, owner="different"))
        self.store.acknowledge_cancel(job)
        self.store.acknowledge_cancel(job)
        self.assertEqual(self.store.get(identity)["status"], "cancelled")

    def test_worker_cancellation_wins_after_execution_before_publish(self):
        identity, _ = self.store.enqueue(request(), "cancel-publish")

        def cancel_during_result(store, job, telemetry):
            store.cancel(identity)
            return {"response": {"decision": {"status": "candidate"}}, "grading": {"passed": True}}

        with patch("sqlarbiter.workflows.service.execute_one", side_effect=cancel_during_result):
            self.assertTrue(process_next(self.store))
        value = self.store.get(identity)
        self.assertEqual(value["status"], "cancelled")
        self.assertIsNone(value["result_version"])

    def test_expired_cancellation_terminates_without_replay(self):
        identity, _ = self.store.enqueue(request(), "cancel-expired")
        job = self.store.claim(lease_seconds=-1)
        self.store.cancel(identity)
        self.assertIsNone(self.store.claim())
        self.assertEqual(self.store.get(identity)["status"], "cancelled")
        self.store.acknowledge_cancel(job)

    def test_shutdown_records_interruption_and_no_result(self):
        identity, _ = self.store.enqueue(request(), "shutdown-job")
        stopped = threading.Event()
        stopped.set()
        self.assertTrue(process_next(self.store, stopped))
        self.assertEqual(self.store.get(identity)["status"], "interrupted")
        self.assertIsNone(self.store.get(identity)["result"])

    def test_workflow_atomic_admission_and_idempotent_creation_across_connections(self):
        payload = {"name": "Metric checks", "jobs": [request(), request("case-005")]}
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(
                pool.map(
                    lambda _: JobStore(self.root).enqueue_workflow(
                        payload, "workflow-key", "operator"
                    ),
                    range(2),
                )
            )
        self.assertEqual(values[0][0], values[1][0])
        self.assertEqual(sum(v[1] for v in values), 1)
        self.assertEqual(len(self.store.list()), 2)
        with self.assertRaises(Conflict):
            self.store.enqueue_workflow(dict(payload, name="Changed"), "workflow-key", "operator")
        for index in range(13):
            self.store.enqueue(request(), "admission-%s" % index)
        with self.assertRaises(Conflict):
            self.store.enqueue_workflow(payload, "workflow-full", "operator")
        self.assertEqual(len(self.store.list_workflows()), 1)
        self.assertEqual(len(self.store.list()), 15)

    def test_workflow_real_end_to_end_outcomes_and_finished_members_are_preserved_on_cancel(self):
        body = {
            "name": "Revenue and event checks",
            "case_ids": ["case-001", "case-003", "case-005"],
        }
        response = self.client.post(
            "/api/workflows", json=body, headers={"Idempotency-Key": "workflow-live-local"}
        )
        self.assertEqual(response.status_code, 202)
        identity = response.json()["id"]
        self.assertEqual(
            self.client.post(
                "/api/workflows", json=body, headers={"Idempotency-Key": "workflow-live-local"}
            ).status_code,
            200,
        )
        for _ in range(3):
            self.assertTrue(process_next(self.store))
        value = self.store.get_workflow(identity)
        self.assertEqual(value["status"], "needs_attention")
        self.assertEqual(value["counts"]["resolved"], 2)
        self.assertEqual(value["counts"]["attention"], 1)
        versions = [job["result_version"] for job in value["jobs"]]
        self.assertEqual(
            [
                job["result_version"]
                for job in self.store.cancel_workflow(identity, "operator", "Stop remaining")[
                    "jobs"
                ]
            ],
            versions,
        )
        self.assertEqual(self.client.get("/api/workflows").json()[0]["id"], identity)
        with self.assertRaises(Conflict):
            self.store.cancel(value["jobs"][0]["id"])

    def test_workflow_cancel_and_input_access_boundaries(self):
        headers = {"Idempotency-Key": "workflow-invalid"}
        for body, expected in (
            ({"name": " ", "case_ids": ["case-001"]}, 409),
            ({"name": "Duplicate", "case_ids": ["case-001", "case-001"]}, 409),
            ({"name": "Unknown", "case_ids": ["case-001", "missing"]}, 404),
            ({"name": "Empty", "case_ids": []}, 422),
        ):
            self.assertEqual(
                self.client.post("/api/workflows", json=body, headers=headers).status_code, expected
            )
        self.assertEqual(self.store.list(), [])
        result = self.client.post(
            "/api/workflows",
            json={"name": "Cancel group", "case_ids": ["case-001", "case-005"]},
            headers=headers,
        ).json()
        response = self.client.post("/api/workflows/" + result["id"] + "/cancel", json={})
        self.assertEqual(response.json()["counts"]["cancelled"], 2)
        self.assertIsNone(self.store.claim())
        token = "workflow-private-" + "x" * 32
        with TestClient(
            create_app(self.root, token=token), base_url="http://localhost"
        ) as protected:
            self.assertEqual(protected.get("/api/workflows").status_code, 401)
            self.assertEqual(
                protected.post("/api/workflows/" + result["id"] + "/cancel", json={}).status_code,
                401,
            )

    def test_actual_subprocess_cancel_and_shutdown_reaps_child(self):
        runtime = self.root / "runtime"
        runtime.mkdir()
        (runtime / "worker.py").write_text(
            "import os,time\nfrom pathlib import Path\nPath('child.pid').write_text(str(os.getpid()))\ntime.sleep(60)\n"
        )

        def stop_when_running():
            if (self.root / "child.pid").exists():
                raise ExecutionInterrupted("test shutdown")

        started = time.monotonic()
        with execution_scope(stop_when_running), self.assertRaises(ExecutionInterrupted):
            run_worker(self.root)
        self.assertLess(time.monotonic() - started, 4)
        with self.assertRaises(ProcessLookupError):
            os.kill(int((self.root / "child.pid").read_text()), 0)

    def test_actual_worker_output_budget_is_enforced(self):
        runtime = self.root / "runtime"
        runtime.mkdir()
        (runtime / "worker.py").write_text("print('x'*2000001)\n")
        with self.assertRaises(InvestigatorError):
            run_worker(self.root)
