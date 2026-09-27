"""Request-bounded own-data APIs and their standalone product workspace."""

from pathlib import Path
from typing import Any

from fastapi import HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .ingestion import Upload, Preview, UploadBoundary, UploadProblem, profile, preview
from .service import run
from .signing import attest, verify_report
from .imports import FileImport, FORMATS, import_file

WRITE_PATHS = {
    "/api/uploads/import",
    "/api/uploads/profile",
    "/api/uploads/preview",
    "/api/uploads/analyze",
    "/api/uploads/analyze-stream",
    "/api/uploads/check-report",
}


class ReportCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    report: dict[str, Any] = Field(max_length=32)


CONFIG = {
    "title": "Find the discrepancy in your metric.",
    "description": "Upload a transaction export, declare its logical grain and eligibility rules, then reconcile exact totals and duplicate deliveries.",
    "fields": [
        ["key", "Logical record key", True],
        ["amount", "Amount", True],
        ["group", "Group results by", False],
        ["status", "Eligibility status", False],
    ],
    "options": [
        ["unit", "Amount unit", ["dollars", "cents"]],
        ["eligible_status", "Include this status only", None],
        ["reported_total", "Reported total to compare (dollars)", None],
    ],
    "template": "event_id,amount,category,status\nevent-101,125.50,Software,completed\nevent-101,125.50,Software,completed\nevent-102,74.50,Services,completed\nevent-103,90.00,Software,pending\n",
    "suggest": {
        "key": ["event_id", "id", "transaction_id"],
        "amount": ["amount", "revenue", "total"],
        "group": ["category", "region"],
        "status": ["status"],
    },
    "notice": "The key must identify a single logical record. Only exact duplicate rows can be collapsed; conflicting records stop the investigation. This workspace generates contract SQL, rather than executing an arbitrary SQL or dbt upload.",
}


def attach(app, root):
    static = Path(root) / "frontend/apps/uploads"
    app.add_middleware(UploadBoundary)

    @app.get("/uploads", include_in_schema=False)
    def workspace():
        return FileResponse(
            Path(root) / "frontend/apps/product/index.html",
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            },
        )

    @app.get("/uploads/recording.html", include_in_schema=False)
    def recording():
        return FileResponse(static / "recording.html", headers={"Cache-Control": "no-store"})

    @app.get("/uploads-assets/{name}", include_in_schema=False)
    def assets(name: str):
        if name not in ("style.css", "recording.html", "walkthrough.webm", "poster.png"):
            raise HTTPException(404, "Asset unavailable")
        return FileResponse(static / name, headers={"Cache-Control": "no-store"})

    @app.get("/api/uploads/capabilities")
    def capabilities(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return {
            "project": "SQLArbiter",
            **{k: v for k, v in CONFIG.items() if k != "template"},
            "live_ai": False,
            "run_record_schema": "run-v1",
            "formats": sorted(FORMATS),
            "max_csv_bytes": 400000,
            "max_rows": 5000,
            "retention": "Unsaved files are processed for this request and remain in browser memory. Optional device history or configured account storage requires explicit save consent. Hosting metadata may be retained; file contents are not deliberately logged.",
        }

    @app.get("/api/uploads/template")
    def template():
        return Response(
            CONFIG["template"],
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="sqlarbiter-template.csv"',
                "Cache-Control": "no-store",
            },
        )

    @app.post("/api/uploads/import")
    def import_tabular(body: FileImport):
        try:
            return JSONResponse(
                import_file(body, max_rows=5000), headers={"Cache-Control": "no-store"}
            )
        except UploadProblem as error:
            return JSONResponse(error.response(), status_code=422)
        except ValueError:
            raise HTTPException(422, "Invalid tabular file; check the export and retry") from None

    @app.post("/api/uploads/profile")
    def inspect(upload: Upload):
        try:
            return profile(upload.csv)
        except UploadProblem as error:
            return JSONResponse(error.response(), status_code=422)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @app.post("/api/uploads/analyze")
    def analyze(upload: Upload):
        try:
            result = run(upload)
        except UploadProblem as error:
            return JSONResponse(error.response(), status_code=422)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        return JSONResponse(
            attest(result),
            headers={"Cache-Control": "no-store", "X-Run-ID": result["run_record"]["run_id"]},
        )

    @app.post("/api/uploads/preview")
    def preview_rows(body: Preview):
        try:
            return preview(body)
        except UploadProblem as error:
            return JSONResponse(error.response(), status_code=422)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @app.post("/api/uploads/analyze-stream")
    def analyze_stream(upload: Upload):
        from .stream import stream

        return stream(upload)

    @app.post("/api/uploads/check-report")
    def check_saved_report(body: ReportCheck):
        return {
            "verified": verify_report(body.report),
            "scope": "Authenticity of a past computed report; not a fresh source-system check.",
        }
