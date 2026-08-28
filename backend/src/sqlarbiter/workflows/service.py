"""Independent execution service used by queue workers, not HTTP request handlers."""

import copy
import hashlib
import os
import shutil
import sqlite3
from contextlib import nullcontext
import subprocess
import threading
from dataclasses import asdict
from pathlib import Path

from sqlarbiter.evaluation import evaluation
from sqlarbiter.domain.cases import incidents
from sqlarbiter.persistence.jobs import Conflict
from sqlarbiter.persistence.jobs import JobCancelled
from sqlarbiter.persistence.jobs import digest
from sqlarbiter.platform.run_contract import record


def find_case(case_id):
    for case in incidents():
        if case.case_id == case_id:
            return case
    raise ValueError("Unknown incident")


def case_version(case, engine=None):
    engine = engine or os.environ.get("SQLARBITER_SQL_ENGINE", "duckdb")
    files = [evaluation.__file__] + [
        evaluation.runtime_source(name) for name in evaluation.RUNTIME_FILES
    ]
    from sqlarbiter.platform import run_contract

    files += [__file__, run_contract.__file__]
    files += [
        Path(__file__).resolve().parents[4] / "pyproject.toml",
        Path(__file__).resolve().parents[3] / "requirements/runtime.txt",
    ]
    code_hash = hashlib.sha256()
    for file in files:
        code_hash.update(Path(file).read_bytes())
    return digest(
        {"incident": asdict(case), "engine": engine, "execution_code": code_hash.hexdigest()}
    )


def execute_one(store, job, telemetry=None):
    """Correlate queue, exported worker, billing lineage and trusted verifier."""
    request = job["request"]
    parent_id = request.get("parent_id")
    parent = store.get(parent_id) if parent_id else None
    budget_id = (
        (parent.get("result") or {}).get("run_record", {}).get("budget_run_id", parent_id)
        if parent
        else job["id"]
    )
    with evaluation.execution_identity(job["id"], budget_id):
        result = _execute_one(store, job, telemetry)
    mode = (
        "operator-revision"
        if request["kind"] in ("verification", "dbt_verification")
        else request["investigator"]
    )
    live = mode in ("anthropic", "langgraph")
    model = result["response"].get("model_run", {})
    known_usage = (
        model.get("status") == "completed"
        and not model.get("additional_billing_unknown")
        and all(
            type(model.get("usage", {}).get(k)) is int for k in ("input_tokens", "output_tokens")
        )
    )
    result["run_record"] = record(
        run_id=job["id"],
        budget_run_id=budget_id,
        parent_run_id=parent_id,
        task="dbt_repair" if request.get("project_id") else "incident_investigation",
        mode=mode,
        owner_scope="operator-workspace",
        input_sha256=request["input_version"],
        contract=result["contract"],
        result={"decision": result["response"].get("decision", {}), "grading": result["grading"]},
        verification_scope="independent-regression",
        verification_passed=result["grading"]["passed"],
        check_count=max(1, len(result["grading"].get("checks", []))),
        evidence_count=len(result["response"].get("trace", [])),
        producer_versions={
            "execution": request["input_version"],
            "contract": result["contract"].get("version", "unversioned"),
        },
        billing=("provider-reported" if known_usage else "unknown") if live else "not-used",
    )
    return result


