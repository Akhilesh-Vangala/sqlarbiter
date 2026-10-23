"""Strict public findings, ledger persistence and independently replayable diagnostics."""
import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

from vdir.domain.cases import incidents
from vdir.domain.cases import Incident
from vdir.domain.cases import Source
from vdir.evaluation.evaluation import export_workspace
from vdir.evaluation.evaluation import grade
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "agent/investigator"))
from tools import EvidenceTools
from agent_policy import validate_findings
from agent_policy import working_memory
from graph import investigate
from fixtures.model_fixtures import ScriptedClient
from fixtures.model_fixtures import completion
from fixtures.model_fixtures import call


class AgentMemoryTests(unittest.TestCase):
    def test_join_profile_null_duplicates_empty_and_static_sql_safety_in_both_engines(self):
        source = Source("join-profile", {"left_rows": (("key TEXT",), (("a",), ("a",), ("b",), (None,))),
            "right_rows": (("key TEXT",), (("a",), ("a",), ("c",), (None,))), "empty": (("key TEXT",), ())})
        case = Incident("join-profile", {}, (source,), "SELECT key FROM left_rows", {}, ())
        for engine in ("sqlite", "duckdb"):
            with self.subTest(engine=engine), tempfile.TemporaryDirectory() as directory:
                tools = EvidenceTools(export_workspace(case, Path(directory) / "evidence", engine))
                args = {"left_table": "left_rows", "left_key": "key", "right_table": "right_rows", "right_key": "key"}
                reply = tools.call("check_join", args)
                self.assertTrue(reply["ok"], reply)
                stats = reply["result"]["statistics"]
                self.assertEqual((stats["inner_join_rows"], stats["left_duplicate_keys"], stats["right_duplicate_keys"], stats["unmatched_left_nonnull_rows"], stats["left_null_key_rows"]), (4, 1, 1, 1, 1))
                empty = tools.call("check_join", dict(args, right_table="empty"))["result"]["statistics"]
                self.assertEqual((empty["inner_join_rows"], empty["unmatched_left_nonnull_rows"]), (0, 3))
                self.assertFalse(tools.call("check_join", dict(args, right_table="sqlite_master"))["ok"])
                self.assertFalse(tools.call("check_join", dict(args, left_key="key; DROP TABLE left_rows"))["ok"])
                inspected = tools.call("inspect_sql", {"sql": "SELECT l.key, SUM(1) AS n FROM left_rows l JOIN right_rows r ON l.key=r.key GROUP BY l.key"})
                self.assertTrue(inspected["ok"])
                self.assertEqual(inspected["result"]["tables"], ["left_rows", "right_rows"])
                self.assertEqual(inspected["result"]["aggregates"], ["SUM"])
                self.assertEqual(len(inspected["result"]["joins"]), 1)
                self.assertFalse(tools.call("inspect_sql", {"sql": "DELETE FROM left_rows"})["ok"])

    def test_diagnostics_replay_and_semantic_grade_remain_independent(self):
        case = incidents()[0]
        for engine in ("sqlite", "duckdb"):
            with tempfile.TemporaryDirectory() as directory:
                tools = EvidenceTools(export_workspace(case, Path(directory) / "evidence", engine))
                tools.call("inspect_sql", {"sql": case.current_sql})
                tools.call("check_join", {"left_table": "order_items", "left_key": "product_id", "right_table": "product_versions", "right_key": "product_id"})
                response = {"decision": {"status": "candidate", "explanation": "Profile only does not repair semantics.", "candidate_sql": case.current_sql,
                    "evidence_ids": [r["evidence_id"] for r in tools.trace]}, "trace": tools.trace}
                result = grade(case, response, Path(directory) / "grading", engine)
                self.assertFalse(result["passed"])
                self.assertNotEqual(result["reason"], "Evidence trace does not match source replay")

    def test_rejected_oversize_result_is_not_retained_in_error_record(self):
        with tempfile.TemporaryDirectory() as directory:
            tools = EvidenceTools(export_workspace(incidents()[0], Path(directory) / "evidence"))
            tools.manifest["changes"] = "x" * 50000
            record = tools.call("changes")
            self.assertFalse(record["ok"])
            self.assertNotIn("result", record)
            self.assertLess(len(json.dumps(record)), 500)

    def test_strict_findings_reject_stale_unknown_unexecuted_or_incomplete_evidence(self):
        plans = [{"revision": 1, "hypotheses": [{"id": "h1", "test_sql": "SELECT 1"}]}]
        trace = [{"evidence_id": "ev-test", "method": "query", "ok": True, "params": {"sql": "SELECT 1"}, "result": {"truncated": False}}]
        value = {"plan_revision": 1, "findings": [{"hypothesis_id": "h1", "assessment": "inconclusive", "summary": "One row alone does not establish metric correctness.", "evidence_ids": ["ev-test"]}]}
        self.assertEqual(validate_findings(value, plans, trace), value)
        for invalid in (dict(value, plan_revision="1"), dict(value, plan_revision=2), dict(value, extra="hidden"),
                        dict(value, findings=[dict(value["findings"][0], evidence_ids=["invented"])])):
            with self.assertRaises(ValueError):
                validate_findings(invalid, plans, trace)
        trace[0]["result"]["truncated"] = True
        with self.assertRaises(ValueError):
            validate_findings(value, plans, trace)

    def test_graph_findings_are_checkpointed_bounded_and_in_next_model_context(self):
        case = incidents()[4]
        with tempfile.TemporaryDirectory() as directory:
            tools = EvidenceTools(export_workspace(case, Path(directory) / "evidence"))
            def plan(messages):
                return completion([call("record_plan", {"objective": "Check current SQL execution.", "hypotheses": [{"id": "h1", "claim": "The current query returns complete data.", "test_sql": case.current_sql, "expected_signal": "Complete rows."}], "evidence_ids": [tools.trace[0]["evidence_id"]]})])
            def findings(messages):
                return completion([call("record_findings", {"plan_revision": 1, "findings": [{"hypothesis_id": "h1", "assessment": "supports", "summary": "Current SQL executed completely; semantic checks remain separate.", "evidence_ids": [tools.trace[0]["evidence_id"]]}]})])
            def finish(messages):
                self.assertIn("latest_findings", client.system)
                self.assertIn("Current SQL executed completely", client.system)
                return completion([call("finish", {"status": "no_change", "explanation": "Check current SQL independently.", "evidence_ids": [tools.trace[0]["evidence_id"]]})])
            client = ScriptedClient([completion([call("query", {"sql": case.current_sql})]), plan, findings, finish])
            response = asyncio.run(investigate(tools, client))
            self.assertEqual(response["graph_run"]["version"], "vdir-graph-3")
            self.assertEqual(len(response["agent_workflow"]["findings"]), 1)
            self.assertTrue(grade(case, response, Path(directory) / "grading")["passed"])
            self.assertIn("findings", [event["stage"] for event in response["agent_workflow"]["activity"]])
            self.assertLess(len(json.dumps(response["agent_workflow"]["working_memory"])), 16000)

    def test_working_memory_keeps_bounded_index_and_handles_metadata_arrays(self):
        trace = [{"evidence_id": "ev-" + str(i), "method": "changes", "ok": True, "result": []} for i in range(24)]
        memory = working_memory([], [], trace)
        self.assertEqual(len(memory["evidence_index"]), 12)
        self.assertEqual(memory["evidence_index"][0]["evidence_id"], "ev-12")

    def test_findings_survive_fresh_controller_continuation_without_evidence_replay(self):
        case = incidents()[2]
        sql = "SELECT event_id FROM events WHERE utc_offset_minutes IS NULL"
        with tempfile.TemporaryDirectory() as directory:
            workspace = export_workspace(case, Path(directory) / "evidence")
            tools = EvidenceTools(workspace)
            def plan(messages):
                return completion([call("record_plan", {"objective": "Identify missing authoritative offsets.", "hypotheses": [{"id": "h1", "claim": "Offsets are missing.", "test_sql": sql, "expected_signal": "Affected event IDs."}], "evidence_ids": [tools.trace[0]["evidence_id"]]})])
            def findings(messages):
                return completion([call("record_findings", {"plan_revision": 1, "findings": [{"hypothesis_id": "h1", "assessment": "supports", "summary": "The complete query identifies events missing offsets.", "evidence_ids": [tools.trace[0]["evidence_id"]]}]})])
            def clarify(messages):
                return completion([call("finish", {"status": "needs_information", "explanation": "Authoritative offsets are required.", "affected_ids": ["t1", "t2"], "required_fields": ["utc_offset_minutes"], "evidence_ids": [tools.trace[0]["evidence_id"]]})])
            first = asyncio.run(investigate(tools, ScriptedClient([completion([call("query", {"sql": sql})]), plan, findings, clarify])))
            restored = EvidenceTools(workspace)
            client = ScriptedClient([clarify])
            continued = asyncio.run(investigate(restored, client, guidance="Continue requesting source offsets; do not infer them."))
            self.assertEqual(continued["agent_workflow"]["findings"], first["agent_workflow"]["findings"])
            self.assertEqual(continued["trace"], first["trace"])
            self.assertEqual(continued["model_run"]["rounds"], 5)
            self.assertIn("events missing offsets", client.system)
            self.assertTrue(grade(case, continued, Path(directory) / "grading")["passed"])
