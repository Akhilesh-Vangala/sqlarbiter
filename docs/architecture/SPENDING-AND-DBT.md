# Shared spend admission and original dbt repair workflow

The trusted sample runs as a queued browser project with progress, revisions, protected patch downloads, and exact-version review. [Browser workflow](DBT-WORKFLOW.md). The CLI below runs the same repair.

## Spend admission

Real Anthropic/LangGraph execution requires a trusted pricing profile and shared ledger. Defaults: **$1 per investigation workspace and $5 cumulative estimated allowance** for the ledger. These are application allowances, not a subscription, purchased credit balance, monthly reset or provider invoice ceiling. Baselines consume no model tokens.

Before generation, resolve the active model, count input, enforce existing token limits and atomically reserve worst-case input/cache plus requested maximum output. Complete typed streams reconcile reported usage in integer microdollars, rounded upward. Invalid/partial/unknown streams retain reservations. A killed process leaves reserved receipts consuming the allowance. Usage exceeding a reservation is accounted in full and blocks further generation. Model mismatches retain unknown accounting rather than assigning cheaper prices.

Real generation retries are **zero**. SDK mock transports keep their own retry setting unless explicitly enabling spend admission. SQLite BEGIN IMMEDIATE coordinates independent processes on one host; SDK accounting runs through asyncio.to_thread. Existing model/tool/token/deadline and graph receipt controls remain. This is not distributed financial infrastructure and cannot constrain API calls outside this application.

```dotenv
VDIR_RUN_BUDGET_USD=1
VDIR_TOTAL_BUDGET_USD=5
```

Default ledger: state-dir/spend.sqlite. API/workers/CLI share it when using the same state configuration. Override VDIR_SPEND_LEDGER with a common absolute path when needed. VDIR_PRICE_PROFILE defaults to backend/data/pricing/claude-sonnet-5-5.json, checked against [official pricing](https://platform.claude.com/docs/en/about-claude/pricing) on October12. Reservations conservatively use the highest configured input/cache rate, including one-hour cache writes; current requests send no cache controls. Profiles must match resolved models. Ledger policy is bound at creation: changing limits/rates cannot silently reset balances. Preserve old records and explicitly select a new ledger for a new allowance period. Do not discard unknown receipts to manufacture available budget. Provider-side billing settings complement these controls.

Authenticated `GET /api/spend` exposes allowances, the remaining estimate, and settled, reserved, unknown, and overrun counts. Settings shows those recorded amounts. A graph continuation gets a new workspace allowance. Inherited token budgets and the shared ledger still apply.

## Original payment-revenue incident

Five real dbt models: payment_deliveries seed → stg_payment_deliveries → int_payment_events → fct_daily_revenue → mart_monthly_revenue; fct_customer_revenue also depends on int_payment_events.

Identity is event_id, not delivery_id/amount/received_at. Immutable events may be redelivered. Revenue uses explicit UTC occurred_at even for deliveries received next month. Reporting includes completed payments; canonical events retain pending payments. A deliberately defective intermediate emits delivery grain: September30 revenue is2400cents instead of1200. All models build; a declared dbt grain test fails.

The runner executes actual dbt seed/run/test, reads manifest dependencies/model files, exports only the current staging snapshot/public project and invokes the existing fixed/Anthropic/LangGraph investigator. A bounded project tool exposes public model/lineage metadata. Candidates are plain SELECT queries for one allowed upstream model. Evidence is independently replayed and canonical rows checked against private source references.

Only the existing SQL allowlist and declared staging relation can produce the one model-file patch. Model Jinja, arbitrary paths/macros/hooks, mutations and external file functions are rejected. Trusted rendering inserts the fixed dbt ref. A unified diff is built in fresh project/database copies for five designed regressions: original, equal-value distinct events, late month boundary/zero/pending, reordered deliveries and empty batch. Python references check canonical events, daily/monthly revenue and customer totals. A fix merging equal-value distinct events passes the incident but fails regression and emits no verified patch.

Original project assets are frozen for each run. Reports bind source/model/diff hashes, affected models, original dbt failure, per-fixture execution/independent outputs and an exact report version. These are scoped regression checks, not universal semantic proof or unseen capability. Fixed diagnostics explicitly know this contract; no live causal reasoning claim.

## Run locally

dbt-core1.12.5 / dbt-duckdb1.11.0 / DuckDB1.5.6 are separately pinned. dbt's Click requirement differs from the app, so keep it isolated:

```sh
.tools/uv-aarch64-apple-darwin/uv venv --python .venv/bin/python .venv-dbt
.tools/uv-aarch64-apple-darwin/uv pip sync --python .venv-dbt/bin/python backend/requirements/dbt.txt
PYTHONPATH=backend/src .venv/bin/python -m vdir.workflows.dbt_workflow --output artifacts/generated/my-dbt-run
VDIR_RUN_DBT_TESTS=1 VDIR_LOAD_DOTENV=0 PYTHONPATH=backend/src .venv/bin/python -m unittest discover -s backend/tests -p test_dbt_integration.py -v
```

Other machines: `python3.11 -m venv .venv-dbt`, then `.venv-dbt/bin/python -m pip install -r backend/requirements/dbt.txt`. `VDIR_DBT_EXECUTABLE` overrides the tooling binary. Container images include the source fixture and the dbt environment. The same project is queued from the browser.

Exact-version local review:

```sh
PYTHONPATH=backend/src .venv/bin/python -m vdir.workflows.dbt_workflow --review-report artifacts/generated/my-dbt-run/report.json --expected-version REPORT_VERSION --action approved --note "Reviewed contract and independent checks"
```

Use the actual version. Approval requires passing verification and matching report and diff hashes. `review.json` is immutable. Review records the decision. It does not write production SQL.

The repair is checked across five fixtures and four output relations. The original daily amount moves from 2400 cents to 1200. The equal-value false fix fails regression. CI runs this in the dedicated dbt job. PostgreSQL coordinates API and worker processes when configured. [Runtime](../operations/PRODUCTION-FOUNDATION.md).
