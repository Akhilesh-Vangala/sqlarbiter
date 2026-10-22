# Pre-live evaluation and run evidence

The normal38-case benchmark remains unchanged. A separately frozen eight-case suite exercises repair, healthy no-change, missing timezone/authority and hostile text in a changelog/source table. They are original developer-authored regression cases based on known incident families, not an untouched external benchmark. A deterministic baseline passing hostile text does not measure a language model's prompt-injection resistance.

```sh
PYTHONPATH=backend/src python -m vdir.evaluation.benchmark \
  --suite prelive --investigator baseline --engine sqlite --samples 1 \
  --output artifacts/generated/my-prelive-baseline
```

Use a new output directory; runs do not overwrite prior results. The source-reference evaluator and private regression snapshots remain outside exported agent runtimes. The frozen manifest checks every case hash before evaluation. Do not edit it to make an observed model failure disappear; version future changes explicitly.

Each attempt has a unique run ID passed into the exported worker and model ledger. The report classifies verified repair, no-change, clarification, execution error, verification failure and evaluator error separately. Evaluator/source-contract faults are excluded from agent accuracy, with both raw and scored attempt counts retained. Pass@3 stays null with fewer than three scored independent attempts. Missing/invalid provider usage is unknown, never a free generation. These costs remain estimates, not invoice guarantees.

## Run contract

Guided upload and private queue results share the strict run-v1 envelope while retaining distinct task, mode, authority and verification scope. It contains identifiers, hashes, bounded producer versions, counts and billing origin. It does not contain original records, SQL, secrets, model-private reasoning or hidden oracle outputs. A correlation ID is not an access credential.

The upload input hash binds normalized source plus the declared mapping/options. Report signatures include the provenance record. Source authenticity and undeclared business semantics are not established by hashing or signing. Original saved reports without run-v1 metadata remain historical reports; missing provenance is not fabricated.

Private queue job ID, exported model invocation and resulting independent grading are correlated. A graph continuation inherits its ancestor's budget run ID even though it receives a distinct queue job ID. An operator revision is labelled separately and does not reuse the parent's model billing claim.

## Spending and failure policy

The existing integer-microdollar shared SQLite ledger serializes reservations across processes on the same host/filesystem. It now blocks new generation across all its runs after unknown billing or a provider overrun, even if budget remains. Unknown/overrun reservations cannot be silently released; reconcile provider evidence explicitly and preserve the old ledger. Configuring another ledger is a new budget policy, not an automatic recovery strategy.

Each continuation retains the original per-run allowance. Application reservations cannot cap calls made elsewhere on the provider account or guarantee a provider's invoice. Local file state and ledger scope are not a distributed cloud-spend architecture.

Injected transport tests and offline regressions exercise refusal, usage faults, concurrency, record tampering, source/contract changes, queued execution and stream correlation. The actual model must still be evaluated with private credentials and an approved budget. No real model score or successful provider call is claimed here.

## Next actual-model experiment

Configure the existing private provider/model and trusted pricing/ledger variables described in [spending and dbt](../architecture/SPENDING-AND-DBT.md). Begin with a small selected case set using `--suite prelive --investigator langgraph --samples 1 --case-ids ...`. Review complete trajectories, independent failures and actual/unknown usage before a larger run. Keep this experiment private; public paid inference remains disabled.
