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
            if connection.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0] >= 16:
                raise Conflict("Queue is full; wait for active investigations")
            if request.get("parent_id"):
                parent = connection.execute("SELECT * FROM jobs WHERE id=?", (request["parent_id"],)).fetchone()
                if not parent:
                    raise NotFound("Parent investigation not found")
                if parent["status"] != "completed" or parent["result_version"] != request.get("parent_version"):
                    raise Conflict("Parent result changed or is incomplete; refresh before verifying")
                result = json.loads(parent["result_json"])
                if result["response"]["decision"].get("status") != "candidate":
                    raise Conflict("Only a proposed repair can have a new candidate revision")
                if result["case_id"] != request["case_id"] or result["input_version"] != request["input_version"]:
                    raise Conflict("Candidate revision must use the same incident version")
            job_id, now = uuid.uuid4().hex, time.time()
            connection.execute("INSERT INTO jobs(id,idempotency_key,request_json,request_hash,status,created_at,updated_at) "
                               "VALUES (?,?,?,?,?,?,?)", (job_id, key, encoded(request), digest(request), "queued", now, now))
            self._event(connection, job_id, "queued", actor, {"kind": request["kind"]})
        return job_id, True

    def claim(self, lease_seconds=300):
        """Expired work is interrupted, never automatically replayed/billed."""
        with self.connection(write=True) as connection:
            now = time.time()
            expired = connection.execute("SELECT id FROM jobs WHERE status='running' AND lease_until<?", (now,)).fetchall()
            for row in expired:
                connection.execute("UPDATE jobs SET status='interrupted',updated_at=?,error=?,owner=NULL WHERE id=?",
                                   (now, "Worker lease expired; create a new run to retry", row["id"]))
                self._event(connection, row["id"], "interrupted", "system")
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
                "UPDATE jobs SET lease_until=? WHERE id=? AND status='running' AND owner=? AND lease_until>=?",
                (now + lease_seconds, job["id"], job["owner"], now))
            if cursor.rowcount != 1:
                raise Conflict("Worker no longer owns this investigation")

    def finish(self, job, result=None, error=None):
        with self.connection(write=True) as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
            if (not row or row["status"] != "running" or row["owner"] != job["owner"]
                    or row["lease_until"] < time.time()):
                raise Conflict("Worker no longer owns this investigation")
            status = "failed" if error else "completed"
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
        with self.connection() as connection:
            return [self._decode(row, False) for row in connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC,id DESC LIMIT 50")]

    def stats(self):
        with self.connection() as connection:
            completed, verified = 0, 0
            for row in connection.execute("SELECT result_json FROM jobs WHERE status='completed'"):
                completed += 1
                result = json.loads(row["result_json"])
                verified += int(result["grading"]["passed"] and
                                result["response"]["decision"].get("status") == "candidate")
            return {"completed": completed, "verified_candidates": verified}

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
