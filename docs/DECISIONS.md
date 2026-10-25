# Decisions

## October13 — PostgreSQL coordination and Kubernetes staging boundary — Implemented foundation

Keep SQLite for offline development and preserved histories; select PostgreSQL through explicit environment configuration for replicated API/worker operation. Use advisory transaction locks for idempotent admission, `FOR UPDATE SKIP LOCKED` for competing claims, and ownership/lease checks for every result publication. Use the official PostgreSQL LangGraph checkpointer with one stable thread per job; retain separate call receipts and fail closed on uncertain provider results.

Use Docker Compose as the local topology and Kustomize as the Kubernetes packaging. The base separates migration, API, and worker roles. Kind supplies the CI overlay. AWS Terraform defines EKS, RDS, EFS, S3, ECR, and KMS. CI validates the configuration. EFS is the shared filesystem for path-based workspaces. [Implementation](operations/PRODUCTION-FOUNDATION.md).

## October12 — Browser dbt jobs and immutable stored artifacts — Implemented

Reuse the existing persistent queue/worker, access boundaries and exact-version review for the trusted sample; do not accept arbitrary project code uploads. Progress is owner-fenced and tied to real execution stages. Supervise dbt subprocess groups under cancellation/shutdown/deadlines. Store the verified report/diff/model text in the immutable job result, checking their hashes again at review/download, so mutable local files cannot change a downloaded artifact. Keep app and dbt dependencies in separate environments and include dbt in the runtime and test containers. [Flow](architecture/DBT-WORKFLOW.md).

## October12 — Spend admission and original dbt patch boundary — Implemented locally

Use a trusted shared ledger outside model-visible evidence. Bind policy at creation, atomically reserve before paid generation, reconcile complete usage, and retain unresolved allowances. Disable automatic real generation retries. Existing graph receipts block uncertain replay. This is estimated admission control, not an invoice guarantee.

Use a separate pinned dbt environment because its Click dependency differs from the app. Keep the original payment-delivery incident in dbt/revenue_incident; use actual manifest lineage/public files with the existing investigator. Restrict repairs to one upstream model and plain allowlisted SELECT SQL, render only our declared ref, and independently build/check five regressions before generating the verified diff. The baseline diagnostic knows the contract. Local exact-version review does not apply production code. [Implementation](architecture/SPENDING-AND-DBT.md). The same project is queued from the browser.

## October 8 — Distinct task pages and URL-addressed sections — Implemented

Use full creation forms and separate collection and detail views, public metric definitions, and read-only settings. Native links address sections and preserve keyboard, history, reload, and return behavior. The metadata endpoint exposes no private regression sources. [Page map](architecture/APPLICATION-PAGES.md).

## October 8 — Owned memory and lifecycle before additional runtimes — Implemented

Retain pinned LangGraph/Pydantic/AsyncAnthropic/SQLGlot/DuckDB/OTel. Add a strict findings node bound to complete executed hypothesis-test citations and a twelve-ID memory index in counted context, without claiming compaction. Add targeted static SQL/equality-join diagnostics rather than unvalidated confidence claims. Preserve private verification and review authority. Use the existing single-host queue transaction for all-or-nothing one-off workflow admission and owner-fenced cancellation; supervise subprocess groups and avoid automatic replay. Expose group and member outcomes through the workbench pages. [Implementation](architecture/WORKFLOWS.md).

## October 8 — Page routes and bounded summary queries

Implement user-requested home/full-record navigation and overlays in the existing same-origin browser app. FastAPI serves only explicit page routes; protected APIs still require their existing access checks, with no catch-all swallowing API errors. Native dialogs provide modal focus/Escape behavior. Browser history/contextual return state and legacy links are tested. Keep black/white/neutral design and actual development-data labels.

Project queue fields and JSON outcomes in SQL and aggregate totals in the database. Add idempotent recent, status, and audit indexes. PostgreSQL is the configured multi-worker store. [Runtime](operations/PRODUCTION-FOUNDATION.md).

## D001 — October 7, 2026 — Initial local engine — Superseded for active runtime by D011

Use standard-library SQLite to validate source and output semantics offline. PostgreSQL is the configured multi-worker store. dbt is the separate repair project.

## D002 — October 7, 2026 — Metric definition implemented

Completed-order item amounts, integer cents, authoritative business date, latest product category within snapshot. Excludes refunds/tax/accounting revenue recognition. Category rule is declared, not inferred.

## D003 — October 7, 2026 — Independent grading implemented

Python source calculation accepts semantically valid SQL alternatives. Equal-amount and category-change cases reject symptom-hiding fixes. Ambiguous reference sources raise evaluator errors. Evaluator references and regressions stay out of exported evidence.

## D004 — October 7, 2026 — Local execution controls implemented

Fresh memory database, query-only mode, authorizer allowlist and row/progress limits. Tested restrictions are defense in depth, not production process/container isolation.

## D005 — October 7, 2026 — Evidence export and replay implemented

Standalone runtime receives current source/schema/contract/lineage/change/SQL only. Fixed/model investigators share six allowlisted tools. Evaluator replays trace records to reject fabricated evidence; model tool boundary offers no filesystem or import operation. Isolated Python subprocess imports do not restrict host filesystem authority.

