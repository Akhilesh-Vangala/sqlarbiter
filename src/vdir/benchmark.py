"""Reproducible repeated-attempt evaluation; scripted controller tests are excluded."""
import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import time
from collections import defaultdict
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from .benchmark_cases import benchmark_cases
from .config import load_local_configuration
from .evaluation import InvestigatorError, export_workspace, grade, run_worker

MANIFEST = Path(__file__).resolve().parents[2] / "data" / "benchmark" / "manifest.json"


def corpus_manifest():
    cases = [asdict(case) for case in benchmark_cases()]
    payload = json.dumps(cases, sort_keys=True, separators=(",", ":"))
    return {"version": "synthetic-v1", "sha256": hashlib.sha256(payload.encode()).hexdigest(),
            "count": len(cases), "cases": [{"case_id": c["incident"]["case_id"],
                "family": c["family"], "split": c["split"], "template_group": c["template_group"],
                "sha256": hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()}
                for c in cases]}


def pass_at_k(successes, attempts, k):
    """Unbiased sampling estimator; no value when fewer than k attempts exist."""
    if not 0 <= successes <= attempts or k < 1:
        raise ValueError("Invalid Pass@k inputs")
    if attempts < k:
        return None
    return 1 - math.comb(attempts - successes, k) / math.comb(attempts, k) if attempts - successes >= k else 1.0


def estimate_cost(model_run, pricing):
    if not model_run or not pricing:
        return None
    if model_run.get("resolved_model") != pricing.get("model"):
        return None
    # Cache categories are separate from ordinary input tokens in Messages usage.
    usage = model_run.get("usage", {})
    if model_run.get("additional_billing_unknown") or model_run.get("status") != "completed":
        return None
    return sum([
        usage.get("input_tokens", 0) * pricing["input_per_million"],
        usage.get("output_tokens", 0) * pricing["output_per_million"],
        model_run.get("cache_creation_input_tokens", 0) * pricing["cache_write_per_million"],
        model_run.get("cache_read_input_tokens", 0) * pricing["cache_read_per_million"],
    ]) / 1000000


def sqlite_case(case):
    if case.contract["metric"] != "utc_daily_event_count" or "INTERVAL" not in case.current_sql:
        return case
    sign = "-" if " - utc_offset_minutes" in case.current_sql else "+"
    sql = ("SELECT date(local_timestamp, printf('%%+d minutes', %sutc_offset_minutes)) "
           "AS business_date, COUNT(*) AS event_count FROM events GROUP BY business_date" % sign)
    return replace(case, current_sql=sql)


def summarize(records):
    grouped = defaultdict(list)
    for record in records:
        grouped[record["case_id"]].append(record)
    def metric(k, sql_only=False):
        values = [pass_at_k(sum(r["sql_execution_passed"] if sql_only else r["grading"]["passed"] for r in attempts),
                            len(attempts), k) for attempts in grouped.values()
                  if not sql_only or attempts[0]["repairable"]]
        return statistics.mean(values) if values and all(v is not None for v in values) else None
    paid = [r["cost_usd_estimate"] for r in records if r["cost_usd_estimate"] is not None]
    return {"cases": len(grouped), "attempts": len(records), "pass_at_1": metric(1),
            "pass_at_3": metric(3), "sql_execution_pass_at_1": metric(1, True),
            "sql_execution_pass_at_3": metric(3, True),
            "mean_tool_calls": statistics.mean(r["tool_calls"] for r in records),
            "mean_model_rounds": statistics.mean(r.get("model_run", {}).get("rounds", 0) for r in records),
            "mean_investigation_seconds": statistics.mean(r["investigation_seconds"] for r in records),
            "mean_verification_seconds": statistics.mean(r["verification_seconds"] for r in records),
            "total_reported_input_tokens": sum(r.get("model_run", {}).get("usage", {}).get("input_tokens", 0) for r in records),
            "total_reported_output_tokens": sum(r.get("model_run", {}).get("usage", {}).get("output_tokens", 0) for r in records),
            "total_cost_usd_estimate": sum(paid) if len(paid) == len(records) else None,
            "costed_attempts": len(paid)}


