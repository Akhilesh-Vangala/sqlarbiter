# Progress

Earlier dated entries preserve historical milestones; the most recent entry defines current status.

## October 7, 2026 — Operational web workbench

User requested continued building. Implemented FastAPI endpoints, a separate worker, persistent transactional job queue, atomic ownership/300-second renewable leases, bounded admission and idempotent submission. Added immutable result hashes, source/execution version checks, independently verified SQL revisions, exact-version review/audit and report export. Expired worker jobs become interrupted and require explicit new runs; no automatic paid retries.

Built the original responsive interface under src/vdir/web: scenario/engine selection, persistent run history, findings/checks, actual expandable evidence tables, current/candidate SQL, edited-revision verification, review notes, contracts and JSON export. Local-only unauthenticated mode and optional shared operator access are implemented. No personal portfolio work occurred.

**50 unittest checks passed**, including queue races, renewal, restart persistence, origin/host/body limits, version review and unsafe/failed candidates. Browser testing found a JavaScript function named history shadowing window.history and breaking URL selection; renamed it and reran successfully. Initial 12 Chromium checks passed; final **13 checks passed** in browser-smoke-76f81514 after adding idle launcher/worker shutdown validation. Desktop/mobile screenshots were manually inspected. Web dependency compatibility check passed.

Local app launched at http://127.0.0.1:8000. Pinned requirements, Docker/Compose and CI definitions prepared; Docker is unavailable on this Mac, so image/container/remote CI have not been run. Asked for cloud provider/account choice; no external deployment, model call, training, paid resource or GitHub publication occurred.

## October 7, 2026 — Diagnostic environment and model interface

Implemented six known scenarios across retail revenue, event identity and UTC-date semantics, including healthy/no-change and unavailable-information controls. Source-level references independently compute expected results; ambiguous payloads and missing offsets require precisely scoped clarification.

Added current-evidence exports, schema/contract/lineage/change/SQL tools, bounded source queries, isolated-import subprocess workers and a fixed workflow. Evaluator replays tool operations before accepting cited evidence and grades candidates on private regression snapshots. Exported runtime has no reference imports or regression data; this is not OS/container isolation.

Native Anthropic tool-use adapter and investigator are implemented with explicit local configuration, eight-round/24-evidence-call limits, validated final decisions, token-usage recording and sanitized provider failures. Ten scripted/transport tests exercise the model interface; no live model call, provider performance or training result exists.

Final verification: **34 tests passed on Python 3.9.6**; fixed workflow passed six scenarios in [development-run-003](artifacts/generated/development-run-003/report.json). Results are known-fixture development checks. Run-001 exposed a balanced UTC-boundary fixture that concealed the date error; corrected it to unequal crossings, added a hand-calculated reference check, and preserved the historical artifact. A direct-controller test also found tuple/list trace differences across JSON transport; source results now use JSON-native rows for stable replay.

No API server, browser app, cloud resources, learned policy, GitHub publication or spending yet.

## October 7, 2026 — Local environment foundation

Created with workspace scaffold. Implemented immutable original source snapshots, explicit metric contract, independent non-SQL reference calculation, bounded SQLite SELECT runner, semantic comparisons and JSON CLI.

Python 3.9.6: eight tests passed. Current transformation fails all three snapshots; DISTINCT-amount candidate passes incident only; latest-version candidate passes all three. Alternate correlated-subquery repair passes. Tests cover hand-calculated references, ambiguous source identity, output schema/types/duplicates, query restrictions and row/computation limits.

Initial run identified Python 3.9 sqlite3.Warning for multiple statements; normalized this rejection alongside SQLite errors. Final tests and demonstration passed.

Historical milestone: eight tests and one fault mechanism before the diagnostic expansion above. These were known development cases, not model/benchmark results or production security evidence.

## October 7, 2026 — SDK, analytics, evaluation and executed containers

Implemented the user's remediation checklist: official async Anthropic SDK with typed SSE/retry/count-token preflight, bounded async controller, failed-run metadata, aligned Python 3.11.17, DuckDB/SQLite analytical abstraction, query/schema/profile/context guards, frozen 38-case corpus/Pass@k/latency/cost runner, OTel propagation and Phoenix collector.

**Measured:** 59 unittest and 13 Chromium checks pass locally and inside the Linux ARM64 test container. Fixed baseline passed all 38 cases in both engines; local DuckDB 114/114 attempts, container 38/38. Real Compose API/worker completed six scenarios, candidate reviews/exports passed, six completed jobs survived restart. Phoenix REST verification returned 63 spans across six propagated job traces. No live model generation occurred: private API key absent. Remote GitHub CI, learned policy, cloud deployment and production readiness remain pending.

SDK streaming/rate-limit retry tests use mocked HTTP, explicitly separate from AI evaluation. Schema pagination initially broke the browser query-table renderer; fixed its type/rows check and reran the full workflow. Initial container browser dependency build failed Debian checksum checks; changed package sources to HTTPS and rebuilt successfully without weakening verification.

Project-local uv supplies Python 3.11.17; .venv aliases .venv311 and old .venv39-legacy is preserved. Local app restarted on port 8000 with Python 3.11.17. Docker runs through Lima/rootless guest with no host mounts and no copied provider credentials. The original Docker auto-provision failed and was repaired with official installation plus uidmap/rootless setup. Evidence: artifacts/generated/remediation-001 and docs/10-REMEDIATION-AND-BENCHMARK.md.

New isolated Git repository initialized within this project; no existing personal repo accessed for inspiration. New repository name/visibility and publication access are pending; no remote/push/Actions result. Earlier no-Git status is historical. portfolio/ untouched.
