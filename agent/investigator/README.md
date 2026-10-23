# Exportable investigator runtime

This small runtime is copied into each isolated evidence workspace. Its local model, graph, tools and telemetry imports intentionally remain flat so it can run without importing evaluator code. Source-reference computations and private expected results stay under backend/src/vdir/verification and evaluation; they are not exported to the investigator. Spending uses the controlled exported implementation.
