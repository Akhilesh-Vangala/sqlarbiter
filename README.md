# Verified Data Incident Resolution

Advanced applied/agentic AI project for investigating business-metric discrepancies, proposing evidence-backed SQL repairs, and independently checking them before operator review.

**Implemented and tested:** web workbench, persistent worker, async Anthropic SDK integration, DuckDB/SQLite analytical tools, OpenTelemetry/Phoenix tracing, and a frozen 38-case synthetic evaluation corpus. **Live model quality is unmeasured:** no API key has been supplied and no live generation has run. Training and cloud deployment remain planned. GitHub URL: **TBD**; local project Git repository initialized; publication and remote CI pending repository details/access.

## Run the app

Python **3.11.17**, matching the container. From this project directory:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
PYTHONPATH=src .venv/bin/python -m vdir.serve
```

On this Mac, the project environment is already installed: `.venv` points to `.venv311`; the old Python 3.9 environment is preserved as `.venv39-legacy`. Apple system Python is unchanged. If Python 3.11 is unavailable, install it with uv as described in [setup](docs/07-SETUP-AND-DEPLOYMENT.md).

Open **http://127.0.0.1:8000**. The launcher starts a separate worker and preserves runs/reviews in artifacts/generated/app. The app defaults to DuckDB analytics; SQLite retains local job state. The initial investigator is a fixed diagnostic baseline. A private `.env` is loaded automatically without overriding process environment variables. Copy .env.example on a fresh checkout; enter credentials locally, never in chat or Git.

## Verified evidence — October 7, 2026

- **59 unittest tests** and **13 Chromium workflow checks** passed locally on Python 3.11.17 and inside the Linux ARM64 test container.
- The fixed baseline passed **38/38 synthetic cases** in both analytical engines. Three local DuckDB attempts per case passed **114/114**; this deterministic baseline does not measure model variance or AI accuracy.
- Real Docker Compose API/worker resolved all six app scenarios and retained completed jobs after restart. Phoenix received **63 spans across six job traces**.
- Live model runs, remote GitHub Actions, load/scalability tests and cloud deployment remain unverified.

[Remediation evidence and limits](docs/10-REMEDIATION-AND-BENCHMARK.md). Generated artifacts are ignored and must be regenerated on another machine.

## Tests and evaluation

```sh
.venv/bin/python -m playwright install chromium
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python tests/browser_smoke.py
PYTHONPATH=src .venv/bin/python -m vdir --investigate artifacts/generated/six-case-run --engine duckdb
PYTHONPATH=src .venv/bin/python -m vdir.benchmark --output artifacts/generated/benchmark-run --engine duckdb --samples 3
```

Choose a fresh output directory for every run. Benchmark reports include Pass@1/Pass@3, SQL execution accuracy on private regression sources, rounds/tool calls, investigation/verification latency, reported tokens, failures and configurable cost estimates. Missing live costs/insufficient attempts produce null, never an invented zero.

For live evaluation, privately set ANTHROPIC_API_KEY and VDIR_ANTHROPIC_MODEL in .env, then run:

```sh
PYTHONPATH=src .venv/bin/python -m vdir --investigate artifacts/generated/live-six-run --investigator anthropic --engine duckdb
```

This makes billable API calls. The example model is validated against the account's Models API before generation. Claude 3.5 Sonnet is retired; see [model configuration](docs/05-AI-DESIGN.md). Scripted SDK/controller tests are separate from live model evaluation.

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
- [Decisions](docs/DECISIONS.md), [references](docs/REFERENCES.md)
- [Plan](PLAN.md), [progress](PROGRESS.md), [handoff](HANDOFF.md)

Evaluator/reference code is in src/vdir; exported investigators are in investigator_runtime. Only the current source/contract/schema/lineage/changes are exported. Private regression sources and Python references stay with the evaluator. Tool allowlists and isolated Python imports are **not an OS sandbox**. SQLite job leases are single-host infrastructure; distributed state, per-investigation OS isolation, individual identity, realistic external incidents and cloud delivery remain release work.
