"""Local operational API; investigate, inspect and record version-bound review."""

import os
import json
import re
import secrets
from pathlib import Path
from typing import Literal
from typing import Optional
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi import Header
from fastapi import Request
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from sqlarbiter.domain.cases import incidents
from sqlarbiter.persistence.jobs import Conflict
from sqlarbiter.persistence.jobs import NotFound
from sqlarbiter.persistence.jobs import encoded
from sqlarbiter.persistence.postgres_jobs import create_job_store
from sqlarbiter.workflows.service import case_version
from sqlarbiter.workflows.service import find_case

STATIC = Path(__file__).resolve().parents[4] / "frontend/apps/workbench"
LABELS = {
    "case-001": (
        "Catalog revenue · release 41",
        "Completed-order revenue by business date and product category.",
    ),
    "case-002": ("Event revenue · September 1", "Daily revenue from customer event deliveries."),
    "case-003": ("Event volume · September 3", "Daily event counts aligned to UTC reporting."),
    "case-004": ("Event volume · September 4", "UTC reporting across local-date boundaries."),
    "case-005": (
        "Catalog revenue · release 42",
        "Review the current catalog reporting transformation.",
    ),
    "case-006": ("Event revenue · September 5", "Review a newly delivered customer-event batch."),
}


class NewJob(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(min_length=1, max_length=64)
    investigator: Literal["baseline", "anthropic", "langgraph"] = "baseline"
    engine: Literal["duckdb", "sqlite"] = "duckdb"


class CandidateRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_version: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_sql: str = Field(min_length=1, max_length=50000)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(pattern=r"^[a-f0-9]{64}$")
    action: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=2000)


class GraphContinuation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_version: str = Field(pattern=r"^[a-f0-9]{64}$")
    guidance: str = Field(min_length=1, max_length=2000)


class CancelWork(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="Operator requested cancellation", max_length=500)


class NewWorkflow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    case_ids: list[str] = Field(min_length=1, max_length=6)
    investigator: Literal["baseline", "anthropic", "langgraph"] = "baseline"
    engine: Literal["duckdb", "sqlite"] = "duckdb"


class NewDbtRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: Literal["payment-revenue"]
    investigator: Literal["baseline", "anthropic", "langgraph"] = "baseline"


