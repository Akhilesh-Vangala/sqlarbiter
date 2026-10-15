# VerifyOps system flowcharts

Current implementation, October 12, 2026. This is the visual reference for the [README](../../README.md). Live model quality and cloud deployment remain pending. Framework integration and scripted-provider tests do not establish AI accuracy.

## Application and authority boundaries

```mermaid
%%{init: {"theme": "neutral"}}%%
flowchart TD
    Operator["Operator"] --> Web["Web workbench<br/>Home, investigations, workflows, dbt, runs, metrics, settings"]
    Web --> API["FastAPI<br/>Access, host/origin, request and idempotency checks"]
    API --> Queue[("SQLite job store<br/>16 active-job admission bound")]
    Queue --> Worker["Separate worker<br/>Atomic claim, lease and heartbeat"]
    Worker --> Source["Source and runtime fingerprint check"]
    Source --> Type{"Run type"}
    Type --> Metric["Metric snapshot and contract"]
    Type --> DBT["Actual dbt build<br/>Public model and manifest context"]
    Metric --> Public["Export public evidence workspace"]
    DBT --> Public
    Public --> Choice{"Selected investigator"}
    Choice --> Fixed["Fixed contract-specific diagnostic"]
    Choice --> Hosted["Async hosted tool-use controller"]
    Choice --> Graph["LangGraph StateGraph"]
    Fixed --> Proposal
    Hosted --> Proposal
    Graph --> Proposal["Candidate, no change, or clarification<br/>Actual evidence and decision"]
    Proposal --> Verify["Independent evidence replay<br/>Python source references and private regressions"]
    Verify --> Gate{"Outcome"}
    Gate -->|Failed| Fail["Saved failure<br/>Approval blocked"]
    Gate -->|Valid information gap| Gap["Paused or unresolved result"]
    Gate -->|Passed| Result["Versioned result<br/>Evidence, checks and artifact hashes"]
    Result --> Review["Exact-version immutable human review"]
    Result --> Download["Report export<br/>Verified dbt patch download"]
    Result --> Edit["Edited SQL becomes a new verification job"]
    Edit --> Worker
```

- The API admits work; it does not perform a long model investigation in the HTTP request.
- The worker owns execution and result publication. Cancellation or lost ownership prevents publication.
- The investigator sees exported public evidence, not private regression data or reference answers.
- Verification compares outputs with independent references, rather than accepting the model's own assertion.
- Review records approval/rejection of the exact result. Production SQL application and repository merge are not implemented.

## LangGraph AI layers

```mermaid
%%{init: {"theme": "neutral"}}%%
flowchart TD
    Start["Start or explicit continuation"] --> Version["Validate source, runtime and package versions"]
    Version --> Prepare["Prepare bounded round<br/>Latest plan, findings and evidence index"]
    Prepare --> Admit["Resolve active model and count input<br/>Token, time and estimated spend admission"]
    Admit --> Model["Official AsyncAnthropic streaming call"]
    Model --> Route{"Tool action"}
    Route -->|Evidence request| Tool["Execute read-only tools<br/>Record receipts before checkpoint commit"]
    Tool --> Prepare
    Route -->|record_plan| Plan["Validate strict hypothesis plan<br/>1-3 hypotheses, SQL tests and citations"]
    Plan -->|Valid| Prepare
    Route -->|record_findings| Finding["Validate supports, contradicts, inconclusive<br/>Citations match complete executed tests"]
    Finding -->|Valid| Prepare
    Route -->|finish| Decision["Validate fields and cited evidence"]
    Decision --> Precheck["Require executed plan test for repair<br/>Public SQL execution and output precheck"]
    Plan -->|Invalid| Feedback
    Finding -->|Invalid| Feedback
    Decision -->|Invalid| Feedback
    Precheck -->|Rejected| Feedback["Public correction feedback<br/>At most two iterations"]
    Feedback --> Prepare
    Precheck -->|Candidate or no change| Submit["Submit to independent verifier"]
    Precheck -->|Needs information| Pause["Persist clarification and interrupt"]
    Pause --> Guidance["Explicit guidance for metric continuation<br/>Immutable parent, new child, retained budgets"]
    Guidance --> Version
    Admit -->|Limit or invalid configuration| Stop["Stop with recorded failure"]
    Model -->|Invalid protocol or provider failure| Stop
    Feedback -->|Correction allowance exhausted| Stop
```

The graph has distinct `prepare`, `model`, `evidence`, `plan`, `findings`, `decide`, `review` (public precheck), `feedback`, and `clarify` nodes. Planning/findings validate public artifacts, not hidden chain-of-thought. Recorded findings are interpretations, not certified conclusions. Planning may incorporate already executed tests; a recorded plan does not prove the model planned before gathering evidence.

