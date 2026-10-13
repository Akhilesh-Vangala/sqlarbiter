# Vercel engineering showcase

## Public surface

[verifyops.vercel.app](https://verifyops.vercel.app) runs the real VerifyOps FastAPI and native JavaScript interface on Vercel's Python 3.12 runtime. Visitors can inspect six original synthetic incidents, reporting contracts, source schemas, current SQL, the dbt project catalog and the product's review workflow.

The deployment is intentionally read only. `VDIR_PUBLIC_SHOWCASE=1` permits public API reads and rejects every state-changing API request with `405 Public showcase is read-only`. The interface displays a persistent public-showcase banner and disables creation controls. Live model availability is forced false; no provider credential is uploaded.

## Why execution is disabled

Full investigations depend on the separate persistent worker, SQLite ownership leases, dbt subprocesses, checkpoints and local artifacts. Vercel Functions have request-scoped execution and an ephemeral filesystem. Running those workflows inside the public function would misrepresent durability, recovery and concurrency.

The local and container application retain the implemented investigation, LangGraph, dbt verification, review and recovery behavior. The public site exposes their actual product surface and links to recorded execution evidence.

This deployment proves a successful Vercel build, public routing, metadata reads, static asset delivery, browser rendering and server-enforced write rejection. It does not prove live model quality, unseen generalization, durable cloud jobs, customer warehouse connectivity, individual authorization, monitored operations or user adoption. The completion tracker therefore remains unchanged.

## Reproduction and verification

- `app.py` is the Vercel ASGI entrypoint.
- `.python-version` selects Python 3.12; Python 3.11 remains supported by local and CI execution.
- `.vercelignore` excludes `.env`, virtual environments, generated state, test artifacts and local tooling.
- The upload retains the dbt and investigator source used by public version hashes while excluding executable local environments.
- `tests/test_api.py` checks remote reads, public configuration and server-side write rejection.

The production deployment completed in Vercel `iad1`. External smoke checks verified the HTML, JavaScript, six incidents, dbt catalog, empty public queue/stat/workflow reads and write rejection. A Chromium journey verified the banner, disabled actions, six scenario cards and zero console errors.