def create_app(state_dir=None, token=None, public_origin=None, operator=None):
    public_showcase = os.environ.get("SQLARBITER_PUBLIC_SHOWCASE") == "1"
    public_demo = public_showcase and os.environ.get("SQLARBITER_PUBLIC_DEMO") == "1"
    if state_dir is None:
        from sqlarbiter.platform.config import load_local_configuration

        load_local_configuration()
    token = os.environ.get("SQLARBITER_ACCESS_TOKEN", "") if token is None else token
    public_origin = public_origin or os.environ.get("SQLARBITER_PUBLIC_ORIGIN", "")
    operator = operator or os.environ.get("SQLARBITER_OPERATOR_NAME", "local-operator")
    if token and len(token) < 32:
        raise ValueError("SQLARBITER_ACCESS_TOKEN must contain at least 32 characters")
    if public_origin and (not token or urlsplit(public_origin).scheme != "https"):
        raise ValueError("Public origin requires HTTPS and SQLARBITER_ACCESS_TOKEN")
    store = create_job_store(
        state_dir or os.environ.get("SQLARBITER_STATE_DIR", "artifacts/generated/app")
    )
    app = FastAPI(
        title="SQLArbiter public showcase"
        if public_showcase
        else "Verified Data Incident Resolution",
        version="0.2.0",
    )
    app.state.store = store
    if hasattr(store, "close"):
        app.add_event_handler("shutdown", store.close)
    hosts = ["*"] if public_showcase else ["localhost", "127.0.0.1", "::1"]
    if public_origin:
        hosts.append(urlsplit(public_origin).hostname)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.exception_handler(Conflict)
    async def conflict_handler(request, error):
        return JSONResponse({"detail": str(error)}, status_code=409)

    @app.exception_handler(NotFound)
    async def missing_handler(request, error):
        return JSONResponse({"detail": str(error)}, status_code=404)

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            from sqlarbiter.api.public_demo import WRITE_PATHS
            from sqlarbiter.uploads.api import WRITE_PATHS as UPLOAD_PATHS
            from sqlarbiter.product.api import WRITE_PATHS as ACCOUNT_PATHS

            UPLOAD_PATHS = UPLOAD_PATHS | ACCOUNT_PATHS
            if (
                public_showcase
                and request.method != "GET"
                and not (
                    public_demo
                    and request.method == "POST"
                    and request.url.path in (WRITE_PATHS | UPLOAD_PATHS)
                )
            ):
                return JSONResponse({"detail": "Public showcase is read-only"}, status_code=405)
            if public_showcase:
                pass
            elif token:
                provided = request.headers.get("authorization", "")
                if not secrets.compare_digest(provided, "Bearer " + token):
                    return JSONResponse(
                        {"detail": "Operator access code required"}, status_code=401
                    )
            elif not request.client or request.client.host not in ("127.0.0.1", "::1"):
                return JSONResponse(
                    {"detail": "Unauthenticated access is local only"}, status_code=403
                )
            if request.method == "POST":
                expected_origin = public_origin or (
                    request.url.scheme + "://" + request.headers.get("host", "")
                )
                origin = request.headers.get("origin")
                if origin and origin.rstrip("/") != expected_origin.rstrip("/"):
                    return JSONResponse(
                        {"detail": "Cross-origin changes are not allowed"}, status_code=403
                    )
                if (
                    request.headers.get("content-type", "").split(";")[0].strip()
                    != "application/json"
                ):
                    return JSONResponse({"detail": "JSON body required"}, status_code=415)
                chunks, size = [], 0
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > (1000000 if request.url.path in UPLOAD_PATHS else 75000):
                        return JSONResponse(
                            {"detail": "Request exceeds size limit"}, status_code=413
                        )
                    chunks.append(chunk)
                request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def key(value):
        if not value or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", value):
            raise Conflict("Provide a valid Idempotency-Key header (8–128 characters)")
        return value

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/readyz")
    def ready():
        try:
            with store.connection() as connection:
                connection.execute("SELECT 1").fetchone()
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ready"}

    @app.get("/api/config")
    def config():
        return {
            "hosted_available": False
            if public_showcase
            else bool(
                os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("SQLARBITER_ANTHROPIC_MODEL")
            ),
            "operator": "Public showcase" if public_showcase else operator,
            "scope": "public_showcase" if public_showcase else "development",
            "default_engine": "duckdb",
            "access_mode": "public_read_only"
            if public_showcase
            else ("shared_operator" if token else "local_loopback"),
            "public_showcase": public_showcase,
        }

    @app.get("/api/incidents")
    def case_list():
        return [
            {
                "id": case.case_id,
                "title": LABELS[case.case_id][0],
                "description": LABELS[case.case_id][1],
                "metric": case.contract["metric"],
                "input_version": case_version(case),
            }
            for case in incidents()
        ]

    @app.get("/api/spend")
    def spend_summary():
        from sqlarbiter.platform.spending import SpendLedger
        from sqlarbiter.platform.spending import configuration

        settings = configuration(store.root)
        try:
            ledger = SpendLedger(
                settings["SQLARBITER_SPEND_LEDGER"],
                json.loads(Path(settings["SQLARBITER_PRICE_PROFILE"]).read_text()),
                settings["SQLARBITER_RUN_BUDGET_USD"],
                settings["SQLARBITER_TOTAL_BUDGET_USD"],
            )
            return ledger.summary()
        except (ValueError, OSError):
            return JSONResponse(
                {"detail": "Spend policy unavailable; live calls require a valid policy"},
                status_code=503,
            )

    @app.get("/api/incidents/{case_id}")
    def case_detail(case_id: str):
        try:
            case = find_case(case_id)
        except ValueError:
            raise NotFound("Metric not found") from None
        source = case.sources[0]
        return {
            "id": case.case_id,
            "title": LABELS[case.case_id][0],
            "description": LABELS[case.case_id][1],
            "contract": case.contract,
            "current_sql": case.current_sql,
            "lineage": case.lineage,
            "schema": {
                table: list(definitions) for table, (definitions, rows) in source.tables.items()
            },
            "snapshot_id": source.snapshot_id,
            "input_version": case_version(case),
        }

    @app.get("/api/jobs")
    def list_jobs():
        return store.list()

    @app.get("/api/dbt/projects")
    def dbt_projects():
        from sqlarbiter.workflows.dbt_service import project

        return [project()]

    @app.post("/api/dbt/runs")
    def dbt_new(body: NewDbtRun, idempotency_key: Optional[str] = Header(None)):
        from sqlarbiter.workflows.dbt_service import project
        from sqlarbiter.workflows.dbt_service import CASE_ID

        definition = project()
        if not definition["available"]:
            return JSONResponse(
                {"detail": "dbt tooling is unavailable on the worker host"}, status_code=503
            )
        if body.investigator in ("anthropic", "langgraph") and not config()["hosted_available"]:
            return JSONResponse(
                {"detail": "Hosted investigator is not configured"}, status_code=503
            )
        request = {
            "kind": "dbt_investigation",
            "case_id": CASE_ID,
            "project_id": body.project_id,
            "investigator": body.investigator,
            "engine": "duckdb",
            "input_version": definition["input_version"],
        }
        identity, created = store.enqueue(request, key(idempotency_key), operator)
        return JSONResponse(store.get(identity), status_code=202 if created else 200)

    @app.post("/api/dbt/runs/{job_id}/revisions")
    def dbt_revision(
        job_id: str, body: CandidateRevision, idempotency_key: Optional[str] = Header(None)
    ):
        from sqlarbiter.workflows.dbt_service import is_dbt
        from sqlarbiter.workflows.dbt_service import project_version

        parent = store.get(job_id)
        if not is_dbt(parent):
            raise Conflict("This is not a dbt project investigation")
        if project_version() != parent["request"]["input_version"]:
            raise Conflict("The dbt project changed; start a new investigation")
        request = {
            **parent["request"],
            "kind": "dbt_verification",
            "investigator": "baseline",
            "parent_id": job_id,
            "parent_version": body.parent_version,
            "candidate_sql": body.candidate_sql,
        }
        if not body.candidate_sql.strip():
            raise Conflict("Candidate SQL cannot be empty")
        identity, created = store.enqueue(request, key(idempotency_key), operator)
        return JSONResponse(store.get(identity), status_code=202 if created else 200)

    @app.get("/api/dbt/runs/{job_id}/patch")
    def dbt_patch(job_id: str):
        from sqlarbiter.workflows.dbt_service import is_dbt
        from sqlarbiter.workflows.dbt_service import validate_result

        job = store.get(job_id)
        if not is_dbt(job) or job["status"] != "completed" or not job.get("result"):
            raise Conflict("A completed dbt investigation is required")
        validate_result(job["result"], require_passed=True)
        return Response(
            job["result"]["patch"],
            media_type="text/plain",
            headers={"Content-Disposition": 'attachment; filename="repair-%s.patch"' % job["id"]},
        )

    @app.get("/api/stats")
    def statistics():
        return store.stats()

    @app.post("/api/jobs")
    def new_job(body: NewJob, idempotency_key: Optional[str] = Header(None)):
        try:
            case = find_case(body.case_id)
        except ValueError:
            raise NotFound("Incident not found")
        if body.investigator in ("anthropic", "langgraph") and not config()["hosted_available"]:
            return JSONResponse(
                {"detail": "Hosted investigator is not configured"}, status_code=503
            )
        request = {
            "kind": "investigation",
            "case_id": body.case_id,
            "investigator": body.investigator,
            "engine": body.engine,
            "input_version": case_version(case, body.engine),
        }
        job_id, created = store.enqueue(request, key(idempotency_key), operator)
        return JSONResponse(store.get(job_id), status_code=202 if created else 200)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        return store.get(job_id)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, body: CancelWork):
        return store.cancel(job_id, operator, body.reason)

    @app.get("/api/workflows")
    def workflow_list():
        return store.list_workflows()

    @app.post("/api/workflows")
    def workflow_new(body: NewWorkflow, idempotency_key: Optional[str] = Header(None)):
        if not body.name.strip() or len(set(body.case_ids)) != len(body.case_ids):
            raise Conflict("Provide a name and unique incident IDs")
        if body.investigator in ("anthropic", "langgraph") and not config()["hosted_available"]:
            return JSONResponse(
                {"detail": "Hosted investigator is not configured"}, status_code=503
            )
        requests = []
        for case_id in body.case_ids:
            try:
                case = find_case(case_id)
            except ValueError:
                raise NotFound("Incident not found")
            requests.append(
                {
                    "kind": "investigation",
                    "case_id": case_id,
                    "engine": body.engine,
                    "investigator": body.investigator,
                    "input_version": case_version(case, body.engine),
                }
            )
        identity, created = store.enqueue_workflow(
            {"name": body.name.strip(), "jobs": requests}, key(idempotency_key), operator
        )
        return JSONResponse(store.get_workflow(identity), status_code=202 if created else 200)

    @app.get("/api/workflows/{workflow_id}")
    def workflow_get(workflow_id: str):
        return store.get_workflow(workflow_id)

    @app.post("/api/workflows/{workflow_id}/cancel")
    def workflow_cancel(workflow_id: str, body: CancelWork):
        return store.cancel_workflow(workflow_id, operator, body.reason)

    @app.post("/api/jobs/{job_id}/candidates")
    def revise(job_id: str, body: CandidateRevision, idempotency_key: Optional[str] = Header(None)):
        parent = store.get(job_id)
        if parent["request"].get("project_id"):
            raise Conflict("Use the dbt project revision endpoint")
        request = {
            "kind": "verification",
            "case_id": parent["request"]["case_id"],
            "input_version": parent["request"]["input_version"],
            "engine": parent["request"].get("engine", "duckdb"),
            "parent_id": job_id,
            "parent_version": body.parent_version,
            "candidate_sql": body.candidate_sql,
        }
        if not body.candidate_sql.strip():
            raise Conflict("Candidate SQL cannot be empty")
        new_id, created = store.enqueue(request, key(idempotency_key), operator)
        return JSONResponse(store.get(new_id), status_code=202 if created else 200)

    @app.post("/api/jobs/{job_id}/review")
    def review_job(job_id: str, body: Review):
        return store.review(job_id, body.version, body.action, operator, body.note)

    @app.post("/api/jobs/{job_id}/resume")
    def resume_graph(
        job_id: str, body: GraphContinuation, idempotency_key: Optional[str] = Header(None)
    ):
        parent = store.get(job_id)
        if parent["request"].get("project_id"):
            raise Conflict(
                "dbt clarification continuation is not available; start a new controlled investigation"
            )
        if not body.guidance.strip():
            raise Conflict("Investigation guidance cannot be empty")
        if not config()["hosted_available"]:
            return JSONResponse(
                {"detail": "Hosted investigator is not configured"}, status_code=503
            )
        request = {
            "kind": "graph_resume",
            "case_id": parent["request"]["case_id"],
            "investigator": "langgraph",
            "engine": parent["request"].get("engine", "duckdb"),
            "input_version": parent["request"]["input_version"],
            "parent_id": job_id,
            "parent_version": body.parent_version,
            "guidance": body.guidance,
        }
        new_id, created = store.enqueue(request, key(idempotency_key), operator)
        return JSONResponse(store.get(new_id), status_code=202 if created else 200)

    @app.get("/api/jobs/{job_id}/report")
    def report(job_id: str):
        value = store.get(job_id)
        return Response(
            encoded(value),
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="investigation-%s.json"' % value["id"]
            },
        )

    @app.get("/assets/app.js", include_in_schema=False)
    def workbench_script():
        return FileResponse(STATIC / "assets/scripts/app.js")

    @app.get("/assets/style.css", include_in_schema=False)
    def workbench_styles():
        return FileResponse(STATIC / "assets/styles/style.css")

    app.mount("/assets", StaticFiles(directory=str(STATIC)), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/investigations", include_in_schema=False)
    @app.get("/investigations/{job_id}", include_in_schema=False)
    @app.get("/runs", include_in_schema=False)
    @app.get("/workflows", include_in_schema=False)
    @app.get("/workflows/{workflow_id}", include_in_schema=False)
    @app.get("/metrics", include_in_schema=False)
    @app.get("/metrics/{case_id}", include_in_schema=False)
    @app.get("/settings", include_in_schema=False)
    @app.get("/dbt", include_in_schema=False)
    @app.get("/dbt/new", include_in_schema=False)
    @app.get("/dbt/runs/{job_id}", include_in_schema=False)
    def index(request: Request):
        if public_demo and request.url.path == "/":
            return FileResponse(STATIC.parent / "product/index.html")
        return FileResponse(STATIC / "index.html")

    @app.get("/investigations/{job_id}/{section}", include_in_schema=False)
    def investigation_section(job_id: str, section: str):
        if not re.fullmatch(r"[a-f0-9]{32}", job_id) or section not in {
            "evidence",
            "sql",
            "activity",
            "definition",
        }:
            raise NotFound("Page not found")
        return FileResponse(STATIC / "index.html")

    if public_demo:
        from sqlarbiter.api.public_demo import attach

        attach(app, LABELS)
    from sqlarbiter.uploads.api import attach as attach_uploads

    attach_uploads(app, Path(__file__).resolve().parents[4])
    from sqlarbiter.product.api import attach as attach_product

    attach_product(app, Path(__file__).resolve().parents[4])
    return app
