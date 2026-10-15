# Findings, multi-metric workflows and cancellation

October 8 later user direction: “have proper opages”. [Application pages](APPLICATION-PAGES.md) now provide full investigation/workflow setup and separate workflow collection/detail, with metrics/settings and direct section links. This supersedes setup-dialog descriptions below; cancellation/evidence inspection remain contextual dialogs. Agent/backend lifecycle behavior is unchanged.

October 8, 2026. Implemented in the existing project, with unchanged pinned dependencies. This milestone adds owned workflow **vdir-graph-3**, source-cited findings and public working memory, two analytical diagnostics, atomic multi-metric admission, supervised investigator cancellation and a monochrome Workflows page. Local checks: **109 unit tests, 31 existing browser checks, 20 scripted-provider graph browser checks and 23 automation browser checks**. The same checks pass inside Linux ARM64 Docker, exit 0. Read-only host verification covers 25 views and 52,049 neutral color values with no mutations, browser errors or overflow. Rebuilt Compose passes seven actual separate-worker workflow/cancellation/history checks.

## Business workflow

An operator can group one to six distinct development metrics into a named workflow. Each metric receives its own investigation, source/runtime version, independent verification and review record. The workflow shows original member outcomes, resolved/attention/cancelled counts and links to each full record. Operators can stop remaining work without deleting finished results. This makes a bounded revenue/event review operationally manageable while preserving each metric's correctness boundary.

These are one-off checks of the existing original synthetic scenarios. They do not ingest customer data, schedule recurring paid calls, modify a warehouse or promote a repair. Graph and hosted methods become selectable only with private configuration; the fixed diagnostic method remains the default. Choosing hosted methods performs a separate potentially billable investigation per selected metric, under each investigation's existing budget.

## Graph-3 findings and working memory

The graph now routes `record_findings` to a dedicated validation/checkpoint node. Strict Pydantic fields accept the current integer plan revision and one to three distinct declared hypotheses, with `supports`, `contradicts` or `inconclusive` assessments, summaries of at most 480 characters and one to four unique evidence IDs. Each ID must refer to a successful, complete public `query` whose SQL exactly matches that hypothesis's test. Unknown, stale, duplicate, partial or unrelated citations fail validation and use the existing shared two-correction allowance.

Findings are model interpretations, not certified conclusions. Replacing a finding updates the current revision/hypothesis entry; prior plan revisions remain present. Three plan revisions with three hypotheses bound the ledger to nine entries. Source/runtime fingerprints bind checkpoints to this run. Old graph-2 checkpoints cannot be continued after the version change; their saved completed results remain readable. Manual candidate revisions still discard inherited agent assessments.

