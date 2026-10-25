# Investigator runtime

This runtime is copied into each isolated evidence workspace. Its imports are flat so it runs without the backend or evaluator code. Reference computations and expected results stay in `backend/src/vdir/verification` and `evaluation` and are never exported here.

| File | Responsibility |
| --- | --- |
| `graph.py` | LangGraph `StateGraph`, checkpoints, routing |
| `agent_policy.py` | Pydantic schemas for plans, findings, decisions |
| `model.py` | Async SDK transport, streaming, call receipts |
| `tools.py` | Read-only evidence tools |
| `engines.py` | DuckDB and SQLite execution guards |
| `baseline.py` | Fixed diagnostic investigator |
| `spending.py` | Exported spend admission |
| `telemetry.py` | Span export |
| `worker.py` | Process entrypoint |

[Agent design](../../docs/architecture/AGENT-ORCHESTRATION.md).
