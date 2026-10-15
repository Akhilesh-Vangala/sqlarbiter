# VerifyOps tests

Tests are grouped by the responsibility they exercise. API, agent, analytics/verification, persistence and workflow directories may contain both isolated and integration checks; their names do not claim external dependencies are mocked. e2e contains actual browser journeys. fixtures owns reusable scripted provider responses; production code does not import test fixtures. Live model quality remains a separate evaluation gate.

Run `PYTHONPATH=backend/src python -m unittest discover -s backend/tests -v`.
