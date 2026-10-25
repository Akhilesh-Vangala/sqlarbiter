# Corpus and scoring

The benchmark is a frozen set of original synthetic incidents. DuckDB is the default analytical engine and SQLite is the alternative. Both are graded by the same source references. Current suite counts are in the [evaluation index](README.md).

`backend/src/sqlarbiter/evaluation/benchmark_cases.py` defines six original controls plus 32 variants across join fan-out, outer-join null handling, eligibility-filter omissions, and explicit-offset UTC boundaries. The families contain eight SQL-shape templates, varied values, healthy controls, and private regression snapshots. These are 38 scenarios. They are not 38 independent fault mechanisms.

The frozen `backend/data/benchmark/manifest.json` records corpus and case hashes and explicit calibration and evaluation membership. Shape A variants and original controls are calibration; Shape B variants are evaluation. Template groups do not overlap, but schemas, contracts, and underlying fault families do. The cases are known to the fixed baseline. Version the manifest after reviewed changes rather than adapting the corpus to an observed output.

Every attempt launches a fresh exported investigator, replays the trace on public evidence, and checks candidate/current SQL against independent Python source references on private snapshots. Missing-information scope and healthy no-change behavior are also graded. Invalid reference sources raise evaluator errors rather than count as agent failures. Query schemas/values must match exactly; repeated keys, wrong types and truncated results fail.

Pass@k uses 1 - C(n-c,k)/C(n,k), with c independently successful attempts out of n. Pass@3 is null when fewer than three attempts exist. All-outcome Pass@k includes clarification/no-change; SQL execution Pass@k covers repairable sources (including healthy controls), requiring every private snapshot to pass. It is not a repair-only population or an explanation-quality metric. Samples are separate nonadaptive attempts; the evaluator does not feed hidden answers back to the model.

Reports capture corpus/runtime/evaluator hashes, Python, requested/resolved/reported model, UTC timestamps, prompt version, rounds, tokens, partial usage/billing uncertainty, tool calls, investigation latency and verification latency. Cost estimates require a model-matched profile with verified_at/source_url and input/output/cache read/cache write rates per million. Failures or unknown pricing return null. Estimates exclude infrastructure charges and may differ from invoices.

## Results observed

| Run | Investigator | Engine | Cases / attempts | All-outcome Pass@1 / Pass@3 | Interpretation |
| --- | --- | --- | --- | --- | --- |
| benchmark-duckdb-001 | Fixed baseline | DuckDB | 38 / 114 | 1.0 / 1.0 | Known contract-specific deterministic workflow; repetitions do not measure AI variance |
| benchmark-sqlite-001 | Fixed baseline | SQLite | 38 / 38 | 1.0 / null | Backend/corpus compatibility |
| container-benchmark | Fixed baseline | DuckDB | 38 / 38 | 1.0 / null | Linux container evaluation |

The fixed workflow averages 7.92 evidence calls per case. The container run observed mean investigator subprocess time 0.332 s and mean replay/verification time 1.663 s on that local VM, including process overhead.

The investigator uses the official async SDK. DuckDB is the analytical engine in the app and the benchmark; it is not a warehouse connector. Claude 3.5 Sonnet was retired on October 28, 2025. [AI design](../architecture/AI-DESIGN.md).
