# Evaluation and engineering evidence

## What is measured

| Scope | Implemented checks |
| --- | --- |
| Native regression suite | 147 cases. Five PostgreSQL or dbt cases skip unless that integration is configured. CI provides those services. |
| Public browser journey | Actual investigation, evidence/verification, version-bound review, false SQL repair rejection, JSON download, reload/history, mobile layout and video metadata. |
| Private integration | Original SQL/workflow/cancellation/pages suites and actual dbt browser execution; native PostgreSQL ownership and Kind two-worker execution. |
| Known synthetic regression | 38 fixed-diagnostic cases, plus five dbt fixtures and four output relations per patch verification. |

Local and container executions repeat the same distinct cases; do not add their counts as unique tests. The required CI artifacts are the source for those counts.

## Independent acceptance boundary

Source-level reference computations and private regression snapshots remain outside the exported investigator evidence. Trace replay checks provenance; candidate SQL is compared across snapshots. The dbt pipeline tests five designed fixtures and four output relations, including an equal-value false repair that passes the original incident but fails regression. These are contract-specific checks, not a proof of arbitrary SQL semantics.

[Known corpus and scoring details](BENCHMARK.md).
