# Operator workbench and persistent jobs

FastAPI serves the operator workbench (`frontend/apps/workbench`) as native HTML, CSS and JavaScript. A separate worker process executes investigations and independent verification. Each task has its own URL; evidence drawers and cancellation confirmations stay contextual dialogs.

## Pages

| URL | Purpose |
| --- | --- |
| `/` | Workspace totals, five recent runs, provider readiness and the six scenarios |
| `/investigations` | Searchable queue of the latest 50 runs with outcome filters |
| `/investigations/new` | Investigation setup: metric, investigator and analytical engine |
| `/investigations/{id}` | Finding, independent checks and run context |
| `/investigations/{id}/evidence` | Executed tool evidence |
| `/investigations/{id}/sql` | Current and candidate SQL, revision verification and exact-version review |
| `/investigations/{id}/activity` | Recorded plans, findings and graph activity (LangGraph runs only) |
| `/investigations/{id}/definition` | Metric contract recorded for the run |
| `/workflows`, `/workflows/new`, `/workflows/{id}` | Multi-metric workflow collection, setup and detail |
| `/dbt`, `/dbt/new`, `/dbt/runs/{id}` | dbt project runs ([dbt](DBT.md)) |
| `/runs` | Searchable recent-run table |
| `/metrics`, `/metrics/{case_id}` | Metric catalog and the public contract, SQL, source schema and version for one case |
| `/settings` | Read-only workspace, operator, method, access and spend configuration |

Every route survives reload and Back/Forward, and section tabs are real links with arrow, Home and End key support. Opening setup from a metric carries `?metric=<case_id>` so the selection survives reload. Form drafts survive background polling but not a full reload. Polling never swaps an open evidence drawer to another version, and a late response for a previous selection cannot replace the current detail. Workspace search (⌘/Ctrl K) is a native overlay over recent runs and pages. A fixed-diagnostic run has no graph activity, so its activity URL returns to the summary with an explanation.

Editing SQL creates a new verification job, and approval stays disabled until that version has passed its own checks. Missing-information and healthy no-change outcomes are shown explicitly with no repair approval. Reviews name an exact immutable result version and the server-configured operator; notes render as text. The JSON report includes evidence, checks, version, review and audit events.

`backend/tests/e2e/browser_pages_smoke.py` covers metric search and metadata, preselected setup with reload and cancel, run and workflow execution, section links with history, unavailable activity, settings, workflow detail and a missing metric across six page types at widths from 320 to 1440 pixels.

## API

| Method and route | Behavior |
| --- | --- |
| `GET /healthz`, `GET /readyz` | Process liveness; database readiness |
| `GET /api/config` | Operator name, investigator availability and `access_mode`; no keys |
| `GET /api/incidents`, `GET /api/incidents/{case_id}` | Scenario list; public contract, SQL, lineage, source schema and version. No rows, regression snapshots or reference answers |
| `GET /api/stats` | Database aggregate across the whole workspace |
| `GET /api/jobs`, `POST /api/jobs` | Latest 50 summaries; queue an investigation (Idempotency-Key required) |
| `GET /api/jobs/{id}` | Result, evidence trace, version, review and events |
| `POST /api/jobs/{id}/candidates` | Queue edited SQL against the exact parent version |
| `POST /api/jobs/{id}/review` | Approve or reject the exact result version |
| `POST /api/jobs/{id}/resume` | Continue a paused LangGraph run into one child ([Agent](AGENT.md#checkpoints-receipts-and-continuation)) |
| `POST /api/jobs/{id}/cancel` | Cancel a queued or running job |
| `GET /api/jobs/{id}/report` | JSON report download |
| `GET/POST /api/workflows`, `GET /api/workflows/{id}`, `POST /api/workflows/{id}/cancel` | Multi-metric workflows |
| `GET /api/spend` | Spend ledger summary |

Idempotency keys are 8 to 128 characters. Repeating a key with the same body returns the same job; a different body returns `409`. At most 16 jobs may be queued or running. JSON bodies are limited to 75 KB and candidate SQL to 50,000 characters, executed under the read-only budgets.

## Persistence and recovery

The local store is `jobs.sqlite` plus per-job `runs/` directories in the state directory, using WAL, foreign keys, parameterized statements and `BEGIN IMMEDIATE`. PostgreSQL replaces it when `SQLARBITER_DATABASE_URL` is set ([Deployment](../operations/DEPLOYMENT.md#postgresql)). A claim assigns one owner and a 300-second lease, renewed every 30 seconds. Expired jobs become `interrupted` when a worker next claims work and are never retried automatically. A worker must still hold the unexpired lease to publish.

List responses project public metadata and outcome fields in SQL; indexes support recent-run ordering, status scans and audit lookup. Source and execution hashes bind the incident records, contract, transformations, evaluator and exported runtime, and a change before execution fails the queued job. Result hashes bind the source version, proposed SQL, evidence and grading. Reviews are immutable through the API and identical repeats are idempotent. The database itself remains administrator-editable, not a tamper-proof ledger.

## Multi-metric workflows

An operator can group one to six distinct metrics into a named workflow. Each metric gets its own investigation, version, verification and review. Hosted investigators run a separate, budgeted investigation per metric.

`POST /api/workflows` takes a bounded name, unique case IDs, an investigator and an engine. An idempotency key and request digest identify the whole operation, and one transaction checks the 16-job limit and creates every member job, its ordered membership and audit entries, or none of them. Case versions are captured at admission and rechecked during execution.

`resolved` counts completed candidate or no-change decisions that passed independent checks. `attention` counts failed, interrupted and paused work plus unresolved or rejected outcomes. Member runs are immutable: later clarifications or SQL revisions create child runs and do not change the group totals. Approval is not production application.

## Cancellation and process ownership

Job and workflow cancellation use the shared access, origin and body rules. A bounded reason is saved to the audit trail. Workflow cancellation affects only queued and running members.

| Before | Action | After |
| --- | --- | --- |
| queued | Operator cancels | `cancelled` immediately; never claimed |
| running | Operator cancels | `cancelling`; owner stops local execution |
| cancelling | Owner acknowledges | `cancelled`; result publication forbidden |
| running | Worker shuts down | `interrupted`; no automatic replay |
| cancelling | Lease expires | `cancelled`; no automatic replay |
| completed or paused | Single-run cancellation | `409`; saved result preserved |

The worker runs investigators in their own POSIX process groups and polls cancellation, ownership, shutdown and elapsed time about every 200 ms. It sends TERM, escalates to KILL, reaps the process and checks ownership again before publishing. Output streams go to temporary files checked against a 2 MB threshold. Subprocess deadlines are 30 seconds for the fixed diagnostic and 270 seconds for hosted investigators. Heartbeats keep a cancelling lease alive while its owner shuts down, and racing cancellation and publication serialize through the same ownership checks. Provider requests already sent may still complete and be billed.

## Access boundary

The local launcher binds `127.0.0.1`. Unauthenticated API requests require a loopback peer and an allowed Host header. POST requests must be JSON and same-origin. Responses carry a restrictive content security policy and `no-store`, and no CORS is enabled. `SQLARBITER_ACCESS_TOKEN` (at least 32 characters) enables shared bearer access; the browser keeps it in memory only. `SQLARBITER_PUBLIC_ORIGIN` requires HTTPS and a configured token.

[Overview](OVERVIEW.md) · [Agent](AGENT.md) · [dbt](DBT.md)
