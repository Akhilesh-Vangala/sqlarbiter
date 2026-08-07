"""PostgreSQL queue adapter with fenced claims and multi-worker-safe admission."""

import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from sqlarbiter.persistence.jobs import Conflict
from sqlarbiter.persistence.jobs import JobCancelled
from sqlarbiter.persistence.jobs import JobStore
from sqlarbiter.persistence.jobs import NotFound
from sqlarbiter.persistence.jobs import digest
from sqlarbiter.persistence.jobs import encoded
from sqlarbiter.persistence.migrations import SCHEMA_VERSION


class _Row(dict):
    """Retain the mapping and positional access used by the SQLite adapter."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class _Cursor:
    def __init__(self, cursor):
        self.cursor = cursor

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def _row(self, value):
        return _Row(value) if value is not None else None

    def fetchone(self):
        return self._row(self.cursor.fetchone())

    def fetchall(self):
        return [self._row(value) for value in self.cursor.fetchall()]

    def __iter__(self):
        for value in self.cursor:
            yield self._row(value)


class _Connection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, parameters=()):
        # Owned queries use DB-API qmark placeholders and contain no literal question marks.
        return _Cursor(self.connection.execute(statement.replace("?", "%s"), parameters))


class PostgresJobStore(JobStore):
    """The JobStore contract backed by PostgreSQL instead of a local SQLite file."""

    def __init__(self, root, database_url, pool_size=None):
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database_url = database_url
        size = pool_size or int(os.getenv("SQLARBITER_DATABASE_POOL_SIZE", "5"))
        if size < 1 or size > 32:
            raise ValueError("SQLARBITER_DATABASE_POOL_SIZE must be between 1 and 32")
        self.pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=size,
            kwargs={"row_factory": dict_row},
            open=True,
        )
        self.pool.wait(timeout=10)
        with self.connection() as connection:
            row = connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
            ).fetchone()
        if not row or row["version"] != SCHEMA_VERSION:
            self.close()
            raise RuntimeError(
                "PostgreSQL schema is missing or incompatible; run python -m sqlarbiter.persistence.migrations"
            )

    def close(self):
        pool = getattr(self, "pool", None)
        if pool is not None:
            pool.close()

    @contextmanager
    def connection(self, write=False):
        with self.pool.connection() as connection:
            with connection.transaction():
                yield _Connection(connection)

    @staticmethod
    def _admission_lock(connection):
        # Serializes queue-cap admission while idempotency keys use their own lock.
        connection.execute("SELECT pg_advisory_xact_lock(812947301)")

    def enqueue(self, request, key, actor="operator"):
        with self.connection(write=True) as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(?,0))", (key,))
            self._admission_lock(connection)
            existing = connection.execute(
                "SELECT * FROM jobs WHERE idempotency_key=?", (key,)
            ).fetchone()
            if existing:
                if existing["request_hash"] != digest(request):
                    raise Conflict("Idempotency key already belongs to a different request")
                return existing["id"], False
            if (
                connection.execute(
                    "SELECT COUNT(*) AS count FROM jobs WHERE status IN ('queued','running','cancelling')"
                ).fetchone()[0]
                >= 16
            ):
                raise Conflict("Queue is full; wait for active investigations")
            if request.get("parent_id"):
                parent = connection.execute(
                    "SELECT * FROM jobs WHERE id=? FOR UPDATE", (request["parent_id"],)
                ).fetchone()
                if not parent:
                    raise NotFound("Parent investigation not found")
                resuming = request.get("kind") == "graph_resume"
                expected_status = "paused" if resuming else "completed"
                if parent["status"] != expected_status or parent["result_version"] != request.get(
                    "parent_version"
                ):
                    raise Conflict(
                        "Parent result changed or is incomplete; refresh before verifying"
                    )
                result = json.loads(parent["result_json"])
                if resuming:
                    if (
                        result["response"].get("graph_run", {}).get("status") != "paused"
                        or request.get("investigator") != "langgraph"
                    ):
                        raise Conflict("Only a paused graph can be continued")
                    if connection.execute(
                        "SELECT 1 FROM graph_continuations WHERE parent_id=?", (parent["id"],)
                    ).fetchone():
                        raise Conflict("This paused graph already has a continuation")
                elif result["response"]["decision"].get("status") != "candidate":
                    raise Conflict("Only a proposed repair can have a new candidate revision")
                if (
                    result["case_id"] != request["case_id"]
                    or result["input_version"] != request["input_version"]
                ):
                    raise Conflict("Candidate revision must use the same incident version")
            job_id, now = uuid.uuid4().hex, time.time()
            connection.execute(
                "INSERT INTO jobs(id,idempotency_key,request_json,request_hash,status,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (job_id, key, encoded(request), digest(request), "queued", now, now),
            )
            self._event(connection, job_id, "queued", actor, {"kind": request["kind"]})
            if request.get("kind") == "graph_resume":
                connection.execute(
                    "INSERT INTO graph_continuations(parent_id,child_id) VALUES (?,?)",
                    (request["parent_id"], job_id),
                )
                self._event(
                    connection,
                    request["parent_id"],
                    "continuation_created",
                    actor,
                    {"child_id": job_id},
                )
        return job_id, True

    def claim(self, lease_seconds=300):
        """Fence an available job with a row lock; expired work remains fail-closed."""
        with self.connection(write=True) as connection:
            now = time.time()
            expired = connection.execute(
                "SELECT id,status FROM jobs WHERE status IN ('running','cancelling') "
                "AND lease_until<? FOR UPDATE SKIP LOCKED",
                (now,),
            ).fetchall()
            for row in expired:
                status = "cancelled" if row["status"] == "cancelling" else "interrupted"
                connection.execute(
                    "UPDATE jobs SET status=?,updated_at=?,error=?,owner=NULL,lease_until=NULL WHERE id=?",
                    (
                        status,
                        now,
                        "Cancellation finalized after worker lease expired"
                        if status == "cancelled"
                        else "Worker lease expired; create a new run to retry",
                        row["id"],
                    ),
                )
                self._event(
                    connection, row["id"], status, "system", {"reason": "Worker lease expired"}
                )
            row = connection.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY created_at,id "
                "LIMIT 1 FOR UPDATE SKIP LOCKED"
            ).fetchone()
            if row is None:
                return None
            owner = uuid.uuid4().hex
            connection.execute(
                "UPDATE jobs SET status='running',updated_at=?,owner=?,lease_until=? WHERE id=?",
                (now, owner, now + lease_seconds, row["id"]),
            )
            self._event(connection, row["id"], "running", "worker")
            return {"id": row["id"], "owner": owner, "request": json.loads(row["request_json"])}

    def progress(self, job, stage, status, details=None):
        with self.connection(write=True) as connection:
            row = connection.execute(
                "SELECT status,owner,lease_until FROM jobs WHERE id=? FOR UPDATE", (job["id"],)
            ).fetchone()
            if not row:
                raise Conflict("Worker no longer owns this investigation")
            if row["status"] == "cancelling" and row["owner"] == job["owner"]:
                raise JobCancelled("Operator requested cancellation")
            if (
                row["status"] != "running"
                or row["owner"] != job["owner"]
                or row["lease_until"] < time.time()
            ):
                raise Conflict("Worker no longer owns this investigation")
            connection.execute("UPDATE jobs SET updated_at=? WHERE id=?", (time.time(), job["id"]))
            self._event(
                connection,
                job["id"],
                "dbt_progress",
                "worker",
                {"stage": stage, "status": status, **(details or {})},
            )

    def finish(self, job, result=None, error=None):
        with self.connection(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id=? FOR UPDATE", (job["id"],)
            ).fetchone()
            if (
                not row
                or row["status"] != "running"
                or row["owner"] != job["owner"]
                or row["lease_until"] < time.time()
            ):
                raise Conflict("Worker no longer owns this investigation")
            status = (
                "failed"
                if error
                else (
                    "paused"
                    if result
                    and result.get("response", {}).get("graph_run", {}).get("status") == "paused"
                    else "completed"
                )
            )
            version = digest(result) if result is not None else None
            connection.execute(
                "UPDATE jobs SET status=?,updated_at=?,result_json=?,result_version=?,error=?,"
                "owner=NULL,lease_until=NULL WHERE id=?",
                (
                    status,
                    time.time(),
                    encoded(result) if result is not None else None,
                    version,
                    error,
                    job["id"],
                ),
            )
            self._event(connection, job["id"], status, "worker", {"result_version": version})

    def cancel(self, job_id, actor="operator", reason="Operator requested cancellation"):
        with self.connection(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id=? FOR UPDATE", (job_id,)
            ).fetchone()
            if row is None:
                raise NotFound("Investigation not found")
            self._cancel_row(connection, row, actor, reason)
        return self.get(job_id)

    def acknowledge_cancel(self, job):
        with self.connection(write=True) as connection:
            row = connection.execute(
                "SELECT status,owner FROM jobs WHERE id=? FOR UPDATE", (job["id"],)
            ).fetchone()
            if row and row["status"] == "cancelled":
                return
            if not row or row["owner"] != job["owner"] or row["status"] != "cancelling":
                raise Conflict("Cancellation ownership changed")
            connection.execute(
                "UPDATE jobs SET status='cancelled',owner=NULL,lease_until=NULL,updated_at=? WHERE id=?",
                (time.time(), job["id"]),
            )
            self._event(connection, job["id"], "cancelled", "worker")

    def interrupt(self, job):
        with self.connection(write=True) as connection:
            row = connection.execute(
                "SELECT status,owner FROM jobs WHERE id=? FOR UPDATE", (job["id"],)
            ).fetchone()
            if (
                not row
                or row["owner"] != job["owner"]
                or row["status"] not in ("running", "cancelling")
            ):
                raise Conflict("Worker ownership changed")
            status = "cancelled" if row["status"] == "cancelling" else "interrupted"
            connection.execute(
                "UPDATE jobs SET status=?,owner=NULL,lease_until=NULL,updated_at=?,error=? WHERE id=?",
                (
                    status,
                    time.time(),
                    "Worker stopped before completion; no automatic retry",
                    job["id"],
                ),
            )
            self._event(connection, job["id"], status, "worker", {"reason": "Worker shutdown"})

    def enqueue_workflow(self, request, key, actor):
        items = request.get("jobs", [])
        if not 1 <= len(items) <= 6 or len({item["case_id"] for item in items}) != len(items):
            raise Conflict("A workflow requires 1–6 unique incidents")
        with self.connection(write=True) as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(?,0))", (key,))
            self._admission_lock(connection)
            prior = connection.execute(
                "SELECT id,request_hash FROM workflows WHERE idempotency_key=?", (key,)
            ).fetchone()
            if prior:
                if prior["request_hash"] != digest(request):
                    raise Conflict("Idempotency key belongs to a different workflow")
                return prior["id"], False
            active = connection.execute(
                "SELECT COUNT(*) AS count FROM jobs WHERE status IN ('queued','running','cancelling')"
            ).fetchone()[0]
            if active + len(items) > 16:
                raise Conflict("Queue cannot admit this entire workflow; no runs were created")
            identity, now = uuid.uuid4().hex, time.time()
            connection.execute(
                "INSERT INTO workflows(id,idempotency_key,request_json,request_hash,actor,created_at) "
                "VALUES (?,?,?,?,?,?)",
                (identity, key, encoded(request), digest(request), actor, now),
            )
            for position, item in enumerate(items):
                job_id = uuid.uuid4().hex
                connection.execute(
                    "INSERT INTO jobs(id,idempotency_key,request_json,request_hash,status,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        job_id,
                        "workflow:" + identity + ":" + str(position),
                        encoded(item),
                        digest(item),
                        "queued",
                        now,
                        now,
                    ),
                )
                connection.execute(
                    "INSERT INTO workflow_jobs(workflow_id,job_id,position) VALUES (?,?,?)",
                    (identity, job_id, position),
                )
                self._event(
                    connection,
                    job_id,
                    "queued",
                    actor,
                    {"kind": item["kind"], "workflow_id": identity},
                )
        return identity, True

    def cancel_workflow(self, workflow_id, actor, reason):
        with self.connection(write=True) as connection:
            if (
                connection.execute("SELECT 1 FROM workflows WHERE id=?", (workflow_id,)).fetchone()
                is None
            ):
                raise NotFound("Workflow not found")
            rows = connection.execute(
                "SELECT * FROM jobs WHERE id IN "
                "(SELECT job_id FROM workflow_jobs WHERE workflow_id=?) "
                "AND status IN ('queued','running') FOR UPDATE",
                (workflow_id,),
            ).fetchall()
            for row in rows:
                self._cancel_row(connection, row, actor, reason)
        return self.get_workflow(workflow_id)

    def _summaries(self, connection, workflow_id=None):
        scope = (
            " WHERE id IN (SELECT job_id FROM workflow_jobs WHERE workflow_id=?)"
            if workflow_id
            else ""
        )
        rows = connection.execute(
            "SELECT id,request_json,status,created_at,updated_at,result_version,error,result_json "
            "FROM jobs" + scope + " ORDER BY created_at DESC,id DESC LIMIT 50",
            (workflow_id,) if workflow_id else (),
        )
        summaries = []
        for row in rows:
            value = dict(row)
            value["request"] = json.loads(value.pop("request_json"))
            result_json = value.pop("result_json")
            if result_json:
                result = json.loads(result_json)
                value["outcome"] = {
                    "status": result["response"]["decision"].get("status"),
                    "passed": bool(result["grading"]["passed"]),
                }
            summaries.append(value)
        return summaries

    def stats(self):
        completed = 0
        verified = 0
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT result_json FROM jobs WHERE status='completed'"
            ).fetchall()
        for row in rows:
            completed += 1
            if row["result_json"]:
                result = json.loads(row["result_json"])
                verified += bool(
                    result["grading"]["passed"]
                    and result["response"]["decision"].get("status") == "candidate"
                )
        return {"completed": completed, "verified_candidates": int(verified)}

    def review(self, job_id, version, action, actor, note):
        if action not in ("approved", "rejected"):
            raise ValueError("Unknown review action")
        with self.connection(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id=? FOR UPDATE", (job_id,)
            ).fetchone()
            if not row:
                raise NotFound("Investigation not found")
            if row["status"] != "completed" or row["result_version"] != version:
                raise Conflict("Review version is stale or the investigation is incomplete")
            result = json.loads(row["result_json"])
            if result.get("dbt"):
                from sqlarbiter.workflows.dbt_service import validate_result

                validate_result(result, require_passed=action == "approved")
            if result["response"]["decision"].get("status") != "candidate":
                raise Conflict("There is no repair candidate to review")
            if action == "approved" and not result["grading"]["passed"]:
                raise Conflict("A candidate that failed verification cannot be approved")
            prior = connection.execute(
                "SELECT * FROM reviews WHERE job_id=? FOR UPDATE", (job_id,)
            ).fetchone()
            if prior:
                if (prior["version"], prior["action"], prior["actor"], prior["note"]) != (
                    version,
                    action,
                    actor,
                    note,
                ):
                    raise Conflict("This result already has an immutable review")
            else:
                connection.execute(
                    "INSERT INTO reviews(job_id,version,action,actor,note,created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (job_id, version, action, actor, note, time.time()),
                )
                self._event(
                    connection,
                    job_id,
                    "review_" + action,
                    actor,
                    {"version": version, "note": note},
                )
        return self.get(job_id)


def create_job_store(root=None, database_url=None):
    root = root or os.getenv("SQLARBITER_STATE_DIR", "artifacts/generated/app")
    database_url = (
        database_url if database_url is not None else os.getenv("SQLARBITER_DATABASE_URL")
    )
    if database_url:
        return PostgresJobStore(root, database_url)
    return JobStore(root)
