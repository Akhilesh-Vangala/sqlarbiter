"""Trusted evaluator: export evidence only, run worker, independently grade outcomes."""
import json
import os
import re
import shutil
import sqlite3
import subprocess
import signal
import tempfile
import time
from contextvars import ContextVar
from contextlib import contextmanager
import sys
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from vdir.domain.cases import incidents

RUNTIME = Path(__file__).resolve().parents[4] / "agent" / "investigator"
RUNTIME_FILES = ("tools.py", "baseline.py", "model.py", "graph.py", "agent_policy.py", "worker.py", "engines.py", "telemetry.py", "spending.py")


def runtime_source(name):
    return (Path(__file__).resolve().parents[1] / "platform/spending.py") if name == "spending.py" else RUNTIME / name


def materialize(source, path, engine="sqlite"):
    schema = {}
    if engine == "duckdb":
        import duckdb
        conn = duckdb.connect(str(path))
    elif engine == "sqlite":
        conn = sqlite3.connect(str(path))
    else:
        raise ValueError("Unknown analytical engine")
    try:
        for table, (definitions, rows) in source.tables.items():
            if not re.fullmatch(r"[a-z][a-z_]*", table):
                raise ValueError("Invalid internal table name")
            columns = [definition.split()[0] for definition in definitions]
            if any(not re.fullmatch(r"[a-z][a-z_]*", name) for name in columns):
                raise ValueError("Invalid internal column name")
            conn.execute("CREATE TABLE %s (%s)" % (table, ", ".join(definitions)))
            if rows:
                conn.executemany("INSERT INTO %s VALUES (%s)" %
                                 (table, ",".join("?" for _ in columns)), rows)
            schema[table] = {"columns": columns, "definitions": list(definitions)}
        conn.commit()
    finally:
        conn.close()
    return schema


