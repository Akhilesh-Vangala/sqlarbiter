import copy
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from vdir.cases import incidents
from vdir.evaluation import (
    evaluate_all, export_workspace, grade, reference_outcome, run_worker,
)


class IncidentEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cases = incidents()

    def tearDown(self):
        self.temp.cleanup()

    def response(self, case):
        return run_worker(export_workspace(case, self.root / "evidence"))

    def test_hand_calculated_event_and_utc_references(self):
        event = self.cases[1]
        self.assertEqual(reference_outcome(event, event.sources[0])["rows"],
                         {("2026-09-01",): 2000})
        self.assertEqual(reference_outcome(event, event.sources[1])["rows"],
                         {("2026-09-02",): 2400})
        time = self.cases[3]
        self.assertEqual(reference_outcome(time, time.sources[0])["rows"],
                         {("2026-09-03",): 1, ("2026-09-04",): 2})

    def test_all_six_workflows_and_semantic_outcomes(self):
        report = evaluate_all(self.root / "run")
        self.assertTrue(report["passed"])
        self.assertEqual([case["decision"]["status"] for case in report["cases"]],
                         ["candidate", "candidate", "needs_information", "candidate",
                          "no_change", "needs_information"])
        self.assertTrue((self.root / "run" / "report.json").exists())

    def test_event_amount_deduplication_fails_unseen_equal_events(self):
        case = self.cases[1]
        response = self.response(case)
        response["decision"]["candidate_sql"] = (
            "SELECT substr(occurred_at,1,10) AS business_date, "
            "SUM(DISTINCT amount_cents) AS revenue_cents FROM event_deliveries GROUP BY business_date")
        result = grade(case, response, self.root / "grading")
        self.assertFalse(result["passed"])
        self.assertTrue(result["checks"][0]["passed"])
        self.assertFalse(result["checks"][1]["passed"])

    def test_timezone_guess_cannot_replace_missing_source_information(self):
        case = self.cases[2]
        response = self.response(case)
        response["decision"].update(status="candidate", candidate_sql=case.current_sql)
        self.assertFalse(grade(case, response, self.root / "grading")["passed"])

    def test_clarification_must_scope_affected_records(self):
        case = self.cases[2]
        response = self.response(case)
        self.assertEqual(response["decision"]["affected_ids"], ["t1", "t2"])
        response["decision"]["affected_ids"].append("t3")
        self.assertFalse(grade(case, response, self.root / "grading")["passed"])

    def test_abstaining_on_a_repairable_case_fails(self):
        case = self.cases[0]
        response = self.response(case)
        response["decision"].update(status="needs_information", affected_ids=[])
        self.assertFalse(grade(case, response, self.root / "grading")["passed"])

    def test_no_change_on_broken_input_fails(self):
        case = self.cases[0]
        response = self.response(case)
        response["decision"].update(status="no_change")
        self.assertFalse(grade(case, response, self.root / "grading")["passed"])

    def test_conflicting_payload_cannot_be_silently_resolved_with_max(self):
        case = self.cases[5]
        response = self.response(case)
        self.assertEqual(response["decision"]["affected_ids"], ["e5"])
        response["decision"].update(status="candidate", candidate_sql=case.current_sql)
        self.assertFalse(grade(case, response, self.root / "grading")["passed"])

    def test_export_contains_only_public_current_evidence(self):
        workspace = export_workspace(self.cases[0], self.root / "evidence")
        self.assertEqual({path.name for path in workspace.iterdir()},
                         {"incident.json", "schema.json", "source.sqlite", "runtime"})
        self.assertEqual({path.name for path in (workspace / "runtime").iterdir()},
                             {"tools.py", "baseline.py", "model.py", "graph.py", "agent_policy.py", "worker.py", "engines.py", "telemetry.py", "spending.py"})
        text = (workspace / "incident.json").read_text()
        for hidden in ("expected_revenue", "reference_outcome", "regression-equal-amounts",
                       "regression-category-change", "candidate_sql", "fault_label"):
            self.assertNotIn(hidden, text)
        conn = sqlite3.connect(str(workspace / "source.sqlite"))
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 3)
            self.assertEqual({row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")},
                {"orders", "order_items", "product_versions"})
        finally:
            conn.close()

    def test_rpc_has_no_filesystem_or_import_tools(self):
        workspace = export_workspace(self.cases[0], self.root / "evidence")
        requests = [{"method": "read_file", "params": {"path": "../../reference.py"}},
                    {"method": "import", "params": {"module": "vdir.reference"}},
                    {"method": [], "params": {}},
                    {"method": "query", "params": {"sql": "SELECT * FROM sqlite_master"}},
                    {"method": "query", "params": {"sql": "ATTACH DATABASE '/tmp/hidden' AS hidden"}},
                    {"method": "query", "params": {"sql": "SELECT printf('%100000000s', 'x')"}},
                    {"method": "query", "params": {"sql": "DELETE FROM orders"}}]
        replies = run_worker(workspace, mode="rpc", requests="".join(
            json.dumps(request) + "\n" for request in requests))
        self.assertTrue(all(not reply["ok"] for reply in replies))

    def test_rpc_budgets_and_malformed_requests(self):
        workspace = export_workspace(self.cases[0], self.root / "evidence")
        requests = [{"method": "query", "params": {"sql": "WITH RECURSIVE t(n) AS "
                     "(SELECT 1 UNION ALL SELECT n+1 FROM t) SELECT SUM(n) FROM t"}}]
        requests.extend({"method": "describe"} for _ in range(25))
        replies = run_worker(workspace, mode="rpc", requests="[]\n" + "".join(
            json.dumps(request) + "\n" for request in requests))
        self.assertFalse(replies[0]["ok"])
        self.assertFalse(replies[1]["ok"])
        self.assertIn("budget", replies[-1]["error"])

    def test_fabricated_evidence_ids_and_results_fail(self):
        case = self.cases[0]
        response = self.response(case)
        forged = copy.deepcopy(response)
        forged["decision"]["evidence_ids"] = ["ev-made-up"]
        self.assertFalse(grade(case, forged, self.root / "bad-ids")["passed"])
        response["trace"][-1]["result"]["rows"][0][-1] += 1
        result = grade(case, response, self.root / "bad-results")
        self.assertFalse(result["passed"])
        self.assertIn("source replay", result["reason"])

    def test_baseline_uses_contract_not_case_id(self):
        renamed = replace(self.cases[1], case_id="unrelated-name")
        response = self.response(renamed)
        self.assertEqual(response["decision"]["status"], "candidate")
        self.assertTrue(grade(renamed, response, self.root / "grading")["passed"])

    def test_bad_reference_source_fails_evaluator(self):
        case = self.cases[3]
        source = case.sources[0]
        tables = copy.deepcopy(source.tables)
        definitions, rows = tables["events"]
        tables["events"] = (definitions, rows + (("bad", "2026-09-04T12:00:00", 9999),))
        with self.assertRaises(ValueError):
            reference_outcome(case, replace(source, tables=tables))

    def test_malformed_decision_is_rejected(self):
        for response in ([], {}, {"decision": []}):
            with self.subTest(response=response):
                self.assertFalse(grade(self.cases[0], response, self.root / "grading")["passed"])

    def test_no_change_must_not_carry_a_patch(self):
        case = self.cases[4]
        response = self.response(case)
        response["decision"]["candidate_sql"] = case.current_sql
        self.assertFalse(grade(case, response, self.root / "grading")["passed"])


if __name__ == "__main__":
    unittest.main()