def _execute_one(store, job, telemetry=None):
    request = job["request"]
    if request.get("project_id"):
        from sqlarbiter.workflows.dbt_service import execute

        return execute(store, job)
    engine = request.get("engine", os.environ.get("SQLARBITER_SQL_ENGINE", "duckdb"))
    case = find_case(request["case_id"])
    if case_version(case, engine) != request["input_version"]:
        raise ValueError("Incident or execution code changed; start a new investigation")
    root = store.root / "runs" / job["id"]
    root.mkdir(parents=True, exist_ok=False)
    if request["kind"] == "verification":
        parent = store.get(request["parent_id"])
        if parent["result_version"] != request["parent_version"]:
            raise ValueError("Parent investigation version changed")
        response = copy.deepcopy(parent["result"]["response"])
        response["decision"].update(
            candidate_sql=request["candidate_sql"],
            explanation="Operator-submitted candidate revision; independent checks below.",
        )
        response.pop("model_run", None)
        response.pop("agent_workflow", None)
        response.pop("graph_run", None)
    elif request["kind"] == "graph_resume":
        parent = store.get(request["parent_id"])
        if parent["status"] != "paused" or parent["result_version"] != request["parent_version"]:
            raise ValueError("Parent graph checkpoint version changed")
        original = store.root / "runs" / parent["id"] / "evidence"
        workspace = root / "evidence"
        shutil.copytree(original, workspace, ignore=shutil.ignore_patterns("graph-*.sqlite*"))
        # SQLite backup includes committed WAL pages; the immutable parent is never resumed in place.
        checkpoint_files = ["graph-receipts.sqlite"]
        if not os.environ.get("SQLARBITER_CHECKPOINT_DATABASE_URL"):
            checkpoint_files.insert(0, "graph-checkpoints.sqlite")
        for name in checkpoint_files:
            source = original / name
            if not source.is_file() or source.is_symlink():
                raise ValueError("Missing graph checkpoint")
            with sqlite3.connect("file:%s?mode=ro" % source, uri=True) as src:
                with sqlite3.connect(workspace / name) as dst:
                    src.backup(dst)
        options = {
            "mode": "langgraph",
            "continuation": {"guidance": request["guidance"]},
            "spend_root": store.root,
        }
        if os.environ.get("SQLARBITER_CHECKPOINT_DATABASE_URL"):
            options["checkpoint_thread_id"] = parent["id"]
        response = evaluation.run_worker(workspace, **options)
    else:
        workspace = evaluation.export_workspace(case, root / "evidence", engine)
        options = {"mode": request["investigator"], "spend_root": store.root}
        if os.environ.get("SQLARBITER_CHECKPOINT_DATABASE_URL"):
            options["checkpoint_thread_id"] = job["id"]
        response = evaluation.run_worker(workspace, **options)
    with (
        telemetry.span("verification", **{"arbiter.engine": engine}) if telemetry else nullcontext()
    ):
        grading = evaluation.grade(case, response, root / "grading", engine)
    return {
        "case_id": case.case_id,
        "engine": engine,
        "input_version": request["input_version"],
        "current_sql": case.current_sql,
        "contract": case.contract,
        "response": response,
        "grading": grading,
        "scope": "Known development scenario; not production verification or a held-out benchmark",
    }


def process_next(store, stopped=None):
    job = store.claim()
    if job is None:
        return False
    stop = threading.Event()

    def keep_lease():
        while not stop.wait(30):
            try:
                store.heartbeat(job)
            except (Conflict, OSError):
                return

    lease_thread = threading.Thread(target=keep_lease, daemon=True)
    lease_thread.start()

    def control():
        store.ensure_active(job)
        if stopped is not None and stopped.is_set():
            raise evaluation.ExecutionInterrupted("Worker shutdown requested")

    try:
        with evaluation.execution_scope(control):
            try:
                from sqlarbiter.platform.observability import Telemetry

                telemetry = Telemetry(
                    store.root / "telemetry" / job["id"], service="sqlarbiter-worker"
                )
                try:
                    with telemetry.root("job.execute", **{"arbiter.job_id": job["id"]}):
                        result = execute_one(store, job, telemetry)
                finally:
                    telemetry.close()
            except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired):
                # Raw worker output is not reflected into the browser/logs.
                control()
                store.finish(
                    job,
                    error="Investigation failed; check configuration and restart with a new run",
                )
            else:
                control()
                store.finish(job, result=result)
    except JobCancelled:
        store.acknowledge_cancel(job)
    except evaluation.ExecutionInterrupted:
        store.interrupt(job)
    except Conflict:
        # Cancellation may win between the final control check and publication.
        try:
            store.ensure_active(job)
        except JobCancelled:
            store.acknowledge_cancel(job)
        except Conflict:
            pass
    finally:
        stop.set()
        lease_thread.join(timeout=1)
    return True
