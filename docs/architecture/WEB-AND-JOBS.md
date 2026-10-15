# Web workbench and persistent jobs

October 8 page update: [full task pages and section URLs](APPLICATION-PAGES.md) replace setup dialogs. Workflow collection/detail are separate; metric catalog/definitions and read-only settings are implemented. Local/Linux111unit +96browser checks and host45page/layout checks pass. API/current-public-metadata access tests retain the evaluator boundary. Earlier dialogs/layouts below are preserved historical descriptions.

October 8: [graph findings, multi-metric workflow admission, worker cancellation and new workflow pages](WORKFLOWS.md) are implemented and verified with 109 unit / 74 browser checks locally and in Linux containers. State is still single-host, and live model quality remains unmeasured. Earlier milestone evidence below is preserved.

Implemented October 7, 2026. Local application at http://127.0.0.1:8000 when the launcher is running. FastAPI serves an original HTML/CSS/JavaScript interface; the separate worker executes investigations and independent verification. This application belongs to the project, not the personal portfolio folder.

User-requested monochrome theme: black surfaces, white type and neutral gray controls/borders across desktop/mobile, evidence/SQL, dialogs, statuses and toasts. Success/failure/clarification retain explicit labels/icons and distinct/dashed borders; no color filter is used. October 8 adds a home overview, dedicated record pages and inspection overlays. Earlier UI milestones are preserved in PROGRESS.md.

## Operator journey

**Home** (`/`) shows actual workspace totals, five recent runs, provider readiness and six original selectable scenarios. Scenario cards preselect the incident in the launch dialog. **Investigations** (`/investigations`) is a full-width queue; **Run history** (`/runs`) is a searchable recent-run table. Selecting a run opens `/investigations/{id}`, with the finding/checks/editor and a separate context/progress panel. These same-origin routes survive browser Back/Forward and reload. The contextual back button returns to the originating home/queue/history view, retaining in-memory filters. Old `?job=` and known hash navigation links remain supported. Reload restores the run rather than unsaved form drafts.

Evidence and audit details open in native modal side drawers with Escape/close and focus restoration. Drawers show the selected result snapshot and actual source/result versions/events; polling does not silently change an open inspector to another version. Workspace search (⌘/Ctrl K or the toolbar button) is a native overlay with title/ID search across recent runs and page links, explicit empty state and standard Tab/Enter/Escape interaction. It does not imply global warehouse search. Missing runs have a visible error/retry path. Home/layout checks cover 320–1440 pixels; drawers are full-width on narrow displays.

Use **New investigation** to open a native dialog, select a sample metric, investigator and analytical engine, then submit a run. The rule-based workflow is the default; hosted/checkpointed AI is enabled only when provider/model configuration exists. Engine selection is submitted to the existing API and retained in revisions. The dialog supports keyboard submission, Cancel and Escape with restored focus.

The investigation queue searches titles/run IDs and filters verified repair candidates, missing-information outcomes, queued/running work and failures. Filters apply only to the latest 50 runs; the visible count/scope makes this explicit. “Repair candidates” includes reviewed proposals, not an unreviewed backlog, because job summaries do not expose review state. Workspace totals come from the full-workspace stats endpoint. The separate **Run history** view provides real title/ID, investigation method, outcome and dated creation time; page routes survive reload and selecting a row opens its full record.

Details show source scenario context, run method/engine, actual timestamps and recorded review actor/time. Inspect the finding and independent checks, expand actual tool evidence, and compare current/candidate SQL side by side on desktop (stacked on smaller screens). Editing SQL creates a new verification job. Approval is disabled until the edited version has its own successful checks. Missing source information and healthy no-change outcomes are explicit, with no repair approval. **Metric definition** exposes the authoritative contract. The audit trail/full version hash is a secondary expandable section. Tabs support arrows/Home/End and visible keyboard focus.