Working memory indexes the latest 12 evidence records plus the current plan/findings. The original transcript remains retained. Public prechecks check execution, columns, and completeness; they do not establish semantic correctness. dbt clarification continuation is not currently supported; start a fresh controlled run.

## Tool execution layer

```mermaid
%%{init: {"theme": "neutral"}}%%
flowchart LR
    Agent["Investigator"] --> Interface["Bounded evidence tool interface"]
    Interface --> Context["contract, current_sql<br/>lineage, changes"]
    Interface --> Metadata["describe, profile"]
    Interface --> Diagnostics["inspect_sql, check_join"]
    Interface --> Project["project<br/>Available when dbt context is supplied"]
    Interface --> SQL["query"]
    SQL --> Parse["SQLGlot read-only validation<br/>Declared relations and permitted functions"]
    Parse --> Engine["DuckDB default<br/>SQLite alternative"]
    Engine --> Bounds["Row, column, cell and byte bounds<br/>Query time and memory limits"]
    Context --> Record["Evidence IDs, trace and durable receipts"]
    Metadata --> Record
    Diagnostics --> Record
    Project --> Record
    Bounds --> Record
    Record --> Agent
```

Static SQL inspection and equality-join profiles are diagnostics. They do not cover every join predicate or establish metric correctness. `record_plan`, `record_findings`, and `finish` are separate graph controls. Source values and operator guidance do not override the authoritative contract.

## dbt incident-to-patch pipeline

```mermaid
%%{init: {"theme": "neutral"}}%%
flowchart TD
    Original["Frozen trusted payment project"] --> Build["Actual dbt seed, run, test"]
    Build --> Fault["Models build; event-grain test fails<br/>Daily revenue 2400 cents"]
    Fault --> Context["Model files, manifest dependencies<br/>Public staging snapshot and contract"]
    Context --> Investigate["Selected investigator"]
    Investigate --> Candidate["Plain SELECT for int_payment_events"]
    Candidate --> Grade["Evidence replay and canonical source-reference checks"]
    Grade -->|Fail| Fail["Failed report<br/>Verified download and approval blocked"]
    Grade -->|Pass| Patch["Restrict SQL and relation<br/>Render one permitted model-file patch"]
    Patch --> Fixtures["Fresh project/database copies<br/>Five designed regression fixtures"]
    Fixtures --> Rebuild["Actual dbt build on each fixture"]
    Rebuild --> Outputs["Compare canonical events, daily revenue<br/>monthly revenue and customer revenue"]
    Outputs --> All{"All 20 model checks pass?"}
    All -->|No| Fail
    All -->|Yes| Result["Versioned report and patch/model hashes<br/>Daily revenue 1200 cents"]
    Result --> UI["Impact, evidence, checks and diff"]
    UI --> Review["Exact-version review and protected download"]
    UI --> Edit["Operator SQL revision creates a new run"]
    Edit --> Candidate
```

The project accepts one trusted original sample, not arbitrary repository uploads. Fixtures cover the original incident, equal-value distinct events, late month boundaries/zero/pending values, reordered deliveries, and an empty batch. These are designed regressions, not unseen model evaluation or universal semantic proof.

## Cross-cutting operation

| Layer | Ownership and persistence |
| --- | --- |
| Job lifecycle | SQLite jobs, events, workflows and reviews; atomic claims, renewable leases, heartbeats, owner-fenced progress/publication. |
| Agent state | SQLite LangGraph checkpoints plus a separate call-receipt journal. Unresolved receipts block automatic replay. |
| Model spending | Shared estimated spend ledger: reserve before generation; settle complete reported usage; retain unknown reservations. Real generation retries are disabled. |
| Cancellation | Supervised subprocess groups stop and reap work. Already-sent provider requests can still be billed. |
| Observability | OTel spans propagate through jobs, model calls, tools and verification; JSONL locally or optional OTLP/Phoenix. |
| Evaluation | Known 38-case synthetic corpus and repeated-attempt reporting; scripted integration checks remain separate from live quality. |
| Delivery | Actual native, container and dbt GitHub Actions jobs; archived reports; no API key required for CI. |

SQLite is single-host state. Individual identity, PostgreSQL/distributed recovery, OS-isolated execution, broader held-out/safety tests, actual user feedback and monitored cloud hosting remain pending. See [operational limits](../../README.md#operational-controls), [graph design](AGENT-ORCHESTRATION.md), [dbt workflow](DBT-WORKFLOW.md), and [spend accounting](SPENDING-AND-DBT.md).
