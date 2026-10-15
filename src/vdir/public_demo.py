"""Interactive, bounded synthetic investigations for the public Vercel app.

Uses the existing fixed worker, evidence replay and independent regression
verifier. Signed per-browser scope replaces shared ephemeral result histories.
"""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from typing import Literal
import uuid

from fastapi import HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from . import evaluation
from .demo_security import DemoSession
from .service import find_case, case_version

ASSETS = Path(__file__).parent / "demo_assets"
WRITE_PATHS = {"/api/demo/investigate", "/api/demo/verify", "/api/demo/review"}
CAPACITY = threading.BoundedSemaphore(2)


class Start(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: Literal["case-001", "case-002", "case-003", "case-004", "case-005", "case-006"]


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    token: str = Field(min_length=1, max_length=18000)


class Revision(Envelope):
    candidate_sql: str = Field(min_length=1, max_length=6000)


class Review(Envelope):
    action: Literal["approve", "reject"]


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def investigate(case_id, candidate_sql=None):
    if not CAPACITY.acquire(blocking=False):
        raise HTTPException(429, "Two investigations are running; retry shortly")
    deadline = time.monotonic() + 25

    def control():
        if time.monotonic() > deadline:
            raise evaluation.ExecutionInterrupted("Public investigation time allowance exceeded")

    try:
        case = find_case(case_id)
        source_version = case_version(case, "sqlite")
        with tempfile.TemporaryDirectory(prefix="verifyops-public-demo-") as directory:
            root = Path(directory)
            # Resolve installed third-party roots; do not pass repository/src
            # or evaluator paths into the isolated exported worker.
            import sqlglot
            import opentelemetry.sdk

            dependencies = {
                Path(sqlglot.__file__).resolve().parents[1],
                Path(next(iter(opentelemetry.sdk.__path__))).resolve().parents[1],
            }
            with evaluation.worker_dependencies(dependencies), evaluation.execution_scope(control):
                workspace = evaluation.export_workspace(case, root / "evidence", "sqlite")
                response = evaluation.run_worker(workspace, mode="baseline")
                if candidate_sql is not None:
                    requests = [
                        {"method": r["method"], "params": r["params"]} for r in response["trace"]
                    ]
                    requests.append({"method": "query", "params": {"sql": candidate_sql}})
                    response = copy.deepcopy(response)
                    response["trace"] = evaluation.run_worker(
                        workspace,
                        mode="rpc",
                        requests="".join(json.dumps(r) + "\n" for r in requests),
                    )
                    response["decision"].update(
                        status="candidate",
                        candidate_sql=candidate_sql,
                        explanation="Operator-submitted SQL; independently checked against source references and regression snapshots.",
                    )
                grading = evaluation.grade(case, response, root / "grading", "sqlite")
            candidate = response["decision"].get("candidate_sql") or case.current_sql

            def query_evidence(sql):
                return next(
                    (
                        r.get("result")
                        for r in reversed(response["trace"])
                        if r.get("ok") and r["method"] == "query" and r["params"].get("sql") == sql
                    ),
                    None,
                )

            report = {
                "case_id": case_id,
                "source_version": source_version,
                "engine": "sqlite",
                "decision": response["decision"],
                "grading": grading,
                "evidence": response["trace"],
                "current_sql": case.current_sql,
                "candidate_sql": candidate,
                "contract": case.contract,
                "before": query_evidence(case.current_sql),
                "after": query_evidence(candidate),
            }
            report["version"] = fingerprint(report)
            return report
    except (evaluation.ExecutionInterrupted, RuntimeError, subprocess.TimeoutExpired):
        raise HTTPException(
            503, "The bounded investigation did not finish; start a new run"
        ) from None
    finally:
        CAPACITY.release()


def attach(app, labels):
    session = DemoSession(os.environ.get("VDIR_DEMO_SECRET", ""), "verifyops_demo_session")

    def source_check(saved):
        if saved.get("source_version") != case_version(find_case(saved["case_id"]), "sqlite"):
            raise HTTPException(409, "Incident or execution code changed; investigate again")

    def publish(request, saved, report, stage):
        saved = {
            **saved,
            "version": report["version"],
            "source_version": report["source_version"],
            "stage": stage,
        }
        return {
            **report,
            "id": saved["id"],
            "parent_id": saved.get("parent_id"),
            "stage": stage,
            "title": labels[saved["case_id"]][0],
            "mode": "Guided fixed investigator · no model calls",
            "token": session.issue(saved, session.visitor(request)),
            "scope": "Synthetic request-bounded investigation. SQL and independent checks run on the server; history/review branch is retained in this browser, not a durable cloud queue. No customer warehouse writes.",
        }

    @app.get("/api/demo/config")
    def config(request: Request, response: Response):
        session.visitor(request, response)
        return {
            "project": "VerifyOps",
            "interactive": True,
            "mode": "guided",
            "live_model": False,
            "history": "this browser session",
            "cases": [{"id": key, "title": v[0], "description": v[1]} for key, v in labels.items()],
        }

    @app.post("/api/demo/investigate")
    def start(body: Start, request: Request):
        session.visitor(request)
        report = investigate(body.case_id)
        return publish(
            request,
            {"id": uuid.uuid4().hex, "case_id": body.case_id, "revision_sql": None},
            report,
            "assessed",
        )

    @app.post("/api/demo/verify")
    def verify(body: Revision, request: Request):
        saved = session.consume(request, body.token)
        source_check(saved)
        if not body.candidate_sql.strip():
            raise HTTPException(400, "Provide a candidate query")
        report = investigate(saved["case_id"], body.candidate_sql)
        child = {
            **saved,
            "id": uuid.uuid4().hex,
            "parent_id": saved["id"],
            "revision_sql": body.candidate_sql,
        }
        return publish(request, child, report, "assessed")

    @app.post("/api/demo/review")
    def review(body: Review, request: Request):
        saved = session.consume(request, body.token)
        source_check(saved)
        if saved["stage"] != "assessed":
            raise HTTPException(409, "This review branch already has a decision")
        report = investigate(saved["case_id"], saved.get("revision_sql"))
        if report["version"] != saved["version"]:
            raise HTTPException(409, "Result changed; investigate again")
        if body.action == "approve" and not report["grading"]["passed"]:
            raise HTTPException(409, "A failed verification cannot be accepted")
        return publish(
            request, saved, report, "approved" if body.action == "approve" else "rejected"
        )

    @app.get("/demo/recording")
    @app.get("/demo")
    @app.get("/demo/runs/{identity}")
    def index(identity: str = ""):
        return FileResponse(ASSETS / "index.html")

    @app.get("/demo-assets/{name}")
    def assets(name: Literal["app.js", "style.css", "walkthrough.webm", "poster.png"]):
        return FileResponse(ASSETS / name)

    @app.get("/api/demo/runs")
    def history():
        return []

    @app.get("/api/demo/runs/{identity}")
    def detail(identity: str):
        raise HTTPException(404, "Demo results are retained only in their browser session")
