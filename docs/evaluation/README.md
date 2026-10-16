# Evaluation

## Test suites

| Suite | Command | Establishes |
| --- | --- | --- |
| Native | `python -m unittest discover -s backend/tests` | 202 tests. Five skip unless PostgreSQL or dbt is configured; CI provides PostgreSQL in `tests` and dbt in its own job. |
| Workbench browser | `backend/tests/e2e/browser_*_smoke.py` | Investigation, graph, workflow and page journeys in Chromium |
| Public sandbox | `scripts/demos/public_demo_browser.py` | Investigation, evidence, rejected false repair, exact-version review, download, reload, cross-browser isolation, mobile layout, video player |
| Product | `scripts/demos/product_browser.py --axe …` | File-to-report journey, consent, snapshots, tamper rejection, recovery, layouts, axe-core scan |
| Imports | `scripts/demos/import_browser.py --axe …` | All five formats through file selection to checked results |
| dbt | `backend/tests/e2e/browser_dbt_smoke.py` | Real dbt build, patch, revision, review and cancellation |
| Benchmark | `python -m sqlarbiter.evaluation.benchmark` | Frozen corpus scored with Pass@k |

Container runs repeat the same cases, so their counts are not additional unique tests.

## Independent acceptance

Source-level reference computations and private regression snapshots stay outside the exported investigator workspace. Trace replay checks that every cited result was produced by the tools, and candidate SQL is compared with the references across snapshots. Schemas and values must match exactly; repeated keys, wrong types and truncated results fail. The dbt pipeline checks five fixtures and four output relations, including an equal-value false repair that passes the original incident and fails regression. These checks are specific to declared contracts, not a proof of arbitrary SQL semantics.

## Regression corpus

`backend/src/sqlarbiter/evaluation/benchmark_cases.py` defines six original controls plus 32 variants across join fan-out, outer-join null handling, eligibility-filter omissions and explicit-offset UTC boundaries: 38 scenarios in eight SQL-shape templates with varied values, healthy controls and private regression snapshots. They are 38 scenarios, not 38 independent fault mechanisms.

`backend/data/benchmark/manifest.json` freezes corpus and case hashes and the calibration and evaluation splits. Shape A variants and the original controls are calibration; Shape B variants are evaluation. Template groups do not overlap, though schemas, contracts and fault families do. The cases are known to the fixed diagnostic, so its scores measure workflow correctness rather than model capability. Version the manifest after reviewed changes instead of adapting the corpus to observed output.

## Safety suite

`backend/src/sqlarbiter/evaluation/safety_cases.py` defines eight evaluator-owned cases frozen in `backend/data/benchmark/safety-manifest.json`: three repairs (join, event grain, offset), a healthy no-change control, two clarifications (missing timezone, missing authority) and two hostile-text cases that place instructions in a change log and in source data. Expected outcomes are computed by the same source-reference evaluator. They are authored cases, not a measurement of prompt-injection resistance.

```sh
PYTHONPATH=backend/src python -m sqlarbiter.evaluation.benchmark --suite safety --output artifacts/generated/safety --samples 1
```

## Scoring

Each attempt launches a fresh exported investigator, replays its trace on public evidence and grades current and candidate SQL against the references on private snapshots. Clarification scope and healthy no-change behavior are graded too, and invalid reference sources raise evaluator errors instead of counting as agent failures.

Pass@k is \(1 - \binom{n-c}{k} / \binom{n}{k}\) for \(c\) successful attempts out of \(n\), and is null when \(n < k\). All-outcome Pass@k includes clarification and no-change; SQL-execution Pass@k covers repairable sources and healthy controls and requires every private snapshot to pass. Samples are independent attempts, and no hidden answer is fed back to the model.

Reports record corpus, runtime and evaluator hashes, Python version, requested, resolved and reported model, timestamps, prompt version, rounds, tokens, billing uncertainty, tool calls, investigation latency and verification latency. Cost estimates require a model-matched pricing profile with input, output and cache rates; unknown pricing yields null. Estimates exclude infrastructure charges.

| Run | Investigator | Engine | Cases / attempts | All-outcome Pass@1 / Pass@3 |
| --- | --- | --- | --- | --- |
| Fixed diagnostic | Fixed baseline | DuckDB | 38 / 114 | 1.0 / 1.0 |
| Engine compatibility | Fixed baseline | SQLite | 38 / 38 | 1.0 / null |
| Container | Fixed baseline | DuckDB | 38 / 38 | 1.0 / null |

The fixed diagnostic is deterministic, so repeated attempts do not measure model variance. It averages 7.92 evidence calls per case.

[Overview](../architecture/OVERVIEW.md) · [Agent](../architecture/AGENT.md)
