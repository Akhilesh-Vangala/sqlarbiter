# Decisions

## October 8 — Distinct task pages and URL-addressed sections — Implemented

Follow the user's “have proper opages” direction with full creation forms and separate collection/detail views, public metric definitions and actual read-only settings. Use native links for URL-addressed sections and preserve keyboard/history/reload/contextual return behavior. Retain existing HTML/CSS/JavaScript dependencies and useful evidence/cancellation dialogs; the personal portfolio remains empty. Current metadata endpoint has the existing access controls and exposes no private regression sources. [Page map and tested behavior](13-APPLICATION-PAGES.md).

## October 8 — Owned memory and lifecycle before additional runtimes — Implemented

Retain pinned LangGraph/Pydantic/AsyncAnthropic/SQLGlot/DuckDB/OTel. Add a strict findings node bound to complete executed hypothesis-test citations and a twelve-ID memory index in counted context, without claiming compaction. Add targeted static SQL/equality-join diagnostics rather than unvalidated confidence claims. Preserve private verification and review authority. Use the existing single-host queue transaction for all-or-nothing one-off workflow admission and owner-fenced cancellation; supervise subprocess groups and avoid automatic replay. Expose actual group/member outcomes through monochrome native pages/dialogs. [Implementation/evidence/limits](12-WORKFLOWS-AND-CANCELLATION.md). PostgreSQL, identity, external connectors, live matched routing evaluations and cloud delivery remain release work; no additional runtime installed. Earlier entries remain dated history.

## October 8 — Page routes and bounded summary queries

Implement user-requested home/full-record navigation and overlays in the existing same-origin browser app. FastAPI serves only explicit page routes; protected APIs still require their existing access checks, with no catch-all swallowing API errors. Native dialogs provide modal focus/Escape behavior. Browser history/contextual return state and legacy links are tested. Keep black/white/neutral design and actual development-data labels.

Project queue fields/JSON outcomes in SQL and aggregate totals in the database, avoiding complete result hydration in Python on every poll. Add idempotent recent/status/audit indexes, retaining SQLite's single-host limitation. Larger PostgreSQL/checkpointer/cancellation/event-stream and React/TypeScript/TanStack Query migrations are proposals documented under workspace setup, not dependencies silently added during this redesign.

## D001 — October 7, 2026 — Initial local engine — Superseded for active runtime by D011

Use standard-library SQLite on available Python 3.9.6 to validate source/output semantics immediately. This is an environment choice, not a production stack or budget restriction. dbt/analytical warehouse integration planned.

## D002 — October 7, 2026 — Metric definition implemented

Completed-order item amounts, integer cents, authoritative business date, latest product category within snapshot. Excludes refunds/tax/accounting revenue recognition. Category rule is declared, not inferred.

## D003 — October 7, 2026 — Independent grading implemented

Python source calculation accepts semantically valid SQL alternatives. Equal-amount and category-change cases reject symptom-hiding fixes. Ambiguous reference sources raise evaluator errors. Evaluator references/regressions now stay out of exported evidence; OS isolation remains pending.

## D004 — October 7, 2026 — Local execution controls implemented

Fresh memory database, query-only mode, authorizer allowlist and row/progress limits. Tested restrictions are defense in depth, not production process/container isolation.

## D005 — October 7, 2026 — Evidence export and replay implemented

Standalone runtime receives current source/schema/contract/lineage/change/SQL only. Fixed/model investigators share six allowlisted tools. Evaluator replays trace records to reject fabricated evidence; model tool boundary offers no filesystem or import operation. Isolated Python subprocess imports do not restrict host filesystem authority.

## D006 — October 7, 2026 — Initial native transport — Superseded by D011

Use a dependency-free Anthropic transport as the initial optional hosted-model adapter, retaining a provider-independent controller interface. Require explicit key/model configuration; no secrets read during development, no billable calls made. This does not finalize provider/model selection. Controller tests are scripted, not AI performance.

## D007 — October 7, 2026 — Clarification and healthy controls implemented

Authoritative event IDs define deduplication; payload conflict cannot be repaired by arbitrary MAX. Missing timezone offsets require scoped clarification. Unequal UTC-boundary crossings ensure a wrong local-date transformation cannot accidentally match totals. Healthy current SQL must produce no-change.

## D008 — October 7, 2026 — Persistent operational app implemented

Use FastAPI for HTTP and a separate worker with SQLite transactions for the local product slice. Avoid request-bound fire-and-forget execution: queued work/results/reviews persist across restart. Atomic claims, renewable leases and explicit interrupted outcomes prevent concurrent ownership and automatic paid retries. Single-host state is a local choice; PostgreSQL/distributed orchestration remain future work.

## D009 — October 7, 2026 — Version-bound candidate review implemented

Bind source/execution inputs and complete results with SHA-256 content versions. Edited SQL becomes a separately verified job; stale parent/result versions and failed-candidate approval are rejected. Reviews are immutable through the API. Approval is a recorded review, not production promotion or a cryptographic claim about administrator-proof storage.

