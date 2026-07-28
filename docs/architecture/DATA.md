# Data and integrations

Original controlled records in backend/src/vdir/environment.py. No personal repositories or academic/customer data used.

Orders key: order_id. Items key: item_id. Product versions key: product_id/version. Integer cents avoid floating-point comparisons. Latest product version within snapshot supplies current category; historical as-of categorization is outside scope. Completed orders qualify; pending/canceled do not.

Six known scenarios in backend/src/vdir/domain/cases.py include the original three retail snapshots, two event-delivery batches, incomplete and explicit-offset event sources, a healthy retail control and conflicting payloads for one event ID. delivery_id identifies a transmission; event_id identifies the business event. Equal amounts/customer/time do not imply duplicate business events. Conflicting payloads require authoritative resolution. UTC counts require explicit minute offsets; missing offsets cannot be inferred from unrelated rows.

Simple lineage and neutral change metadata are original fixtures, not live dbt integrations. Only the current snapshot is exported into source.duckdb or source.sqlite plus incident.json/schema.json; regression sources remain evaluator-owned. A frozen 38-case synthetic corpus now exists with explicit SQL-shape groups/splits and private regression sources; it remains known and limited, not a real-world held-out benchmark. No customer dataset, warehouse connector or training trajectories exist. Hosted-model API transport is implemented but has not been used live.

[Corpus and limitations](../evaluation/BENCHMARK.md). Null/distinct profiling uses exact aggregates with execution budgets; schema metadata is paginated in 50-column pages. No external-file SQL functions or warehouse network access are allowed by the analytical tools.
