# VerifyOps current handoff

Updated October 15, 2026. Start with the [README](../../README.md), [layout](../development/LAYOUT.md), [plan](PLAN.md) and [progress](PROGRESS.md).

A checkpointed LangGraph investigator uses bounded evidence tools and public corrective feedback. Independent SQL verification and a real dbt workflow check restricted patches across five fixtures and four output relations. PostgreSQL coordinates separate workers and optional graph checkpoints; workspace files still require shared same-node storage.

Public app: https://verifyops.vercel.app/demo. Recording: https://verifyops.vercel.app/demo/recording. Six original synthetic incidents. Run the fixed diagnostic, inspect source evidence, edit SQL, rerun independent regressions and review the exact checked result. Incorrect repairs cannot be accepted. No production warehouse writes or repository merges occur. Both mode and dataset scope must stay visible. No live-model quality, customer feedback or monitored persistent cloud claim is established.

The `chore/repository-structure` increment moves sources/docs into explicit areas and refreshes actual recordings. Native suites pass 147cases with5Postgres/dbt skips; actual Linux/container/deployment conclusions belong to required CI and source-linked publication records, not prepared files. Publish only through the [protected branch workflow](../../BRANCHING.md).

Keep data and ignored `.env`/runtime state unchanged. Do not copy provider keys between projects. The public entrypoint disables live model credentials. Checkpoint/review source fingerprints deliberately reject stale continuation after path/runtime changes; preserve historical records and start a new run.

Prior implementation and deployment narratives are retained in [dated handoff history](history/PRE-ORGANIZATION-HANDOFF.md). Current instructions and repository paths take precedence.
