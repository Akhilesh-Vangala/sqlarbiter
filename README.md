# Verified Data Incident Resolution

Current development release: a monochrome investigation application with bounded analytical tools, a checkpointed LangGraph workflow, independent repair verification and exact-version operator review. Live model quality and cloud operation remain unverified. [GitHub publication status and CI scope](docs/14-GITHUB-PUBLICATION.md). The dated entries below preserve implementation history; the latest page milestone defines current coverage.

[Repository](https://github.com/Akhilesh-Vangala/verified-data-incident-resolution) · [GitHub Actions](https://github.com/Akhilesh-Vangala/verified-data-incident-resolution/actions/workflows/checks.yml)

![Verify workbench](https://github.com/Akhilesh-Vangala/verified-data-incident-resolution/actions/workflows/checks.yml/badge.svg)

October 8 proper-page milestone: full investigation/workflow setup, separate workflow collection/detail, searchable metric catalog/current public definitions and read-only settings. Evidence/SQL/activity/contract sections have native links and URLs with reload/history. Monochrome styling and existing review/cancellation remain. **111 unit / 96 browser checks pass locally and in Linux ARM64 Docker** (31existing/20scriptedgraph/23automation/22pages); host45views/92,049neutralcolors, no mutations/errors/overflow, one existing run/version preserved. [Page map and implementation](docs/13-APPLICATION-PAGES.md). Current evidence: artifacts/generated/proper-pages-001/summary.json. Earlier page/dialog and test counts below are historical.

October 8 deeper internal milestone: owned **vdir-graph-3** adds strict source-cited findings and bounded public working memory, static SQL/join-cardinality diagnostics, atomic one-off multi-metric workflows and supervised cancellation with publication fencing. New monochrome `/workflows` list/detail pages, setup/cancellation overlays, contextual member navigation and audit reasons expose actual state. **109 unit / 31 existing browser / 20 scripted graph browser / 23 automation browser checks pass locally and in Linux ARM64 Docker** (74 browser checks per platform), exit 0; unchanged fixed synthetic benchmark 38/38. Read-only host passes 25 views / 52,049 neutral color values, no mutations/errors/overflow. [Full implementation and limits](docs/12-WORKFLOWS-AND-CANCELLATION.md). Evidence: artifacts/generated/deep-workflows-001/summary.json. Old graph-2 checkpoints require new runs; saved results remain readable. Live model generation remains unmeasured. Earlier milestones below are preserved history.

Advanced applied/agentic AI project for investigating business-metric discrepancies, proposing evidence-backed SQL repairs, and independently checking them before operator review.

**Implemented and tested:** web workbench, persistent worker, async Anthropic SDK, selectable LangGraph investigator with persistent checkpoints/clarification continuation, DuckDB/SQLite tools, OpenTelemetry/Phoenix and a frozen 38-case synthetic corpus. **Live model quality is unmeasured:** no live generation has run. Training/cloud deployment remain planned. The project is public on GitHub; actual CI results and archived test reports are available through the Actions link above. Earlier dated publication/test statements below describe their own historical milestones.

## Run the app

Python **3.11.17**, matching the container. From this project directory:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
PYTHONPATH=src .venv/bin/python -m vdir.serve
```

On this Mac, the project environment is already installed: `.venv` points to `.venv311`; the old Python 3.9 environment is preserved as `.venv39-legacy`. Apple system Python is unchanged. If Python 3.11 is unavailable, install it with uv as described in [setup](docs/07-SETUP-AND-DEPLOYMENT.md).

Open **http://127.0.0.1:8000**. The launcher starts a separate worker and preserves runs/reviews in artifacts/generated/app. The app defaults to DuckDB analytics; SQLite retains local job state. The initial investigator is a fixed diagnostic baseline. A private `.env` is loaded automatically without overriding process environment variables. Copy .env.example on a fresh checkout; enter credentials locally, never in chat or Git.

The monochrome interface has a **Home** overview with actual recent runs and selectable metric scenarios, an **Investigations** queue, **Run history**, dedicated investigation pages and **Workflows** for grouped metric checks. Use **New investigation** to open its full setup page and select a sample metric, investigator and DuckDB/SQLite engine. **Run workflow** opens its own multi-metric setup page. **Metrics** contains public reporting definitions/SQL/source schemas, and **Settings** shows actual read-only configuration. Open a run to inspect evidence, compare current/candidate SQL and record an exact-version review. Evidence and audit drawers, contextual back navigation and workspace search (⌘/Ctrl K) support investigation work. History shows the latest 50 runs; totals cover all stored completed runs. Sample data and development scope remain explicit.

Current coverage: **92 unit / 31 workflow browser / 18 scripted-provider graph browser checks locally and inside Linux ARM64 Docker**, exit 0. Page reload, browser Back/Forward, overlays, home data and 320–1440-pixel home layout/palette checks pass. Queue/totals queries avoid complete-result hydration in Python. [Product flow and evidence](docs/09-WEB-AND-JOBS.md). Evidence: artifacts/generated/workspace-pages-001/summary.json. Fixed container benchmark also passed 38/38; no live AI-quality claim.

The `Checkpointed AI · LangGraph` option is implemented and enables with private provider/model configuration. Clarifications pause the graph; Resume investigation creates a version-checked child from saved evidence/checkpoints, retaining budgets and the original result. [Graph flow, recovery and limits](docs/11-AGENT-ORCHESTRATION.md). The rule-based baseline stays the default pending live evaluation.

The strengthened workflow adds strict hypothesis plans, executed/cited plan tests before repairs, public SQL prechecks and at most two corrective feedback iterations under the original budgets. **Agent activity** shows actual plans, tool steps and public assessments. Public prechecks do not certify semantic correctness; the independent verifier remains authoritative. Old graph-1 checkpoints need fresh investigations, with historical results preserved.

## Verified evidence — October 7, 2026

October 8 update: the page-based UI and query projection pass **92 unit / 31 workflow browser / 18 graph browser checks locally**. Current screenshots/reports: artifacts/generated/browser-smoke-77173933 and browser-graph-6385015a. The following October 7 results are historical to that milestone.

Current source: **89 unit tests / 21 workflow browser checks / 18 graph browser checks pass locally and inside Linux ARM64 Docker**. Tests include correction/citation/SQL/partial-output handling, retained plans and budgets, precheck crash recovery, independent semantic rejection and stale-assessment removal from operator revisions. Container fixed benchmark **38/38** with current runtime hash; rebuilt Compose passed six baseline investigations/reviews/exports. Evidence: artifacts/generated/agent-framework-001/summary.json; [details](docs/11-AGENT-ORCHESTRATION.md). Live AI quality remains unmeasured. The following preserves earlier integration evidence:

- **79 unittest tests**, **13 existing Chromium workflows** and **11 LangGraph browser checks** pass locally on Python 3.11.17 and inside the rebuilt Linux ARM64 test container. Graph recovery/continuation and real SDK mocked-HTTP streaming are tested; no live quality claim.
- The fixed baseline passed **38/38 synthetic cases** in both analytical engines. Three local DuckDB attempts per case passed **114/114**; this deterministic baseline does not measure model variance or AI accuracy.
- Real Docker Compose API/worker resolved all six app scenarios and retained completed jobs after restart. Phoenix received **63 spans across six job traces**.
- Live model runs, remote GitHub Actions, load/scalability tests and cloud deployment remain unverified.

Previous graph-1 evidence: artifacts/generated/langgraph-integration-001/summary.json (ignored, local). That Compose build passed six baseline workflows/reviews/exports; its fixed container benchmark passed 38/38 with the investigator hash from that milestone. Current source evidence is recorded above/in graph documentation.

[Remediation evidence and limits](docs/10-REMEDIATION-AND-BENCHMARK.md). Generated artifacts are ignored and must be regenerated on another machine.

## Tests and evaluation

```sh
.venv/bin/python -m playwright install chromium
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python tests/browser_smoke.py
PYTHONPATH=src .venv/bin/python tests/browser_graph_smoke.py
PYTHONPATH=src .venv/bin/python tests/browser_automation_smoke.py
PYTHONPATH=src .venv/bin/python tests/browser_pages_smoke.py
PYTHONPATH=src .venv/bin/python -m vdir --investigate artifacts/generated/six-case-run --engine duckdb
PYTHONPATH=src .venv/bin/python -m vdir.benchmark --output artifacts/generated/benchmark-run --engine duckdb --samples 3
```

Choose a fresh output directory for every run. Benchmark reports include Pass@1/Pass@3, SQL execution accuracy on private regression sources, rounds/tool calls, investigation/verification latency, reported tokens, failures and configurable cost estimates. Missing live costs/insufficient attempts produce null, never an invented zero.

For live evaluation, privately set ANTHROPIC_API_KEY and VDIR_ANTHROPIC_MODEL in .env, then run:

```sh
PYTHONPATH=src .venv/bin/python -m vdir --investigate artifacts/generated/live-six-run --investigator anthropic --engine duckdb
```

This makes billable API calls. The example model is validated against the account's Models API before generation. Claude 3.5 Sonnet is retired; see [model configuration](docs/05-AI-DESIGN.md). Scripted SDK/controller tests are separate from live model evaluation.

Use `--investigator langgraph` instead of `anthropic` for the graph investigator in either CLI/evaluation command. Six scripted graph scenarios pass independent verification in both engines; this is integration evidence, not a live quality score.

## Containers

```sh
docker build --target test -t vdir:test .
docker run --name vdir-check vdir:test
docker compose up --build -d
```

Compose requires a private operator access token of at least 32 characters. It runs API, worker and Phoenix with local volumes and loopback ports. See [setup/deployment](docs/07-SETUP-AND-DEPLOYMENT.md) for the validated Lima setup on this Mac and collector configuration. A local container demonstration does not establish cloud or production readiness.

## Documentation

- [Brief](docs/01-PROJECT-BRIEF.md), [architecture](docs/02-ARCHITECTURE.md), [flow](docs/03-PROJECT-FLOW.md)
- [Data](docs/04-DATA-AND-INTEGRATIONS.md), [AI design](docs/05-AI-DESIGN.md), [evaluation](docs/06-EVALUATION.md)
- [Setup/deployment](docs/07-SETUP-AND-DEPLOYMENT.md), [demo](docs/08-PORTFOLIO-AND-DEMO.md)
- [Web/API/jobs](docs/09-WEB-AND-JOBS.md), [remediation and benchmark](docs/10-REMEDIATION-AND-BENCHMARK.md)
- [Implemented LangGraph orchestration, checkpoints and continuation](docs/11-AGENT-ORCHESTRATION.md)
- [Findings, bounded workflow automation and cancellation](docs/12-WORKFLOWS-AND-CANCELLATION.md)
- [Application page map, setup flows and section links](docs/13-APPLICATION-PAGES.md)
- [Decisions](docs/DECISIONS.md), [references](docs/REFERENCES.md)
- [Plan](PLAN.md), [progress](PROGRESS.md), [handoff](HANDOFF.md)

Evaluator/reference code is in src/vdir; exported investigators are in investigator_runtime. Only the current source/contract/schema/lineage/changes are exported. Private regression sources and Python references stay with the evaluator. Tool allowlists and isolated Python imports are **not an OS sandbox**. SQLite job leases are single-host infrastructure; distributed state, per-investigation OS isolation, individual identity, realistic external incidents and cloud delivery remain release work.
