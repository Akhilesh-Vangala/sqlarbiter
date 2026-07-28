"""Transactional local job queue and append-only review API; no repair promotion."""
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class Conflict(ValueError):
    pass


class NotFound(ValueError):
    pass


class JobCancelled(Conflict):
    pass


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


class JobStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "jobs.sqlite"
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL,
                    request_json TEXT NOT NULL, request_hash TEXT NOT NULL,
                    status TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
                    owner TEXT, lease_until REAL, result_json TEXT, result_version TEXT,
                    error TEXT);
                CREATE TABLE IF NOT EXISTS reviews (
                    job_id TEXT PRIMARY KEY REFERENCES jobs(id), version TEXT NOT NULL,
                    action TEXT NOT NULL, actor TEXT NOT NULL, note TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES jobs(id), name TEXT NOT NULL,
                    actor TEXT NOT NULL, created_at REAL NOT NULL, payload_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS graph_continuations (
                    parent_id TEXT PRIMARY KEY REFERENCES jobs(id), child_id TEXT UNIQUE NOT NULL REFERENCES jobs(id));
                CREATE INDEX IF NOT EXISTS jobs_recent ON jobs(created_at DESC,id DESC);
                CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs(status,created_at,id);
                CREATE INDEX IF NOT EXISTS events_job_sequence ON events(job_id,sequence);
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL,
                    request_json TEXT NOT NULL, request_hash TEXT NOT NULL,
                    actor TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS workflow_jobs (
                    workflow_id TEXT NOT NULL REFERENCES workflows(id),
                    job_id TEXT UNIQUE NOT NULL REFERENCES jobs(id), position INTEGER NOT NULL,
                    PRIMARY KEY(workflow_id,position));
            """)

    @contextmanager
    def connection(self, write=False):
        connection = sqlite3.connect(str(self.database), timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.commit()
        except Exception:
            if write:
                connection.rollback()
            raise
        finally:
            connection.close()

    def _event(self, connection, job_id, name, actor, payload=None):
        connection.execute("INSERT INTO events(job_id,name,actor,created_at,payload_json) VALUES (?,?,?,?,?)",
                           (job_id, name, actor, time.time(), encoded(payload or {})))

    def enqueue(self, request, key, actor="operator"):
        with self.connection(write=True) as connection:
            existing = connection.execute("SELECT * FROM jobs WHERE idempotency_key=?", (key,)).fetchone()
            if existing:
                if existing["request_hash"] != digest(request):
                    raise Conflict("Idempotency key already belongs to a different request")
                return existing["id"], False
            if connection.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running','cancelling')").fetchone()[0] >= 16:
                raise Conflict("Queue is full; wait for active investigations")
            if request.get("parent_id"):
                parent = connection.execute("SELECT * FROM jobs WHERE id=?", (request["parent_id"],)).fetchone()
                if not parent:
                    raise NotFound("Parent investigation not found")
                resuming = request.get("kind") == "graph_resume"
                expected_status = "paused" if resuming else "completed"
                if parent["status"] != expected_status or parent["result_version"] != request.get("parent_version"):
                    raise Conflict("Parent result changed or is incomplete; refresh before verifying")
                result = json.loads(parent["result_json"])
                if resuming:
                    if (result["response"].get("graph_run", {}).get("status") != "paused"
                            or request.get("investigator") != "langgraph"):
                        raise Conflict("Only a paused graph can be continued")
                    if connection.execute("SELECT 1 FROM graph_continuations WHERE parent_id=?", (parent["id"],)).fetchone():
                        raise Conflict("This paused graph already has a continuation")
                elif result["response"]["decision"].get("status") != "candidate":
                    raise Conflict("Only a proposed repair can have a new candidate revision")
                if result["case_id"] != request["case_id"] or result["input_version"] != request["input_version"]:
                    raise Conflict("Candidate revision must use the same incident version")
            job_id, now = uuid.uuid4().hex, time.time()
            connection.execute("INSERT INTO jobs(id,idempotency_key,request_json,request_hash,status,created_at,updated_at) "
                               "VALUES (?,?,?,?,?,?,?)", (job_id, key, encoded(request), digest(request), "queued", now, now))
            self._event(connection, job_id, "queued", actor, {"kind": request["kind"]})
            if request.get("kind") == "graph_resume":
                connection.execute("INSERT INTO graph_continuations VALUES (?,?)", (request["parent_id"], job_id))
                self._event(connection, request["parent_id"], "continuation_created", actor, {"child_id": job_id})
        return job_id, True

    def claim(self, lease_seconds=300):
        """Expired work is interrupted, never automatically replayed/billed."""
        with self.connection(write=True) as connection:
            now = time.time()
            expired = connection.execute("SELECT id,status FROM jobs WHERE status IN ('running','cancelling') AND lease_until<?", (now,)).fetchall()
            for row in expired:
                status = "cancelled" if row["status"] == "cancelling" else "interrupted"
                connection.execute("UPDATE jobs SET status=?,updated_at=?,error=?,owner=NULL,lease_until=NULL WHERE id=?",
                    (status, now, "Cancellation finalized after worker lease expired" if status == "cancelled" else "Worker lease expired; create a new run to retry", row["id"]))
                self._event(connection, row["id"], status, "system", {"reason": "Worker lease expired"})
            row = connection.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at,id LIMIT 1").fetchone()
            if row is None:
                return None
            owner = uuid.uuid4().hex
            connection.execute("UPDATE jobs SET status='running',updated_at=?,owner=?,lease_until=? WHERE id=?",
                               (now, owner, now + lease_seconds, row["id"]))
            self._event(connection, row["id"], "running", "worker")
            return {"id": row["id"], "owner": owner, "request": json.loads(row["request_json"])}

    def heartbeat(self, job, lease_seconds=300):
        with self.connection(write=True) as connection:
            now = time.time()
            cursor = connection.execute(
                "UPDATE jobs SET lease_until=? WHERE id=? AND status IN ('running','cancelling') AND owner=? AND lease_until>=?",
                (now + lease_seconds, job["id"], job["owner"], now))
            if cursor.rowcount != 1:
                raise Conflict("Worker no longer owns this investigation")

    def progress(self, job, stage, status, details=None):
        self.ensure_active(job)
        with self.connection(write=True) as connection:
            row = connection.execute("SELECT status,owner,lease_until FROM jobs WHERE id=?", (job["id"],)).fetchone()
            if not row:
                raise Conflict("Worker no longer owns this investigation")
            if row["status"] == "cancelling":
                raise JobCancelled("Operator requested cancellation")
            if row["status"] != "running" or row["owner"] != job["owner"] or row["lease_until"] < time.time():
                raise Conflict("Worker no longer owns this investigation")
            connection.execute("UPDATE jobs SET updated_at=? WHERE id=?", (time.time(), job["id"]))
            self._event(connection, job["id"], "dbt_progress", "worker", {"stage": stage, "status": status, **(details or {})})

    def finish(self, job, result=None, error=None):
        with self.connection(write=True) as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
            if (not row or row["status"] != "running" or row["owner"] != job["owner"]
                    or row["lease_until"] < time.time()):
                raise Conflict("Worker no longer owns this investigation")
            status = "failed" if error else ("paused" if result and
                result.get("response", {}).get("graph_run", {}).get("status") == "paused" else "completed")
            version = digest(result) if result is not None else None
            connection.execute("UPDATE jobs SET status=?,updated_at=?,result_json=?,result_version=?,error=?,"
                               "owner=NULL,lease_until=NULL WHERE id=?",
                               (status, time.time(), encoded(result) if result is not None else None,
                                version, error, job["id"]))
            self._event(connection, job["id"], status, "worker", {"result_version": version})

    def _decode(self, row, include_result=True):
        value = dict(row)
        value["request"] = json.loads(value.pop("request_json"))
        result_json = value.pop("result_json")
        result = json.loads(result_json) if result_json else None
        # Never expose ownership tokens or idempotency/request hashes through the API.
        for name in ("owner", "lease_until", "idempotency_key", "request_hash"):
            value.pop(name)
        if include_result:
            value["result"] = result
        elif result:
            value["outcome"] = {"status": result["response"]["decision"].get("status"),
                                "passed": result["grading"]["passed"]}
        return value

    def get(self, job_id):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise NotFound("Investigation not found")
            value = self._decode(row)
            review = connection.execute("SELECT * FROM reviews WHERE job_id=?", (job_id,)).fetchone()
            value["review"] = dict(review) if review else None
            value["events"] = [dict(event) for event in connection.execute(
                "SELECT sequence,name,actor,created_at,payload_json FROM events WHERE job_id=? ORDER BY sequence", (job_id,))]
            for event in value["events"]:
                event["payload"] = json.loads(event.pop("payload_json"))
            return value

    def list(self):
        """Project summaries without hydrating complete evidence/results in Python."""
        with self.connection() as connection:
            return self._summaries(connection)

    def _summaries(self, connection, workflow_id=None):
        scope = " WHERE id IN (SELECT job_id FROM workflow_jobs WHERE workflow_id=?)" if workflow_id else ""
        rows = connection.execute("""
            SELECT id,request_json,status,created_at,updated_at,result_version,error,
                result_json IS NOT NULL AS has_result,
                json_extract(result_json,'$.response.decision.status') AS outcome_status,
                json_extract(result_json,'$.grading.passed') AS outcome_passed
            FROM jobs""" + scope + " ORDER BY created_at DESC,id DESC LIMIT 50", (workflow_id,) if workflow_id else ())
        summaries = []
        for row in rows:
            value = dict(row)
            value["request"] = json.loads(value.pop("request_json"))
            has_result = value.pop("has_result")
            status, passed = value.pop("outcome_status"), value.pop("outcome_passed")
            if has_result:
                value["outcome"] = {"status": status, "passed": bool(passed)}
            summaries.append(value)
        return summaries

    def ensure_active(self, job):
        with self.connection() as connection:
            row = connection.execute("SELECT status,owner,lease_until FROM jobs WHERE id=?", (job["id"],)).fetchone()
            if row and row["owner"] == job["owner"] and row["status"] == "cancelling":
                raise JobCancelled("Operator requested cancellation")
            if not row or row["owner"] != job["owner"] or row["status"] != "running" or row["lease_until"] < time.time():
                raise Conflict("Worker no longer owns this investigation")

    def _cancel_row(self, connection, row, actor, reason):
        if row["status"] in ("cancelled", "cancelling"):
            return
        if row["status"] not in ("queued", "running"):
            raise Conflict("Only queued or running work can be cancelled")
        status = "cancelled" if row["status"] == "queued" else "cancelling"
        connection.execute("UPDATE jobs SET status=?,updated_at=? WHERE id=?", (status, time.time(), row["id"]))
        self._event(connection, row["id"], "cancelled" if status == "cancelled" else "cancellation_requested", actor,
                    {"reason": reason, "provider_billing_unknown": row["status"] == "running" and json.loads(row["request_json"]).get("investigator") in ("anthropic", "langgraph")})

    def cancel(self, job_id, actor="operator", reason="Operator requested cancellation"):
        with self.connection(write=True) as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise NotFound("Investigation not found")
            self._cancel_row(connection, row, actor, reason)
        return self.get(job_id)

    def acknowledge_cancel(self, job):
        with self.connection(write=True) as connection:
            row = connection.execute("SELECT status,owner FROM jobs WHERE id=?", (job["id"],)).fetchone()
            if row and row["status"] == "cancelled":
                return
            if not row or row["owner"] != job["owner"] or row["status"] != "cancelling":
                raise Conflict("Cancellation ownership changed")
            connection.execute("UPDATE jobs SET status='cancelled',owner=NULL,lease_until=NULL,updated_at=? WHERE id=?", (time.time(), job["id"]))
            self._event(connection, job["id"], "cancelled", "worker")

    def interrupt(self, job):
        with self.connection(write=True) as connection:
            row = connection.execute("SELECT status,owner FROM jobs WHERE id=?", (job["id"],)).fetchone()
            if not row or row["owner"] != job["owner"] or row["status"] not in ("running", "cancelling"):
                raise Conflict("Worker ownership changed")
            status = "cancelled" if row["status"] == "cancelling" else "interrupted"
            connection.execute("UPDATE jobs SET status=?,owner=NULL,lease_until=NULL,updated_at=?,error=? WHERE id=?",
                (status, time.time(), "Worker stopped before completion; no automatic retry", job["id"]))
            self._event(connection, job["id"], status, "worker", {"reason": "Worker shutdown"})

    def enqueue_workflow(self, request, key, actor):
        items = request.get("jobs", [])
        if not 1 <= len(items) <= 6 or len({item["case_id"] for item in items}) != len(items):
            raise Conflict("A workflow requires 1–6 unique incidents")
        with self.connection(write=True) as connection:
            prior = connection.execute("SELECT id,request_hash FROM workflows WHERE idempotency_key=?", (key,)).fetchone()
            if prior:
                if prior["request_hash"] != digest(request):
                    raise Conflict("Idempotency key belongs to a different workflow")
                return prior["id"], False
            active = connection.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running','cancelling')").fetchone()[0]
            if active + len(items) > 16:
                raise Conflict("Queue cannot admit this entire workflow; no runs were created")
            identity, now = uuid.uuid4().hex, time.time()
            connection.execute("INSERT INTO workflows VALUES (?,?,?,?,?,?)", (identity, key, encoded(request), digest(request), actor, now))
            for position, item in enumerate(items):
                job_id = uuid.uuid4().hex
                connection.execute("INSERT INTO jobs(id,idempotency_key,request_json,request_hash,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                    (job_id, "workflow:" + identity + ":" + str(position), encoded(item), digest(item), "queued", now, now))
                connection.execute("INSERT INTO workflow_jobs VALUES (?,?,?)", (identity, job_id, position))
                self._event(connection, job_id, "queued", actor, {"kind": item["kind"], "workflow_id": identity})
        return identity, True

    def _workflow(self, connection, row):
        if row is None:
            raise NotFound("Workflow not found")
        request = json.loads(row["request_json"])
        summaries = self._summaries(connection, row["id"])
        positions = {item["job_id"]: item["position"] for item in connection.execute("SELECT job_id,position FROM workflow_jobs WHERE workflow_id=?", (row["id"],))}
        summaries.sort(key=lambda item: positions[item["id"]])
        running = sum(item["status"] in ("running", "cancelling") for item in summaries)
        queued = sum(item["status"] == "queued" for item in summaries)
        terminal = sum(item["status"] in ("completed", "failed", "interrupted", "cancelled") for item in summaries)
        resolved = sum(item["status"] == "completed" and item.get("outcome", {}).get("passed", False) and item["outcome"]["status"] in ("candidate", "no_change") for item in summaries)
        attention = sum(item["status"] in ("failed", "interrupted", "paused") or (item["status"] == "completed" and (not item.get("outcome", {}).get("passed") or item["outcome"]["status"] not in ("candidate", "no_change"))) for item in summaries)
        cancelled = sum(item["status"] == "cancelled" for item in summaries)
        return {"id": row["id"], "name": request["name"], "actor": row["actor"], "created_at": row["created_at"],
            "investigator": request["jobs"][0]["investigator"], "engine": request["jobs"][0]["engine"], "jobs": summaries,
            "counts": {"total": len(summaries), "terminal": terminal, "resolved": resolved, "attention": attention, "cancelled": cancelled, "queued": queued, "running": running},
            "status": "running" if running else "queued" if queued else "needs_attention" if attention else "cancelled" if cancelled == len(summaries) else "completed"}

    def get_workflow(self, workflow_id):
        with self.connection() as connection:
            return self._workflow(connection, connection.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone())

    def list_workflows(self):
        with self.connection() as connection:
            return [self._workflow(connection, row) for row in connection.execute("SELECT * FROM workflows ORDER BY created_at DESC,id DESC LIMIT 20")]

    def cancel_workflow(self, workflow_id, actor, reason):
        with self.connection(write=True) as connection:
            if connection.execute("SELECT 1 FROM workflows WHERE id=?", (workflow_id,)).fetchone() is None:
                raise NotFound("Workflow not found")
            for row in connection.execute("SELECT * FROM jobs WHERE id IN (SELECT job_id FROM workflow_jobs WHERE workflow_id=?) AND status IN ('queued','running')", (workflow_id,)).fetchall():
                self._cancel_row(connection, row, actor, reason)
        return self.get_workflow(workflow_id)

    def stats(self):
        with self.connection() as connection:
            row = connection.execute("""
                SELECT COUNT(*) AS completed,
                    COALESCE(SUM(CASE WHEN json_extract(result_json,'$.grading.passed')=1
                        AND json_extract(result_json,'$.response.decision.status')='candidate'
                        THEN 1 ELSE 0 END),0) AS verified_candidates
                FROM jobs WHERE status='completed'
            """).fetchone()
            return dict(row)

    def review(self, job_id, version, action, actor, note):
        if action not in ("approved", "rejected"):
            raise ValueError("Unknown review action")
        with self.connection(write=True) as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise NotFound("Investigation not found")
            if row["status"] != "completed" or row["result_version"] != version:
                raise Conflict("Review version is stale or the investigation is incomplete")
            result = json.loads(row["result_json"])
            if result.get("dbt"):
                from vdir.workflows.dbt_service import validate_result
                validate_result(result, require_passed=action == "approved")
            if result["response"]["decision"].get("status") != "candidate":
                raise Conflict("There is no repair candidate to review")
            if action == "approved" and not result["grading"]["passed"]:
                raise Conflict("A candidate that failed verification cannot be approved")
            prior = connection.execute("SELECT * FROM reviews WHERE job_id=?", (job_id,)).fetchone()
            if prior:
                if (prior["version"], prior["action"], prior["actor"], prior["note"]) != (version, action, actor, note):
                    raise Conflict("This result already has an immutable review")
            else:
                connection.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?)",
                                   (job_id, version, action, actor, note, time.time()))
                self._event(connection, job_id, "review_" + action, actor, {"version": version, "note": note})
        return self.get(job_id)
