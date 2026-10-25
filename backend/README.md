# VerifyOps backend

Application code lives in [src/vdir](src/vdir), one package per capability. Each package has its own README.

| Package | Responsibility |
| --- | --- |
| [api](src/vdir/api/) | HTTP routes, request contracts, public sandbox scope |
| [workers](src/vdir/workers/) | Background worker process and database readiness |
| [persistence](src/vdir/persistence/) | Job store, claims, leases, migrations |
| [workflows](src/vdir/workflows/) | Admission, version and review gates, dbt execution |
| [verification](src/vdir/verification/) | Reference computations and guarded SQL execution |
| [evaluation](src/vdir/evaluation/) | Benchmark runner and reports |
| [domain](src/vdir/domain/) | Incident cases and the synthetic environment |
| [platform](src/vdir/platform/) | Configuration, telemetry, spend ledger, run contract |
| [uploads](src/vdir/uploads/) | Visitor file ingestion and checked results |
| [product](src/vdir/product/) | Product routes and optional accounts |
| [cli](src/vdir/cli/) | Local server and graph continuation entrypoints |

Other folders:

- [tests](tests/): unit, integration, and browser journeys.
- [requirements](requirements/): pinned runtime, development, and dbt locks.
- [docker](docker/Dockerfile): runtime and test image stages.
- [data](data/): benchmark manifests, development contract, pricing.
- [dbt/revenue_incident](dbt/revenue_incident/): the restricted repair target.

The investigator runtime is outside the backend at [agent/investigator](../agent/investigator/), so it never imports [verification](src/vdir/verification/). [Layout](../docs/development/LAYOUT.md).
