"""Trusted sample dbt project admission and queue execution; no arbitrary code uploads."""
import hashlib
import json
import os
import time
from pathlib import Path

from . import dbt_workflow, evaluation
from .jobs import Conflict, digest

PROJECT_ID = "payment-revenue"
CASE_ID = "dbt-payment-grain"


def executable():
    return Path(os.getenv("VDIR_DBT_EXECUTABLE", dbt_workflow.ROOT / ".venv-dbt/bin/dbt"))


def project_version():
    paths = [path for path in dbt_workflow.TEMPLATE.rglob("*") if path.is_file()]
    paths += [Path(__file__), Path(dbt_workflow.__file__), Path(evaluation.__file__)]
    paths += [evaluation.runtime_source(name) for name in evaluation.RUNTIME_FILES]
    paths += [dbt_workflow.ROOT / "backend/requirements-dbt.txt", dbt_workflow.ROOT / "backend/requirements-web.txt"]
    return digest({str(path.relative_to(dbt_workflow.ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)})


def project():
    return {"id": PROJECT_ID, "name": "Payment revenue", "description": "Investigate payment reporting and verify an upstream model repair across daily, monthly and customer outputs.",
            "sample": True, "models": 5, "regression_fixtures": 5, "input_version": project_version(),
            "available": executable().is_file(), "patch_path": dbt_workflow.TARGET}


def is_dbt(job):
    return job["request"].get("project_id") == PROJECT_ID


def validate_result(result, require_passed=False):
    report = result.get("dbt", {})
    if require_passed and (not result.get("grading", {}).get("passed") or not report.get("passed")):
        raise Conflict("This dbt patch did not pass independent verification")
    patch = result.get("patch")
    # Failed diagnostics can be rejected even though no verified patch exists.
    if patch is None:
        if require_passed:
            raise Conflict("No verified dbt patch is available")
        return
    unsigned = {key: value for key, value in report.items() if key != "version"}
    if digest(unsigned) != report.get("version"):
        raise Conflict("The dbt verification report changed")
    if hashlib.sha256(patch.encode()).hexdigest() != report.get("patch_sha256"):
        raise Conflict("The verified patch changed")
    if hashlib.sha256(result.get("model_sql", "").encode()).hexdigest() != report.get("model_sha256"):
        raise Conflict("The verified model changed")


def execute(store, job):
    request = job["request"]
    if request["input_version"] != project_version():
        raise ValueError("dbt project or execution code changed; start a new investigation")
    root = store.root / "runs" / job["id"] / "dbt"
    candidate = None
    if request["kind"] == "dbt_verification":
        parent = store.get(request["parent_id"])
        if not is_dbt(parent) or parent["result_version"] != request["parent_version"]:
            raise ValueError("Parent dbt result changed")
        candidate = request["candidate_sql"]
    started = time.monotonic()
    original_control = evaluation.EXECUTION_CONTROL.get()
    def control():
        if original_control:
            original_control()
        if time.monotonic() - started > 600:
            raise evaluation.ExecutionInterrupted("dbt investigation deadline exhausted")
    with evaluation.execution_scope(control):
        report = dbt_workflow.run(root, request["investigator"], executable(), candidate,
            progress=lambda stage, status, details: store.progress(job, stage, status, details), spend_root=store.root)
    manifest = json.loads((root / "evidence/incident.json").read_text())
    response = json.loads((root / "trace.json").read_text())
    checks = report.get("verification", [])
    passed = bool(report.get("passed"))
    result = {"case_id": CASE_ID, "engine": "duckdb", "input_version": request["input_version"],
        "current_sql": manifest["current_sql"], "contract": manifest["contract"], "response": response,
        "grading": {"passed": passed, "reason": "Independent dbt rebuilds and source-reference reconciliation",
                    "checks": [{"snapshot_id": item["fixture"], "passed": item["passed"]} for item in checks] or report.get("grading", {}).get("checks", [])},
        "dbt": report, "scope": report["scope"], "patch": None, "model_sql": None}
    if (root / "repair.patch").is_file():
        result["patch"] = (root / "repair.patch").read_text()
        result["model_sql"] = (root / "verification/incident" / dbt_workflow.TARGET).read_text()
        validate_result(result)
    return result
