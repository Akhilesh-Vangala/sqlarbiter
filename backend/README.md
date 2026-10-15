# VerifyOps backend

Application code is grouped by responsibility in [src/vdir](src/vdir). Each capability has a local guide.

- [Tests](tests/): capability-grouped regression/integration cases and browser journeys where applicable.
- [Dependency locks](requirements/): runtime and development requirements, plus isolated dbt tooling.
- [Docker image](docker/Dockerfile): runtime and test build stages.
- [Fixtures and pricing](data/): original versioned synthetic material.
- [Exportable investigator](agents/investigator/): deliberately isolated from [independent verification](src/vdir/verification/).
- [dbt project](dbt/revenue_incident/): original restricted repair target.

[Full layout](../docs/development/LAYOUT.md) · [Run locally](../README.md#run-locally).
