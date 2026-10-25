# Web workbench and persistent jobs

FastAPI serves the HTML, CSS, and JavaScript workbench. A separate worker executes investigations and independent verification. [Page map](APPLICATION-PAGES.md). [Workflows and cancellation](WORKFLOWS.md).

The interface uses black surfaces, white type, and neutral controls. Success, failure, and clarification keep explicit labels.

## Operator journey

**Home** (`/`) shows actual workspace totals, five recent runs, provider readiness and six original selectable scenarios. Scenario cards preselect the incident in the launch dialog. **Investigations** (`/investigations`) is a full-width queue; **Run history** (`/runs`) is a searchable recent-run table. Selecting a run opens `/investigations/{id}`, with the finding/checks/editor and a separate context/progress panel. These same-origin routes survive browser Back/Forward and reload. The contextual back button returns to the originating home/queue/history view, retaining in-memory filters. Old `?job=` and known hash navigation links remain supported. Reload restores the run rather than unsaved form drafts.

Evidence and audit details open in native modal side drawers with Escape/close and focus restoration. Drawers show the selected result snapshot and actual source/result versions/events; polling does not silently change an open inspector to another version. Workspace search (⌘/Ctrl K or the toolbar button) is a native overlay with title/ID search across recent runs and page links, explicit empty state and standard Tab/Enter/Escape interaction. It does not imply global warehouse search. Missing runs have a visible error/retry path. Home/layout checks cover 320–1440 pixels; drawers are full-width on narrow displays.

Use **New investigation** to open a native dialog, select a sample metric, investigator and analytical engine, then submit a run. The rule-based workflow is the default; hosted/checkpointed AI is enabled only when provider/model configuration exists. Engine selection is submitted to the existing API and retained in revisions. The dialog supports keyboard submission, Cancel and Escape with restored focus.

The investigation queue searches titles/run IDs and filters verified repair candidates, missing-information outcomes, queued/running work and failures. Filters apply only to the latest 50 runs; the visible count/scope makes this explicit. “Repair candidates” includes reviewed proposals, not an unreviewed backlog, because job summaries do not expose review state. Workspace totals come from the full-workspace stats endpoint. The separate **Run history** view provides real title/ID, investigation method, outcome and dated creation time; page routes survive reload and selecting a row opens its full record.

Details show source scenario context, run method/engine, actual timestamps and recorded review actor/time. Inspect the finding and independent checks, expand actual tool evidence, and compare current/candidate SQL side by side on desktop (stacked on smaller screens). Editing SQL creates a new verification job. Approval is disabled until the edited version has its own successful checks. Missing source information and healthy no-change outcomes are explicit, with no repair approval. **Metric definition** exposes the authoritative contract. The audit trail/full version hash is a secondary expandable section. Tabs support arrows/Home/End and visible keyboard focus.

Unchanged polling preserves drafts and focus. Changing the selected run clears stale controls during loading. A late response for another selection cannot replace the current detail.

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

List responses project public metadata and JSON outcome fields. Totals use a database aggregate across the workspace, beyond the 50-item list. Idempotent indexes support recent-run ordering, status scans, and audit lookup. Overlapping interval refreshes are coalesced; selected-ID/timestamp guards and unchanged-render caching preserve the existing response/draft behavior.

State directory contains jobs.sqlite and per-job runs/. SQLite uses WAL, foreign keys, parameterized statements and BEGIN IMMEDIATE transactions. Separate API/worker processes share this local directory. Claims atomically assign one owner and a 300-second lease; the active worker renews it every 30 seconds. Expired jobs become interrupted when a worker next claims work. They are never automatically retried. Queued jobs survive process restarts. A worker must still own the unexpired lease to publish its result.

The selectable LangGraph investigator additionally persists local graph-checkpoints.sqlite/graph-receipts.sqlite inside its public evidence directory. Independently checked clarification decisions become `paused` results. The app accepts operator guidance for a unique, exact-version child continuation; parent results remain unchanged. It copies committed SQLite state with backup, restores consumed budgets and checks source/code/package version before model calls. Guidance does not replace authoritative source data. Unresolved request receipts block replay; current app interrupted jobs still require a new run. [Graph behavior and standalone recovery](AGENT-ORCHESTRATION.md).

Source/execution version hashes bind the incident records, contract, transformations, evaluator and exported runtime. Changes before execution fail the queued job. Result hashes bind source version, proposed SQL, evidence and grading. Revision creation checks the exact parent version; review creation checks the exact result version and rejects failed verification. An existing review is immutable through the API; an identical repeated review is idempotent. The local database remains administrator-editable, not a tamper-proof ledger.

## Access boundary

The local launcher binds 127.0.0.1; unauthenticated API requests require a loopback peer and an allowed Host. POST requests require JSON and reject mismatched browser origins. Responses use a restrictive content security policy. No general CORS permission is enabled.

`VDIR_ACCESS_TOKEN` enables shared operator bearer access. It must contain at least 32 characters. The browser prompts for the code and keeps it in memory. `VDIR_PUBLIC_ORIGIN` requires HTTPS plus configured operator access. The token is a shared operator credential. Authentication is server configuration.

