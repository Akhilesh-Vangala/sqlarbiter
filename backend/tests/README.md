# SQLArbiter tests

Tests are grouped by the responsibility they exercise: `api`, `agents`, `verification`, `persistence`, and `workflows`. Each directory may hold isolated and integration cases. `e2e` holds browser journeys. `fixtures` holds scripted provider responses and pricing; production code does not import it.

```sh
PYTHONPATH=backend/src SQLARBITER_LOAD_DOTENV=0 python -m unittest discover -s backend/tests -v
```

PostgreSQL cases run when `SQLARBITER_TEST_DATABASE_URL` is set. Real dbt cases run when `SQLARBITER_RUN_DBT_TESTS=1` and the dbt environment exists.
