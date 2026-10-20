# SQLArbiter backend

Application code lives in [src/sqlarbiter](src/sqlarbiter), one package per capability. Each package has its own README.

| Package | Responsibility |
| --- | --- |
| [api](src/sqlarbiter/api/) | HTTP routes, request contracts, public sandbox scope |
| [workers](src/sqlarbiter/workers/) | Background worker process and database readiness |
| [persistence](src/sqlarbiter/persistence/) | Job store, claims, leases, migrations |
| [workflows](src/sqlarbiter/workflows/) | Admission, version and review gates, dbt execution |
| [verification](src/sqlarbiter/verification/) | Reference computations and guarded SQL execution |
| [evaluation](src/sqlarbiter/evaluation/) | Benchmark runner and reports |
| [domain](src/sqlarbiter/domain/) | Incident cases and the synthetic environment |
| [platform](src/sqlarbiter/platform/) | Configuration, telemetry, spend ledger, run contract |
| [uploads](src/sqlarbiter/uploads/) | Visitor file ingestion and checked results |
| [product](src/sqlarbiter/product/) | Product routes and optional accounts |
| [cli](src/sqlarbiter/cli/) | Local server and graph continuation entrypoints |

Other folders:

- [tests](tests/): unit, integration, and browser journeys.
- [requirements](requirements/): pinned runtime, development, and dbt locks.
- [docker](docker/Dockerfile): runtime and test image stages.
- [data](data/): benchmark manifests, development contract, pricing.
- [dbt/revenue_incident](dbt/revenue_incident/): the restricted repair target.

The investigator runtime is outside the backend at [agent/investigator](../agent/investigator/), so it never imports [verification](src/sqlarbiter/verification/). [Layout](../docs/development/LAYOUT.md).
