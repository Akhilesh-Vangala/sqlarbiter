# Application pages

Each main task has its own page. Investigation and workflow setup occupy full pages. Workflow collection and detail are separate. Evidence drawers and cancellation confirmations stay dialogs because they are contextual actions.

## Page map

| URL | Purpose |
| --- | --- |
| `/` | Workspace home, totals, recent investigations and scenario shortcuts |
| `/investigations` | Searchable investigation queue |
| `/investigations/new` | Full investigation setup with method/engine selection and explanatory side panel |
| `/investigations/{id}` | Investigation summary and run context |
| `/investigations/{id}/evidence` | Directly linkable evidence section |
| `/investigations/{id}/sql` | SQL comparison, revision verification and exact-version review |
| `/investigations/{id}/activity` | Recorded plans, findings and graph activity when present |
| `/investigations/{id}/definition` | Recorded metric contract for that run |
| `/workflows` | Named workflow collection with actual status and finished counts |
| `/workflows/new` | Full multi-metric setup with bounded selection and explanatory side panel |
| `/workflows/{id}` | Dedicated workflow result/progress/member page |
| `/runs` | Searchable recent-run table |
| `/metrics` | Searchable six-scenario development metric catalog |
| `/metrics/{case_id}` | Current public reporting contract, SQL, source-table schema and source/runtime version |
| `/settings` | Read-only actual workspace/operator/method/access configuration and review scope |

Creation forms retain the existing API and field identifiers. Header actions and home scenario shortcuts route into setup pages. Opening an investigation from a metric includes `?metric=case-001` or its actual case ID, so the selection survives reload. Cancel/back returns to the originating collection or metric; direct links fall back to the corresponding collection. Form drafts survive background polling while the page remains open. Arbitrary in-memory drafts are not persisted across a full browser reload.

Collection pages have their own headings, search/empty states and content. Workspace totals appear on home rather than every page. Workflow details show only that workflow, with member drill-down and back to the collection. A missing metric displays an unavailable/retry state; the API responds 404. The settings page is read-only and never accepts or renders provider credentials. Mobile navigation accommodates six pages, with accessible link names retained when visual labels collapse.

## URL and history behavior

The existing same-origin FastAPI shell serves these routes, with client routing and existing HTML/CSS/JavaScript. No additional server framework or frontend dependency was introduced. Each investigation section has an actual link; modifier-click/open-in-new-tab preserves native browser behavior, and keyboard arrow/Home/End tab navigation is retained. Reload and browser Back/Forward restore the selected section from the URL. Contextual parent breadcrumbs and back buttons remain available. Legacy `?job=` and `#runs`/`#investigations` links still resolve.

A fixed investigator has no graph activity. Opening its activity URL explicitly returns to summary with an explanation rather than showing another run's assessment. Result revision/verification still creates a new run and removes inherited agent metadata. The new routes do not change independent verification, review authorization, cancellation ownership or graph recovery.

## Public metadata boundary

GET `/api/incidents/{case_id}` exposes only current public case metadata: ID/title/description, contract, current SQL, lineage, source table definitions, current snapshot ID and version. It includes no source rows, regression snapshots or evaluator functions/answers. Existing API access and no-store/CSP controls apply. Config adds the non-secret `access_mode` label (`local_loopback` or `shared_operator`) so settings describes the real mode rather than suggesting individual accounts exist.

API tests verify schema and contract equivalence, field boundaries, exclusion of private snapshot names, 404 behavior, and protected access. The server validates investigation section names.

## Tests

`backend/tests/e2e/browser_pages_smoke.py` covers metric search and metadata, preselected setup with reload and cancel, run and workflow execution, section links with reload and history, unavailable activity, settings, workflow collection and detail, and a missing metric. It renders six page types at five widths from 320 to 1440 pixels.
