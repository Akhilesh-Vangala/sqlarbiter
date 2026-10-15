#!/bin/sh
set -eu
python -m unittest discover -s backend/tests -v
python tests/e2e/browser_smoke.py
python tests/e2e/browser_graph_smoke.py
python tests/e2e/browser_automation_smoke.py
python tests/e2e/browser_pages_smoke.py
python tests/e2e/browser_dbt_smoke.py
python -m vdir.benchmark --output artifacts/generated/container-benchmark --samples 1
