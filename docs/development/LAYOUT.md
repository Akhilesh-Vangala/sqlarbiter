# Repository layout

Root folders are organized by deployable component, and folders inside a component by responsibility. The only top-level files are the Python, Vercel and Git configuration files, `app.py`, `.env.example` and the README. `scripts/checks/check_repository.py` requires every backend capability package to have its own README and validates every Markdown link.

```text
sqlarbiter/
├── .github/                 CI, public health monitor, issue and PR templates, CONTRIBUTING
├── app.py                   Vercel entrypoint (public build)
├── agent/investigator/      LangGraph graph, agent policy, model transport, evidence tools,
│                            engines, fixed diagnostic, spend bridge, telemetry, worker entry
├── backend/
│   ├── data/                benchmark and safety manifests, development contract and SQL, pricing
│   ├── dbt/revenue_incident/  dbt project: models, seeds, tests
│   ├── docker/              runtime and test image
│   ├── requirements/        hash-locked runtime, development and dbt dependencies
│   ├── src/sqlarbiter/
│   │   ├── api/             FastAPI app, public sandbox, envelope signing
│   │   ├── cli/             local launcher and graph continuation
│   │   ├── domain/          synthetic cases and fixture environment
│   │   ├── evaluation/      regression corpus, safety cases, benchmark runner
│   │   ├── persistence/     SQLite and PostgreSQL job stores, migrations
│   │   ├── platform/        configuration, observability, run contract, spend ledger
│   │   ├── product/         product routes and cloud accounts
│   │   ├── uploads/         imports, ingestion, analysis, SSE, report signing
│   │   ├── verification/    references, verifier, trace replay runner
│   │   ├── workers/         leased worker and database wait
│   │   └── workflows/       job service and dbt workflow
│   └── tests/
│       ├── agents/  api/  persistence/  verification/  workflows/  fixtures/
│       └── e2e/             workbench, graph, workflow, page and dbt browser journeys
├── frontend/apps/
│   ├── product/             product workspace (ES modules)
│   ├── demo/                interactive sandbox and recorded walkthrough
│   ├── workbench/           operator workbench assets
│   └── uploads/             upload walkthrough recording page and media
├── infrastructure/
│   ├── containers/          Compose topology
│   ├── kubernetes/          base resources with kind and aws overlays
│   ├── terraform/aws/       EKS, RDS, EFS, S3, ECR, KMS
│   └── supabase/            owner-isolated account migration
├── scripts/
│   ├── checks/              repository, RLS, public health, container entrypoint
│   ├── demos/               browser journeys and recorders
│   └── deployment/          Compose launcher and Kind smoke test
└── docs/
    ├── architecture/  product/  operations/  evaluation/  development/
    ├── demos/               recording manifests
    └── assets/demos/        recording preview
```

## Ownership

- **Backend API.** Owns request validation, origin checks, identity and the public write allowlist.
- **Agent.** Owns observation and proposal only. It keeps flat imports so it runs when exported into an isolated workspace without backend or evaluator code.
- **Verification and evaluation.** Decide whether a proposal passes, using references the agent never sees.
- **Workflows.** Own job execution, dbt builds and patch rendering.
- **Persistence and workers.** Own claiming, leases and recovery.
- **Frontend apps.** Own presentation and browser storage, with no build step and no Node service.

Source paths feed the runtime and review fingerprints, so moving files intentionally invalidates old checkpoints and checked proposals.

[Development](DEVELOPMENT.md) · [Branching](BRANCHING.md)
