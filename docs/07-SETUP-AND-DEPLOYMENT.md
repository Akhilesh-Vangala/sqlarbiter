# Setup and deployment

October 13: [verifyops.vercel.app](https://verifyops.vercel.app) serves the real interface as a public read-only engineering showcase on Vercel Python 3.12. The API exposes current synthetic incident and dbt project metadata while rejecting every state-changing method. See the [deployment record and boundary](18-VERCEL-SHOWCASE.md). The persistent API/worker/PostgreSQL/Phoenix Compose system is the local production-topology target. Kubernetes and Terraform foundations are documented in [19-PRODUCTION-FOUNDATION.md](19-PRODUCTION-FOUNDATION.md); no AWS resource has been applied.

## Python and dependencies

Use **Python 3.12** locally and in Docker. The project supports >=3.11,<3.13; `.python-version` records 3.12. Runtime pins include web, SDK, PostgreSQL/checkpoint, analytical and OTel dependencies. `requirements-dev.txt` adds HTTP test and browser dependencies.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
PYTHONPATH=src .venv/bin/python -m vdir.serve
```

If needed, [uv-managed Python](https://docs.astral.sh/uv/guides/install-python/) can supply the interpreter:

```sh
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
```

On this Mac uv is project-local at `.tools/uv-aarch64-apple-darwin/uv`; `.venv312` is the isolated production-foundation verification environment. Older environments are preserved and ignored. Apple system Python was not modified.

## Private configuration

A private .env is automatically loaded with override=False by the CLI/launcher/worker and default app factory. It is ignored and permissioned 0600 on this Mac. On a new checkout copy .env.example; never overwrite an existing credential file. VDIR_LOAD_DOTENV=0 disables file loading (tests/containers use this). Key/model values are not printed or added to logs.

- ANTHROPIC_API_KEY and VDIR_ANTHROPIC_MODEL enable explicit billable hosted runs. Current key is absent; no live generation occurred.
- VDIR_ACCESS_TOKEN must contain at least 32 characters before exposing a shared service. This is shared operator access, not individual authentication.
- VDIR_DATABASE_URL selects the PostgreSQL queue/review/event adapter; unset keeps the local SQLite adapter.
- VDIR_CHECKPOINT_DATABASE_URL selects the official PostgreSQL LangGraph checkpointer; unset keeps per-workspace SQLite checkpoints.
- VDIR_POSTGRES_PASSWORD is consumed by local Compose interpolation and is never checked in.
- VDIR_PUBLIC_ORIGIN declares the canonical HTTPS origin behind a TLS proxy.
- VDIR_SQL_ENGINE selects duckdb or sqlite for worker fallback; app jobs explicitly record their selected engine, default duckdb.
- VDIR_OTLP_ENDPOINT is an optional OTLP/HTTP URL including /v1/traces; empty disables remote export. Local span JSONL is always retained for investigator/job runs.

Each model run writes model-run.json and stream-events.jsonl in its evidence workspace. Failed investigators also write failed-investigation.json. CLI reports retain failure traces; the browser shows a sanitized failure. Parent timeout/transport failures may leave billing incomplete. Benchmark pricing requires an explicit verified model/rate profile; no profile means live dollar estimates are null.

## Executed Docker setup

Dockerfile has runtime and test stages on Python 3.12 slim. Test stage includes Chromium system dependencies/browser in a readable shared directory and runs unittest, browser workflow and all 38 benchmark cases as UID 10001. Runtime runs as UID 10001.

```sh
docker build --target test -t vdir:test .
docker run --name vdir-check vdir:test
docker build --target runtime -t vdir:app .
docker compose up --build -d
```

**Executed successfully on this Mac:** Linux ARM64 through Lima 2.2.1/Apple virtualization, Docker Engine 29.8.2 in a rootless guest daemon. No host directories are mounted. scripts/source_bundle.py transfers only explicit source/test/build paths, excluding .env, environments, artifacts and tools. The VM's short temporary LIMA_HOME is /private/tmp/vdir-lima-501; this is a disposable local verification VM, not durable production storage. Host app history remains in the project artifacts directory.

The Lima template's initial automatic Docker provision failed; retried official Docker installation and installed uidmap, then configured the rootless daemon. Reproduce or inspect with project-local .tools/bin/limactl. Command history is in the workspace setup log.

The tested guest project is /home/akhileshvangala.guest/vdir. It has a separately generated private test operator token and no Anthropic key. Compose uses local state/traces volumes; API port 8001 was chosen for this verification to leave the host app on 8000. API, worker and digest-pinned Phoenix started successfully; six scenarios/reviews/exports passed and jobs survived API/worker restart. Phoenix UI is http://127.0.0.1:6006. Compose API requires its private guest token.

## Tracing and CI

Compose defaults VDIR_OTLP_ENDPOINT to http://phoenix:6006/v1/traces. For a standalone local collector use http://127.0.0.1:6006/v1/traces. Batch OTLP export avoids per-tool network blocking; JSONL spans remain available locally. Parent trace context propagates from job to investigator subprocess; grading is a sibling span. [Phoenix self-hosting](https://arize.com/docs/phoenix/self-hosting/deploying-phoenix).

GitHub Actions runs pinned-Python unit tests, all four browser suites and the fixed benchmark, builds/runs the full test container, builds runtime, and uploads evidence. The project is [published on GitHub](https://github.com/Akhilesh-Vangala/verified-data-incident-resolution), and real remote runs/results are available in [Actions](https://github.com/Akhilesh-Vangala/verified-data-incident-resolution/actions/workflows/checks.yml). [Publication evidence](14-GITHUB-PUBLICATION.md) distinguishes local checks, triggered remote execution and verified conclusions. No live provider credential is needed for CI. Publication does not deploy the app to the cloud.

AWS infrastructure remains prepared and unapplied. PostgreSQL coordination and Kubernetes topology are implemented; individual OIDC authorization, S3 workspace synchronization, isolated per-investigation execution, TLS/domain wiring, monitored staging, load/failure evidence and realistic external data remain release gates. No AWS resource has been created.