## D006 — October 7, 2026 — Initial native transport — Superseded by D011

Use a dependency-free Anthropic transport as the initial optional hosted-model adapter, retaining a provider-independent controller interface. Require explicit key/model configuration; no secrets read during development, no billable calls made. This does not finalize provider/model selection. Controller tests are scripted, not AI performance.

## D007 — October 7, 2026 — Clarification and healthy controls implemented

Authoritative event IDs define deduplication; payload conflict cannot be repaired by arbitrary MAX. Missing timezone offsets require scoped clarification. Unequal UTC-boundary crossings ensure a wrong local-date transformation cannot accidentally match totals. Healthy current SQL must produce no-change.

## D008 — October 7, 2026 — Persistent operational app implemented

Use FastAPI for HTTP and a separate worker. Queued work, results, and reviews persist across restart. Atomic claims, renewable leases, and explicit interrupted outcomes prevent concurrent ownership and automatic paid retries. SQLite is the offline adapter. PostgreSQL is selected with `VDIR_DATABASE_URL`.

## D009 — October 7, 2026 — Version-bound candidate review implemented

Bind source/execution inputs and complete results with SHA-256 content versions. Edited SQL becomes a separately verified job; stale parent/result versions and failed-candidate approval are rejected. Reviews are immutable through the API. Approval is a recorded review, not production promotion or a cryptographic claim about administrator-proof storage.

## D010 — October 7, 2026 — Original browser client and release packaging implemented

Author plain HTML, CSS, and JavaScript. Six scenarios and evidence are served by the API. Default API access is loopback-only, with same-origin JSON changes and optional shared-operator access. Docker Compose and CI run the container checks.

## D011 — October 7, 2026 — Async SDK and aligned runtime — Implemented/tested

Replace the urllib transport with official AsyncAnthropic and typed streaming. Application budgets stay in force. Failed or partial model metadata persists. Earlier dependency-free and no-retry transport decisions are superseded.

## D012 — October 7, 2026 — Analytical adapter and context controls — Implemented/tested

DuckDB default for app/benchmark, SQLite evidence alternative. SQLGlot restricts SELECT/table/function surface, DuckDB disables external access/extensions and bounds memory/time; SQLite retains authorizer/progress limits. Automatic outer row cap, columns/cells/bytes, paginated schema and profile tools protect context; incomplete results cannot pass reference verification. SQLite job persistence remains single-host; distributed claims require a different durable backend.

## D013 — October 7, 2026 — Frozen synthetic corpus and metrics — Implemented/tested

38 known scenarios with eight SQL-shape templates plus six controls. The manifest records groups and splits, source-independent references, private regressions, and repeated-attempt scoring. Pass@k, SQL execution, calls, tokens, latency, and model-matched price estimates are recorded. Unknown cost is null. A perfect fixed score validates the deterministic checker on this corpus.

## D014 — October 7, 2026 — Executed packaging and trace collection — Implemented/tested

OpenTelemetry JSONL and OTLP with parent propagation, and Phoenix for local traces. Docker test and runtime stages and Compose run without host mounts or copied credentials. GitHub Actions runs the container checks.

## D015 — October 7, 2026 — LangGraph investigator and explicit continuation — Implemented locally

Pin LangGraph 1.2.14 and the SQLite checkpointer 3.1.1. Keep the official Anthropic SDK, bounded public tools, and the external verifier. Separate prepare, model, evidence, decision, and clarification transitions. Persist per-call receipts before the graph commit. Unresolved calls stay blocked.

A verified clarification result is paused. Exact-version continuation creates a unique child, clones committed public checkpoint state, and preserves the parent result. Source, code, or package changes fail closed. Lease expiry interrupts the job without automatic replay. The baseline diagnostic remains the default. [Boundary](architecture/AGENT-ORCHESTRATION.md).

## D016 — October 7, 2026 — Operational monochrome interface — Implemented locally

Use a queue and detail workspace, run-history navigation, modal run creation, SQL comparison, and secondary audit metadata. Workspace totals cover full storage. Search and status filters cover the latest 50 summaries. Show source context, the configured operator, and the recorded review status. [Flow](architecture/WEB-AND-JOBS.md).

## D017 — October 7, 2026 — Plans, public prechecks and bounded feedback — Implemented locally

Keep one LangGraph controller. Use strict Pydantic schemas for public hypothesis and test plans. Require a cited executed test from the latest plan before a repair. Public SQL prechecks enforce execution, output shape, and completeness. They charge the existing budgets and persist receipts before graph commits. They do not read reference answers or private regressions. Two structured corrections are allowed. An operator revision drops inherited agent metadata. Graph version 2 rejects version-1 continuations. Stored results stay readable. The baseline diagnostic remains the default. [Behavior](architecture/AGENT-ORCHESTRATION.md).


## October14 — Executable public sandbox

Use request-bounded original fixtures and signed browser envelopes for Vercel interactive actions. Retain full private durable workers separately. This supports real verification/execution in public without claiming persistent effects or immutable global review. Browser session history and explicit replay/fork limitations are accepted tradeoffs; a shared ephemeral SQLite queue is not used for the new endpoints. [Details](operations/PUBLIC-SANDBOX.md).
