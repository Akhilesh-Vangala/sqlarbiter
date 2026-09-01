# SQLArbiter evaluation

Benchmark runner, corpus definition, and replay grading.

- [benchmark.py](benchmark.py): runs a suite and writes the report.
- [benchmark_cases.py](benchmark_cases.py): the 38-case regression corpus.
- [safety_cases.py](safety_cases.py): the eight-case safety suite.
- [evaluation.py](evaluation.py): launches the exported investigator, replays its trace, and grades the result.

[Scoring](../../../../docs/evaluation/README.md).
