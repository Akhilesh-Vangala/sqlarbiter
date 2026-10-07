"""Local operational API; investigate, inspect and record version-bound review."""
import os
import re
import secrets
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlsplit

from fastapi import FastAPI, Header, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .cases import incidents
from .jobs import Conflict, JobStore, NotFound, encoded
from .service import case_version, find_case

STATIC = Path(__file__).parent / "web"
LABELS = {
    "case-001": ("Catalog revenue · release 41", "Completed-order revenue by business date and product category."),
    "case-002": ("Event revenue · September 1", "Daily revenue from customer event deliveries."),
    "case-003": ("Event volume · September 3", "Daily event counts aligned to UTC reporting."),
    "case-004": ("Event volume · September 4", "UTC reporting across local-date boundaries."),
    "case-005": ("Catalog revenue · release 42", "Review the current catalog reporting transformation."),
    "case-006": ("Event revenue · September 5", "Review a newly delivered customer-event batch."),
}


class NewJob(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(min_length=1, max_length=64)
    investigator: Literal["baseline", "anthropic"] = "baseline"
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


def create_app(state_dir=None, token=None, public_origin=None, operator=None):
    if state_dir is None:
        from .config import load_local_configuration
        load_local_configuration()
    token = os.environ.get("VDIR_ACCESS_TOKEN", "") if token is None else token
    public_origin = public_origin or os.environ.get("VDIR_PUBLIC_ORIGIN", "")
    operator = operator or os.environ.get("VDIR_OPERATOR_NAME", "local-operator")
    if token and len(token) < 32:
        raise ValueError("VDIR_ACCESS_TOKEN must contain at least 32 characters")
    if public_origin and (not token or urlsplit(public_origin).scheme != "https"):
        raise ValueError("Public origin requires HTTPS and VDIR_ACCESS_TOKEN")
    store = JobStore(state_dir or os.environ.get("VDIR_STATE_DIR", "artifacts/generated/app"))
    app = FastAPI(title="Verified Data Incident Resolution", version="0.2.0")
    app.state.store = store
    hosts = ["localhost", "127.0.0.1", "::1"]
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
            if token:
                provided = request.headers.get("authorization", "")
                if not secrets.compare_digest(provided, "Bearer " + token):
                    return JSONResponse({"detail": "Operator access code required"}, status_code=401)
            elif not request.client or request.client.host not in ("127.0.0.1", "::1"):
                return JSONResponse({"detail": "Unauthenticated access is local only"}, status_code=403)
            if request.method == "POST":
                expected_origin = public_origin or (request.url.scheme + "://" + request.headers.get("host", ""))
                origin = request.headers.get("origin")
                if origin and origin.rstrip("/") != expected_origin.rstrip("/"):
                    return JSONResponse({"detail": "Cross-origin changes are not allowed"}, status_code=403)
                if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
                    return JSONResponse({"detail": "JSON body required"}, status_code=415)
                chunks, size = [], 0
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > 75000:
                        return JSONResponse({"detail": "Request exceeds size limit"}, status_code=413)
                    chunks.append(chunk)
                request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
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

    @app.get("/api/config")
    def config():
        return {"hosted_available": bool(os.environ.get("ANTHROPIC_API_KEY")
                                         and os.environ.get("VDIR_ANTHROPIC_MODEL")),
                "operator": operator, "scope": "development", "default_engine": "duckdb"}

    @app.get("/api/incidents")
    def case_list():
        return [{"id": case.case_id, "title": LABELS[case.case_id][0],
                 "description": LABELS[case.case_id][1], "metric": case.contract["metric"],
                 "input_version": case_version(case)} for case in incidents()]

    @app.get("/api/jobs")
    def list_jobs():
        return store.list()

    @app.get("/api/stats")
    def statistics():
        return store.stats()

    @app.post("/api/jobs")
    def new_job(body: NewJob, idempotency_key: Optional[str] = Header(None)):
        try:
            case = find_case(body.case_id)
        except ValueError:
            raise NotFound("Incident not found")
        if body.investigator == "anthropic" and not config()["hosted_available"]:
            return JSONResponse({"detail": "Hosted investigator is not configured"}, status_code=503)
        request = {"kind": "investigation", "case_id": body.case_id,
                   "investigator": body.investigator, "engine": body.engine, "input_version": case_version(case, body.engine)}
        job_id, created = store.enqueue(request, key(idempotency_key), operator)
        return JSONResponse(store.get(job_id), status_code=202 if created else 200)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        return store.get(job_id)

    @app.post("/api/jobs/{job_id}/candidates")
    def revise(job_id: str, body: CandidateRevision, idempotency_key: Optional[str] = Header(None)):
        parent = store.get(job_id)
        request = {"kind": "verification", "case_id": parent["request"]["case_id"],
                   "input_version": parent["request"]["input_version"],
                   "engine": parent["request"].get("engine", "duckdb"),
                   "parent_id": job_id, "parent_version": body.parent_version,
                   "candidate_sql": body.candidate_sql}
        if not body.candidate_sql.strip():
            raise Conflict("Candidate SQL cannot be empty")
        new_id, created = store.enqueue(request, key(idempotency_key), operator)
        return JSONResponse(store.get(new_id), status_code=202 if created else 200)

    @app.post("/api/jobs/{job_id}/review")
    def review_job(job_id: str, body: Review):
        return store.review(job_id, body.version, body.action, operator, body.note)

    @app.get("/api/jobs/{job_id}/report")
    def report(job_id: str):
        value = store.get(job_id)
        return Response(encoded(value), media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="investigation-%s.json"' % value["id"]})

    app.mount("/assets", StaticFiles(directory=str(STATIC)), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    return app
