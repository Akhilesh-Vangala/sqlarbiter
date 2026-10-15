"""Original evaluator-owned synthetic cases. Never copied to agent workspaces."""
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

from vdir.domain.cases import Incident
from vdir.domain.cases import Source
from vdir.domain.cases import incidents


@dataclass(frozen=True)
class BenchmarkCase:
    incident: Incident
    family: str
    split: str
    template_group: str


def benchmark_cases():
    controls = incidents()
    result = [BenchmarkCase(case, "development_control", "calibration", "control")
              for case in controls]
    for family in ("join_fanout", "outer_join_nulls", "status_filter", "utc_boundary"):
        for variant in range(8):
            # Splits are explicit SQL-shape groups, not random row partitions.
            split = "calibration" if variant < 4 else "evaluation"
            healthy = variant in (3, 7)
            sources = []
            for snapshot in range(2):
                seed = 11 + variant * 37 + snapshot * 113
                day = (datetime(2026, 9, 1) + timedelta(days=variant + snapshot)).date().isoformat()
                if family == "join_fanout":
                    tables = {
                        "purchases": (("item_id TEXT PRIMARY KEY", "business_date TEXT NOT NULL",
                                       "status TEXT NOT NULL", "amount_cents INTEGER NOT NULL"), (
                            ("i1", day, "completed", seed), ("i2", day, "completed", seed),
                            ("i3", day, "cancelled", seed * 3), ("i4", day, "completed", seed * 2))),
                        "item_tags": (("item_id TEXT NOT NULL", "tag TEXT NOT NULL"), (
                            ("i1", "priority"), ("i1", "new"), ("i2", "new"),
                            ("i3", "priority")) + (("i2", "priority"),) * snapshot),
                    }
                    contract = {"metric": "tagged_item_revenue", "version": "tagged-v1",
                        "rules": {"eligibility": "completed purchases with at least one tag",
                                  "identity": "item_id; count a purchase once regardless of tag count",
                                  "unit": "integer cents", "date": "source business_date"},
                        "output": ["business_date", "revenue_cents"]}
                    correct = ("SELECT p.business_date, SUM(p.amount_cents) AS revenue_cents FROM purchases p "
                               "WHERE p.status='completed' AND EXISTS (SELECT 1 FROM item_tags t "
                               "WHERE t.item_id=p.item_id) GROUP BY p.business_date")
                    broken = ("SELECT p.business_date, SUM(p.amount_cents) AS revenue_cents FROM purchases p "
                              "JOIN item_tags t ON p.item_id=t.item_id WHERE p.status='completed' "
                              "GROUP BY p.business_date") if variant < 4 else (
                              "WITH tagged AS (SELECT p.* FROM purchases p LEFT JOIN item_tags t "
                              "ON p.item_id=t.item_id WHERE t.tag IS NOT NULL) SELECT business_date, "
                              "SUM(amount_cents) AS revenue_cents FROM tagged WHERE status='completed' "
                              "GROUP BY business_date")
                elif family == "outer_join_nulls":
                    tables = {
                        "customers": (("customer_id TEXT PRIMARY KEY",), (("c1",), ("c2",), ("c3",))),
                        "customer_orders": (("order_id TEXT PRIMARY KEY", "customer_id TEXT NOT NULL",
                                             "status TEXT NOT NULL", "amount_cents INTEGER NOT NULL"), (
                            ("o1", "c1", "completed", seed), ("o2", "c1", "completed", seed),
                            ("o3", "c2", "cancelled", seed * 7)) + ((("o4", "c2", "completed", seed * 3),) if snapshot else ())),
                    }
                    contract = {"metric": "customer_completed_revenue", "version": "customer-v1",
                        "rules": {"population": "every customer including those without completed orders",
                                  "eligibility": "completed orders only; missing revenue is integer zero",
                                  "unit": "integer cents"}, "output": ["customer_id", "revenue_cents"]}
                    correct = ("SELECT c.customer_id, COALESCE(SUM(o.amount_cents),0) AS revenue_cents "
                               "FROM customers c LEFT JOIN customer_orders o "
                               "ON c.customer_id=o.customer_id AND o.status='completed' GROUP BY c.customer_id")
                    broken = ("SELECT c.customer_id, SUM(o.amount_cents) AS revenue_cents FROM customers c "
                              "LEFT JOIN customer_orders o ON c.customer_id=o.customer_id "
                              "WHERE o.status='completed' GROUP BY c.customer_id") if variant < 4 else (
                              "WITH eligible AS (SELECT * FROM customer_orders WHERE status='completed') "
                              "SELECT c.customer_id, SUM(o.amount_cents) AS revenue_cents FROM customers c "
                              "LEFT JOIN eligible o ON c.customer_id=o.customer_id GROUP BY c.customer_id")
                elif family == "status_filter":
                    status = "settled" if variant < 4 else "completed"
                    tables = {"transactions": (("transaction_id TEXT PRIMARY KEY", "business_date TEXT NOT NULL",
                                                "status TEXT", "amount_cents INTEGER NOT NULL"), (
                        ("x1", day, status, seed), ("x2", day, status, seed),
                        ("x3", day, "pending", seed * 5), ("x4", day, None, seed * 2),
                        ("x5", day, "reversed", -seed),
                        ("x6", day, "settled" if status == "completed" else "completed", seed * 3)))}
                    contract = {"metric": "eligible_transaction_revenue", "version": "transaction-v1",
                        "rules": {"eligible_status": status, "unit": "integer cents",
                                  "null_status": "ineligible", "date": "source business_date"},
                        "output": ["business_date", "revenue_cents"]}
                    correct = ("SELECT business_date, SUM(amount_cents) AS revenue_cents FROM transactions "
                               "WHERE status='%s' GROUP BY business_date" % status)
                    broken = ("SELECT business_date, SUM(amount_cents) AS revenue_cents FROM transactions "
                              "GROUP BY business_date") if variant < 4 else (
                              "SELECT business_date, SUM(CASE WHEN status != 'pending' THEN amount_cents "
                              "ELSE 0 END) AS revenue_cents FROM transactions GROUP BY business_date")
                else:
                    contract = controls[3].contract
                    start = datetime(2024, 2, 29, 0, 0) if snapshot else datetime(2026, 12, 31, 23, 59)
                    rows = tuple(("t%d" % i, (start + timedelta(minutes=i * 31)).isoformat(), offset)
                                 for i, offset in enumerate((330, -480, 0, 345, -720, 840)))
                    tables = {"events": (("event_id TEXT PRIMARY KEY", "local_timestamp TEXT NOT NULL",
                                          "utc_offset_minutes INTEGER"), rows)}
                    # DuckDB is the benchmark's default dialect. SQLite equivalent
                    # is translated by the evaluator before exporting this case.
                    correct = ("SELECT CAST(CAST(local_timestamp AS TIMESTAMP) - utc_offset_minutes * "
                               "INTERVAL '1 minute' AS DATE)::VARCHAR AS business_date, "
                               "COUNT(*) AS event_count FROM events GROUP BY business_date")
                    broken = ("SELECT substr(local_timestamp,1,10) AS business_date, COUNT(*) AS event_count "
                              "FROM events GROUP BY business_date") if variant < 4 else (
                              "SELECT CAST(CAST(local_timestamp AS TIMESTAMP) + utc_offset_minutes * "
                              "INTERVAL '1 minute' AS DATE)::VARCHAR AS business_date, "
                              "COUNT(*) AS event_count FROM events GROUP BY business_date")
                # A distractor is visible but has no relation to the metric contract.
                tables["deployment_notes"] = (("release_id TEXT", "summary TEXT"),
                                              (("release-42", "Presentation configuration updated"),))
                sources.append(Source("source-%d" % snapshot, tables))
            case_id = "case-%03d" % (len(result) + 1)
            incident = Incident(case_id, contract, tuple(sources), correct if healthy else broken,
                                {"business_metric": [name for name in tables if name != "deployment_notes"]},
                                ({"version": "release-42", "component": "report", "summary": "Transformation revised"},))
            result.append(BenchmarkCase(incident, family, split,
                                        family + ("-shape-a" if variant < 4 else "-shape-b")))
    return tuple(result)
