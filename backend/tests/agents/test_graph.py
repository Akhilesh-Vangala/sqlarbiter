"""Scripted protocol/recovery tests; these do not measure live model quality."""
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from sqlarbiter.domain.cases import incidents
from sqlarbiter.evaluation.evaluation import export_workspace
from sqlarbiter.evaluation.evaluation import grade
from sqlarbiter.evaluation.evaluation import evaluate_all
from sqlarbiter.persistence.jobs import JobStore
from sqlarbiter.persistence.jobs import Conflict
from sqlarbiter.workflows.service import case_version

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "agent/investigator"))
import graph as graph_runtime
from graph import investigate
from graph import Receipts
from tools import EvidenceTools
from model import InvestigationFailed
from baseline import investigate as fixed_investigate
from fixtures.model_fixtures import ScriptedClient
from fixtures.model_fixtures import completion
from fixtures.model_fixtures import call


def finish(messages):
    evidence = json.loads(messages[-1]["content"][0]["content"])["evidence_id"]
    return completion([call("finish", {"status": "no_change", "explanation": "Current SQL satisfies the contract.",
                                       "evidence_ids": [evidence]})])


def plan_for(sql, evidence):
    return {"objective": "Check metric semantics against the source contract.",
        "hypotheses": [{"id": "h1", "claim": "Join cardinality or source identity may change the metric.",
            "test_sql": sql, "expected_signal": "Rows expose the proposed source-level cause."}],
        "evidence_ids": [evidence]}


class GraphInvestigatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.case = incidents()[4]
        self.workspace = export_workspace(self.case, self.root / "evidence")
        self.tools = EvidenceTools(self.workspace)

    def tearDown(self):
        self.temp.cleanup()

    def run_graph(self, steps, **kwargs):
        client = ScriptedClient(steps)
        response = asyncio.run(investigate(self.tools, client, **kwargs))
        return response, client

    def test_real_graph_checkpoints_and_independent_verification(self):
        response, client = self.run_graph([completion([call("contract", {})]),
            completion([call("query", {"sql": self.case.current_sql})]), finish])
        self.assertTrue(grade(self.case, response, self.root / "grading")["passed"])
        self.assertEqual(response["model_run"]["rounds"], 3)
        self.assertEqual(response["model_run"]["usage"], {"input_tokens": 60, "output_tokens": 30})
        self.assertEqual(response["model_run"]["framework"], "langgraph")
        self.assertTrue((self.workspace / "graph-checkpoints.sqlite").is_file())
        with self.assertRaisesRegex(InvestigationFailed, "completed"):
            self.run_graph([], recover=True)

    @unittest.skipUnless(
        os.getenv("SQLARBITER_TEST_DATABASE_URL"),
        "Set SQLARBITER_TEST_DATABASE_URL for PostgreSQL checkpoint integration",
    )
    def test_postgres_checkpointer_runs_the_real_graph_without_local_checkpoint_state(self):
        from sqlarbiter.persistence.migrations import setup_checkpoints

        database_url = os.environ["SQLARBITER_TEST_DATABASE_URL"]
        asyncio.run(setup_checkpoints(database_url))
        thread_id = "integration-" + uuid.uuid4().hex
        with patch.dict(
            os.environ,
            {
                "SQLARBITER_CHECKPOINT_DATABASE_URL": database_url,
                "SQLARBITER_CHECKPOINT_THREAD_ID": thread_id,
            },
        ):
            response, _ = self.run_graph(
                [
                    completion([call("contract", {})]),
                    completion([call("query", {"sql": self.case.current_sql})]),
                    finish,
                ]
            )
        self.assertTrue(grade(self.case, response, self.root / "postgres-grading")["passed"])
        self.assertFalse((self.workspace / "graph-checkpoints.sqlite").exists())
        import psycopg

        with psycopg.connect(database_url) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id=%s", (thread_id,)
            ).fetchone()[0]
        self.assertGreater(count, 0)

    def test_six_scripted_scenarios_use_same_tools_and_verifier_in_both_engines(self):
        for engine in ("sqlite", "duckdb"):
            for case in incidents():
                with self.subTest(engine=engine, case=case.case_id):
                    control = EvidenceTools(export_workspace(case, self.root / (engine + "-control-" + case.case_id), engine))
                    decision = fixed_investigate(control)
                    tools = EvidenceTools(export_workspace(case, self.root / (engine + "-graph-" + case.case_id), engine))
                    steps = [completion([call(record["method"], record["params"], str(index))
                            for index, record in enumerate(control.trace)]),
                    ]
                    if decision["status"] == "candidate":
                        diagnostic = next(r for r in control.trace if r["method"] == "query")
                        steps.append(completion([call("record_plan", plan_for(diagnostic["params"]["sql"], control.trace[0]["evidence_id"]), "plan")]))
                    steps.append(completion([call("finish", decision, "finish")]))
                    response = asyncio.run(investigate(tools, ScriptedClient(steps)))
                    self.assertTrue(grade(case, response, self.root / (engine + "-grade-" + case.case_id), engine)["passed"])
                    self.assertEqual(response["trace"], control.trace)
                    self.assertEqual(response["graph_run"]["status"],
                        "paused" if decision["status"] == "needs_information" else "completed")

    def test_receipt_closes_tool_execution_checkpoint_crash_window(self):
        original = Receipts.complete
        def crash(receipts, identity, payload):
            original(receipts, identity, payload)
            if identity.startswith("tool-"):
                raise RuntimeError("simulated process loss before checkpoint")
        with patch.object(Receipts, "complete", crash), self.assertRaisesRegex(RuntimeError, "process loss"):
            self.run_graph([completion([call("contract", {})])])
        self.tools = EvidenceTools(self.workspace)
        original_call = self.tools.call
        def only_precheck(method, params):
            self.assertEqual(method, "query", "The contract call must reuse its receipt")
            return original_call(method, params)
        with patch.object(self.tools, "call", side_effect=only_precheck):
            response, client = self.run_graph([finish], recover=True)
        self.assertEqual(len(client.requests), 1)
        self.assertEqual(response["model_run"]["rounds"], 2)
        self.assertEqual(len(response["trace"]), 2)
        self.assertEqual(response["model_run"]["usage"]["input_tokens"], 40)

    def test_receipt_closes_model_response_checkpoint_crash_window(self):
        original = Receipts.complete
        def crash(receipts, identity, payload):
            original(receipts, identity, payload)
            if identity.startswith("model-"):
                raise RuntimeError("simulated loss after model result")
        with patch.object(Receipts, "complete", crash), self.assertRaises(RuntimeError):
            self.run_graph([completion([call("contract", {})])])
        self.tools = EvidenceTools(self.workspace)
        response, client = self.run_graph([finish], recover=True)
        self.assertEqual(len(client.requests), 1)
        self.assertEqual(response["model_run"]["rounds"], 2)
        self.assertEqual(response["model_run"]["usage"]["input_tokens"], 40)

    def test_saved_receipt_recovers_in_a_new_isolated_python_process(self):
        code = '''
import asyncio, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "runtime"))
from graph import investigate, Receipts
from tools import EvidenceTools
tools = EvidenceTools(Path(sys.argv[1]))
recover = sys.argv[2] == "recover"
class Client:
    async def complete(self, messages, definitions, max_tokens=2048):
        params = ({"status":"no_change", "explanation":"Contract satisfied.",
                   "evidence_ids":[tools.trace[0]["evidence_id"]]} if recover else {})
        return {"stop_reason":"tool_use", "content":[{"type":"tool_use", "name":"finish" if recover else "contract",
                "id":"call", "input":params}], "usage":{"input_tokens":20, "output_tokens":10}}
if not recover:
    original = Receipts.complete
    def crash(self, identity, payload):
        original(self, identity, payload)
        if identity.startswith("tool-"): os._exit(9)
    Receipts.complete = crash
print(json.dumps(asyncio.run(investigate(tools, Client(), recover=recover))))
'''
        command = [sys.executable, "-I", "-B", "-c", code, str(self.workspace)]
        environment = {"PATH": os.defpath, "PYTHONIOENCODING": "utf-8"}
        crashed = subprocess.run(command + ["start"], capture_output=True, text=True, env=environment, timeout=20)
        self.assertEqual(crashed.returncode, 9, crashed.stderr)
        recovered = subprocess.run(command + ["recover"], capture_output=True, text=True, env=environment, timeout=20)
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        response = json.loads(recovered.stdout)
        self.assertEqual(response["model_run"]["rounds"], 2)
        self.assertEqual(response["model_run"]["usage"]["input_tokens"], 40)
        self.assertEqual(len(response["trace"]), 2)

    def test_ambiguous_provider_attempt_cannot_be_automatically_replayed(self):
        class FailingClient:
            async def complete(self, *args, **kwargs):
                raise RuntimeError("network lost with unknown completion")
        with self.assertRaises(RuntimeError):
            asyncio.run(investigate(self.tools, FailingClient()))
        metadata = json.loads((self.workspace / "model-run.json").read_text())
        self.assertTrue(metadata["additional_billing_unknown"])
        client = ScriptedClient([])
        with self.assertRaisesRegex(InvestigationFailed, "Unresolved call"):
            asyncio.run(investigate(EvidenceTools(self.workspace), client, recover=True))
        self.assertEqual(client.requests, [])

    def test_clarification_survives_reopen_and_keeps_budgets(self):
        self.case = incidents()[2]
        self.workspace = export_workspace(self.case, self.root / "clarification")
        self.tools = EvidenceTools(self.workspace)
        def clarify(messages):
            evidence = json.loads(messages[-1]["content"][0]["content"])["evidence_id"]
            return completion([call("finish", {"status": "needs_information", "explanation": "Offsets missing.",
                "evidence_ids": [evidence], "affected_ids": ["t1", "t2"], "required_fields": ["utc_offset_minutes"]})])
        response, _ = self.run_graph([completion([call("contract", {})]), clarify])
        self.assertEqual(response["graph_run"]["status"], "paused")
        self.assertTrue(grade(self.case, response, self.root / "grading")["passed"])
        self.tools = EvidenceTools(self.workspace)
        with self.assertRaisesRegex(InvestigationFailed, "explicit operator"):
            self.run_graph([], recover=True)
        def unchanged(messages):
            payload = json.loads(messages[-1]["content"][0]["content"])
            self.assertIn("operator_guidance", payload)
            decision = response["decision"]
            return completion([call("finish", decision)])
        continued, client = self.run_graph([unchanged], guidance="Keep requesting authoritative source offsets.")
        self.assertEqual(continued["graph_run"]["status"], "paused")
        self.assertEqual(continued["model_run"]["rounds"], 3)
        self.assertEqual(continued["model_run"]["usage"]["input_tokens"], 60)
        self.assertEqual(len(continued["trace"]), 1)
        self.assertEqual(len(client.requests), 1)

    def test_resume_rejects_changed_evidence_before_provider_call(self):
        original = Receipts.complete
        def crash(receipts, identity, payload):
            original(receipts, identity, payload)
            raise RuntimeError("crash")
        with patch.object(Receipts, "complete", crash), self.assertRaises(RuntimeError):
            self.run_graph([completion([call("contract", {})])])
        manifest = self.workspace / "incident.json"
        manifest.write_text(manifest.read_text() + "\n")
        with self.assertRaisesRegex(InvestigationFailed, "changed"):
            self.run_graph([], recover=True)

    def test_context_preflight_counter_survives_recovery(self):
        class CountingClient(ScriptedClient):
            context_tokens_requested = 0
            async def complete(self, *args, **kwargs):
                self.context_tokens_requested += 15000
                return await super().complete(*args, **kwargs)
        original = Receipts.complete
        def crash(receipts, identity, payload):
            original(receipts, identity, payload)
            if identity.startswith("tool-"):
                raise RuntimeError("crash")
        with patch.object(Receipts, "complete", crash), self.assertRaises(RuntimeError):
            asyncio.run(investigate(self.tools, CountingClient([completion([call("contract", {})])])))
        client = CountingClient([finish])
        response = asyncio.run(investigate(EvidenceTools(self.workspace), client, recover=True))
        self.assertEqual(client.context_tokens_requested, 30000)

    def test_non_allowlisted_tool_is_feedback_then_accepted_decision(self):
        response, client = self.run_graph([completion([call("read_file", {"path": "reference.py"})]),
            completion([call("contract", {})]), finish])
        self.assertTrue(client.requests[1][-1]["content"][0]["is_error"])
        self.assertFalse(response["trace"][0]["ok"])

    def test_round_and_repetition_limits(self):
        with self.assertRaisesRegex(InvestigationFailed, "Repeated identical"):
            self.run_graph([completion([call("contract", {})])] * 4)
        metadata = json.loads((self.workspace / "model-run.json").read_text())
        self.assertEqual(metadata["usage"]["input_tokens"], 80)
        self.workspace = export_workspace(self.case, self.root / "rounds")
        self.tools = EvidenceTools(self.workspace)
        with self.assertRaisesRegex(InvestigationFailed, "round budget"):
            self.run_graph([completion([call("query", {"sql": "SELECT %d AS value" % i})]) for i in range(8)])

    def test_excess_output_usage_is_rejected_and_accounted(self):
        response = completion([call("contract", {})])
        response["usage"]["output_tokens"] = 12001
        with self.assertRaisesRegex(InvestigationFailed, "Output-token budget"):
            self.run_graph([response])
        metadata = json.loads((self.workspace / "model-run.json").read_text())
        self.assertEqual(metadata["usage"]["output_tokens"], 12001)
        self.assertEqual(metadata["status"], "failed")
        self.assertEqual(self.tools.trace, [])

    def test_tool_budget_cannot_reset_on_recovery(self):
        with self.assertRaisesRegex(InvestigationFailed, "tool budget"):
            self.run_graph([completion([call("query", {"sql": "SELECT %d AS value" % i}, str(i)) for i in range(25)])])
        self.tools = EvidenceTools(self.workspace)
        with self.assertRaisesRegex(InvestigationFailed, "Unresolved call"):
            self.run_graph([], recover=True)
        self.assertEqual(len(self.tools.trace), 24)

    def test_private_reference_data_not_exported_or_checkpointed(self):
        self.run_graph([completion([call("contract", {})]), finish])
        self.assertNotIn("cases.py", [p.name for p in (self.workspace / "runtime").iterdir()])
        for name in ("graph-checkpoints.sqlite", "graph-receipts.sqlite"):
            self.assertNotIn(b"regression-equal-amounts", (self.workspace / name).read_bytes())

    def test_graph_evaluation_requires_key_before_creating_output(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "locally"):
            evaluate_all(self.root / "live", mode="langgraph")
        self.assertFalse((self.root / "live").exists())

    def test_invalid_finish_and_provider_protocol_fail_closed(self):
        responses = [completion([call("finish", {"status": "no_change", "explanation": "Claim", "evidence_ids": ["invented"]})]),
            completion([], "max_tokens"), completion([call("contract", {}, "same"), call("describe", {}, "same")]),
            completion([call("contract", {}, "one"), call("finish", {}, "two")])]
        for index, response in enumerate(responses):
            tools = EvidenceTools(export_workspace(self.case, self.root / ("invalid-%d" % index)))
            with self.subTest(index=index), self.assertRaises(InvestigationFailed):
                asyncio.run(investigate(tools, ScriptedClient([response] * 3)))

    def test_invalid_citation_is_corrected_without_resetting_rounds_or_usage(self):
        invalid = completion([call("finish", {"status": "no_change", "explanation": "Claim", "evidence_ids": ["invented"]})])
        def corrected(messages):
            feedback = json.loads(messages[-1]["content"][0]["content"])
            self.assertEqual(feedback["kind"], "controller_feedback")
            self.assertEqual(feedback["remaining_corrections"], 1)
            return completion([call("finish", {"status": "no_change", "explanation": "Contract satisfied.",
                "evidence_ids": [self.tools.trace[0]["evidence_id"]]})])
        response, _ = self.run_graph([completion([call("contract", {})]), invalid, corrected])
        self.assertEqual(response["model_run"]["rounds"], 3)
        self.assertEqual(response["model_run"]["usage"]["input_tokens"], 60)
        self.assertEqual(response["agent_workflow"]["corrections"], 1)
        self.assertTrue(grade(self.case, response, self.root / "corrected")["passed"])

    def test_unexecuted_plan_cannot_support_a_repair(self):
        self.case = incidents()[0]
        self.workspace = export_workspace(self.case, self.root / "unexecuted")
        self.tools = EvidenceTools(self.workspace)
        def plan(messages):
            return completion([call("record_plan", plan_for("SELECT 1 AS diagnostic", self.tools.trace[0]["evidence_id"]))])
        def candidate(messages):
            return completion([call("finish", {"status": "candidate", "explanation": "Repair proposed.",
                "candidate_sql": self.case.current_sql, "evidence_ids": [self.tools.trace[0]["evidence_id"]]})])
        with self.assertRaisesRegex(InvestigationFailed, "correction budget"):
            self.run_graph([completion([call("contract", {})]), plan, candidate, candidate, candidate])
        self.assertEqual(len(self.tools.trace), 1, "No unchecked repair may reach the SQL precheck")

    def test_missing_plan_and_invalid_sql_receive_bounded_feedback_then_valid_repair(self):
        self.case = incidents()[0]
        self.workspace = export_workspace(self.case, self.root / "repair")
        self.tools = EvidenceTools(self.workspace)
        diagnostic = "SELECT product_id, COUNT(*) AS versions FROM product_versions GROUP BY product_id"
        from baseline import LATEST_SQL
        def candidate(sql):
            return lambda messages: completion([call("finish", {"status": "candidate", "explanation": "Latest source version preserves item identity.",
                "candidate_sql": sql, "evidence_ids": [r["evidence_id"] for r in self.tools.trace if r["ok"]]})])
        def plan(messages):
            return completion([call("record_plan", plan_for(diagnostic, self.tools.trace[0]["evidence_id"]))])
        response, client = self.run_graph([completion([call("contract", {})]), candidate(LATEST_SQL), plan,
            completion([call("query", {"sql": diagnostic})]), candidate("SELECT invented_function(product_id) FROM product_versions"), candidate(LATEST_SQL)])
        self.assertTrue(grade(self.case, response, self.root / "repair-grade")["passed"])
        self.assertEqual(response["agent_workflow"]["corrections"], 2)
        self.assertEqual(response["model_run"]["rounds"], 6)
        self.assertFalse(response["trace"][-2]["ok"])
        self.assertTrue(client.requests[-1][-1]["content"][0]["is_error"])
        self.assertEqual(response["agent_workflow"]["public_precheck"]["status"], "passed")

    def test_precheck_cannot_accept_partial_or_wrong_shape_results(self):
        for index, result in enumerate([
                {"columns": self.case.contract["output"], "rows": [], "truncated": True},
                {"columns": ["wrong_alias"], "rows": [[1]], "truncated": False}]):
            self.workspace = export_workspace(self.case, self.root / ("incomplete-%d" % index))
            self.tools = EvidenceTools(self.workspace)
            def decision(messages):
                return completion([call("finish", {"status": "no_change", "explanation": "Claim", "evidence_ids": [self.tools.trace[0]["evidence_id"]]})])
            with self.subTest(result=result), patch.object(self.tools, "query", return_value=result), \
                    self.assertRaisesRegex(InvestigationFailed, "correction budget"):
                self.run_graph([completion([call("contract", {})]), decision, decision, decision])

    def test_precheck_receipt_survives_crash_without_requery_or_model_request(self):
        original = Receipts.complete
        def crash(receipts, identity, payload):
            original(receipts, identity, payload)
            if identity.startswith("precheck-"):
                raise RuntimeError("lost after public SQL execution")
        with patch.object(Receipts, "complete", crash), self.assertRaises(RuntimeError):
            self.run_graph([completion([call("contract", {})]), finish])
        self.tools = EvidenceTools(self.workspace)
        with patch.object(self.tools, "call", side_effect=AssertionError("Must reuse precheck receipt")):
            response, client = self.run_graph([], recover=True)
        self.assertEqual(client.requests, [])
        self.assertEqual(len(response["trace"]), 2)
        self.assertTrue(grade(self.case, response, self.root / "receipt-grade")["passed"])

    def test_public_execution_is_not_independent_semantic_verification(self):
        self.case = incidents()[0]
        self.workspace = export_workspace(self.case, self.root / "wrong-semantics")
        self.tools = EvidenceTools(self.workspace)
        def plan(messages):
            return completion([call("record_plan", plan_for(self.case.current_sql, self.tools.trace[0]["evidence_id"]))])
        def bad_candidate(messages):
            return completion([call("finish", {"status": "candidate", "explanation": "Unsupported semantic claim.",
                "candidate_sql": self.case.current_sql, "evidence_ids": [r["evidence_id"] for r in self.tools.trace]})])
        response, _ = self.run_graph([completion([call("contract", {})]), plan,
            completion([call("query", {"sql": self.case.current_sql})]), bad_candidate])
        self.assertEqual(response["agent_workflow"]["public_precheck"]["status"], "passed")
        self.assertTrue(response["agent_workflow"]["public_precheck"]["reused_evidence"])
        self.assertFalse(grade(self.case, response, self.root / "wrong-grade")["passed"])

    def test_strict_plan_validation_can_recover_from_extra_fields(self):
        def plan(messages):
            return completion([call("record_plan", plan_for(self.case.current_sql, self.tools.trace[0]["evidence_id"]))])
        def bad_plan(messages):
            value = plan_for(self.case.current_sql, self.tools.trace[0]["evidence_id"])
            value["approve"] = True
            return completion([call("record_plan", value)])
        def decision(messages):
            return completion([call("finish", {"status": "no_change", "explanation": "Contract satisfied.",
                "evidence_ids": [self.tools.trace[0]["evidence_id"]]})])
        response, _ = self.run_graph([completion([call("contract", {})]), bad_plan, plan, decision])
        self.assertEqual(len(response["agent_workflow"]["plans"]), 1)
        self.assertEqual(response["agent_workflow"]["corrections"], 1)

    def test_plan_citations_and_hypothesis_ids_cannot_be_fabricated_or_duplicated(self):
        from agent_policy import validate_plan
        observed = self.tools.call("contract")
        valid = plan_for(self.case.current_sql, observed["evidence_id"])
        fabricated = dict(valid, evidence_ids=["invented"])
        duplicate = dict(valid, hypotheses=valid["hypotheses"] * 2)
        for value in (fabricated, duplicate):
            with self.assertRaises(ValueError):
                validate_plan(value, self.tools.trace)

    def test_plan_and_activity_survive_human_continuation(self):
        self.case = incidents()[2]
        self.workspace = export_workspace(self.case, self.root / "planned-clarification")
        self.tools = EvidenceTools(self.workspace)
        def plan(messages):
            return completion([call("record_plan", plan_for("SELECT event_id FROM events WHERE utc_offset_minutes IS NULL",
                self.tools.trace[0]["evidence_id"]))])
        def clarify(messages):
            return completion([call("finish", {"status": "needs_information", "explanation": "Offsets are missing.",
                "evidence_ids": [self.tools.trace[0]["evidence_id"]], "affected_ids": ["t1", "t2"], "required_fields": ["utc_offset_minutes"]})])
        first, _ = self.run_graph([completion([call("contract", {})]), plan, clarify])
        self.tools = EvidenceTools(self.workspace)
        continued, _ = self.run_graph([clarify], guidance="Keep requesting authoritative offsets.")
        self.assertEqual(continued["agent_workflow"]["plans"], first["agent_workflow"]["plans"])
        self.assertEqual(continued["model_run"]["rounds"], 4)
        self.assertIn("clarification", [entry["stage"] for entry in continued["agent_workflow"]["activity"]])

    def test_correction_budget_survives_result_checkpoint_crash(self):
        bad = completion([call("finish", {"status": "no_change", "explanation": "Claim", "evidence_ids": ["invented"]})])
        original = Receipts.complete
        def crash(receipts, identity, payload):
            original(receipts, identity, payload)
            if identity == "model-4":
                raise RuntimeError("lost before final decision check")
        with patch.object(Receipts, "complete", crash), self.assertRaises(RuntimeError):
            self.run_graph([completion([call("contract", {})]), bad, bad, bad])
        client = ScriptedClient([])
        with self.assertRaisesRegex(InvestigationFailed, "correction budget"):
            asyncio.run(investigate(EvidenceTools(self.workspace), client, recover=True))
        self.assertEqual(client.requests, [])
        metadata = json.loads((self.workspace / "model-run.json").read_text())
        self.assertEqual(metadata["decision_corrections"], 2)
        self.assertEqual(metadata["usage"]["input_tokens"], 80)


