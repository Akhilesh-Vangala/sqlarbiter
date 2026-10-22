# VerifyOps current implementation status

Updated October21,2026 — pre-live run contracts. This page is the current scoped implementation description; dated project history remains preserved. Final publication evidence is recorded separately after protected CI and deployment checks. Local native regressions and actual product/guided browser rehearsals pass; required remote checks are not yet assumed complete.

## Implemented in this increment

Guided upload reports carry a strict run-v1 provenance record: unique correlation ID, input and contract hashes, result fingerprint, producer versions, verification scope/count and explicit billing origin. Source contents, SQL and credentials do not enter that metadata. SSE progress and its final report share an ID; the synchronous endpoint exposes X-Run-ID. Existing report signatures cover the record and reject its modification. Older signed reports remain supported without inventing missing provenance.

The private queue/worker report shares a run ID and budget lineage with exported model calls. Graph continuations inherit the original budget run, so a fresh job ID does not reset its run allowance. Unknown charges block the shared SQLite ledger, including other runs with remaining budget. The separately frozen eight-case pre-live suite records clarification, no-change, verified-repair, execution, verification and evaluator outcomes; evaluator faults are excluded from accuracy. It is developer-authored known evidence, not unseen performance or measured injection resistance.

## Scope and remaining gates

Public workflows remain deterministic and report live_ai=false. No real provider request, hosted identity configuration, durable cloud tenant deployment, real ERP write or actual-user evaluation is established by these changes. Existing file formats, approvals, independent numerical checks, consented history and original demonstrations are preserved.

The first preparation increment begins with VerifyOps. Broader connector/dbt/semantic features, full cross-app budget policies and remote storage/checkpoint work are separate staged increments. A controlled actual-model run remains the next evidence gate after private credentials and a concrete evaluation budget.

[Repository layout](../development/LAYOUT.md) · [Availability and monitoring limits](../operations/AVAILABILITY.md).

[Pre-live suite, provenance and spending contract](../evaluation/PRE-LIVE.md).
