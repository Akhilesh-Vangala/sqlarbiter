# Shared spend admission and original dbt repair workflow

October 12, 2026. Implemented and verified locally. Live model quality/cloud operation remain unverified.

## Spend admission

Real Anthropic/LangGraph execution requires a trusted pricing profile and shared ledger. Defaults: **$1 per investigation workspace and $5 cumulative estimated allowance** for the ledger. These are application allowances, not a subscription, purchased credit balance, monthly reset or provider invoice ceiling. Baselines consume no model tokens.

Before generation, resolve the active model, count input, enforce existing token limits and atomically reserve worst-case input/cache plus requested maximum output. Complete typed streams reconcile reported usage in integer microdollars, rounded upward. Invalid/partial/unknown streams retain reservations. A killed process leaves reserved receipts consuming the allowance. Usage exceeding a reservation is accounted in full and blocks further generation. Model mismatches retain unknown accounting rather than assigning cheaper prices.

Real generation retries are **zero**. SDK mock transports keep their own retry setting unless explicitly enabling spend admission. SQLite BEGIN IMMEDIATE coordinates independent processes on one host; SDK accounting runs through asyncio.to_thread. Existing model/tool/token/deadline and graph receipt controls remain. This is not distributed financial infrastructure and cannot constrain API calls outside this application.

```dotenv
VDIR_RUN_BUDGET_USD=1
VDIR_TOTAL_BUDGET_USD=5
```

Default ledger: state-dir/spend.sqlite. API/workers/CLI share it when using the same state configuration. Override VDIR_SPEND_LEDGER with a common absolute path when needed. VDIR_PRICE_PROFILE defaults to data/pricing/claude-sonnet-5-5.json, checked against [official pricing](https://platform.claude.com/docs/en/about-claude/pricing) on October12. Reservations conservatively use the highest configured input/cache rate, including one-hour cache writes; current requests send no cache controls. Profiles must match resolved models. Ledger policy is bound at creation: changing limits/rates cannot silently reset balances. Preserve old records and explicitly select a new ledger for a new allowance period. Do not discard unknown receipts to manufacture available budget. Provider-side billing settings complement these controls.

Authenticated GET /api/spend exposes allowances, remaining estimate and settled/reserved/unknown/overrun counts, without paths or credentials. Settings displays actual read-only amounts and unresolved requests. Graph child continuation is a new workspace allowance; inherited token budgets and the shared ledger still apply. Operator billing reconciliation and PostgreSQL coordination remain pending.

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
.tools/uv-aarch64-apple-darwin/uv pip sync --python .venv-dbt/bin/python requirements-dbt.txt
PYTHONPATH=src .venv/bin/python -m vdir.dbt_workflow --output artifacts/generated/my-dbt-run
VDIR_RUN_DBT_TESTS=1 VDIR_LOAD_DOTENV=0 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_dbt_integration.py -v
```

Other machines: python3.11 -m venv .venv-dbt, then .venv-dbt/bin/python -m pip install -r requirements-dbt.txt. VDIR_DBT_EXECUTABLE/--dbt-executable overrides the tooling binary. Container images include the source fixture; executing dbt also requires its tooling environment. This is a CLI workflow, not yet a queued browser dbt connector.

--investigator langgraph or anthropic makes billable calls with private provider configuration and valid spend policy. No live generation is in this milestone. Evaluate a small case first and report real failures/results.

Exact-version local review:

```sh
PYTHONPATH=src .venv/bin/python -m vdir.dbt_workflow --review-report artifacts/generated/my-dbt-run/report.json --expected-version REPORT_VERSION --action approved --note "Reviewed contract and independent checks"
```

Use the actual version. Approval requires passing verification and matching report/diff hashes; review.json is immutable. It records local review only, with no production SQL write/merge. No actual operator approval of the generated demonstration is claimed; test approvals use temporary directories.

## Evidence and release boundaries

Local artifacts/generated/dbt-incident-003/report.json passes five fixtures/four output relations; original daily amount2400 becomes1200. Real integration also rejects the equal-value false fix. Cost tests cover independent-process admission, restart/unknown retention, invalid model/policy/usage, overrun blocking and real SDK mocked-HTTP spend/no-retry/settlement. CI has a separate dbt job; final remote outcomes are recorded separately after verification.

No PostgreSQL migration, individual authentication, OS execution sandbox, cloud deployment, live benchmark or user feedback claimed. dbt release milestone remains partial until live diagnosis and actual operator review. Vercel remains optional for a later frontend; full app/API/worker hosting still uses a proposed container architecture.
