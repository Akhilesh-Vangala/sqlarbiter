# VerifyOps: work with your own data

CSV, TSV, Excel `.xlsx`, JSON, and JSONL are accepted. [Formats and limits](FILE-IMPORTS.md). PDFs and images are refused.

The public `/uploads` workspace accepts visitor-owned CSVs and returns source-derived results. Existing sample investigations remain separate. No provider keys are configured in the public deployment: these are explicitly reviewed contract workflows, not live language interpretation or measured general-purpose agent accuracy.

```mermaid
flowchart LR
    A[Visitor CSV] --> B[Bounded parse and profile]
    B --> C[Review column and business contract]
    C --> D[Execute source-derived workflow]
    D --> E[Independent verification]
    E --> F[Review results and export]
```

## Business contract

Map a logical key, amount, optional grouping and optional eligibility status. The key identifies a single record; exact repeated rows are duplicate deliveries. Conflicting payloads for one key stop the run. Dollars require at most two decimals; cents require integers. All eligible unique amounts are summed using integer cents. A separately populated in-memory SQLite table executes the generated `SELECT DISTINCT` contract; its grouped result must equal an independent Python reference. An optional reported total is compared in dollars. Negative corrections are permitted. No eligible rows produces an explicit zero total and empty grouped result.

SQL refers to normalized `records` columns (`c0`, `c1`, …), plus `__amount_cents` and `__eligible`; column bindings accompany the export. This is an inspectable contract query, not a directly executable patch for an unknown warehouse. Arbitrary SQL, dbt macros and code uploads are deliberately outside this public workflow. The existing isolated dbt repair workflow remains available in the private worker deployment.

## Data handling and limits

- UTF-8 comma-separated CSV with one header row; maximum 400,000 UTF-8 bytes, 60 columns, 120 characters per header and 2,048 characters per cell. Case-insensitive duplicate headers, ragged records, invalid control characters and empty files are refused.
- At most 5000 rows per analysis; at most 100 aggregate result groups. Each numeric source value is at most 100 million in magnitude; RelayOps also enforces its existing ten-million action bound.
- The browser reads a selected file and transmits its CSV text inside bounded JSON. An outer ASGI middleware counts actual streamed bytes before JSON decoding, rejects bodies over 1 MB and limits body reception to 15 seconds. No multipart package is necessary.
- Parsing/analysis run in FastAPI's synchronous handler thread pool, outside the event loop. This does not provide global admission control across serverless instances.
- Processing uses memory and, for operational worlds, automatically cleaned temporary scratch. Unsaved original rows/results are not deliberately persisted in shared history, application logs, browser local storage or session storage. Unsaved browser files/results disappear on reload or Clear. Optional consented IndexedDB or configured cloud snapshots are described in [the product workspace](PRODUCT-WORKSPACE.md); clearing active work does not delete saved history. Hosting providers may retain request metadata; this is not a confidential-data hosting certification.
- User content is rendered with text nodes, never HTML. CSV exports neutralize formula-like text while preserving typed numeric negatives. Filenames never become server filesystem paths. No uploaded code, external URLs, extensions, or arbitrary SQL are executed.

The app's limits remain below [Vercel's request/response payload limit](https://vercel.com/docs/functions/limitations). Larger exports need a separately designed direct-object-upload and durable-worker flow, not a larger JSON request.

## Endpoints

`GET /api/uploads/capabilities`, `GET /api/uploads/template`, `POST /api/uploads/profile`, `POST /api/uploads/analyze`, `POST /api/uploads/preview`, `POST /api/uploads/analyze-stream`, `POST /api/uploads/check-report`. The narrow public upload allowlist does not enable legacy state-changing operator endpoints. Every analysis request includes the original CSV and explicit mapping/options. API responses are not cached.

See the `uploads` package and `backend/tests/api/test_uploads.py` for expected values, changed-input, validation, and isolation regressions.

## Product journey

[Pages, guided review, saved-work consent, report authenticity, and optional cloud accounts](PRODUCT-WORKSPACE.md). Account sign-in is off unless `VDIR_SUPABASE_URL` and `VDIR_SUPABASE_PUBLISHABLE_KEY` are set.
