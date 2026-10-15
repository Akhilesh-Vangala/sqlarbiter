import json
import tempfile
import unittest
from pathlib import Path

from vdir.dbt_workflow import independent_outputs, fixtures, patch_sql, review, digest


class DbtBoundaryTests(unittest.TestCase):
    def test_equal_value_events_and_late_deliveries_use_event_identity_and_occurrence_date(self):
        output = independent_outputs(fixtures()["equal_value_distinct_events"])
        self.assertEqual(output["fct_daily_revenue"], [["2026-09-30", 1000]])
        self.assertEqual(output["mart_monthly_revenue"], [["2026-09", 1000]])
        self.assertEqual(len(output["int_payment_events"]), 2)
        boundary = independent_outputs(fixtures()["late_month_boundary_and_zero"])
        self.assertEqual(boundary["fct_daily_revenue"], [["2026-09-30", 0], ["2026-10-01", 200]])
        rows = fixtures()["incident"]
        self.assertEqual(independent_outputs(rows), independent_outputs(list(reversed(rows))))
        self.assertTrue(all(value == [] for value in independent_outputs([]).values()))

    def test_conflicting_payload_requires_source_clarification(self):
        rows = fixtures()["incident"]
        changed = [*rows[0][:-1], 999]
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            independent_outputs([rows[0], tuple(changed)])

    def test_only_declared_plain_select_can_become_the_target_model(self):
        sql = patch_sql("SELECT DISTINCT event_id, customer_id, occurred_at, status, amount_cents FROM stg_payment_deliveries")
        self.assertIn("{{ ref('stg_payment_deliveries') }}", sql)
        for candidate in ("DELETE FROM stg_payment_deliveries", "SELECT * FROM read_csv('/tmp/secret')", "SELECT * FROM {{ ref('other') }}", "SELECT * FROM other", "SELECT 1", "SELECT * FROM stg_payment_deliveries; DROP TABLE x"):
            with self.assertRaises(ValueError):
                patch_sql(candidate)

    def test_exact_version_review_is_immutable_and_tampered_patch_cannot_be_approved(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "repair.patch").write_text("patch")
            report = {"passed": True, "patch_sha256": hashlib.sha256(b"patch").hexdigest()}
            version = digest(report)
            (root / "report.json").write_text(json.dumps(dict(report, version=version)))
            accepted = review(root / "report.json", version, "approved", "Checked")
            self.assertEqual(review(root / "report.json", version, "approved", "Checked"), accepted)
            with self.assertRaises(ValueError):
                review(root / "report.json", version, "rejected")
            (root / "repair.patch").write_text("changed")
            with self.assertRaisesRegex(ValueError, "Patch artifact"):
                review(root / "report.json", version, "approved", "Checked")
