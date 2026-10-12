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

from . import evaluation
from .cases import incidents
from .jobs import Conflict, JobCancelled, digest


def find_case(case_id):
    for case in incidents():
        if case.case_id == case_id:
            return case
    raise ValueError("Unknown incident")


def case_version(case, engine=None):
    engine = engine or os.environ.get("VDIR_SQL_ENGINE", "duckdb")
    files = [evaluation.__file__] + [evaluation.runtime_source(name) for name in evaluation.RUNTIME_FILES]
    files += [evaluation.RUNTIME.parent / name for name in ("pyproject.toml", "requirements-web.txt")]
    code_hash = hashlib.sha256()
    for file in files:
        code_hash.update(Path(file).read_bytes())
    return digest({"incident": asdict(case), "engine": engine, "execution_code": code_hash.hexdigest()})


def execute_one(store, job, telemetry=None):
    request = job["request"]
    engine = request.get("engine", os.environ.get("VDIR_SQL_ENGINE", "duckdb"))
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
        response["decision"].update(candidate_sql=request["candidate_sql"],
                                     explanation="Operator-submitted candidate revision; independent checks below.")
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
        for name in ("graph-checkpoints.sqlite", "graph-receipts.sqlite"):
            source = original / name
            if not source.is_file() or source.is_symlink():
                raise ValueError("Missing graph checkpoint")
            with sqlite3.connect("file:%s?mode=ro" % source, uri=True) as src:
                with sqlite3.connect(workspace / name) as dst:
                    src.backup(dst)
        response = evaluation.run_worker(workspace, mode="langgraph", continuation={"guidance": request["guidance"]}, spend_root=store.root)
    else:
        workspace = evaluation.export_workspace(case, root / "evidence", engine)
        response = evaluation.run_worker(workspace, mode=request["investigator"], spend_root=store.root)
    with telemetry.span("verification", **{"vdir.engine": engine}) if telemetry else nullcontext():
        grading = evaluation.grade(case, response, root / "grading", engine)
    return {"case_id": case.case_id, "engine": engine, "input_version": request["input_version"],
            "current_sql": case.current_sql, "contract": case.contract,
            "response": response, "grading": grading,
            "scope": "Known development scenario; not production verification or a held-out benchmark"}


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
                from .observability import Telemetry
                telemetry = Telemetry(store.root / "telemetry" / job["id"], service="vdir-worker")
                try:
                    with telemetry.root("job.execute", **{"vdir.job_id": job["id"]}):
                        result = execute_one(store, job, telemetry)
                finally:
                    telemetry.close()
            except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired):
                # Raw worker output is not reflected into the browser/logs.
                control()
                store.finish(job, error="Investigation failed; check configuration and restart with a new run")
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