Unchanged polling preserves drafts/focus and avoids replacing queue/history DOM unnecessarily. Changing selected runs clears stale controls during loading; late responses for another selection or an older result cannot replace the current detail. Synthetic sample scope and absent production connections stay explicit. The UI does not imply SSO, customer warehouse connections or a production-ready deployment.

Graph-2 results add **Agent activity**, containing recorded hypothesis plans/SQL tests, actual node activity, corrections and public precheck status. This shows saved task artifacts, not hidden reasoning or fabricated live progress. Public checks cover execution/schema/completeness; independent correctness remains in Summary. Operator-edited revisions omit inherited agent workflow/graph/model metadata so checks from a different SQL version are not shown as current.

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
| POST /api/jobs/{id}/resume | Continue a paused LangGraph result into one immutable-parent child; exact parent_version, guidance and Idempotency-Key required |
| GET /api/jobs/{id}/report | Download JSON report |

Use an 8–128 character Idempotency-Key for each new run/revision. Repeating the same key/body returns the same job; reusing it with a different body returns 409. At most 16 queued/running jobs are admitted. Repeated submission does not silently create additional billable work. JSON changes have a 75 KB body limit; SQL is additionally capped at 50,000 characters and executed under existing read-only budgets.

## Persistence and recovery

October 8 queue reads project only public metadata and JSON outcome fields; full evidence results are not deserialized in Python for list responses. Totals use a database aggregate, preserving whole-workspace scope beyond the 50-item list. SQLite still parses stored JSON; these changes do not demonstrate distributed scale or measured speedup. Idempotent indexes support recent-run ordering, status/created scans and audit lookup. Overlapping interval refreshes are coalesced; selected-ID/timestamp guards and unchanged-render caching preserve the existing response/draft behavior.

State directory contains jobs.sqlite and per-job runs/. SQLite uses WAL, foreign keys, parameterized statements and BEGIN IMMEDIATE transactions. Separate API/worker processes share this local directory. Claims atomically assign one owner and a 300-second lease; the active worker renews it every 30 seconds. Expired jobs become interrupted when a worker next claims work. They are never automatically retried. Queued jobs survive process restarts. A worker must still own the unexpired lease to publish its result.

The selectable LangGraph investigator additionally persists local graph-checkpoints.sqlite/graph-receipts.sqlite inside its public evidence directory. Independently checked clarification decisions become `paused` results. The app accepts operator guidance for a unique, exact-version child continuation; parent results remain unchanged. It copies committed SQLite state with backup, restores consumed budgets and checks source/code/package version before model calls. Guidance does not replace authoritative source data. Unresolved request receipts block replay; current app interrupted jobs still require a new run. [Graph behavior and standalone recovery](AGENT-ORCHESTRATION.md).

Source/execution version hashes bind the incident records, contract, transformations, evaluator and exported runtime. Changes before execution fail the queued job. Result hashes bind source version, proposed SQL, evidence and grading. Revision creation checks the exact parent version; review creation checks the exact result version and rejects failed verification. An existing review is immutable through the API; an identical repeated review is idempotent. The local database remains administrator-editable, not a tamper-proof ledger.

## Access boundary

The local launcher binds 127.0.0.1; unauthenticated API requests require a loopback peer and an allowed Host. POST requests require JSON and reject mismatched browser origins. Responses use a restrictive content security policy. No general CORS permission is enabled.

VDIR_ACCESS_TOKEN enables shared operator bearer access. It must contain at least 32 characters. The browser prompts for the code and keeps it in memory, without storing it in the URL or browser storage. VDIR_PUBLIC_ORIGIN requires HTTPS plus configured operator access. Shared access is not individual identity, SSO, authorization roles or multi-tenant isolation; these remain release work. Authentication changes are server-side configuration, not model instructions.

## Verification evidence

Completed October 8 Linux container also passes **92 unit / 31 workflow browser / 18 graph browser checks**, exit 0; fixed benchmark38/38. Evidence: artifacts/generated/workspace-pages-001/summary.json/logs/copied reports. This supersedes pending Linux verification in the local milestone below. Existing Compose deployment is unchanged from October7; host8000 runs the new pages.

