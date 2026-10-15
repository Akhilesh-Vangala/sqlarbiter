> Historical record. [Current project overview](../../../README.md) and [current handoff](../HANDOFF.md) take precedence.

# Evaluation

Verifier checks exact columns, string group keys, integer cents, unique groups, missing/unexpected groups and amount equality. Independent Python source aggregation has hand-calculated checks.

Current verification: **59 unittest checks passed on Python 3.11.17 locally and inside the Linux test container.** The earlier 50-check Python 3.9 milestone is historical. The original candidate comparison remains:

| Candidate | Incident | Equal-amount regression | Category-change regression |
| --- | --- | --- | --- |
| Current join | Fail | Fail | Fail |
| DISTINCT amount | Pass | Fail | Fail |
| Latest product version | Pass | Pass | Pass |

Alternative correlated-subquery repair passes. Invalid reference sources raise evaluator errors. Tested query restrictions and row/computation limits.

The expanded fixed workflow produces:

| Known scenario | Required outcome | Fixed workflow |
| --- | --- | --- |
| Product-version join inflation | Candidate repair | Pass |
| Repeated event deliveries | Event-ID repair retaining distinct equal-value events | Pass |
| Missing UTC offsets | Clarify t1/t2, utc_offset_minutes | Pass |
| Known offsets crossing UTC boundaries | Candidate UTC-date repair | Pass |
| Healthy transformation | No change | Pass |
| Conflicting payloads for event e5 | Clarify authoritative_event_payload | Pass |

Trace replay rejects forged evidence/results. Missing-information decisions must match the affected IDs and required source fields. Candidate/no-change decisions are compared with independent Python source calculations on all available scenario snapshots. This tests final correctness and provenance, not whether an explanation is persuasive or a cited query causally supports every claim.

Model interface tests cover tool-result ordering, error feedback, final-decision fields, false evidence IDs, round/tool budgets, truncation/refusal, missing configuration and sanitized HTTP failures. Scripted completions do not measure model accuracy. SDK tests additionally exercise typed streaming, rate-limit retry and pre-generation token rejection; they do not make live calls. [Expanded frozen corpus, scoring and measured results](../../evaluation/BENCHMARK.md).

These are known development checks, not held-out AI/benchmark metrics. Release evaluation requires richer faults, frozen splits, matched baselines, repeats, abstention and ablations; separately test environmental realism, operational properties and user usefulness.

## Operational app validation

Added atomic-claim/idempotency race tests, lease renewal/expiry/owner checks, persistent restart behavior, source-version rejection, API access/origin/host/body limits, immutable exact-version review and failed/mutating candidate blocking. Thirteen real-browser checks cover investigation, evidence, edited SQL/new verification, review/export, escaped notes, clarification, healthy no-change, reload, mobile layout and idle launcher/worker shutdown. See [browser/job evidence](../../architecture/WEB-AND-JOBS.md). Shared-token access is tested at the API; Container runtime and Compose persistence are now tested; live model, cloud recovery, performance under load and independent user usefulness remain untested.
