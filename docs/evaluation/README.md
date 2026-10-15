# Evaluation and engineering evidence

## What is measured

| Scope | Implemented checks |
| --- | --- |
| Native regression suite | 147 cases;5 PostgreSQL/dbt skips without configured integration tooling. CI provides the relevant integration services. |
| Public browser journey | Actual investigation, evidence/verification, version-bound review, false SQL repair rejection, JSON download, reload/history, mobile layout and video metadata. |
| Private integration | Original SQL/workflow/cancellation/pages suites and actual dbt browser execution; native PostgreSQL ownership and Kind two-worker execution. |
| Known synthetic regression | 38 fixed-diagnostic cases, plus five dbt fixtures and four output relations per patch verification. |
| Live model quality | Not measured. Scripted providers and fixed diagnostics are not model-accuracy evidence. |

Local and container executions repeat the same distinct cases; do not add their counts as unique tests. Actual result/source links are in [progress](../project/PROGRESS.md) and the required CI artifacts. The repository-layout increment must pass its own exact-head checks before merge.

## Independent acceptance boundary

Source-level reference computations and private regression snapshots remain outside the exported investigator evidence. Trace replay checks provenance; candidate SQL is compared across snapshots. The dbt pipeline tests five designed fixtures and four output relations, including an equal-value false repair that passes the original incident but fails regression. These are contract-specific checks, not a proof of arbitrary SQL semantics.

## Uncompleted evaluation gates

Frozen unseen task/data families, live model comparisons and repeats, representative real integrations, safety challenges, actual operator feedback, observed costs/latency, and monitored persistent cloud/load/restore evidence remain release work. No live quality, customer impact or causal inference result is inferred from deterministic success.

[Known corpus and scoring details](BENCHMARK.md) · [Prior evaluation history](../project/history/PRE-ORGANIZATION-evaluation-README.md).
