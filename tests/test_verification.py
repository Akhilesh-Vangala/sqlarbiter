import unittest
from dataclasses import replace
from pathlib import Path

from vdir.environment import snapshots
from vdir.reference import expected_revenue
from vdir.runner import QueryRejected, run_query
from vdir.verifier import verify, verify_suite

SQL_DIR = Path(__file__).resolve().parents[1] / "data" / "development" / "sql"


class RevenueVerificationTests(unittest.TestCase):
    def test_hand_calculated_reference(self):
        self.assertEqual(expected_revenue(snapshots()[0]),
                         {("2026-09-01", "home"): 1200, ("2026-09-01", "books"): 800})
        self.assertEqual(expected_revenue(snapshots()[1]),
                         {("2026-09-02", "home"): 2400, ("2026-09-02", "books"): 500})
        self.assertEqual(expected_revenue(snapshots()[2]),
                         {("2026-09-03", "electronics"): 700,
                          ("2026-09-04", "electronics"): 900,
                          ("2026-09-04", "books"): 300})

    def test_fault_and_semantic_repair_across_snapshots(self):
        broken = verify_suite(snapshots(), (SQL_DIR / "current.sql").read_text())
        fixed = verify_suite(snapshots(), (SQL_DIR / "latest-version.sql").read_text())
        self.assertTrue(all(not result.passed for result in broken))
        self.assertTrue(all(result.passed for result in fixed))

    def test_superficial_fix_passes_incident_but_fails_regressions(self):
        checks = verify_suite(snapshots(), (SQL_DIR / "distinct-amount.sql").read_text())
        self.assertTrue(checks[0].passed)
        self.assertFalse(checks[1].passed)
        self.assertFalse(checks[2].passed)

    def test_alternative_sql_is_accepted(self):
        sql = """SELECT o.business_date, p.category, SUM(i.amount_cents) AS revenue_cents
        FROM orders o JOIN order_items i ON i.order_id=o.order_id
        JOIN product_versions p ON p.product_id=i.product_id
        WHERE o.status='completed' AND p.version=(
            SELECT MAX(q.version) FROM product_versions q WHERE q.product_id=p.product_id)
        GROUP BY o.business_date, p.category"""
        self.assertTrue(all(result.passed for result in verify_suite(snapshots(), sql)))

    def test_duplicate_output_keys_and_wrong_types_are_rejected(self):
        sql = (SQL_DIR / "latest-version.sql").read_text().rstrip().rstrip(";")
        duplicated = verify(snapshots()[0], "WITH result AS (" + sql +
                            ") SELECT * FROM result UNION ALL SELECT * FROM result")
        self.assertFalse(duplicated.passed)
        self.assertEqual(duplicated.problems, ("Duplicate output key",))
        self.assertFalse(verify(snapshots()[0],
                         "SELECT '2026-09-01' AS business_date, 'home' AS category, "
                         "'1200' AS revenue_cents").passed)
        self.assertEqual(verify(snapshots()[0], "SELECT 1200 AS amount").problems,
                         ("Output schema does not match contract",))

    def test_invalid_reference_is_not_scored_as_agent_failure(self):
        case = snapshots()[0]
        ambiguous = replace(case, products=case.products + (case.products[0],))
        with self.assertRaises(ValueError):
            verify(ambiguous, "SELECT 1")
        with self.assertRaises(ValueError):
            verify_suite([], "SELECT 1")

    def test_write_and_filesystem_operations_are_denied(self):
        for sql in ("DELETE FROM orders", "ATTACH DATABASE '/tmp/vdir-denied.db' AS other",
                    "SELECT load_extension('anything')", "PRAGMA database_list",
                    "SELECT * FROM sqlite_master", "SELECT 1; SELECT 2"):
            with self.subTest(sql=sql), self.assertRaises(QueryRejected):
                run_query(snapshots()[0], sql)

    def test_row_and_computation_budgets(self):
        with self.assertRaises(QueryRejected):
            run_query(snapshots()[0], "SELECT * FROM orders", max_rows=1)
        with self.assertRaises(QueryRejected):
            run_query(snapshots()[0], """WITH RECURSIVE loop(n) AS
            (SELECT 1 UNION ALL SELECT n+1 FROM loop) SELECT SUM(n) FROM loop""",
                      max_progress_calls=1)


if __name__ == "__main__":
    unittest.main()