Before each model round, the controller builds public working memory from the latest plan, its findings and the latest twelve evidence identifiers/methods/completeness flags. It appends this memory to the graph system prompt, and the official SDK counts and sends that same prompt. Raw result rows are not copied into this index. Original transcripts/receipts and resource limits remain intact: this is **not context compaction or a demonstrated token reduction**. Neither memory nor operator guidance overrides the authoritative contract or independent private evaluator. Structured memory follows the rationale in [Anthropic's context engineering guidance](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents); its benefit to live model quality still requires comparison.

```mermaid
flowchart TD
  M[Bounded model round with public memory] --> T[Read-only evidence and durable receipts]
  T --> M
  M --> P[Validate hypothesis plan]
  P --> M
  M --> F[Validate findings against executed test citations]
  F --> M
  M --> D[Decision and public SQL precheck]
  D --> V[Independent source replay and private regressions]
  V --> R[Exact-version operator review]
```

The app's Agent activity tab renders findings, evidence IDs, the memory index, plan tests, recorded node transitions and public precheck. These are recorded artifacts, not invented real-time agent narration. Findings survive a fresh controller's clarification continuation with unchanged evidence and retained round budgets, verified by an explicit test.

## Analytical tools

`inspect_sql({sql})` parses the permitted single read-only statement with SQLGlot and returns declared source dependencies, join clauses, aggregate names, grouping expressions and DISTINCT usage. This is static inspection: it neither compiles the statement against the database nor establishes semantic correctness.

`check_join({left_table,left_key,right_table,right_key})` validates declared tables/columns and performs a bounded aggregate equality-join profile in DuckDB or SQLite. It measures source rows, distinct non-null keys, duplicate keys, implied inner-join rows, unmatched left non-null rows and null-key counts. It does not return raw records. Null keys do not match. Composite keys, filters, temporal semantics and actual metric correctness need separate queries/checks. Existing read-only function/table restrictions and execution/resource budgets apply; expensive aggregates can be rejected.

Both tools consume the same 24-evidence-call allowance and create receipts/evidence IDs replayed by the trusted evaluator. Replaying valid diagnostics does not make a wrong repair pass. Oversized tool responses now discard the rejected result body before storing/sending the error record. Empty source tables are supported in the DuckDB materializer. SQLite authorization narrowly supports empty-column aggregate reads for declared sources/validated CTE names, retaining the single-query/table/function guards; see [SQLite authorization semantics](https://www.sqlite.org/c3ref/set_authorizer.html).

## Atomic workflow admission

POST `/api/workflows` accepts a bounded name, one to six unique case IDs, a configured investigator and an analytical engine. An idempotency key and request digest identify the entire operation. Under one SQLite `BEGIN IMMEDIATE` transaction, admission checks the total sixteen active-run limit and creates all member jobs, ordered membership and audit entries, or none. Repeating an identical request reuses the same workflow; changing it under the same key conflicts. Case versions are captured before admission and rechecked during execution.

GET `/api/workflows` returns the latest twenty groups; GET `/api/workflows/{id}` retrieves a specific group. Summaries project existing result fields without hydrating full evidence in Python. Member order is the requested order; the queue's ordinary creation-time/ID ordering may execute members in a different order.

`resolved` counts only completed candidate/no-change decisions that passed available independent checks. `attention` includes failed/interrupted/paused work and completed unresolved or rejected outcomes. Active members take status precedence; otherwise attention remains visible. A paused graph can therefore show less than 100% terminal progress with a needs-attention status. Original member runs are immutable: later clarifications or SQL revisions create separate child runs and do not replace the original group totals. Review approval is not resolution or production application.

## Cancellation and process ownership

POST `/api/jobs/{id}/cancel` and POST `/api/workflows/{id}/cancel` use existing shared access, origin, JSON/body limits and server-side ownership rules. A bounded reason is saved and rendered as text in the audit drawer. Workflow cancellation affects only queued/running members and preserves completed/paused results.

| Before | Action | After |
| --- | --- | --- |
| queued | Operator cancels | cancelled immediately; never claimed |
| running | Operator cancels | cancelling; owner stops local execution |
| cancelling | Same owner acknowledges | cancelled; result publication forbidden |
| running | Worker shuts down | interrupted; no automatic replay |
| cancelling | Worker lease expires | cancelled; no automatic replay |
| completed/paused | Single-run cancellation | conflict; saved result preserved |

The worker supervises investigator `Popen` processes in their own POSIX process groups. It polls cancellation/ownership/shutdown and elapsed time about every 200 ms, sends TERM and escalates to KILL if needed, reaps the process and checks ownership again before result publication. Output/error streams go to temporary files and are checked against a two-million-byte threshold; polling can allow transient overshoot, so this is not an OS disk quota. Existing 30-second fixed/270-second hosted subprocess deadlines remain. Private grading remains in the trusted worker with bounded SQL operations; cancellation can wait for an in-flight bounded grading operation, but publication is fenced.

Heartbeats keep a cancelling lease alive while its owner shuts down. Racing cancellation and result publication serialize through the same database ownership/status checks; a stale or cancelled owner cannot publish a result. Already sent provider requests may still complete or be billed. Cancellation is not a refund or exactly-once provider guarantee. Local checkpoint files are not deleted, but this milestone does not add application recovery of interrupted/cancelled runs; create a new run, or use the existing explicit standalone recovery policy where valid.

## UI and verification

New routes `/workflows` and `/workflows/{id}` support reload, browser navigation and investigation-to-workflow back links. The workflow setup and cancellation overlays use native dialogs with focus return/Escape behavior; draft fields survive polling. Missing groups show an explicit unavailable/retry state. All content uses text nodes. The home page links into workflows; run context offers cancellation only for applicable states. Black/white/neutral gray styling and responsive navigation are preserved.

Tests cover concurrent idempotent admission/capacity rollback, cancellation before/after claim and before publication, expired ownership, shutdown, actual child termination/reaping and output overflow; both diagnostic dialects include duplicate/null/unmatched/empty cases. Browser checks exercise real fixed-investigator grouped verification, scripted-provider graph findings, cancellation/audit safety, deep links/back/reload, no-approval cancelled outcomes, stable drafts and 320–1440-pixel layouts. No hosted model generation was performed.

Executed evidence is collected under `artifacts/generated/deep-workflows-001/summary.json` (ignored/local). Existing historical milestone reports remain intact. SQLite job/checkpoint state is still single-host; individual identity, distributed durable state, external dbt/warehouse integration, isolated execution, live matched evaluations, remote CI and cloud deployment remain release work.

## Executed release-check evidence

Test image/container: vdir:deep-workflows-test / vdir-deep-workflows-check, exit0. Both platforms pass109unit +31existing/20graph/23automationbrowser checks. Fixed38-case benchmark passes all known cases under this runtime hash. Compose rebuilt current API/worker after idle checks and verified grouped outcomes, exports/no automatic approval, immutable finished members and six cancellations; eighteen old Compose runs preserved. Host localhost8000 was restarted with one old run/status/result version preserved. No volumes/history were deleted or credentials copied. Full executed logs/copied reports/source hashes are in artifacts/generated/deep-workflows-001/summary.json; generated artifacts remain ignored and machine-local.
