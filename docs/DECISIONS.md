# Architecture decisions

Each record states the decision and the constraint behind it. Superseded records are marked and point at their replacement.

| ID | Decision | Status |
| --- | --- | --- |
| [ADR-001](#adr-001-metric-contract) | Declared metric contract | Accepted |
| [ADR-002](#adr-002-independent-grading) | Independent grading outside the agent | Accepted |
| [ADR-003](#adr-003-guarded-sql-execution) | Guarded SQL execution | Accepted |
| [ADR-004](#adr-004-evidence-export-and-replay) | Evidence export and trace replay | Accepted |
| [ADR-005](#adr-005-clarification-and-no-change-outcomes) | Clarification and no-change outcomes | Accepted |
| [ADR-006](#adr-006-persistent-jobs-and-a-separate-worker) | Persistent jobs and a separate worker | Accepted |
| [ADR-007](#adr-007-version-bound-review) | Version-bound review | Accepted |
| [ADR-008](#adr-008-model-transport) | Official async SDK transport | Accepted |
| [ADR-009](#adr-009-analytical-engine-and-context-limits) | DuckDB engine and context limits | Accepted |
| [ADR-010](#adr-010-frozen-corpus-and-scoring) | Frozen corpus and Pass@k scoring | Accepted |
| [ADR-011](#adr-011-tracing) | OpenTelemetry tracing | Accepted |
| [ADR-012](#adr-012-langgraph-investigator) | LangGraph investigator with call receipts | Accepted |
| [ADR-013](#adr-013-plans-prechecks-and-bounded-correction) | Plans, prechecks, bounded correction | Accepted |
| [ADR-014](#adr-014-findings-memory-and-workflows) | Findings, memory index, multi-metric workflows | Accepted |
| [ADR-015](#adr-015-workbench-pages) | Workbench pages and bounded summaries | Accepted |
| [ADR-016](#adr-016-spend-admission) | Spend admission ledger | Accepted |
| [ADR-017](#adr-017-restricted-dbt-repair) | Restricted dbt repair | Accepted |
| [ADR-018](#adr-018-dbt-jobs-and-immutable-artifacts) | dbt jobs and immutable artifacts | Accepted |
| [ADR-019](#adr-019-postgresql-coordination-and-kubernetes) | PostgreSQL coordination and Kubernetes | Accepted |
| [ADR-020](#adr-020-request-bounded-public-sandbox) | Request-bounded public sandbox | Accepted |

## ADR-001 Metric contract

Revenue is completed-order item amounts in integer cents, on the authoritative business date, with the latest product category inside the snapshot. Refunds, tax, and accounting revenue recognition are excluded. The category rule is declared, not inferred.

## ADR-002 Independent grading

A Python source calculation accepts semantically valid SQL alternatives. Equal-amount and category-change cases reject fixes that only hide the symptom. Ambiguous reference sources raise evaluator errors instead of counting as agent failures. References and regression snapshots never enter the exported evidence.

## ADR-003 Guarded SQL execution

Each query runs against a fresh database in query-only mode, with an authorizer allowlist and row and progress limits. These are defense in depth inside the process; the container is the isolation boundary.

## ADR-004 Evidence export and replay

The investigator receives only the current source, schema, contract, lineage, change log, and SQL. Fixed and model investigators share six allowlisted tools. The evaluator replays trace records and rejects evidence that was not actually produced. The tool surface has no filesystem or import operation.

## ADR-005 Clarification and no-change outcomes

Authoritative event IDs define deduplication, so a payload conflict cannot be resolved with an arbitrary `MAX`. A missing timezone offset requires scoped clarification. Unequal UTC-boundary crossings stop a wrong local-date transformation from matching totals by accident. Healthy SQL must produce a no-change result.

## ADR-006 Persistent jobs and a separate worker

FastAPI handles HTTP and a separate worker executes investigations. Queued work, results, and reviews survive restart. Atomic claims, renewable leases, and explicit interrupted outcomes prevent concurrent ownership and automatic paid retries. SQLite is the offline adapter; PostgreSQL is selected with `VDIR_DATABASE_URL` ([ADR-019](#adr-019-postgresql-coordination-and-kubernetes)).

## ADR-007 Version-bound review

SHA-256 content versions bind source and execution inputs and complete results. Edited SQL becomes a separately verified job. Stale parent or result versions and approval of a failed candidate are rejected. Reviews are immutable through the API. Approval records a decision; it does not promote SQL.

## ADR-008 Model transport

The hosted investigator uses the official `AsyncAnthropic` client with typed streaming and preflight token counting, under application budgets. Failed or partial model metadata is persisted. This replaced an initial dependency-free urllib transport.

## ADR-009 Analytical engine and context limits

DuckDB is the default engine for the app and the benchmark; SQLite is the alternative. SQLGlot restricts the SELECT, table, and function surface. DuckDB disables external access and extensions and bounds memory and time. An automatic outer row cap, column, cell, and byte limits, paginated schema, and profile tools protect model context. Truncated results cannot pass verification.

## ADR-010 Frozen corpus and scoring

38 scenarios: six controls plus variants across eight SQL-shape templates. The manifest records groups, splits, source-independent references, and private regressions. Reports record Pass@k, SQL execution, calls, tokens, latency, and model-matched price estimates. Unknown cost is null. [Corpus](evaluation/BENCHMARK.md).

## ADR-011 Tracing

OpenTelemetry spans propagate through jobs, investigations, model rounds, tools, and verification. Export is JSONL locally or OTLP, with Phoenix as the local collector in Compose.

## ADR-012 LangGraph investigator

LangGraph 1.2.14 with the SQLite and PostgreSQL checkpointers. Prepare, model, evidence, decision, and clarification are separate transitions. Each provider call is reserved in a receipt journal before execution and persisted before the graph commit, so an unresolved call blocks replay instead of being billed twice. A verified clarification pauses the job; exact-version continuation creates a child that clones committed checkpoint state. Source, code, or package changes fail closed. The fixed diagnostic remains the default investigator. [Agent](architecture/AGENT-ORCHESTRATION.md).

## ADR-013 Plans, prechecks, and bounded correction

One controller, not competing agents. Strict Pydantic schemas define public hypothesis and test plans. A repair must cite an executed, complete query that matches a test in the latest plan. Public SQL prechecks enforce execution, output shape, and completeness, charge the existing budgets, and never read reference answers. Two structured corrections are allowed per run. An operator revision drops inherited agent metadata. Graph versions are not migrated; an older checkpoint requires a new run.

## ADR-014 Findings, memory, and workflows

A findings node accepts only interpretations bound to executed hypothesis-test citations. A twelve-identifier memory index is appended to the counted prompt. Static SQL and equality-join diagnostics replace unvalidated confidence scores. Multi-metric workflows are admitted all-or-nothing in one transaction, with owner-fenced cancellation and supervised subprocess groups. [Workflows](architecture/WORKFLOWS.md).

## ADR-015 Workbench pages

Each task has a URL-addressed page; evidence drawers and cancellation stay contextual dialogs. FastAPI serves only explicit page routes, so no catch-all hides API errors. Queue fields and outcomes are projected in SQL and totals are aggregated in the database, with indexes for recent, status, and audit queries. The metadata endpoint exposes no private regression sources. [Pages](architecture/APPLICATION-PAGES.md).

## ADR-016 Spend admission

A trusted shared ledger sits outside model-visible evidence. Policy is bound at creation. Worst-case cost is reserved atomically before generation, complete usage is reconciled, and unresolved reservations are retained. Automatic generation retries are disabled. This is estimated admission control, not an invoice guarantee. [Spending](architecture/SPENDING-AND-DBT.md).

## ADR-017 Restricted dbt repair

dbt runs in its own pinned environment because its Click dependency conflicts with the app. Repairs are limited to one upstream model and plain allowlisted `SELECT` SQL; only the declared `ref` is rendered. Five regression fixtures are built and checked independently before a verified diff is produced.

## ADR-018 dbt jobs and immutable artifacts

dbt runs reuse the persistent queue, worker, access boundaries, and exact-version review. Progress is owner-fenced and tied to real execution stages. The verified report, diff, and model text are stored in the immutable job result and their hashes are checked again at review and download. [dbt workflow](architecture/DBT-WORKFLOW.md).

## ADR-019 PostgreSQL coordination and Kubernetes

PostgreSQL handles replicated API and worker operation: advisory transaction locks for idempotent admission, `FOR UPDATE SKIP LOCKED` for competing claims, and lease checks on every publication. The PostgreSQL LangGraph checkpointer uses one stable thread per job. Compose is the local topology and Kustomize the Kubernetes packaging, with separate migration, API, and worker roles. Kind is the CI overlay. Terraform defines EKS, RDS, EFS, S3, ECR, and KMS. EFS provides the shared workspace filesystem. [Runtime](operations/PRODUCTION-FOUNDATION.md).

## ADR-020 Request-bounded public sandbox

The Vercel deployment runs request-bounded fixtures with signed browser envelopes instead of a shared ephemeral queue. Durable workers stay in the private deployment. Browser-local history and explicit replay and fork limits are accepted tradeoffs. [Sandbox](operations/PUBLIC-SANDBOX.md).