def run_benchmark(output, investigator="baseline", engine="duckdb", samples=1, split="all", case_ids=None, pricing=None):
    if investigator not in ("baseline", "anthropic", "langgraph") or engine not in ("sqlite", "duckdb") or split not in ("all", "calibration", "evaluation"):
        raise ValueError("Invalid benchmark configuration")
    if pricing is not None:
        required = ("input_per_million", "output_per_million", "cache_write_per_million", "cache_read_per_million")
        if (not isinstance(pricing, dict) or not isinstance(pricing.get("model"), str)
                or not isinstance(pricing.get("verified_at"), str) or not isinstance(pricing.get("source_url"), str)
                or any(type(pricing.get(k)) not in (int, float) or not math.isfinite(pricing[k]) or pricing[k] < 0 for k in required)):
            raise ValueError("Pricing requires model, verified_at, source_url and four nonnegative per-million rates")
    if samples < 1 or samples > 3:
        raise ValueError("Samples must be 1–3; every live sample is a separate billable investigation")
    frozen = json.loads(MANIFEST.read_text())
    current = corpus_manifest()
    if frozen != current:
        raise ValueError("Corpus differs from the frozen manifest; review and version the corpus before evaluating")
    selected = [case for case in benchmark_cases() if (split == "all" or case.split == split)
                and (not case_ids or case.incident.case_id in case_ids)]
    if not selected or case_ids and set(case_ids) - {c.incident.case_id for c in selected}:
        raise ValueError("No cases selected or unknown case ID/split combination")
    if investigator in ("anthropic", "langgraph"):
        import os
        if not os.environ.get("ANTHROPIC_API_KEY") or not os.environ.get("VDIR_ANTHROPIC_MODEL"):
            raise ValueError("Configure the private model credentials before creating a live run")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    from .evaluation import runtime_source, RUNTIME_FILES
    runtime_hash = hashlib.sha256(b"".join(runtime_source(name).read_bytes() for name in RUNTIME_FILES)).hexdigest()
    from . import evaluation
    report = {"corpus": current, "investigator": investigator, "engine": engine,
              "python": platform.python_version(), "runtime_sha256": runtime_hash,
              "evaluator_sha256": hashlib.sha256(Path(evaluation.__file__).read_bytes()).hexdigest(),
              "samples": samples, "split": split, "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "38 known synthetic scenarios, including data variants of eight new SQL-shape templates; not a validated real-world benchmark",
              "pricing": pricing, "records": []}
    def checkpoint():
        if report["records"]:
            report["summary"] = summarize(report["records"])
        (output / "report.json").write_text(json.dumps(report, indent=2))
    from .evaluation import reference_outcome
    for selected_case in selected:
        case = selected_case.incident
        if engine == "sqlite":
            case = sqlite_case(case)
        for sample in range(samples):
            root = output / case.case_id / ("attempt-%d" % (sample + 1))
            root.mkdir(parents=True)
            workspace = export_workspace(case, root / "evidence", engine)
            started = time.monotonic()
            try:
                response = run_worker(workspace, mode=investigator)
            except (InvestigatorError, subprocess.TimeoutExpired) as error:
                response = error.response if isinstance(error, InvestigatorError) else {
                    "decision": {}, "trace": [], "error": "Worker timed out; billing may be incomplete"}
                metadata = workspace / "model-run.json"
                if metadata.exists():
                    response["model_run"] = json.loads(metadata.read_text())
                    response["model_run"].update(status="failed", additional_billing_unknown=True)
            investigation_seconds = time.monotonic() - started
            started = time.monotonic()
            checked = grade(case, response, root / "grading", engine)
            record = {"case_id": case.case_id, "family": selected_case.family, "split": selected_case.split,
                      "attempt": sample + 1, "grading": checked,
                      "repairable": reference_outcome(case, case.sources[0])["status"] == "repairable",
                      "sql_execution_passed": bool(checked.get("checks")) and all(c["passed"] for c in checked.get("checks", [])),
                      "tool_calls": len(response.get("trace", [])), "investigation_seconds": investigation_seconds,
                      "verification_seconds": time.monotonic() - started,
                      "decision": response.get("decision", {})}
            if "model_run" in response:
                record["model_run"] = response["model_run"]
            record["cost_usd_estimate"] = estimate_cost(response.get("model_run"), pricing) if investigator in ("anthropic", "langgraph") else 0.0
            (root / "trace.json").write_text(json.dumps(response, indent=2))
            report["records"].append(record)
            checkpoint()
    report["families"] = {family: summarize([r for r in report["records"] if r["family"] == family])
                          for family in sorted({r["family"] for r in report["records"]})}
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["note"] = "Fixed-baseline repeated attempts are deterministic and do not measure model variance. Missing costs/Pass@3 are null, never zero. API invoice may differ from estimates."
    checkpoint()
    return report


def main():
    load_local_configuration()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--investigator", choices=("baseline", "anthropic", "langgraph"), default="baseline")
    parser.add_argument("--engine", choices=("duckdb", "sqlite"), default="duckdb")
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--split", choices=("all", "calibration", "evaluation"), default="all")
    parser.add_argument("--case-ids", nargs="+")
    parser.add_argument("--pricing", type=Path)
    args = parser.parse_args()
    try:
        pricing = json.loads(args.pricing.read_text()) if args.pricing else None
        report = run_benchmark(args.output, args.investigator, args.engine, args.samples, args.split, args.case_ids, pricing)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(report["summary"], indent=2))
    raise SystemExit(0 if report["summary"]["pass_at_1"] == 1 else 1)


if __name__ == "__main__":
    main()
