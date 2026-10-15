# VerifyOps component layout

Run commands from the repository root unless a command states otherwise. The file tree is organized by ownership at the root and responsibility inside each component.

```text
verifyops/
├── backend/
│   ├── src/vdir/
│   ├── tests/
│   ├── requirements/
│   ├── docker/
│   ├── data/
│   ├── agents/investigator/
│   └── dbt/revenue_incident/
├── frontend/
│   └── apps/
│       ├── demo/
│       │   └── assets/
│       │       ├── scripts/
│       │       ├── styles/
│       │       └── media/
│       ├── product/
│       │   ├── lib/
│       │   └── views/
│       ├── uploads/
│       └── workbench/
│           └── assets/
│               ├── scripts/
│               └── styles/
├── infrastructure/
│   ├── containers/
│   ├── kubernetes/
│   ├── terraform/
│   └── supabase/migrations/
├── scripts/
│   ├── checks/
│   ├── demos/
│   ├── deployment/
│   └── development/
├── docs/
│   ├── architecture/
│   ├── operations/
│   ├── evaluation/
│   ├── project/history/
│   └── assets/
│       ├── branding/
│       ├── diagrams/
│       ├── screenshots/
│       └── demos/
└── .github/
```

## Ownership and runtime boundaries

Backend APIs own request validation, identity and action authority. Agents propose bounded decisions; verification and execution code own whether a proposal passes and which effects may occur. Persistence and workers own recovery and claims. Frontend code owns presentation and browser interactions. Tests are grouped by capability, with shared fixtures and cross-component browser journeys identified separately.

Only GitHub/Python/Vercel discovery files, private-configuration examples and the primary README remain at the root. Compose is under infrastructure/containers; `scripts/deployment/compose.sh` supplies the repository project directory so build contexts, private root .env and existing volume naming retain their intended meaning. No live-model call or cloud apply is part of this reorganization.

Source-path changes intentionally change runtime and review fingerprints. Preserve old results; start a fresh investigation when stale checkpoints or checked proposals are rejected. The exportable VerifyOps investigator deliberately keeps a small flat runtime when copied into an isolated workspace; evaluator references remain outside that runtime.

[Branch policy](BRANCHING.md) · [Backend](../../backend/README.md) · [Frontend](../../frontend/README.md) · [Infrastructure](../../infrastructure/README.md) · [Scripts](../../scripts/README.md)

## Full directory navigation

```text
verifyops/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
├── backend/
│   ├── agents/
│   │   └── investigator/
│   ├── data/
│   │   ├── benchmark/
│   │   ├── development/
│   │   │   └── sql/
│   │   └── pricing/
│   ├── dbt/
│   │   └── revenue_incident/
│   │       ├── models/
│   │       ├── seeds/
│   │       └── tests/
│   ├── docker/
│   ├── requirements/
│   ├── src/
│   │   └── vdir/
│   │       ├── api/
│   │       ├── cli/
│   │       ├── domain/
│   │       ├── evaluation/
│   │       ├── persistence/
│   │       ├── platform/
│   │       ├── verification/
│   │       ├── workers/
│   │       └── workflows/
│   └── tests/
│       ├── agents/
│       ├── api/
│       ├── e2e/
│       ├── fixtures/
│       ├── persistence/
│       ├── verification/
│       └── workflows/
├── docs/
│   ├── architecture/
│   ├── assets/
│   │   ├── branding/
│   │   ├── demos/
│   │   ├── diagrams/
│   │   └── screenshots/
│   ├── demos/
│   │   └── history/
│   ├── development/
│   ├── evaluation/
│   ├── evidence/
│   ├── operations/
│   ├── product/
│   └── project/
│       └── history/
├── frontend/
│   └── apps/
│       ├── demo/
│       │   └── assets/
│       │       ├── media/
│       │       ├── scripts/
│       │       └── styles/
│       ├── product/
│       │   ├── lib/
│       │   └── views/
│       ├── uploads/
│       └── workbench/
│           └── assets/
│               ├── scripts/
│               └── styles/
├── infrastructure/
│   ├── containers/
│   ├── kubernetes/
│   │   ├── base/
│   │   └── overlays/
│   │       ├── aws/
│   │       └── kind/
│   ├── terraform/
│   └── supabase/migrations/
│       └── aws/
└── scripts/
    ├── checks/
    ├── demos/
    ├── deployment/
    └── development/
```
