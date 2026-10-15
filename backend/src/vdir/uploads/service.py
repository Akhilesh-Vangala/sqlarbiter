"""Verify a declared metric contract on supplied rows, without executing user SQL."""
import hashlib
import sqlite3
from decimal import Decimal

from .ingestion import column, decimal_value, fingerprint, parse, safe_csv


def run(upload):
    headers, rows = parse(upload.csv)
    if set(upload.mapping) - {"key", "amount", "group", "status"} or set(upload.options) - {"unit", "eligible_status", "reported_total"}:
        raise ValueError("Unsupported metric contract fields")
    key = column(upload.mapping, "key", headers)
    amount = column(upload.mapping, "amount", headers)
    group = column(upload.mapping, "group", headers, True)
    status = column(upload.mapping, "status", headers, True)
    if key == amount:
        raise ValueError("Logical key and amount must be different columns")
    unit = upload.options.get("unit", "dollars")
    if unit not in ("dollars", "cents"):
        raise ValueError("Choose dollars or integer cents")
    wanted = upload.options.get("eligible_status", "").strip()
    if (status is None) != (not wanted):
        raise ValueError("Set both status column and eligible status, or neither")
    factor = 100 if unit == "dollars" else 1
    unique, clean, duplicates = {}, [], 0
    raw_total = 0
    for row in rows:
        identity = row[key].strip()
        if not identity:
            raise ValueError("Logical keys cannot be empty")
        cents = int(decimal_value(row[amount], places=2 if factor == 100 else 0) * factor)
        eligible = status is None or row[status].strip() == wanted
        raw_total += cents if eligible else 0
        # Require exact payload equality, including unmapped source columns.
        if identity in unique:
            if unique[identity] != row:
                raise ValueError("Conflicting records share a logical key; clarify the grain or source before repair")
            duplicates += 1
            continue
        unique[identity] = row
        clean.append((row, cents, eligible))
    reference = {}
    for row, cents, eligible in clean:
        if eligible:
            label = row[group] if group is not None else "All records"
            reference[label] = reference.get(label, 0) + cents
    if len(reference) > 100:
        raise ValueError("More than 100 result groups; choose a broader grouping")
    # Fresh in-memory database; every identifier is generated and all cells are parameters.
    with sqlite3.connect(":memory:") as db:
        fields = ", ".join(f'"c{i}" TEXT' for i in range(len(headers)))
        db.execute(f'CREATE TABLE records ({fields}, __amount_cents INTEGER, __eligible INTEGER)')
        db.executemany("INSERT INTO records VALUES (" + ",".join("?" for _ in range(len(headers)+2)) + ")",
                       [row + [int(decimal_value(row[amount], places=2 if factor == 100 else 0)*factor),
                               int(status is None or row[status].strip() == wanted)] for row in rows])
        g = f'"c{group}"' if group is not None else "'All records'"
        # Exact duplicate payloads only; conflicts above are refused, never silently resolved.
        sql = ("WITH canonical AS (SELECT DISTINCT * FROM records)\n"
               f"SELECT {g} AS segment, SUM(__amount_cents) AS total_cents\n"
               f"FROM canonical WHERE __eligible = 1 GROUP BY {g} ORDER BY segment")
        db.execute("PRAGMA query_only=ON")
        observed = dict(db.execute(sql))
    if observed != reference:
        raise ValueError("SQL and independent integer-cents reference disagree; result withheld")
    results = [{"segment": key, "total_cents": value, "total": str(Decimal(value)/100)}
               for key, value in sorted(reference.items())]
    total = sum(reference.values())
    reported = upload.options.get("reported_total", "").strip()
    reported_cents = int(decimal_value(reported, places=2)*100) if reported else None
    return {"project": "VerifyOps", "mode": "declared-contract", "live_ai": False,
            "source_sha256": hashlib.sha256(upload.csv.encode()).hexdigest(), "contract": {"mapping": upload.mapping, "options": upload.options},
            "summary": {"source_rows": len(rows), "unique_records": len(clean), "duplicate_deliveries": duplicates,
                        "raw_eligible_total_cents": raw_total, "verified_total_cents": total,
                        "reported_total_cents": reported_cents,
                        "difference_cents": None if reported_cents is None else total-reported_cents},
            "checks": {"unambiguous_grain": True, "sql_matches_independent_reference": observed == reference},
            "results": results, "sql": sql,
            "column_bindings": {f"c{i}": h for i, h in enumerate(headers)},
            "csv": safe_csv(["segment", "total_cents"], [[r["segment"], r["total_cents"]] for r in results]),
            "scope": "Verified against your declared key, status and amount rules. Generated SQL targets normalized records with __amount_cents and __eligible; it is not an automatic dbt patch or proof of unstated business semantics.",
            "activity": ["parse-source", "validate-contract-and-grain", "compile-normalized-sql", "execute-in-memory", "independent-cents-reconciliation", "export-evidence"]}