## D010 — October 7, 2026 — Original browser client and release packaging implemented

Author plain HTML/CSS/JavaScript within the existing project; six scenarios and evidence are served by real endpoints. No separate frontend build or personal portfolio work. Use loopback-only default API access, same-origin JSON changes and optional shared-operator access. Shared credentials do not establish individual identity. Docker/Compose and CI definitions prepared, not executed on a cloud account.

## D011 — October 7, 2026 — Async SDK and aligned runtime — Implemented/tested

Replace urllib AI transport with official AsyncAnthropic and typed streaming/preflight token counting; max_retries=1 and application budgets. Python 3.11.17 is the active local/container interpreter. Failed/partial model metadata persists. Live generation pending API key; do not equate transport tests with AI results. Earlier dependency-free/3.9/no-retry decisions are superseded.

## D012 — October 7, 2026 — Analytical adapter and context controls — Implemented/tested

DuckDB default for app/benchmark, SQLite evidence alternative. SQLGlot restricts SELECT/table/function surface, DuckDB disables external access/extensions and bounds memory/time; SQLite retains authorizer/progress limits. Automatic outer row cap, columns/cells/bytes, paginated schema and profile tools protect context; incomplete results cannot pass reference verification. SQLite job persistence remains single-host; distributed claims require a different durable backend.

## D013 — October 7, 2026 — Frozen synthetic corpus and metrics — Implemented/tested

38 known scenarios with eight new SQL-shape templates/data variants plus six controls. Explicit group/split manifest, source-independent references, private regressions and repeated attempt scoring. Record Pass@k, SQL execution, calls/rounds, tokens/latency and explicit model-matched price estimates; unknown cost is null. Perfect fixed scores validate machinery, not AI performance. Dataset realism and learned-policy justification remain open.

## D014 — October 7, 2026 — Executed packaging and trace collection — Implemented/tested

OTel JSONL/OTLP with parent propagation and Phoenix metadata collection. Run actual Docker test/runtime stages and Compose in Lima without host mounts or copied credentials. 59 tests/13 browser checks, six Compose scenarios, restart preservation and 63 Phoenix spans verified. GitHub workflow now runs container checks; remote CI still pending publication. Local VM is not cloud deployment.

## D015 — October 7, 2026 — LangGraph investigator and explicit continuation — Implemented locally

User explicitly requests LangGraph integration. Pin LangGraph 1.2.14/SQLite checkpointer 3.1.1, retain the official Anthropic SDK, bounded public tools and trusted external verifier. Separate prepare/model/evidence/decision/clarification transitions; persist per-call receipts before graph commit to close tested result-to-checkpoint crash windows. Unresolved calls remain blocked, avoiding silent repeated paid work. No in-memory durability claim.

The app's verified clarification result is paused. Exact-version/idempotent continuation creates a unique child, clones committed public checkpoint state and preserves parent result/history. Budgets and provider preflight counters survive resume; source/code/package changes fail closed. Current job lease expiry still interrupts without automatic replay. Standalone recovery is explicitly requested. Keep baseline default pending live evidence. PostgreSQL/Temporal/MCP remain release choices, not integrations. [Detailed boundary and evidence](11-AGENT-ORCHESTRATION.md).

## D016 — October 7, 2026 — Operational monochrome interface — Implemented locally

User requires a credible company-facing UI. Use a focused queue/detail workspace, real run-history navigation, modal run creation, readable SQL comparison and secondary audit metadata. Preserve prior monochrome direction. Workspace totals cover full storage; search/status filters cover only the latest 50 summaries. Do not label verified candidates as pending review without summary review data. Show source context, configured operator and actual review status; avoid fake business KPIs, identity, connections or production claims. Existing plain HTML/CSS/JavaScript fits this UI scope without a new framework/build pipeline. Native dialogs and keyboard tabs support accessible navigation; selection loading/response guards prevent stale controls, unchanged polling preserves drafts. [Flow and local validation](09-WEB-AND-JOBS.md).

## D017 — October 7, 2026 — Plans, public prechecks and bounded feedback — Implemented locally

User asks to improve the agentic framework. Deepen existing LangGraph rather than add competing controllers. Use strict Pydantic schemas for public hypothesis/test plans; require a cited executed latest-plan test before a repair. Keep healthy no-change/clarification lightweight. Public SQL prechecks enforce safe execution/output shape/completeness, charge existing budgets and persist receipts before graph commits. They never read reference answers or private regressions. Permit two total structured corrections within original budgets; restore plans/counters/activity on continuation. Record actual activity for operator review and remove inherited metadata from manually revised SQL. Live quality improvement is unmeasured; retain baseline default pending evidence. Owned graph version 2 intentionally rejects version-1 continuations instead of silently migrating state; stored historical results remain available. [Behavior and tests](11-AGENT-ORCHESTRATION.md).
