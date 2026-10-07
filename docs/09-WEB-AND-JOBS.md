# Web workbench and persistent jobs

Implemented October 7, 2026. Local application at http://127.0.0.1:8000 when the launcher is running. FastAPI serves an original HTML/CSS/JavaScript interface; the separate worker executes investigations and independent verification. This application belongs to the project, not the personal portfolio folder.

## Operator journey

Select a metric scenario and run the fixed diagnostic workflow. Hosted AI is available only when provider/model configuration exists. Inspect the finding and independent checks, expand actual tool evidence, and compare current/candidate SQL. Editing SQL creates a new verification job. Approval is disabled until the edited version has its own successful checks. Missing source information and healthy no-change outcomes are explicit, with no repair approval.

Reviews name an exact immutable result version and server-configured operator. Review notes are rendered as text. Approval records intent; no SQL is promoted into a business system. JSON report export includes the evidence, checks, version, review and audit events. Browser reload preserves selected run via its URL and all job history via the database.

## API

| Method and route | Behavior |
| --- | --- |
| GET /healthz | Process liveness; does not claim worker health |
| GET /api/config | Operator name and hosted-investigator availability; no keys |
| GET /api/incidents | Neutral scenario descriptions and source/execution version |
| GET /api/stats | Counts across the entire workspace |
| GET /api/jobs | Latest 50 run summaries |
| POST /api/jobs | Queue investigation; requires Idempotency-Key |
| GET /api/jobs/{id} | Result, evidence trace, version, review and event history |
| POST /api/jobs/{id}/candidates | Queue edited SQL against the exact parent result version |
| POST /api/jobs/{id}/review | Record approved/rejected review of the exact result version |
| GET /api/jobs/{id}/report | Download JSON report |

Use an 8–128 character Idempotency-Key for each new run/revision. Repeating the same key/body returns the same job; reusing it with a different body returns 409. At most 16 queued/running jobs are admitted. Repeated submission does not silently create additional billable work. JSON changes have a 75 KB body limit; SQL is additionally capped at 50,000 characters and executed under existing read-only budgets.

## Persistence and recovery

State directory contains jobs.sqlite and per-job runs/. SQLite uses WAL, foreign keys, parameterized statements and BEGIN IMMEDIATE transactions. Separate API/worker processes share this local directory. Claims atomically assign one owner and a 300-second lease; the active worker renews it every 30 seconds. Expired jobs become interrupted when a worker next claims work. They are never automatically retried. Queued jobs survive process restarts. A worker must still own the unexpired lease to publish its result.

Source/execution version hashes bind the incident records, contract, transformations, evaluator and exported runtime. Changes before execution fail the queued job. Result hashes bind source version, proposed SQL, evidence and grading. Revision creation checks the exact parent version; review creation checks the exact result version and rejects failed verification. An existing review is immutable through the API; an identical repeated review is idempotent. The local database remains administrator-editable, not a tamper-proof ledger.

## Access boundary

The local launcher binds 127.0.0.1; unauthenticated API requests require a loopback peer and an allowed Host. POST requests require JSON and reject mismatched browser origins. Responses use a restrictive content security policy. No general CORS permission is enabled.

VDIR_ACCESS_TOKEN enables shared operator bearer access. It must contain at least 32 characters. The browser prompts for the code and keeps it in memory, without storing it in the URL or browser storage. VDIR_PUBLIC_ORIGIN requires HTTPS plus configured operator access. Shared access is not individual identity, SSO, authorization roles or multi-tenant isolation; these remain release work. Authentication changes are server-side configuration, not model instructions.

## Verification evidence

59 unittest checks pass on Python 3.11.17 locally and inside containers, covering queue races, owner/lease renewal, restart persistence, idempotency, body/origin/host boundaries, exact-version review, immutable reviews, failing/mutating SQL and existing environment/model tests. Real Chromium smoke passed 13 checks including evidence expansion, edited-candidate approval blocking, failed revision, review/export, escaped notes, clarification, healthy no-change, browser reload, a 390-pixel mobile layout and idle launcher/worker shutdown.

Local generated [browser report](../artifacts/generated/browser-smoke-76f81514/result.json), [desktop view](../artifacts/generated/browser-smoke-76f81514/desktop-result.png) and [mobile view](../artifacts/generated/browser-smoke-76f81514/mobile-result.png) are ignored artifacts, not portable source files. Regenerate with the browser smoke command in the README. Browser tests strip model credentials, disable .env loading and make no provider calls.

## Remaining production work

No cloud deployment or live hosted-model run exists. Docker/Compose and CI definitions are prepared, but Docker is not installed on this Mac, so image build/runtime have not been locally validated. Hosted AI/model learning, customer-realistic incidents, frozen evaluations, Postgres/object storage, individual authentication, distributed job orchestration, cancellation, complete failed-run accounting, container-level repair isolation, operational alerts and controlled promotion remain unfinished.

Current app investigations explicitly record analytical engine (DuckDB default, SQLite optional) in the request/input version; candidate revisions retain the parent engine. Job state remains single-host SQLite WAL. For a distributed release replace queue leases with a durable queue/PostgreSQL claims; no such scaling implementation is claimed. Job/investigator/tool/verification traces are propagated into Phoenix. [Executed container/restart/tracing evidence](10-REMEDIATION-AND-BENCHMARK.md).
