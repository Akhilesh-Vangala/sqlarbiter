# Remediation and measured evidence — October 7, 2026

The user's critique prioritized real AI execution, aligned Python/container validation, an analytical backend, tracing and a larger evaluation matrix. Implemented these engineering changes; live model execution and remote publication remain dependent on missing configuration.

| Requirement | Actual outcome |
| --- | --- |
| Replace blocking urllib AI transport | Official async Anthropic SDK, typed SSE, bounded retry/preflight tokens and async controller; scripted SDK protocol tests pass |
| Run real model on six scenarios | Pending private API key; zero live generations and no model accuracy claim |
| Align Python | Local project and tested container use 3.11.17; Apple system interpreter unchanged |
| Execute Docker/Compose | Built test/runtime images; 59 tests and 13 browser checks passed in test container; six real Compose API/worker workflows passed and survived restart |
| Analytical engine | DuckDB default in app/benchmark; SQLite alternative; both independently graded on all 38 cases |
| Context/data guards | Automatic outer LIMIT of 101 detects truncation, returns at most 100 rows; 50 columns, 256 characters per cell, 32 KB result; schema pages/profile tools; verifier rejects partial results |
| Observability | OTel job/investigation/model-round/tool/verification spans; local JSONL and OTLP/Phoenix; 63 actual fixed-workflow spans in six traces received by Phoenix |
| Evaluation matrix | Frozen 38 original synthetic cases, private source references/regressions, split labels, repeated attempts, Pass@k, tools/tokens/latency and explicit pricing support |
| GitHub/remote CI | Workflow now executes test container; repository details/access pending, remote result unverified |

## Corpus and scoring

src/vdir/benchmark_cases.py defines six original controls plus 32 variants across join fan-out, outer-join null handling, eligibility-filter omissions and explicit-offset UTC boundaries. The new families contain eight SQL-shape templates (two per family), varied values, healthy controls and private regression snapshots. This is **38 scenarios, not 38 independent fault mechanisms**. Source records are small and synthetic; there is no 10-million-row scalability evidence.

The frozen data/benchmark/manifest.json records corpus/case hashes and explicit calibration/evaluation membership. Shape A variants and original controls are calibration; Shape B variants are evaluation. Template groups do not overlap, but schemas/contracts and underlying fault families do. All cases are presently known to the developers/fixed baseline. This is not yet an untouched real-world held-out benchmark or a learned-policy generalization result. Version the manifest after reviewed changes rather than silently adapting the corpus to model outputs.

Every attempt launches a fresh exported investigator, replays the trace on public evidence, and checks candidate/current SQL against independent Python source references on private snapshots. Missing-information scope and healthy no-change behavior are also graded. Invalid reference sources raise evaluator errors rather than count as agent failures. Query schemas/values must match exactly; repeated keys, wrong types and truncated results fail.

Pass@k uses 1 - C(n-c,k)/C(n,k), with c independently successful attempts out of n. Pass@3 is null when fewer than three attempts exist. All-outcome Pass@k includes clarification/no-change; SQL execution Pass@k covers repairable sources (including healthy controls), requiring every private snapshot to pass. It is not a repair-only population or an explanation-quality metric. Samples are separate nonadaptive attempts; the evaluator does not feed hidden answers back to the model.

Reports capture corpus/runtime/evaluator hashes, Python, requested/resolved/reported model, UTC timestamps, prompt version, rounds, tokens, partial usage/billing uncertainty, tool calls, investigation latency and verification latency. Cost estimates require a model-matched profile with verified_at/source_url and input/output/cache read/cache write rates per million. Failures or unknown pricing return null. Estimates exclude infrastructure charges and may differ from invoices.

## Results observed

| Run | Investigator | Engine | Cases / attempts | All-outcome Pass@1 / Pass@3 | Interpretation |
| --- | --- | --- | --- | --- | --- |
| benchmark-duckdb-001 | Fixed baseline | DuckDB | 38 / 114 | 1.0 / 1.0 | Known contract-specific deterministic workflow; repetitions do not measure AI variance |
| benchmark-sqlite-001 | Fixed baseline | SQLite | 38 / 38 | 1.0 / null | Backend/corpus compatibility |
| container-benchmark | Fixed baseline | DuckDB | 38 / 38 | 1.0 / null | Actual Linux container evaluation |
| Live model | Not run | — | 0 | Unmeasured | Missing API key |

Fixed workflow averages 7.92 evidence calls per case. Container run observed mean investigator subprocess time 0.332 s and mean replay/verification time 1.663 s on this local VM, including process overhead. This is neither warehouse latency nor model time-to-resolution. No measured model token/dollar/accuracy figure exists.

59 unittest checks and 13 Chromium checks passed on both local Python 3.11.17 and the container. Six real Compose scenarios passed; candidate reviews/JSON exports worked and six completed jobs remained after restarting API/worker. Phoenix REST queries returned 63 spans, with each job's investigation/tool/verification spans sharing its propagated trace ID. Model-round spans are tested with scripted protocol data, not live generations.

Evidence is under artifacts/generated/remediation-001/, including unit/container logs, compose-smoke.json, summary.json, phoenix-spans.json and extracted container benchmark/browser artifacts. Artifacts are ignored and must be regenerated elsewhere. Benchmark baselines are in artifacts/generated/benchmark-duckdb-001/ and benchmark-sqlite-001/. Old milestones in PROGRESS/decisions are historical, not current runtime claims.

## Remaining release risks

Live prompts/tools have not faced an actual nondeterministic model. No trained policy or advantage over fixed rules exists. Case/lineage realism and fault diversity still need expansion. DuckDB is an analytical test target, not a Snowflake/BigQuery/Postgres connector. LIMIT bounds returned rows, not scans; execution/memory budgets are additional guards. SQLite WAL state is deliberately single-host and not a distributed queue. For a distributed release use PostgreSQL transactions with FOR UPDATE SKIP LOCKED or a durable queue such as Redis Streams/Temporal, with explicit recovery ownership and idempotency. None of those queue replacements is implemented.

The current SQL/tool surface is bounded, but exported imports and an app container do not isolate each investigation from host/evaluator authority. Individual identity, isolation, durable cloud infrastructure, load testing and business-user validation remain required.

The original urllib call ran in a separate investigator process, not directly inside a FastAPI async handler. Moving to the async SDK still materially improves transport/streaming/retry/validation. SQLite itself supports window functions; choosing DuckDB improves analytical fidelity without claiming dialect equivalence to every warehouse. Claude 3.5 Sonnet was retired October 28, 2025; use an account-available active model validated by the Models API. See [AI design and official sources](05-AI-DESIGN.md).
