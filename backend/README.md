# VerifyOps backend

Python application and agent code is in [src/vdir](src/vdir/). Unit/integration tests live in [tests](tests/); the runtime/test image is built from [Dockerfile](Dockerfile) with the repository root as context.

The exportable investigator is separate in [investigator_runtime](investigator_runtime/). Evaluator references stay outside its exported evidence and import path.

[Repository layout](../docs/development/LAYOUT.md) · [Current architecture](../docs/architecture/OVERVIEW.md) · [Run and verify](../README.md#run-locally).
