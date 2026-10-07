# Decisions

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
