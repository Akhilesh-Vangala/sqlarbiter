# Development

Python 3.12 is used locally, in CI and in the container images. Dependencies are installed from the hash-locked `backend/requirements/development.txt`. Generated output goes to the git-ignored `artifacts/generated/`. Run commands from the repository root.

## Setup

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements/development.txt
.venv/bin/python -m playwright install chromium
export PYTHONPATH=backend/src
```

The dbt workflow needs its own environment because dbt's dependency constraints differ from the application's; see [dbt](../architecture/DBT.md#running-it).

## Running

| Target | Command | URL |
| --- | --- | --- |
| Operator workbench with a separate worker | `python -m sqlarbiter.cli.serve` | `http://127.0.0.1:8000` |
| Workbench without the worker | `python -m sqlarbiter.cli.serve --no-worker` | `http://127.0.0.1:8000` |
| Worker process | `python -m sqlarbiter.workers.worker --state-dir artifacts/generated/app` | none |
| Public build (product, sandbox, uploads) | `SQLARBITER_DEMO_SECRET=<48+ chars> python -m uvicorn app:app --port 8000` | `http://127.0.0.1:8000` |
| Compose topology | `scripts/deployment/compose.sh up --build --wait` | `http://127.0.0.1:8000` |

## Configuration

Copy `.env.example` to `.env` on a fresh checkout; never overwrite an existing `.env`. The launcher loads `.env` without overriding variables already set in the process, and `SQLARBITER_LOAD_DOTENV=0` disables loading.

| Variable | Purpose |
| --- | --- |
| `SQLARBITER_STATE_DIR` | Job store, run workspaces and spend ledger |
| `SQLARBITER_ACCESS_TOKEN`, `SQLARBITER_PUBLIC_ORIGIN` | Shared operator bearer token (32+ characters) and HTTPS public origin |
| `SQLARBITER_DATABASE_URL`, `SQLARBITER_CHECKPOINT_DATABASE_URL` | PostgreSQL job store and LangGraph checkpoints. Unset uses SQLite. |
| `ANTHROPIC_API_KEY`, `SQLARBITER_ANTHROPIC_MODEL` | Provider key and model for the hosted and LangGraph investigators. The model must match the pricing profile. |
| `SQLARBITER_RUN_BUDGET_USD`, `SQLARBITER_TOTAL_BUDGET_USD` | Per-workspace and per-ledger spend allowances |
| `SQLARBITER_SQL_ENGINE` | `duckdb` (default) or `sqlite` |
| `SQLARBITER_OTLP_ENDPOINT` | OTLP/HTTP trace endpoint |
| `SQLARBITER_DBT_EXECUTABLE` | Trusted dbt binary; defaults to `.venv-dbt/bin/dbt` |
| `SQLARBITER_DEMO_SECRET`, `SQLARBITER_REPORT_SIGNING_KEY` | Envelope and report signing secrets (48+ characters) |
| `SQLARBITER_SUPABASE_URL`, `SQLARBITER_SUPABASE_PUBLISHABLE_KEY`, `SQLARBITER_ACCOUNT_SIGNUP` | Optional cloud accounts |

## Checks

```sh
pipx run ruff==0.14.0 check . && pipx run ruff==0.14.0 format --check .
python scripts/checks/check_repository.py
SQLARBITER_LOAD_DOTENV=0 python -m unittest discover -s backend/tests -v
SQLARBITER_LOAD_DOTENV=0 python backend/tests/e2e/browser_smoke.py
python scripts/demos/public_demo_browser.py
python scripts/demos/product_browser.py --axe <path to axe.min.js>
python scripts/demos/import_browser.py --axe <path to axe.min.js>
python scripts/demos/uploads_browser.py
python -m sqlarbiter.evaluation.benchmark --output artifacts/generated/benchmark --samples 1
```

PostgreSQL tests run when `SQLARBITER_TEST_DATABASE_URL` points at a disposable database. Container checks:

```sh
docker build -f backend/docker/Dockerfile --target test -t sqlarbiter:test .
docker run --rm sqlarbiter:test
```

[Layout](LAYOUT.md) · [Branching](BRANCHING.md) · [Deployment](../operations/DEPLOYMENT.md)