class GraphContinuationQueueTests(unittest.TestCase):
    def test_duplicate_stale_and_concurrent_continuations(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JobStore(directory)
            case = incidents()[2]
            version = case_version(case)
            parent_id, _ = store.enqueue({"kind": "investigation", "case_id": case.case_id,
                "investigator": "langgraph", "input_version": version}, "graph-parent")
            claimed = store.claim()
            store.finish(claimed, result={"case_id": case.case_id, "input_version": version,
                "response": {"decision": {"status": "needs_information"}, "graph_run": {"status": "paused"}},
                "grading": {"passed": True}})
            parent = store.get(parent_id)
            self.assertEqual(parent["status"], "paused")
            with self.assertRaises(Conflict):
                store.review(parent_id, parent["result_version"], "approved", "test", "")
            request = {"kind": "graph_resume", "investigator": "langgraph", "case_id": case.case_id,
                "input_version": version, "parent_id": parent_id, "parent_version": parent["result_version"],
                "guidance": "Continue carefully."}
            with self.assertRaises(Conflict):
                store.enqueue(dict(request, parent_version="stale"), "stale-resume")
            def enqueue(index):
                try:
                    return JobStore(directory).enqueue(request, "resume-%d" % index)
                except Conflict:
                    return None
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(enqueue, range(2)))
            self.assertEqual(sum(value is not None for value in outcomes), 1)
            child = next(value for value in outcomes if value)
            selected_key = "resume-%d" % outcomes.index(child)
            self.assertEqual(store.enqueue(request, selected_key), (child[0], False))
            self.assertEqual(store.get(parent_id)["result_version"], parent["result_version"])


if __name__ == "__main__":
    unittest.main()
