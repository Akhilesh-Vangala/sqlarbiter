# dbt project investigations in the browser

October 12, 2026. Implements the browser integration of the [original dbt repair pipeline](15-SPENDING-AND-DBT.md). Existing six metric scenarios, history, spending controls and monochrome styling are preserved. The project accepts one trusted original sample; arbitrary repository uploads/remote warehouse connectors are not implemented.

## Pages and operator flow

| Route | Behavior |
| --- | --- |
| /dbt | Project catalog with tooling readiness, five models/five regression fixtures and project-run history |
| /dbt/new | Full setup page; choose fixed diagnostic, LangGraph or hosted investigator; unavailable AI methods disabled |
| /dbt/runs/{id} | Actual progress, source evidence drawer, reporting impact,20 independent model checks, unified file diff, SQL revision, review and downloads |

All routes support direct links/reload. Global run history/search opens the appropriate project detail rather than treating it as a metric. Back navigation returns to the catalog; revisions link to their original run. Setup and detail share existing responsive application styles. Desktop/mobile remain black/white/neutral.

The browser POST queues work, then the existing separate worker executes actual dbt seed/run/test/build. Progress is written only at real build/investigation/fixture boundaries, not invented percentages. Stage events and job timestamps refresh the UI; source/tool calls remain available in the evidence drawer. The known sample's upstream event-grain fix changes September30 revenue2400→1200cents. Five designed regressions independently check canonical events/daily/monthly/customer outputs (20 model checks).

Candidate SQL edits disable approval and create a new verification job. The original source/code version and result are preserved. Operator revisions use fixed diagnostics plus independent verification, consuming no model tokens. A false equal-value fix can pass the original incident and fail regression; no verified artifact can be downloaded or approved for that failed result. The result stores the exact patch/model text and report; downloads use stored verified content rather than a mutable local file.

Approval/rejection reuses the application's exact-version immutable review API. For dbt, the server additionally checks the signed report and stored patch/model hashes. A changed artifact, stale version or failed verification blocks approval/download even if a client bypasses disabled buttons. Reviews record decisions; no production SQL application, repository merge or actual customer approval is claimed. Test reviews occur only in temporary browser/API test workspaces.

## API and execution boundaries

- GET /api/dbt/projects: trusted sample metadata/readiness/source version; no executable or private paths.
- POST /api/dbt/runs: project_id and investigator only; idempotency key required, existing16-job admission bound applies.
- POST /api/dbt/runs/{id}/revisions: exact parent version and plain candidate SQL, creating an independently checked child.
- GET /api/dbt/runs/{id}/patch: completed passing dbt result only; verifies stored artifact hashes and serves a named .patch download.
- Existing /api/jobs/{id}, /cancel, /review and /report provide protected state/audit/cancellation/review/export.

All new API routes inherit the existing bearer/local-loopback, host/origin, JSON/body, CSP and no-store boundaries. Arbitrary project paths/code uploads are rejected by the request schema. Generic metric revision/resume routes cannot reinterpret dbt jobs. dbt clarification continuation remains unavailable; historical paused evidence can be inspected but needs a fresh controlled run rather than automatic paid replay.

The project version hashes trusted source assets, implementation, runtime and dependency locks. The worker checks it before execution; changing source/code invalidates queued work rather than silently operating on another revision. Owner-fenced progress cannot be published after cancellation or lease loss. Each dbt subprocess runs in a supervised process group with90-second/log allowances; cancellation/shutdown/lost ownership stop and reap it. The full queued workflow has a600-second cooperative deadline, retaining existing270-second model-worker/240-second async and3-second query limits. Expired work is interrupted, never silently retried. PostgreSQL/distributed recovery and per-investigation OS isolation remain future release work.

## Tooling and containers

Local default: .venv-dbt/bin/dbt; VDIR_DBT_EXECUTABLE overrides trusted service configuration only. The Docker dependencies now include /opt/dbt as a separate pinned virtual environment for both test/runtime stages. App and dbt Click/Pydantic dependencies remain separate. No user installs or API credentials are needed to run the fixed sample from the browser once the image/environment is built.

CI runs the actual browser dbt journey in its isolated dbt job and in the full container suite. The browser test creates temporary state, performs real project builds, downloads/revises/reviews, checks responsive monochrome routes and cancels work without publishing a result. API tests cover unauthorized access, idempotency, unsupported uploads, stale/cross-type revisions, failed/tampered artifacts and owner-fenced progress. A separate real-process cancellation test confirms dbt supervision terminates/reaps interrupted work.

```sh
PYTHONPATH=src .venv/bin/python -m vdir.serve --port 8000
VDIR_LOAD_DOTENV=0 PYTHONPATH=src .venv/bin/python tests/browser_dbt_smoke.py
VDIR_LOAD_DOTENV=0 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Open http://127.0.0.1:8000/dbt. With configured API credit/key, explicit AI selections use the existing shared spend ledger; fixed execution does not call a model. Live AI quality, actual operator feedback, PostgreSQL migration, individual identity and cloud deployment remain pending. The nine-milestone tracker is not incremented by browser integration alone.
