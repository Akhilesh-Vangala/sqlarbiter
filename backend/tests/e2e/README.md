# Browser journeys

Playwright scripts that drive the API, worker, and frontend together. Run them from the repository root with `PYTHONPATH=backend/src` and Chromium installed.

| Script | Journey |
| --- | --- |
| `browser_smoke.py` | Investigation, evidence, revision, review, export, reload |
| `browser_graph_smoke.py` | LangGraph investigator with scripted provider responses |
| `browser_automation_smoke.py` | Multi-metric workflows and cancellation |
| `browser_pages_smoke.py` | Page routes, history, and responsive layouts |
| `browser_dbt_smoke.py` | dbt project run, patch download, revision, review |

The graph journey loads responses from `backend/tests/fixtures/model_fixtures.py`. Generated captures and state go to the ignored `artifacts/generated/`.