October 8 source passes **92 unit / 31 workflow browser / 18 scripted-provider graph browser checks locally**. New coverage: real home data/scenarios, full-record route/reload, contextual/browser navigation, drawer focus/audit/evidence, keyboard search/empty state, mobile drawer, responsive neutral home palette, missing-run recovery, protected page/API boundaries and summary aggregation beyond 50 results. Current browser artifacts: browser-smoke-77173933 and browser-graph-6385015a. Desktop/mobile screenshots inspected; host route restart preserved one existing run/version. Linux packaging result is appended after execution. Earlier counts below are milestone history.

Current graph-2 source passes **89 unit / 21 workflow browser / 18 graph browser checks locally**, including rendered planned repairs/public prechecks, paused guidance activity, mobile plan layout and stale metadata removal after an operator revision. Browser artifact browser-graph-19a63c9c; screenshots inspected. [Graph policy and packaging evidence](AGENT-ORCHESTRATION.md). Below is the preceding UI-only milestone.

Latest UI redesign: **21 workflow browser checks, 11 scripted-provider LangGraph browser checks and 12 API tests pass locally**. Coverage retains repair/evidence/failed revision/exact review/XSS-safe notes/export/clarification/no-change/reload/worker shutdown, and adds modal keyboard behavior, SQL comparison, draft/focus preservation, submitted SQLite engine, queue filters/empty state, history search/navigation/reload, keyboard tabs and mobile history/dialog. Read-only host check covers **22 views across 320/390/768/1024/1440 pixels**, all computed colors neutral, no horizontal overflow/page errors or API mutations. Host report/screenshots: artifacts/generated/enterprise-ui-001. Run with the project .venv Python against setup/command-records/2026-10-07-enterprise-ui-check.py; workflow scripts regenerate their own ignored reports/screenshots. Desktop/mobile screens were visually inspected. Containers were not rebuilt for this frontend change; below is historical backend/container evidence.

59 unittest checks pass on Python 3.11.17 locally and inside containers, covering queue races, owner/lease renewal, restart persistence, idempotency, body/origin/host boundaries, exact-version review, immutable reviews, failing/mutating SQL and existing environment/model tests. Real Chromium smoke passed 13 checks including evidence expansion, edited-candidate approval blocking, failed revision, review/export, escaped notes, clarification, healthy no-change, browser reload, a 390-pixel mobile layout and idle launcher/worker shutdown.

Local generated browser report (local historical capture: `../../artifacts/generated/browser-smoke-76f81514/result.json`; not a published file), desktop view (local historical capture: `../../artifacts/generated/browser-smoke-76f81514/desktop-result.png`; not a published file) and mobile view (local historical capture: `../../artifacts/generated/browser-smoke-76f81514/mobile-result.png`; not a published file) are ignored artifacts, not portable source files. Regenerate with the browser smoke command in the README. Browser tests strip model credentials, disable .env loading and make no provider calls.

## Remaining production work

No cloud deployment or live hosted-model run exists. The earlier prepared-only Docker status is superseded: test/runtime images and Compose API/worker/Phoenix were built and run in a local Lima guest, with passing container tests and restart/tracing checks. Remote CI remains unverified. Model learning, customer-realistic incidents/untouched release splits, Postgres/object storage, individual authentication, distributed job orchestration, container-level repair isolation, operational alerts and controlled promotion remain unfinished.

Current app investigations explicitly record analytical engine (DuckDB default, SQLite optional) in the request/input version; candidate revisions retain the parent engine. Job state remains single-host SQLite WAL. For a distributed release replace queue leases with a durable queue/PostgreSQL claims; no such scaling implementation is claimed. Job/investigator/tool/verification traces are propagated into Phoenix. [Executed container/restart/tracing evidence](../evaluation/BENCHMARK.md).
