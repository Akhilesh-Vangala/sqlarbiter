"""Independent execution service used by queue workers, not HTTP request handlers."""
import copy
import hashlib
import os
from contextlib import nullcontext
import subprocess
import threading
from dataclasses import asdict
from pathlib import Path

from . import evaluation
from .cases import incidents
from .jobs import Conflict, digest


def find_case(case_id):
    for case in incidents():
        if case.case_id == case_id:
            return case
    raise ValueError("Unknown incident")


def case_version(case, engine=None):
    engine = engine or os.environ.get("VDIR_SQL_ENGINE", "duckdb")
    files = [evaluation.__file__] + [evaluation.RUNTIME / name for name in evaluation.RUNTIME_FILES]
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
    else:
        workspace = evaluation.export_workspace(case, root / "evidence", engine)
        response = evaluation.run_worker(workspace, mode=request["investigator"])
    with telemetry.span("verification", **{"vdir.engine": engine}) if telemetry else nullcontext():
        grading = evaluation.grade(case, response, root / "grading", engine)
    return {"case_id": case.case_id, "engine": engine, "input_version": request["input_version"],
            "current_sql": case.current_sql, "contract": case.contract,
            "response": response, "grading": grading,
            "scope": "Known development scenario; not production verification or a held-out benchmark"}


def process_next(store):
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
    try:
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
            store.finish(job, error="Investigation failed; check configuration and restart with a new run")
        else:
            store.finish(job, result=result)
    finally:
        stop.set()
        lease_thread.join(timeout=1)
    return True
