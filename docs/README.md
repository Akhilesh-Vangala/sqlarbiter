# VerifyOps technical documentation

Start with the [project README](../README.md) for the business problem, original visuals, working dbt demo and quick start. The Python package and some UI labels retain the earlier VDIR name.

## Review paths

Start with the [engineering case study](CASE-STUDY.md) and [recorded demo](DEMO.md) for a concise review of the business problem, owned contribution, failure behavior and evidence.

| Question | Read |
| --- | --- |
| What is the complete system flow? | [Full system flowcharts](17-SYSTEM-FLOWCHARTS.md), [system map](assets/verifyops-architecture.svg) |
| Where is the owned agent design? | [Checkpointed orchestration](11-AGENT-ORCHESTRATION.md), [findings, memory and cancellation](12-WORKFLOWS-AND-CANCELLATION.md), [AI design](05-AI-DESIGN.md) |
| How are candidate repairs verified? | [Architecture](02-ARCHITECTURE.md), [evaluation](06-EVALUATION.md), [source map](../README.md#technology-and-repository-map) |
| What happens in the real dbt workflow? | [Browser routes and review](16-DBT-BROWSER-WORKFLOW.md), [patch restrictions and spend admission](15-SPENDING-AND-DBT.md) |
| What is the observed evidence? | [Recorded evidence](../README.md#verified-evidence), [benchmark scope](10-REMEDIATION-AND-BENCHMARK.md), [progress](../PROGRESS.md) |
| How do jobs, recovery and costs work? | [Web and jobs](09-WEB-AND-JOBS.md), [graph recovery](11-AGENT-ORCHESTRATION.md), [spending](15-SPENDING-AND-DBT.md) |
| How do I run or inspect it? | [Public read-only showcase](https://verifyops.vercel.app), [Vercel boundary](18-VERCEL-SHOWCASE.md), [quick start](../README.md#run-locally), [setup](07-SETUP-AND-DEPLOYMENT.md) |
| How is the production foundation deployed? | [PostgreSQL, Docker, Kubernetes and AWS foundation](19-PRODUCTION-FOUNDATION.md) |
| What remains before release? | [Plan](../PLAN.md), [handoff](../HANDOFF.md), [decisions](DECISIONS.md) |

## Engineering tradeoffs

| Choice | Purpose | Current limit |
| --- | --- | --- |
| Investigation separate from verification | Plausible SQL and persuasive explanations cannot approve their own correctness. | Private regressions cover designed fixtures; they do not prove general warehouse correctness. |
| Restricted patch surface | Bind review to an exact source/model/patch/report version. | One trusted original dbt project, not arbitrary customer repository editing. |
| SQLite plus PostgreSQL queue adapters | Keep offline reproducibility while adding fenced multi-worker claims and production checkpoints. | Cloud execution still uses a shared filesystem until S3 synchronization and isolated tasks are implemented. |
| SDK receipts and estimated spend reservations | Retain unknown generation commitments and avoid paid blind replay. | Trusted estimates are not provider invoice caps. |
| Separate dbt environment | Resolve incompatible dependency constraints while retaining actual dbt CLI execution. | Additional packaging and supervision complexity; validated in the dedicated CI job and container. |

## Demo provenance

The original monochrome SVGs are architecture illustrations. [Catalog](assets/dbt-projects.png) and [repair](assets/dbt-investigation.png) screenshots show actual application/dbt execution on original synthetic data with the fixed diagnostic. They are not live AI evaluation results.

Current checks are linked to a recorded commit and Actions run in the README. Native, container and dedicated dbt jobs publish downloadable evidence. Live model comparisons, held-out evaluation, actual user feedback and monitored cloud delivery remain pending. Earlier milestones remain available in [README history](../README-HISTORY.md).

For repository development, use the [branch, PR and release policy](../BRANCHING.md).

- [Interactive public app, continuous recording and authority boundaries](20-INTERACTIVE-PUBLIC-DEMO.md)
