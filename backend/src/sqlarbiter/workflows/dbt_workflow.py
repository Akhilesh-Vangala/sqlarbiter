"""Original dbt incident: bounded SQL proposal, isolated build and scoped verification.

Only a read-only SELECT over the declared staging table can become the one allowed
model patch. dbt executes trusted local project code, never arbitrary model Jinja.
"""

import argparse
import csv
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path

import duckdb
import sqlglot
from sqlglot import exp

from sqlarbiter.domain.cases import Incident
from sqlarbiter.domain.cases import Source
from sqlarbiter.platform.config import load_local_configuration
from sqlarbiter.evaluation.evaluation import export_workspace
from sqlarbiter.evaluation.evaluation import grade
from sqlarbiter.evaluation.evaluation import run_worker

ROOT = Path(__file__).resolve().parents[4]
TEMPLATE = ROOT / "backend/dbt/revenue_incident"
TARGET = "models/int_payment_events.sql"
COLUMNS = (
    "delivery_id",
    "event_id",
    "customer_id",
    "occurred_at",
    "received_at",
    "status",
    "amount_cents",
)
OUTPUT = ["event_id", "customer_id", "occurred_at", "status", "amount_cents"]


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def fixtures(template=TEMPLATE):
    """Evaluator-owned regression inputs; never included in the investigator context."""
    with (template / "seeds/payment_deliveries.csv").open(newline="") as file:
        original = [
            tuple(int(row[key]) if key == "amount_cents" else row[key] for key in COLUMNS)
            for row in csv.DictReader(file)
        ]
    equal = [
        (
            "a1",
            "a",
            "c",
            "2026-09-30T23:59:00+00:00",
            "2026-10-02T00:00:00+00:00",
            "completed",
            500,
        ),
        (
            "a2",
            "a",
            "c",
            "2026-09-30T23:59:00+00:00",
            "2026-10-03T00:00:00+00:00",
            "completed",
            500,
        ),
        (
            "b1",
            "b",
            "c",
            "2026-09-30T23:59:00+00:00",
            "2026-10-02T00:00:00+00:00",
            "completed",
            500,
        ),
    ]
    boundaries = [
        ("z1", "z", "c0", "2026-09-30T23:59:59+00:00", "2026-10-02T00:00:00+00:00", "completed", 0),
        (
            "q1",
            "q",
            "c1",
            "2026-10-01T00:00:00+00:00",
            "2026-10-03T00:00:00+00:00",
            "completed",
            200,
        ),
        (
            "q2",
            "q",
            "c1",
            "2026-10-01T00:00:00+00:00",
            "2026-10-04T00:00:00+00:00",
            "completed",
            200,
        ),
        ("p1", "p", "c1", "2026-10-01T00:00:00+00:00", "2026-10-03T00:00:00+00:00", "pending", 900),
    ]
    return {
        "incident": original,
        "equal_value_distinct_events": equal,
        "late_month_boundary_and_zero": boundaries,
        "reordered_deliveries": list(reversed(original)),
        "empty_batch": [],
    }


