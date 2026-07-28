"""Verify a declared metric contract on supplied rows, without executing user SQL."""
import hashlib
import sqlite3
from decimal import Decimal

from .ingestion import UploadProblem, column, decimal_value, parse, safe_csv


def run(upload, progress=None):
    progress = progress or (lambda stage, state: None)
    progress("source", "running")
    headers, rows = parse(upload.csv)
    progress("source", "complete")
    progress("contract", "running")
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
    unique, clean, duplicates, locations = {}, [], 0, {}
    raw_total, excluded_source, eligible_source = 0, 0, 0
    issues, duplicate_rows = [], []
    for number, row in enumerate(rows, 2):
        identity = row[key].strip()
        if not identity:
            issues.append({"row": number, "column": headers[key], "message": "Logical key is empty."})
        try:
            cents = int(decimal_value(row[amount], places=2 if factor == 100 else 0) * factor)
        except ValueError:
            issues.append({"row": number, "column": headers[amount], "message": "Use a plain decimal with at most two fractional digits." if factor == 100 else "Use integer cents without symbols or separators."})
            continue
        eligible = status is None or row[status].strip() == wanted
        eligible_source += int(eligible)
        excluded_source += int(not eligible)
        raw_total += cents if eligible else 0
        # Require exact payload equality, including unmapped source columns.
        if identity in unique:
            if unique[identity] != row:
                issues.extend([{"row": locations[identity], "column": headers[key], "message": "Conflicting records share this logical key."},
                               {"row": number, "column": headers[key], "message": "Payload differs from the earlier record with this key."}])
                continue
            duplicates += 1
            if len(duplicate_rows) < 20:
                duplicate_rows.append({"row": number, "original_row": locations[identity], "eligible": eligible, "impact_cents": cents if eligible else 0})
            continue
        unique[identity] = row
        locations[identity] = number
        clean.append((row, cents, eligible))
    if issues:
        message = "Conflicting records share a logical key; clarify the grain or source before repair" if any("Conflicting" in i["message"] for i in issues) else "Some records do not satisfy the selected key and amount rules."
        raise UploadProblem(message, code="contract_records", issues=issues,
                            hint="Review the highlighted records. Fix the source export or choose the correct logical key / amount column, then run again.")
    progress("contract", "complete")
    progress("reference", "running")
    reference = {}
    for row, cents, eligible in clean:
        if eligible:
            label = row[group] if group is not None else "All records"
            reference[label] = reference.get(label, 0) + cents
    if len(reference) > 100:
        raise ValueError("More than 100 result groups; choose a broader grouping")
    progress("reference", "complete")
    progress("sql", "running")
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
    progress("sql", "complete")
    progress("reconcile", "running")
    if observed != reference:
        raise ValueError("SQL and independent integer-cents reference disagree; result withheld")
    results = [{"segment": key, "total_cents": value, "total": str(Decimal(value)/100)}
               for key, value in sorted(reference.items())]
    total = sum(reference.values())
    reported = upload.options.get("reported_total", "").strip()
    try:
        reported_cents = int(decimal_value(reported, places=2)*100) if reported else None
    except ValueError:
        raise UploadProblem("The reported total is not a valid dollar amount.", code="reported_total",
                            issues=[{"field": "reported_total", "message": "Use a plain amount such as 1234.56."}],
                            hint="Remove currency symbols and thousands separators; use at most two decimals.") from None
    progress("reconcile", "complete")
    progress("report", "running")
    result = {"project": "VerifyOps", "mode": "declared-contract", "live_ai": False,
            "source_sha256": hashlib.sha256(upload.csv.encode()).hexdigest(), "contract": {"mapping": upload.mapping, "options": upload.options},
            "summary": {"source_rows": len(rows), "unique_records": len(clean), "duplicate_deliveries": duplicates,
                        "raw_eligible_total_cents": raw_total, "verified_total_cents": total,
                        "reported_total_cents": reported_cents,
                        "eligible_unique_records": sum(eligible for _, _, eligible in clean),
                        "excluded_source_rows": excluded_source, "eligible_source_rows": eligible_source,
                        "difference_cents": None if reported_cents is None else total-reported_cents},
            "checks": {"unambiguous_grain": True, "sql_matches_independent_reference": observed == reference},
            "results": results, "sql": sql,
            "data_quality": {"duplicates": duplicate_rows, "duplicate_examples_capped": duplicates > 20,
                             "duplicate_impact_cents": raw_total-total, "conflicting_keys": 0,
                             "source_records": len(rows), "unique_records": len(clean)},
            "column_bindings": {f"c{i}": h for i, h in enumerate(headers)},
            "csv": safe_csv(["segment", "total_cents"], [[r["segment"], r["total_cents"]] for r in results]),
            "scope": "Verified against your declared key, status and amount rules. Generated SQL targets normalized records with __amount_cents and __eligible; it is not an automatic dbt patch or proof of unstated business semantics.",
            "activity": ["parse-source", "validate-contract-and-grain", "compile-normalized-sql", "execute-in-memory", "independent-cents-reconciliation", "export-evidence"]}
    progress("report", "complete")
    return result
