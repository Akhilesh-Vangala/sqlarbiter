"""Actual dbt seed/run/test/build, enabled explicitly in its isolated CI job."""
import os
import tempfile
import unittest
from pathlib import Path

from sqlarbiter.workflows.dbt_workflow import run


@unittest.skipUnless(os.getenv("SQLARBITER_RUN_DBT_TESTS") == "1", "Run the separate real-dbt integration job")
class DbtIntegrationTests(unittest.TestCase):
    def test_actual_patch_repairs_all_downstream_models_and_false_fix_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = run(root / "verified")
            self.assertTrue(report["passed"])
            self.assertEqual(len(report["verification"]), 5)
            self.assertEqual(report["before"]["fct_daily_revenue"], [["2026-09-30", 2400], ["2026-10-01", 800]])
            incident = report["verification"][0]
            self.assertEqual(incident["models"]["fct_daily_revenue"]["actual"], [["2026-09-30", 1200], ["2026-10-01", 800]])
            self.assertEqual(report["affected_models"], ["fct_customer_revenue", "fct_daily_revenue", "mart_monthly_revenue"])
            self.assertTrue(all(item["passed"] for item in report["grading"]["checks"]))
            false_fix = "SELECT MIN(event_id) AS event_id, customer_id, occurred_at, status, amount_cents FROM stg_payment_deliveries GROUP BY customer_id, occurred_at, status, amount_cents"
            rejected = run(root / "false-fix", candidate=false_fix)
            self.assertFalse(rejected["passed"])
            checks = rejected["grading"]["checks"]
            self.assertTrue(checks[0]["passed"])
            self.assertFalse(next(item for item in checks if item["snapshot_id"] == "equal_value_distinct_events")["passed"])
            self.assertFalse((root / "false-fix/repair.patch").exists())
