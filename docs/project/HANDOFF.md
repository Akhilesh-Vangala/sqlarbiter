# October16 — bounded multi-format import

The product accepts CSV, TSV, Excel .xlsx, JSON and JSONL, with explicit worksheet selection, deterministic normalization and unchanged domain rules. New parser/domain equivalence and actual five-format browser journeys are part of required CI. [Import contract](../product/FILE-IMPORTS.md). Publication status must be verified through the protected PR and canonical source metadata; live inference, hosted Auth and monitored durable customer execution remain separate gates. Previous release notes below are preserved.

# Active increment: coherent product workspace — October 15, 2026

The public root becomes a product landing page with dashboard, guided source/rule/review/result pages, actionable record-level errors, actual SSE progress, charts and inspectable evidence. Opt-in immutable device snapshots support history/projects/reload; changed reports are not presented as verified. Optional Supabase Auth/Postgres integration and owner-policy migration are implemented; hosted configuration, email and cloud operation remain unverified. [Design and boundaries](../product/PRODUCT-WORKSPACE.md). Local Python 3.12 regression: 170 suite cases, one real-dbt case separately passed; actual PostgreSQL RLS/quota checks, 96 private browser checks, 11 grouped product checks and 14 axe views passed. Source-bound recordings are current. Protected publication/deployment is pending until observed; existing histories below remain preserved.

# Active: visitor-owned CSV workspaces

Implementation adds `/uploads`, bounded own-data APIs, exact mapping/contracts, source-derived independently reconciled outputs and evidence exports. RelayOps retains exact-source human approval before export. Local verification: 154 tests with 5 environment-dependent skips, actual file-picker/checked-result/download/mobile/Clear/invalid-file browser journeys, plus refreshed original sample recordings. Protected CI and deployment checks are required before production promotion. Existing release-gate limitations remain. See [contracts](../product/USER-DATA.md).

# VerifyOps current handoff

Updated October 15, 2026. Start with the [README](../../README.md), [layout](../development/LAYOUT.md), [plan](PLAN.md) and [progress](PROGRESS.md).

A checkpointed LangGraph investigator uses bounded evidence tools and public corrective feedback. Independent SQL verification and a real dbt workflow check restricted patches across five fixtures and four output relations. PostgreSQL coordinates separate workers and optional graph checkpoints; workspace files still require shared same-node storage.

Public app: https://verifyops.vercel.app/demo. Recording: https://verifyops.vercel.app/demo/recording. Six original synthetic incidents. Run the fixed diagnostic, inspect source evidence, edit SQL, rerun independent regressions and review the exact checked result. Incorrect repairs cannot be accepted. No production warehouse writes or repository merges occur. Both mode and dataset scope must stay visible. No live-model quality, customer feedback or monitored persistent cloud claim is established.

The `refactor/component-structure` increment groups modules/tests by capability, moves versioned data/dbt under backend, separates native frontend scripts/styles/media, consolidates infrastructure/tooling and refreshes actual source-bound recordings. Native suites pass 147cases with5Postgres/dbt skips; actual Linux/container/deployment conclusions belong to required CI and source-linked publication records, not prepared files. Publish only through the [protected branch workflow](../development/BRANCHING.md).

Keep data and ignored `.env`/runtime state unchanged. Do not copy provider keys between projects. The public entrypoint disables live model credentials. Checkpoint/review source fingerprints deliberately reject stale continuation after path/runtime changes; preserve historical records and start a new run.

Prior implementation and deployment narratives are retained in [dated handoff history](history/PRE-ORGANIZATION-HANDOFF.md). Current instructions and repository paths take precedence.
