# Browser integration journeys

These scripts exercise real API/worker/frontend behavior across the repository. Run them from the root with PYTHONPATH=backend/src and installed Chromium.

The graph journey uses deterministic provider fixtures from backend/tests/model_fixtures.py. Its explicit test-only import path keeps those fixtures outside production runtime code and avoids importing an entire unit-test module. Exported investigator tools remain under backend/investigator_runtime.

Generated captures/state stay under ignored artifacts/generated. [Current layout](../../docs/development/LAYOUT.md).
