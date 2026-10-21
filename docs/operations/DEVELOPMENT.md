# Development and deployment

Run from the repository root. Python 3.11–3.12 is supported; CI and images use 3.12. Source lives under `backend/src/vdir`, browser assets under `frontend/`, and generated state remains in ignored `artifacts/generated/`.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements/development.txt
.venv/bin/python -m playwright install chromium
PYTHONPATH=backend/src .venv/bin/python -m vdir.cli.serve
```

For dbt, create a separate .venv-dbt and install backend/requirements/dbt.txt. Its dependency constraints differ from the application.

## Public application

The Vercel entrypoint `app.py` serves an interactive guided sandbox at `/demo`, with a continuous player at `/demo/recording`. It disables provider credentials, embedded workers and persistent database settings. Only exact bounded public-demo POST routes are enabled; legacy private writes remain blocked. [Public behavior and replay boundaries](PUBLIC-SANDBOX.md).

Use `python scripts/demos/public_demo_browser.py` to start an isolated temporary public app and exercise it. `--url https://verifyops.vercel.app` checks the deployed app. `--record --publish-assets` captures actual browser media into `frontend/apps/demo/`; no model call is needed.

## Private persistent runtime

```sh
docker build -f backend/docker/Dockerfile --target test -t verifyops:test .
docker run --rm verifyops:test
# Configure the required private operator token and PostgreSQL password first.
scripts/deployment/compose.sh up --build -d
```

The build context is the repository root; the Dockerfile is `backend/docker/Dockerfile`. Compose declares this explicitly so frontend assets, original data and the exported investigator/dbt project enter the correct image. API and worker are separate processes, coordinated through PostgreSQL; fixture/workspace files remain on same-node shared storage. [Detailed runtime](PRODUCTION-FOUNDATION.md).

## Private configuration and live inference

Never overwrite an existing `.env`. Configure provider credentials privately, using `.env.example` only as a template on a fresh checkout. The VerifyOps launcher loads .env without overriding explicit process values; VDIR_LOAD_DOTENV=0 disables loading. The official SDK requires a provider key, explicit live selection and a matching model/pricing profile. Live execution is billable and has not been evaluated by the guided demo.

The required CI jobs execute real native/container/browser and PostgreSQL checks, plus actual dbt integration and Terraform validation. Prepared manifests do not establish deployed cloud operation. AWS remains unapplied; individual identity, real connectors, isolated execution, monitored operation and restore/load evidence remain release gates.

[Current layout](../development/LAYOUT.md) · [Dated setup history](../project/history/PRE-ORGANIZATION-operations-DEVELOPMENT.md).
