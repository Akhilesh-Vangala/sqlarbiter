# VerifyOps platform

Configuration, telemetry, spend admission, and run provenance.

- [config.py](config.py): environment configuration.
- [observability.py](observability.py): OpenTelemetry setup and span helpers.
- [spending.py](spending.py): shared spend ledger and reservations.
- [run_contract.py](run_contract.py): strict run-v1 provenance and correlation. Identifiers do not grant authority.