def export_workspace(case, destination, engine="sqlite"):
    """Only current snapshot is investigator-visible; regressions stay with evaluator."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    source = case.sources[0]
    schema = materialize(source, destination / ("source.duckdb" if engine == "duckdb" else "source.sqlite"), engine)
    manifest = {"engine": engine, "snapshot_id": source.snapshot_id, "contract": case.contract,
                "current_sql": case.current_sql, "lineage": case.lineage,
                "changes": case.changes}
    if "project_context" in case.contract:
        manifest["project"] = case.contract["project_context"]
    (destination / "incident.json").write_text(json.dumps(manifest, indent=2))
    (destination / "schema.json").write_text(json.dumps(schema, indent=2))
    runtime = destination / "runtime"
    runtime.mkdir()
    for name in RUNTIME_FILES:
        shutil.copyfile(runtime_source(name), runtime / name)
    return destination


class InvestigatorError(RuntimeError):
    def __init__(self, response):
        super().__init__("Investigator execution failed; see saved trace and model metadata")
        self.response = response


EXECUTION_CONTROL = ContextVar("vdir_execution_control", default=None)
WORKER_DEPENDENCIES = ContextVar("vdir_worker_dependencies", default=())
WORKER_RUN = ContextVar("vdir_worker_run", default=(None, None))


@contextmanager
def execution_identity(run_id, budget_run_id):
    from vdir.platform.run_contract import identifier
    token = WORKER_RUN.set((identifier(run_id), identifier(budget_run_id)))
    try:
        yield
    finally:
        WORKER_RUN.reset(token)


@contextmanager
def worker_dependencies(paths):
    """Trusted deployment dependency roots, never user input or application source."""
    token = WORKER_DEPENDENCIES.set(tuple(str(Path(p).resolve()) for p in paths))
    try:
        yield
    finally:
        WORKER_DEPENDENCIES.reset(token)


class ExecutionInterrupted(RuntimeError):
    pass


@contextmanager
def execution_scope(control):
    token = EXECUTION_CONTROL.set(control)
    try:
        yield
    finally:
        EXECUTION_CONTROL.reset(token)


def _stop_process(process):
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=3)
    except ProcessLookupError:
        process.wait(timeout=3)


def run_worker(workspace, *, mode="baseline", requests=None, continuation=None, spend_root=None,
               checkpoint_thread_id=None, run_id=None, budget_run_id=None):
    workspace = Path(workspace).resolve()
    environment = {"PATH": os.defpath, "PYTHONIOENCODING": "utf-8"}
    from vdir.platform.run_contract import identifier
    inherited_run, inherited_budget = WORKER_RUN.get()
    run_id, budget_run_id = run_id or inherited_run, budget_run_id or inherited_budget
    if run_id:
        environment["VDIR_RUN_ID"] = identifier(run_id)
    if budget_run_id:
        environment["VDIR_BUDGET_RUN_ID"] = identifier(budget_run_id)
    for name in ("VDIR_OTLP_ENDPOINT", "VDIR_TRACEPARENT", "VDIR_CHECKPOINT_DATABASE_URL"):
        if os.environ.get(name):
            environment[name] = os.environ[name]
    if checkpoint_thread_id:
        environment["VDIR_CHECKPOINT_THREAD_ID"] = checkpoint_thread_id
    from opentelemetry import trace
    context = trace.get_current_span().get_span_context()
    if context.is_valid:
        environment["VDIR_TRACEPARENT"] = "00-%032x-%016x-%02x" % (context.trace_id, context.span_id, int(context.trace_flags))
    if continuation is not None and (mode != "langgraph" or requests is not None):
        raise ValueError("Only a graph investigator supports continuation")
    if mode in ("anthropic", "langgraph"):
        from vdir.platform.spending import configuration
        environment.update(configuration(spend_root))
        for name in ("ANTHROPIC_API_KEY", "VDIR_ANTHROPIC_MODEL"):
            if not os.environ.get(name):
                raise ValueError("Set ANTHROPIC_API_KEY and VDIR_ANTHROPIC_MODEL locally")
            environment[name] = os.environ[name]
    control = EXECUTION_CONTROL.get()
    if control:
        control()
    command = [sys.executable, "-I", "-B", str(workspace / "runtime" / "worker.py"),
         "--workspace", str(workspace), "--mode", mode] + (["--resume"] if continuation is not None else [])
    dependency_paths = WORKER_DEPENDENCIES.get()
    if dependency_paths:
        # -I intentionally ignores PYTHONPATH; Vercel vendors packages outside
        # the base interpreter's site-packages. Add only trusted third-party
        # roots while preserving the exported runtime/source boundary.
        bootstrap = "import sys,runpy;sys.path.extend(" + repr(list(dependency_paths)) + ");sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')"
        command = [sys.executable, "-I", "-B", "-c", bootstrap] + command[3:]
    timeout = 270 if mode in ("anthropic", "langgraph") else 30
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as input_file, tempfile.TemporaryFile() as output_file, tempfile.TemporaryFile() as error_file:
        input_file.write(json.dumps(continuation) if continuation is not None else requests or "")
        input_file.seek(0)
        process = subprocess.Popen(command, stdin=input_file, stdout=output_file, stderr=error_file,
            cwd=str(workspace), env=environment, start_new_session=os.name == "posix")
        started = time.monotonic()
        try:
            while process.poll() is None:
                if control:
                    control()
                if time.monotonic() - started >= timeout:
                    raise subprocess.TimeoutExpired(command, timeout)
                if output_file.tell() > 2000000 or error_file.tell() > 2000000:
                    raise InvestigatorError({"decision": {}, "trace": [], "error": "Worker output budget exceeded"})
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
            if control:
                control()
            if output_file.tell() > 2000000 or error_file.tell() > 2000000:
                raise InvestigatorError({"decision": {}, "trace": [], "error": "Worker output budget exceeded"})
            output_file.seek(0)
            stdout = output_file.read(2000001).decode("utf-8")
        finally:
            _stop_process(process)
    if process.returncode:
        try:
            response = json.loads(stdout)
        except (ValueError, TypeError):
            response = {"decision": {}, "trace": [], "error": "Worker exited without a valid response"}
        response.setdefault("decision", {})
        response.setdefault("trace", [])
        (workspace / "failed-investigation.json").write_text(json.dumps(response, indent=2))
        raise InvestigatorError(response)
    if mode == "rpc":
        return [json.loads(line) for line in stdout.splitlines()]
    return json.loads(stdout)


def reference_outcome(case, source):
    """Independent source-level computation. Never included in exported runtime."""
    metric = case.contract["metric"]
    totals = defaultdict(int)
    if metric == "canonical_payment_events":
        events, conflicts = {}, set()
        for delivery, event, customer, occurred, received, status, amount in source.tables["stg_payment_deliveries"][1]:
            payload = (customer, occurred, status, amount)
            if event in events and events[event] != payload:
                conflicts.add(event)
            events[event] = payload
        if conflicts:
            return {"status": "needs_information", "affected_ids": sorted(conflicts), "required_fields": ["authoritative_event_payload"]}
        return {"status": "repairable", "rows": {(event, *payload[:-1]): payload[-1] for event, payload in events.items()}}
    if metric == "completed_item_revenue":
        orders = {row[0]: row[1:] for row in source.tables["orders"][1]}
        if len(orders) != len(source.tables["orders"][1]):
            raise ValueError("Ambiguous order identity")
        products = {}
        seen_versions = set()
        for product_id, version, category in source.tables["product_versions"][1]:
            if (product_id, version) in seen_versions:
                raise ValueError("Ambiguous product version")
            seen_versions.add((product_id, version))
            if product_id not in products or version > products[product_id][0]:
                products[product_id] = (version, category)
        seen_items = set()
        for item_id, order_id, product_id, amount in source.tables["order_items"][1]:
            if item_id in seen_items or type(amount) is not int or amount < 0:
                raise ValueError("Invalid item source")
            seen_items.add(item_id)
            day, status = orders[order_id]
            if status == "completed":
                totals[(day, products[product_id][1])] += amount
    elif metric == "unique_event_revenue":
        events = {}
        conflicts = set()
        seen_deliveries = set()
        for delivery_id, event_id, customer, occurred_at, amount in source.tables["event_deliveries"][1]:
            if delivery_id in seen_deliveries or type(amount) is not int or amount < 0:
                raise ValueError("Invalid delivery source")
            seen_deliveries.add(delivery_id)
            timestamp = datetime.fromisoformat(occurred_at)
            if timestamp.utcoffset() != timedelta(0):
                raise ValueError("Event source contract requires explicit UTC timestamps")
            payload = (customer, occurred_at, amount)
            if event_id in events and events[event_id] != payload:
                conflicts.add(event_id)
            events[event_id] = payload
        if conflicts:
            return {"status": "needs_information", "affected_ids": sorted(conflicts),
                    "required_fields": ["authoritative_event_payload"]}
        for customer, occurred_at, amount in events.values():
            totals[(datetime.fromisoformat(occurred_at).date().isoformat(),)] += amount
    elif metric == "utc_daily_event_count":
        unknown = []
        seen = set()
        for event_id, local_timestamp, offset in source.tables["events"][1]:
            if event_id in seen:
                raise ValueError("Ambiguous event identity")
            seen.add(event_id)
            local = datetime.fromisoformat(local_timestamp)
            if local.tzinfo is not None:
                raise ValueError("Expected source-local timestamp without implicit timezone")
            if offset is None:
                unknown.append(event_id)
            elif type(offset) is not int or not -720 <= offset <= 840:
                raise ValueError("Invalid explicit UTC offset")
            else:
                day = (local - timedelta(minutes=offset)).date().isoformat()
                totals[(day,)] += 1
        if unknown:
            return {"status": "needs_information", "affected_ids": sorted(unknown),
                    "required_fields": ["utc_offset_minutes"]}
    elif metric == "tagged_item_revenue":
        tagged = {row[0] for row in source.tables["item_tags"][1]}
        seen = set()
        for item_id, day, status, amount in source.tables["purchases"][1]:
            if item_id in seen or type(amount) is not int:
                raise ValueError("Invalid purchase identity or amount")
            seen.add(item_id)
            if status == "completed" and item_id in tagged:
                totals[(day,)] += amount
    elif metric == "customer_completed_revenue":
        customers = [row[0] for row in source.tables["customers"][1]]
        if len(set(customers)) != len(customers):
            raise ValueError("Ambiguous customer identity")
        for customer in customers:
            totals[(customer,)] = 0
        seen = set()
        for order_id, customer, status, amount in source.tables["customer_orders"][1]:
            if order_id in seen or customer not in customers or type(amount) is not int:
                raise ValueError("Invalid customer order")
            seen.add(order_id)
            if status == "completed":
                totals[(customer,)] += amount
    elif metric == "eligible_transaction_revenue":
        seen = set()
        for identity, day, status, amount in source.tables["transactions"][1]:
            if identity in seen or type(amount) is not int:
                raise ValueError("Invalid transaction")
            seen.add(identity)
            if status == case.contract["rules"]["eligible_status"]:
                totals[(day,)] += amount
    else:
        raise ValueError("Unknown reference metric")
    return {"status": "repairable", "rows": dict(totals)}


def _execute(source, contract, sql, destination, engine="sqlite"):
    """Use the same evidence runner restrictions without giving it reference truth."""
    case_stub = type("SourceCase", (), {
        "sources": (source,), "contract": contract, "current_sql": sql,
        "lineage": {}, "changes": (),
    })()
    workspace = export_workspace(case_stub, destination, engine)
    replies = run_worker(workspace, mode="rpc", requests=json.dumps(
        {"method": "query", "params": {"sql": sql}}) + "\n")
    return replies[0]


def _matches(result, contract, expected):
    if not result.get("ok"):
        return False
    payload = result["result"]
    if payload.get("truncated") or payload["columns"] != contract["output"]:
        return False
    actual = {}
    for row in payload["rows"]:
        if len(row) != len(contract["output"]):
            return False
        key, value = tuple(row[:-1]), row[-1]
        if any(not isinstance(part, str) for part in key) or type(value) is not int or key in actual:
            return False
        actual[key] = value
    return actual == expected


def grade(case, response, scratch, engine="sqlite"):
    if not isinstance(response, dict) or not isinstance(response.get("decision"), dict):
        return {"passed": False, "reason": "Invalid decision envelope"}
    decision = response.get("decision", {})
    trace = response.get("trace", [])
    references = decision.get("evidence_ids", [])
    if not isinstance(trace, list) or not trace or len(trace) > 24:
        return {"passed": False, "reason": "Invalid tool trace"}
    if not isinstance(references, list) or any(not isinstance(ref, str) for ref in references):
        return {"passed": False, "reason": "Invalid evidence reference types"}
    try:
        requests = "".join(json.dumps({"method": record["method"], "params": record["params"]})
                           + "\n" for record in trace)
        replay_space = export_workspace(case, Path(scratch) / "trace-replay", engine)
        replayed = run_worker(replay_space, mode="rpc", requests=requests)
    except (KeyError, TypeError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        return {"passed": False, "reason": "Malformed or unreplayable tool trace"}
    if replayed != trace:
        return {"passed": False, "reason": "Evidence trace does not match source replay"}
    valid_ids = {record["evidence_id"] for record in trace if record.get("ok")}
    if not references or not set(references).issubset(valid_ids):
        return {"passed": False, "reason": "Missing or invalid evidence references"}
    truth = reference_outcome(case, case.sources[0])
    status = decision.get("status")
    if status == "no_change" and decision.get("candidate_sql"):
        return {"passed": False, "reason": "No-change decision cannot include a patch"}
    if truth["status"] == "needs_information":
        passed = (status == "needs_information" and not decision.get("candidate_sql")
                  and decision.get("affected_ids") == truth["affected_ids"]
                  and decision.get("required_fields") == truth["required_fields"])
        return {"passed": passed, "reason": "Clarification must name the missing authoritative evidence"}
    if status not in ("candidate", "no_change"):
        return {"passed": False, "reason": "Repairable input requires a checked candidate or valid no-change"}
    sql = decision.get("candidate_sql") if status == "candidate" else case.current_sql
    if not isinstance(sql, str):
        return {"passed": False, "reason": "Missing candidate SQL"}
    checks = []
    current_correct = True
    for index, source in enumerate(case.sources):
        expected = reference_outcome(case, source)
        if expected["status"] != "repairable":
            raise ValueError("Reference scenario mixes repairable and unavailable-information outcomes")
        reply = _execute(source, case.contract, sql, Path(scratch) / ("candidate-%d" % index), engine)
        checks.append({"snapshot_id": source.snapshot_id,
                       "passed": _matches(reply, case.contract, expected["rows"])})
        current = _execute(source, case.contract, case.current_sql,
                           Path(scratch) / ("current-%d" % index), engine)
        current_correct = current_correct and _matches(current, case.contract, expected["rows"])
    justified_status = (status == "no_change") if current_correct else (status == "candidate")
    return {"passed": all(check["passed"] for check in checks) and justified_status,
            "checks": checks, "reason": "Independent source references and regression snapshots"}


def evaluate_all(output, mode="baseline", engine="sqlite"):
    if mode not in ("baseline", "anthropic", "langgraph"):
        raise ValueError("Unknown investigator mode")
    if mode in ("anthropic", "langgraph") and any(not os.environ.get(name) for name in
                                  ("ANTHROPIC_API_KEY", "VDIR_ANTHROPIC_MODEL")):
        raise ValueError("Set ANTHROPIC_API_KEY and VDIR_ANTHROPIC_MODEL locally")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {"scope": "six known development scenarios; not a held-out benchmark",
              "investigator": mode, "engine": engine,
              "cases": []}
    for case in incidents():
        case_root = output / case.case_id
        case_root.mkdir()
        workspace = export_workspace(case, case_root / "evidence", engine)
        try:
            response = run_worker(workspace, mode=mode)
            result = grade(case, response, case_root / "grading", engine)
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            # Save failures rather than treating missing outcomes as success.
            response = error.response if isinstance(error, InvestigatorError) else {"decision": {}, "trace": [], "error": "Worker timed out"}
            result = {"passed": False, "reason": "Investigator execution failed"}
        record = {"case_id": case.case_id, "decision": response["decision"],
                  "grading": result, "tool_calls": len(response["trace"])}
        if "model_run" in response:
            record["model_run"] = response["model_run"]
        (case_root / "trace.json").write_text(json.dumps(response, indent=2))
        report["cases"].append(record)
    report["passed"] = all(case["grading"]["passed"] for case in report["cases"])
    (output / "report.json").write_text(json.dumps(report, indent=2))
    return report
