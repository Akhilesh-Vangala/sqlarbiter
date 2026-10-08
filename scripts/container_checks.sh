#!/bin/sh
set -eu
python -m unittest discover -s tests -v
python tests/browser_smoke.py
python tests/browser_graph_smoke.py
python tests/browser_automation_smoke.py
python tests/browser_pages_smoke.py
python -m vdir.benchmark --output artifacts/generated/container-benchmark --samples 1
