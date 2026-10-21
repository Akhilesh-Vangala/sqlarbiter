## October21 — no-credit reliability and availability

Public SSE delivery now retains terminal results/errors separately from a bounded progress mailbox, coalesces cross-thread wakeups and ends with actionable failure after 25 seconds. Slow/disconnected consumers do not receive late reports. Tests inject progress floods, worker faults, deadline expiry and disconnects; a running read-only thread may finish and is not claimed killed.

Agent boundary corrections are verified without model requests: VerifyOps rejects missing/partial usage in both controllers and marks incomplete receipt accounting unknown; RelayOps rejects malformed usage, non-finite/negative elapsed time and invalid tool names; QueryPilot rejects duplicate/non-finite/oversized/nontext model JSON and preserves complete valid tool transcripts. These are protocol reliability tests, not model quality measurements.

A credential-free public monitor checks five real upload formats, exact domain results, SSE progress, report authenticity/tamper rejection, rejection boundaries, current script delivery and recorded-video ranges. Required import/browser CI executes the actual monitor against its isolated local app. A separate twice-hourly canonical workflow retains bounded evidence. [Availability, schedule limitations and recovery](../operations/AVAILABILITY.md). Keep the last ready Vercel deployment serving while previews and protected CI run. Current publication results must be observed and recorded; older dated histories remain preserved.

Remaining gates: genuine private provider credentials/budget, live held-out/cost/latency benchmarks, configured hosted identity, durable isolated monitored tenant operation and actual-user feedback. No public provider enablement, external business writes, new cloud services or paid model calls.

# October16 — bounded multi-format import

The product accepts CSV, TSV, Excel .xlsx, JSON and JSONL, with explicit worksheet selection, deterministic normalization and unchanged domain rules. New parser/domain equivalence and actual five-format browser journeys are part of required CI. [Import contract](../product/FILE-IMPORTS.md). Publication status must be verified through the protected PR and canonical source metadata; live inference, hosted Auth and monitored durable customer execution remain separate gates. Previous release notes below are preserved.

# Active increment: coherent product workspace — October 15, 2026

The public root becomes a product landing page with dashboard, guided source/rule/review/result pages, actionable record-level errors, actual SSE progress, charts and inspectable evidence. Opt-in immutable device snapshots support history/projects/reload; changed reports are not presented as verified. Optional Supabase Auth/Postgres integration and owner-policy migration are implemented; hosted configuration, email and cloud operation remain unverified. [Design and boundaries](../product/PRODUCT-WORKSPACE.md). Local verification passed: 170-case Python 3.12 suite (one dbt case separately exercised successfully), real PostgreSQL ownership/concurrent quota checks, 96 existing private browser checks, the new 11-group product rehearsal and 14 automated accessibility views, plus original guided repair and updated upload journeys. Continuous source-bound recordings were refreshed. Protected CI and deployment remain pending until observed; existing histories below remain preserved.

# VerifyOps progress and evidence

## October 15 — Repository organization and demo refresh

Implemented explicit frontend/backend ownership, a curated technical documentation index, current README/evidence scope and original actual browser recordings. Native regression suites pass; protected remote checks and post-promotion public verification are the publication gates for this increment. Current paths and source ownership are documented in [layout](../development/LAYOUT.md).

| Existing evidence baseline | Scope |
| --- | --- |
| [CI38662563363](https://github.com/Akhilesh-Vangala/verifyops/actions/runs/38662563363) | Passed 147-case suite, real PostgreSQL/dbt, browser, container and Kind before this reorganization. |
| Public application | Synthetic SQL revisions, independent regression rejection and version-bound review. |
| New recording | Actual continuous Chromium capture and a separate six-frame GIF preview. [Provenance](../DEMO.md). |

Do not interpret the older source baseline as a test of new path changes. The required PR workflow verifies the new tree before merge; final publication evidence is linked in the merged PR and current Actions page.

No paid model calls or actual-user validation. The broader VerifyOps completion tracker remains1/9; this increment does not mark a live-model or monitored-cloud milestone complete.

[Full prior progress history](history/PRE-ORGANIZATION-PROGRESS.md).
