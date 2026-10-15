"""Evaluator-owned development cases; never copied into investigator bundles."""
from dataclasses import dataclass
from typing import Tuple

from .environment import snapshots


@dataclass(frozen=True)
class Source:
    snapshot_id: str
    # table -> (SQL column definitions, records)
    tables: dict


@dataclass(frozen=True)
class Incident:
    case_id: str
    contract: dict
    sources: Tuple[Source, ...]
    current_sql: str
    lineage: dict
    changes: tuple


JOIN_SQL = """SELECT o.business_date, p.category, SUM(i.amount_cents) AS revenue_cents
FROM orders o JOIN order_items i ON i.order_id=o.order_id
JOIN product_versions p ON p.product_id=i.product_id
WHERE o.status='completed' GROUP BY o.business_date, p.category"""

LATEST_SQL = """WITH latest AS (
SELECT product_id, MAX(version) AS version FROM product_versions GROUP BY product_id)
SELECT o.business_date, p.category, SUM(i.amount_cents) AS revenue_cents
FROM orders o JOIN order_items i ON i.order_id=o.order_id
JOIN latest l ON l.product_id=i.product_id
JOIN product_versions p ON p.product_id=l.product_id AND p.version=l.version
WHERE o.status='completed' GROUP BY o.business_date, p.category"""

EVENT_SQL = """SELECT substr(occurred_at,1,10) AS business_date,
SUM(amount_cents) AS revenue_cents FROM event_deliveries GROUP BY business_date"""

TIME_SQL = """SELECT substr(local_timestamp,1,10) AS business_date,
COUNT(*) AS event_count FROM events GROUP BY business_date"""


def _retail_source(snapshot):
    return Source(snapshot.snapshot_id, {
        "orders": (("order_id TEXT PRIMARY KEY", "business_date TEXT NOT NULL",
                    "status TEXT NOT NULL"), snapshot.orders),
        "order_items": (("item_id TEXT PRIMARY KEY", "order_id TEXT NOT NULL",
                         "product_id TEXT NOT NULL", "amount_cents INTEGER NOT NULL"), snapshot.items),
        "product_versions": (("product_id TEXT NOT NULL", "version INTEGER NOT NULL",
                              "category TEXT NOT NULL"), snapshot.products),
    })


def _event_source(name, rows):
    return Source(name, {"event_deliveries": (
        ("delivery_id TEXT PRIMARY KEY", "event_id TEXT NOT NULL", "customer_id TEXT NOT NULL",
         "occurred_at TEXT NOT NULL", "amount_cents INTEGER NOT NULL"), rows)})


def _time_source(name, rows):
    return Source(name, {"events": (
        ("event_id TEXT PRIMARY KEY", "local_timestamp TEXT NOT NULL",
         "utc_offset_minutes INTEGER"), rows)})


def incidents():
    retail_contract = {
        "version": "retail-v1", "metric": "completed_item_revenue",
        "rules": {"eligible_status": "completed", "category": "highest product version in snapshot",
                  "date": "source business_date", "unit": "integer cents"},
        "output": ["business_date", "category", "revenue_cents"],
        "identity": {"orders": ["order_id"], "order_items": ["item_id"],
                     "product_versions": ["product_id", "version"]},
    }
    event_contract = {
        "version": "events-v1", "metric": "unique_event_revenue",
        "rules": {"identity": "event_id, not amount/customer/time",
                  "delivery": "one immutable payload per event_id; deliveries can repeat",
                  "date": "UTC occurred_at date", "unit": "integer cents",
                  "conflict": "request authoritative payload if same event_id disagrees"},
        "output": ["business_date", "revenue_cents"],
        "identity": {"event_deliveries": ["delivery_id"]},
    }
    time_contract = {
        "version": "time-v1", "metric": "utc_daily_event_count",
        "rules": {"date": "UTC date computed from local_timestamp and explicit utc_offset_minutes",
                  "missing_offset": "do not infer; request source offsets for affected event_ids"},
        "output": ["business_date", "event_count"], "identity": {"events": ["event_id"]},
    }
    retail_lineage = {"daily_revenue": ["enriched_items"],
                      "enriched_items": ["orders", "order_items", "product_versions"]}
    changes = ({"version": "r41", "component": "product_versions", "summary": "Catalog refresh"},
               {"version": "r42", "component": "report_title", "summary": "Display label update"})
    event_sources = (
        _event_source("batch-a", (
            ("d1", "e1", "c1", "2026-09-01T10:00:00+00:00", 1200),
            ("d2", "e1", "c1", "2026-09-01T10:00:00+00:00", 1200),
            ("d3", "e2", "c2", "2026-09-01T11:00:00+00:00", 800))),
        _event_source("batch-b", (
            ("d4", "e3", "c3", "2026-09-02T10:00:00+00:00", 1200),
            ("d5", "e3", "c3", "2026-09-02T10:00:00+00:00", 1200),
            ("d6", "e4", "c3", "2026-09-02T10:00:00+00:00", 1200))),
    )
    return (
        Incident("case-001", retail_contract, tuple(_retail_source(s) for s in snapshots()),
                 JOIN_SQL, retail_lineage, changes),
        Incident("case-002", event_contract, event_sources, EVENT_SQL,
                 {"daily_event_revenue": ["event_deliveries"]},
                 ({"version": "e21", "component": "event_loader", "summary": "Batch delivery update"},
                  {"version": "e22", "component": "report_title", "summary": "Display label update"})),
        Incident("case-003", time_contract, (_time_source("time-a", (
            ("t1", "2026-09-03T23:30:00", None),
            ("t2", "2026-09-04T00:30:00", None),
            ("t3", "2026-09-10T12:00:00", 0))),), TIME_SQL,
                 {"daily_event_count": ["events"]},
                 ({"version": "t31", "component": "events", "summary": "Source schema update"},)),
        Incident("case-004", time_contract, (_time_source("time-b", (
            ("t4", "2026-09-03T23:30:00", -120),
            ("t5", "2026-09-04T00:30:00", 120),
            ("t6", "2026-09-03T23:45:00", -120))),), TIME_SQL,
                 {"daily_event_count": ["events"]}, ()),
        Incident("case-005", retail_contract, tuple(_retail_source(s) for s in snapshots()),
                 LATEST_SQL, retail_lineage, changes),
        Incident("case-006", event_contract, (_event_source("batch-c", (
            ("d7", "e5", "c4", "2026-09-05T10:00:00+00:00", 1000),
            ("d8", "e5", "c4", "2026-09-05T10:00:00+00:00", 1500))),),
                 EVENT_SQL, {"daily_event_revenue": ["event_deliveries"]}, ()),
    )
