"""Fixed, contract-specific diagnostics. This is not an LLM investigator."""

LATEST_SQL = """WITH latest AS (
SELECT product_id, MAX(version) AS version FROM product_versions GROUP BY product_id)
SELECT o.business_date, p.category, SUM(i.amount_cents) AS revenue_cents
FROM orders o JOIN order_items i ON i.order_id=o.order_id
JOIN latest l ON l.product_id=i.product_id
JOIN product_versions p ON p.product_id=l.product_id AND p.version=l.version
WHERE o.status='completed' GROUP BY o.business_date, p.category"""

EVENT_SQL = """WITH unique_events AS (
SELECT event_id, MAX(occurred_at) AS occurred_at, MAX(amount_cents) AS amount_cents
FROM event_deliveries GROUP BY event_id)
SELECT substr(occurred_at,1,10) AS business_date, SUM(amount_cents) AS revenue_cents
FROM unique_events GROUP BY business_date"""

TIME_SQL = """SELECT date(local_timestamp, printf('%+d minutes', -utc_offset_minutes))
AS business_date, COUNT(*) AS event_count FROM events GROUP BY business_date"""


def investigate(tools):
    evidence = []

    def call(name, params=None):
        response = tools.call(name, params)
        if not response["ok"]:
            raise ValueError("Diagnostic tool failed: " + response["error"])
        if isinstance(response["result"], dict) and response["result"].get("truncated"):
            raise ValueError("Fixed diagnostic requires complete query results")
        evidence.append(response["evidence_id"])
        return response["result"]

    def decision(status, explanation, **kwargs):
        return dict(status=status, explanation=explanation, evidence_ids=evidence, **kwargs)

    contract = call("contract")
    call("describe")
    call("lineage")
    call("changes")
    current_sql = call("current_sql")
    metric = contract["metric"]
    if metric == "completed_item_revenue":
        call("query", {"sql": "SELECT product_id, COUNT(*) AS versions "
                                "FROM product_versions GROUP BY product_id HAVING COUNT(*)>1"})
        candidate = LATEST_SQL
        explanation = "Check product-version selection against the declared category contract."
    elif metric == "unique_event_revenue":
        conflicts = call("query", {"sql": "SELECT event_id FROM event_deliveries GROUP BY event_id "
                                  "HAVING COUNT(DISTINCT customer_id)>1 "
                                  "OR COUNT(DISTINCT occurred_at)>1 "
                                  "OR COUNT(DISTINCT amount_cents)>1"})
        if conflicts["rows"]:
            return decision("needs_information", "Repeated event IDs contain conflicting payloads.",
                            affected_ids=sorted(row[0] for row in conflicts["rows"]),
                            required_fields=["authoritative_event_payload"])
        call("query", {"sql": "SELECT event_id, COUNT(*) AS deliveries FROM event_deliveries "
                     "GROUP BY event_id HAVING COUNT(*)>1"})
        candidate = EVENT_SQL
        explanation = "Count each authoritative event once; preserve separate equal-value events."
    elif metric == "utc_daily_event_count":
        missing = call("query", {"sql": "SELECT event_id FROM events WHERE utc_offset_minutes IS NULL"})
        if missing["rows"]:
            return decision("needs_information", "UTC day cannot be recovered without source offsets.",
                            affected_ids=sorted(row[0] for row in missing["rows"]),
                            required_fields=["utc_offset_minutes"])
        candidate = ("SELECT CAST(CAST(local_timestamp AS TIMESTAMP) - utc_offset_minutes * "
                     "INTERVAL '1 minute' AS DATE)::VARCHAR AS business_date, "
                     "COUNT(*) AS event_count FROM events GROUP BY business_date") if tools.engine == "duckdb" else TIME_SQL
        explanation = "Convert local timestamps using their explicit source offset."
    elif metric == "canonical_payment_events":
        conflicts = call("query", {"sql": "SELECT event_id FROM stg_payment_deliveries GROUP BY event_id HAVING COUNT(DISTINCT customer_id)>1 OR COUNT(DISTINCT occurred_at)>1 OR COUNT(DISTINCT status)>1 OR COUNT(DISTINCT amount_cents)>1"})
        if conflicts["rows"]:
            return decision("needs_information", "Conflicting immutable payment event payloads.", affected_ids=sorted(row[0] for row in conflicts["rows"]), required_fields=["authoritative_event_payload"])
        call("project")
        call("profile", {"table": "stg_payment_deliveries", "columns": ["event_id", "delivery_id"]})
        candidate = "SELECT DISTINCT event_id, customer_id, occurred_at, status, amount_cents FROM stg_payment_deliveries"
        explanation = "Delivery grain violates the declared event identity. Deduplicate complete immutable payloads by event identity before all dependent revenue aggregations."
    elif metric == "tagged_item_revenue":
        call("profile", {"table": "item_tags", "columns": ["item_id"]})
        candidate = ("SELECT p.business_date, SUM(p.amount_cents) AS revenue_cents FROM purchases p "
                     "WHERE p.status='completed' AND EXISTS (SELECT 1 FROM item_tags t "
                     "WHERE t.item_id=p.item_id) GROUP BY p.business_date")
        explanation = "Use tag existence instead of multiplying purchases by tag rows."
    elif metric == "customer_completed_revenue":
        call("profile", {"table": "customer_orders", "columns": ["customer_id", "status"]})
        candidate = ("SELECT c.customer_id, COALESCE(SUM(o.amount_cents),0) AS revenue_cents "
                     "FROM customers c LEFT JOIN customer_orders o ON c.customer_id=o.customer_id "
                     "AND o.status='completed' GROUP BY c.customer_id")
        explanation = "Preserve the full customer population and explicitly return zero for absent revenue."
    elif metric == "eligible_transaction_revenue":
        eligible = contract["rules"]["eligible_status"]
        if eligible not in ("completed", "settled"):
            return decision("unsupported", "Unsupported fixed eligibility contract.")
        call("profile", {"table": "transactions", "columns": ["status"]})
        candidate = ("SELECT business_date, SUM(amount_cents) AS revenue_cents FROM transactions "
                     "WHERE status='%s' GROUP BY business_date" % eligible)
        explanation = "Apply the authoritative eligibility predicate before aggregation."
    else:
        return decision("unsupported", "No fixed diagnostic workflow exists for this metric.")
    current = call("query", {"sql": current_sql})
    proposed = call("query", {"sql": candidate})
    if current["columns"] == proposed["columns"] and sorted(current["rows"]) == sorted(proposed["rows"]):
        return decision("no_change", "Current output already satisfies this diagnostic comparison.")
    return decision("candidate", explanation, candidate_sql=candidate)