def write_seed(project, rows):
    with (project / "seeds/payment_deliveries.csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        writer.writerows(rows)


def copy_project(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    for name in ("dbt_project.yml", "profiles.yml"):
        shutil.copyfile(source / name, destination / name)
    for name in ("models", "seeds", "tests"):
        shutil.copytree(source / name, destination / name)


def run_dbt(project, database, phase, commands, executable):
    executable = Path(executable).resolve()
    if not executable.is_file():
        raise ValueError(
            "Install the isolated dbt environment; set SQLARBITER_DBT_EXECUTABLE if needed"
        )
    environment = {
        "PATH": os.defpath,
        "HOME": str(project),
        "SQLARBITER_DBT_DATABASE": str(database),
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
        "DBT_USE_COLORS": "false",
    }
    environment["DBT_PROFILES_DIR"] = str(project)
    results = []
    for index, command in enumerate(commands):
        log = project / (phase + "-" + str(index) + ".log")
        with log.open("wb") as output:
            process = subprocess.Popen(
                [
                    str(executable),
                    *command,
                    "--project-dir",
                    str(project),
                    "--profiles-dir",
                    str(project),
                    "--no-partial-parse",
                ],
                cwd=project,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                from sqlarbiter.evaluation.evaluation import EXECUTION_CONTROL

                started = time.monotonic()
                while process.poll() is None:
                    control = EXECUTION_CONTROL.get()
                    if control:
                        control()
                    if time.monotonic() - started > 90 or log.stat().st_size > 2000000:
                        raise ValueError("dbt execution time or log allowance exhausted")
                    try:
                        process.wait(timeout=0.2)
                    except subprocess.TimeoutExpired:
                        pass
            except BaseException:
                from sqlarbiter.evaluation.evaluation import _stop_process

                _stop_process(process)
                raise
        if log.stat().st_size > 2000000:
            raise ValueError("dbt log budget exceeded")
        results.append({"command": command, "exit_code": process.returncode, "log": log.name})
    return results


def relations(database):
    values = {}
    with duckdb.connect(str(database), read_only=True) as db:
        for name in (
            "int_payment_events",
            "fct_daily_revenue",
            "mart_monthly_revenue",
            "fct_customer_revenue",
        ):
            values[name] = sorted(
                [list(row) for row in db.execute('SELECT * FROM "' + name + '"').fetchall()]
            )
    return values


def independent_outputs(rows):
    events = {}
    for delivery, event, customer, occurred, received, status, amount in rows:
        if (
            type(amount) is not int
            or amount < 0
            or datetime.fromisoformat(occurred).utcoffset() != timedelta(0)
        ):
            raise ValueError("Invalid immutable payment payload")
        payload = (customer, occurred, status, amount)
        if event in events and events[event] != payload:
            raise ValueError("Conflicting immutable payment payloads require source clarification")
        events[event] = payload
    daily, monthly, customers = defaultdict(int), defaultdict(int), defaultdict(int)
    canonical = []
    for event, (customer, occurred, status, amount) in events.items():
        canonical.append([event, customer, occurred, status, amount])
        if status == "completed":
            day = datetime.fromisoformat(occurred).date().isoformat()
            daily[day] += amount
            monthly[day[:7]] += amount
            customers[customer] += amount
    return {
        "int_payment_events": sorted(canonical),
        "fct_daily_revenue": sorted([key, value] for key, value in daily.items()),
        "mart_monthly_revenue": sorted([key, value] for key, value in monthly.items()),
        "fct_customer_revenue": sorted([key, value] for key, value in customers.items()),
    }


def dependency_context(project):
    manifest = json.loads((project / "target/manifest.json").read_text())
    nodes = {
        key: value
        for key, value in manifest["nodes"].items()
        if value["resource_type"] in ("model", "seed")
    }
    lineage = {
        value["name"]: [
            nodes[parent]["name"]
            for parent in value.get("depends_on", {}).get("nodes", [])
            if parent in nodes
        ]
        for value in nodes.values()
    }
    files = {
        value["original_file_path"]: value.get("raw_code", "")
        for value in nodes.values()
        if value["resource_type"] == "model"
    }
    descendants, frontier = [], ["int_payment_events"]
    while frontier:
        current = frontier.pop()
        for name, parents in lineage.items():
            if current in parents and name not in descendants:
                descendants.append(name)
                frontier.append(name)
    return {
        "target_model": "int_payment_events",
        "allowed_patch_path": TARGET,
        "files": files,
        "lineage": lineage,
        "affected_models": sorted(descendants),
        "dbt_version": manifest["metadata"]["dbt_version"],
        "manifest_sha256": hashlib.sha256(
            (project / "target/manifest.json").read_bytes()
        ).hexdigest(),
    }


def patch_sql(candidate):
    """Validate a plain SELECT and render only our declared dbt reference."""
    from sqlarbiter.evaluation.evaluation import runtime_source

    # Use the same policy as analytical tool execution without evaluating Jinja.
    import importlib.util

    spec = importlib.util.spec_from_file_location("dbt_sql_guard", runtime_source("engines.py"))
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    if not isinstance(candidate, str) or "{{" in candidate or "{%" in candidate:
        raise ValueError("The proposal must be plain read-only SQL, not Jinja or project code")
    guarded = guard.select_sql(
        candidate, "duckdb", {"stg_payment_deliveries": {"columns": list(COLUMNS)}}
    )
    tree = sqlglot.parse_one(guarded, read="duckdb")
    refs = 0
    for table in tree.find_all(exp.Table):
        if table.name == "stg_payment_deliveries":
            table.set("this", exp.Identifier(this="SQLARBITER_STAGING_REF"))
            table.set("db", None)
            table.set("catalog", None)
            refs += 1
    if not refs:
        raise ValueError("The patch must read the declared staging relation")
    return (
        tree.sql(dialect="duckdb", pretty=True).replace(
            "SQLARBITER_STAGING_REF", "{{ ref('stg_payment_deliveries') }}"
        )
        + "\n"
    )


def run(
    output, investigator="baseline", executable=None, candidate=None, progress=None, spend_root=None
):
    load_local_configuration()
    output = Path(output).resolve()
    executable = executable or os.getenv("SQLARBITER_DBT_EXECUTABLE", ROOT / ".venv-dbt/bin/dbt")
    if investigator in ("anthropic", "langgraph") and not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("Configure the private provider key before a live investigation")
    output.mkdir(parents=True, exist_ok=False)

    def update(stage, status, **details):
        if progress:
            progress(stage, status, details)

    update("original_build", "running")
    original = output / "original"
    copy_project(TEMPLATE, original)
    database = original / "warehouse.duckdb"
    commands = run_dbt(original, database, "before", [["seed"], ["run"], ["test"]], executable)
    if any(row["exit_code"] != 0 for row in commands[:2]) or commands[2]["exit_code"] == 0:
        raise ValueError(
            "Expected a successful original build and a failing grain test; inspect saved logs"
        )
    update("original_build", "completed", test_failed=True)
    sources = fixtures(original)
    context = dependency_context(original)
    before = relations(database)
    definitions = tuple(key + (" INTEGER" if key == "amount_cents" else " TEXT") for key in COLUMNS)
    case = Incident(
        "dbt-payment-grain",
        {
            "version": "payments-v1",
            "metric": "canonical_payment_events",
            "output": OUTPUT,
            "rules": {
                "identity": "one immutable payload per event_id regardless of delivery/received_at",
                "status": "preserve all statuses; downstream revenue uses completed only",
                "date": "occurred_at explicit UTC, never received_at",
                "unit": "integer cents",
                "patch": "propose a plain SELECT for int_payment_events over stg_payment_deliveries",
            },
            "project_context": context,
        },
        tuple(
            Source(name, {"stg_payment_deliveries": (definitions, tuple(rows))})
            for name, rows in sources.items()
        ),
        "SELECT event_id, customer_id, occurred_at, status, amount_cents FROM stg_payment_deliveries",
        context["lineage"],
        (
            {
                "component": "payment ingestion",
                "summary": "Retry delivery policy changed; billing dashboard discrepancy reported",
            },
        ),
    )
    evidence = export_workspace(case, output / "evidence", "duckdb")
    manifest_path = evidence / "incident.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["project"] = context
    manifest_path.write_text(json.dumps(manifest, indent=2))
    update("investigation", "running")
    response = run_worker(evidence, mode=investigator, spend_root=spend_root)
    if candidate is not None:
        # Explicit operator revision retains source evidence, then is independently regraded.
        response["decision"].update(
            status="candidate",
            candidate_sql=candidate,
            explanation="Operator-supplied SQL revision",
        )
    proposal = response.get("decision", {})
    (output / "trace.json").write_text(json.dumps(response, indent=2))
    update("investigation", "completed", outcome=proposal.get("status"))
    check = grade(case, response, output / "grading", "duckdb")
    if proposal.get("status") != "candidate" or not check["passed"]:
        update("verification", "failed", reason=check["reason"])
        report = {
            "passed": False,
            "grading": check,
            "decision": proposal,
            "scope": "Known original dbt development incident",
        }
        (output / "report.json").write_text(json.dumps(report, indent=2))
        return report
    patched = patch_sql(proposal["candidate_sql"])
    diff = "".join(
        difflib.unified_diff(
            (original / TARGET).read_text().splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile="a/" + TARGET,
            tofile="b/" + TARGET,
        )
    )
    (output / "repair.patch").write_text(diff)
    checks = []
    for name, rows in sources.items():
        update(
            "verification",
            "running",
            fixture=name,
            fixtures_completed=len(checks),
            fixtures_total=len(sources),
        )
        project = output / "verification" / name
        copy_project(original, project)
        (project / TARGET).write_text(patched)
        write_seed(project, rows)
        database = project / "warehouse.duckdb"
        executions = run_dbt(project, database, "after", [["build"]], executable)
        actual = relations(database) if executions[0]["exit_code"] == 0 else None
        expected = independent_outputs(rows)
        checks.append(
            {
                "fixture": name,
                "passed": actual == expected,
                "dbt": executions,
                "models": {
                    model: {
                        "passed": bool(actual is not None and actual[model] == expected[model]),
                        "expected": expected[model],
                        "actual": actual[model] if actual is not None else None,
                    }
                    for model in expected
                },
            }
        )
        update(
            "verification",
            "running",
            fixture=name,
            fixture_passed=actual == expected,
            fixtures_completed=len(checks),
            fixtures_total=len(sources),
        )
    report = {
        "passed": all(check["passed"] for check in checks),
        "investigator": investigator,
        "grading": check,
        "before": before,
        "before_dbt": commands,
        "decision": proposal,
        "patch_path": TARGET,
        "patch_sha256": hashlib.sha256(diff.encode()).hexdigest(),
        "model_sha256": hashlib.sha256(patched.encode()).hexdigest(),
        "source_version": digest({"files": context["files"], "rows": sources["incident"]}),
        "execution_versions": {
            "app_python": os.sys.version.split()[0],
            "dbt_core": context["dbt_version"],
            "dbt_duckdb_requirement": "1.11.0",
            "duckdb": duckdb.__version__,
            "versions_scope": "dbt-core from actual manifest; adapter pin is a requirement, actual adapter version is in build logs",
        },
        "project_assets": {
            str(path.relative_to(original)): hashlib.sha256(path.read_bytes()).hexdigest()
            for name in ("models", "seeds", "tests")
            for path in sorted((original / name).rglob("*"))
            if path.is_file()
        },
        "affected_models": context["affected_models"],
        "verification": checks,
        "scope": "Original synthetic development incident and five designed regression fixtures; not unseen capability or production promotion",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    report["version"] = digest(report)
    (output / "report.json").write_text(json.dumps(report, indent=2))
    update(
        "verification",
        "completed" if report["passed"] else "failed",
        fixtures_completed=len(checks),
        fixtures_total=len(sources),
    )
    return report


def review(report_path, version, action, note=""):
    path = Path(report_path)
    report = json.loads(path.read_text())
    recorded = report.pop("version", None)
    if recorded != version or digest(report) != version:
        raise ValueError("Verification report version changed")
    patch = path.parent / "repair.patch"
    if hashlib.sha256(patch.read_bytes()).hexdigest() != report["patch_sha256"]:
        raise ValueError("Patch artifact changed after verification")
    if action not in ("approved", "rejected") or action == "approved" and not report["passed"]:
        raise ValueError("Only an independently passing patch can be approved")
    value = {
        "version": version,
        "action": action,
        "note": note,
        "actor": os.getenv("SQLARBITER_OPERATOR_NAME", "local-operator"),
        "scope": "Local exact-version review; no production application",
    }
    destination = path.parent / "review.json"
    if destination.exists():
        if json.loads(destination.read_text()) != value:
            raise ValueError("Review is immutable")
        return value
    with destination.open("x") as file:
        json.dump(value, file, indent=2)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--investigator", choices=("baseline", "anthropic", "langgraph"), default="baseline"
    )
    parser.add_argument("--dbt-executable", type=Path)
    parser.add_argument(
        "--candidate-sql", type=Path, help="Explicit local operator revision, independently checked"
    )
    parser.add_argument("--review-report", type=Path)
    parser.add_argument("--expected-version")
    parser.add_argument("--action", choices=("approved", "rejected"))
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    try:
        if args.review_report:
            if not args.expected_version or not args.action:
                parser.error("Review requires --expected-version and --action")
            result = review(args.review_report, args.expected_version, args.action, args.note)
        else:
            if not args.output:
                parser.error("A fresh --output directory is required")
            result = run(
                args.output,
                args.investigator,
                args.dbt_executable,
                args.candidate_sql.read_text() if args.candidate_sql else None,
            )
    except (ValueError, RuntimeError, OSError) as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("passed", "version", "affected_models", "scope", "action")
                if key in result
            },
            indent=2,
        )
    )
    if result.get("passed") is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
