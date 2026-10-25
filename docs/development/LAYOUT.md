# VerifyOps component layout

Run commands from the repository root unless a command states otherwise. The file tree is organized by ownership at the root and responsibility inside each component.

```text
verifyops/
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
├── agent/
│   └── investigator/
├── backend/
│   ├── src/vdir/
│   ├── tests/
│   ├── data/
│   └── dbt/revenue_incident/
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
│   └── assets/
│       ├── branding/
│       ├── diagrams/
│       └── demos/
└── .github/
```

## Ownership and runtime boundaries

Backend APIs own request validation, identity and action authority. Agents propose bounded decisions; verification and execution code own whether a proposal passes and which effects may occur. Persistence and workers own recovery and claims. Frontend code owns presentation and browser interactions. Tests are grouped by capability, with shared fixtures and cross-component browser journeys identified separately.

GitHub, Python, and Vercel discovery files, private-configuration examples, and the primary README stay at the root. Compose is under `infrastructure/containers`. `scripts/deployment/compose.sh` sets the repository directory so build contexts, the private root `.env`, and volume names stay stable.

Source-path changes intentionally change runtime and review fingerprints. Preserve old results; start a fresh investigation when stale checkpoints or checked proposals are rejected. The exportable VerifyOps investigator deliberately keeps a small flat runtime when copied into an isolated workspace; evaluator references remain outside that runtime.

[Branch policy](BRANCHING.md) · [Backend](../../backend/README.md) · [Frontend](../../frontend/README.md) · [Infrastructure](../../infrastructure/README.md) · [Scripts](../../scripts/README.md)

## Full directory navigation

```text
verifyops/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/
├── agent/
│   └── investigator/
├── backend/
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
│   │   └── diagrams/
│   ├── demos/
│   ├── development/
│   ├── evaluation/
│   ├── operations/
│   └── product/
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
