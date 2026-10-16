# Data imports

The public `/uploads` workspace accepts visitor-owned **CSV, TSV, Excel `.xlsx`, JSON and JSONL** files and returns source-derived, independently checked results. The public deployment has no model key, so the workflow is an explicitly reviewed contract calculation, not live language interpretation.

```mermaid
flowchart LR
    A[Visitor file] --> B[Import and normalize]
    B --> C[Bounded parse and profile]
    C --> D[Review column and business contract]
    D --> E[Generated SQL and independent reference]
    E --> F[Checked report and exports]
```

## Business contract

Map a logical key, an amount, an optional grouping and an optional eligibility status. The key identifies one record: exact repeated rows are duplicate deliveries, and conflicting payloads for one key stop the run. Dollars allow at most two decimals and cents must be integers. Eligible unique amounts are summed in integer cents. A separately populated in-memory SQLite table executes the generated `SELECT DISTINCT` query, and its grouped result must equal an independent Python reference. An optional reported total is compared in dollars. Negative corrections are allowed, and no eligible rows produces an explicit zero total.

Generated SQL refers to normalized `records` columns (`c0`, `c1`, …) plus `__amount_cents` and `__eligible`, and the column bindings accompany every export. It is an inspectable contract query, not a patch for an unknown warehouse. Arbitrary SQL, dbt macros and code uploads are outside this workflow; the [dbt repair](../architecture/DBT.md) runs in the private worker deployment.

## Formats

| Format | Contract |
| --- | --- |
| CSV | UTF-8 with one header row. Original text, including BOM and CRLF, is kept so saved source fingerprints stay stable. |
| TSV | UTF-8 tab-separated with one header row; quoted tabs and newlines follow CSV quoting. |
| Excel `.xlsx` | A rectangular table starting at row 1. When several visible worksheets exist the user picks one; sheets are never combined. Numeric cells use stored values, not display formatting. Text IDs keep leading zeros. Dates become ISO text without an invented timezone. |
| JSON | A non-empty array of flat objects with identical field sets (use `null` for missing values). The first record fixes column order, and numbers are parsed as `Decimal`. |
| JSONL | One flat object per line with the same rules; blank lines are refused. |

Every format normalizes to an inspectable CSV table. The browser records the format, selected sheet, original-file SHA-256 and normalized-table SHA-256. Import metadata describes the conversion; it does not authenticate the business document. Saved snapshots and backups keep the normalized table, rules and report, not the original workbook.

PDFs, images, legacy `.xls`, `.xlsm`, arbitrary ZIPs, Parquet and code are refused.

## Limits

- Each file and its normalized table is at most 400,000 bytes, with at most 5,000 records, 60 columns, 120 characters per header and 2,048 characters per cell. Case-insensitive duplicate headers, ragged records, control characters and empty files are refused.
- At most 100 result groups, and each numeric value is at most 100 million in magnitude.
- Files travel as bounded base64 inside JSON. An ASGI middleware counts streamed bytes before decoding, rejects bodies over 1 MB and limits reception to 15 seconds. Filenames never become server paths.
- Excel parsing uses read-only openpyxl with defusedxml. Before loading, the archive is bounded to 200 members, 8 MB total expansion, 4 MB per member and a 150:1 compression ratio, with no duplicate, traversing or encrypted entries. DTDs, entities, formulas, merged cells, macros, external links, embeddings and ActiveX are refused, and declared dimensions cannot hide extra cells.
- Parsing and analysis run in FastAPI's worker thread pool, outside the event loop. There is no global admission control across serverless instances.
- User content is rendered as text nodes, never HTML. CSV exports neutralize formula-like text while keeping numeric negatives.

These limits stay below [Vercel's function payload limit](https://vercel.com/docs/functions/limitations). Larger files would need direct object upload and a durable worker rather than a larger JSON request.

Errors return structured guidance without cell values or parser traces. Ambiguous JSON, ragged records, unsupported types and unsafe workbooks withhold results, and cancelling worksheet selection commits no partial source.

## Endpoints

`GET /api/uploads/capabilities`, `GET /api/uploads/template`, `POST /api/uploads/import`, `POST /api/uploads/profile`, `POST /api/uploads/preview`, `POST /api/uploads/analyze`, `POST /api/uploads/analyze-stream` and `POST /api/uploads/check-report`. Every analysis request carries the source and an explicit mapping, responses are not cached, and the public upload allowlist enables no operator write endpoints.

`POST /api/uploads/import` takes `filename`, `content_base64` and an optional `sheet`. A multi-sheet workbook returns `needs_sheet` with the visible sheet names; a completed import returns the normalized table, profile and metadata.

## Verification

- `backend/tests/api/test_uploads.py`: expected values, changed inputs, validation and request isolation.
- `backend/tests/api/test_imports.py`: conversions, exact decimals and IDs, BOM identity, malformed JSON, workbook formulas, merged cells, entities, ZIP bounds, lying dimensions, transport limits, and equal results across all five formats.
- `scripts/demos/import_browser.py`: real file selection for all five formats, worksheet choice and Escape cancellation, invalid-file recovery, layouts from 320 to 1440 pixels and an optional axe-core scan.
- `scripts/demos/uploads_browser.py`: changed-input results, JSON and CSV downloads, mobile layout and clearing.

Parser references: [openpyxl security](https://openpyxl.readthedocs.io/en/stable/#security), [read-only mode](https://openpyxl.readthedocs.io/en/stable/optimized.html).
