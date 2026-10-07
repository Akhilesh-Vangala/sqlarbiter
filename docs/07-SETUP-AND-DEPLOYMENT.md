# Setup and deployment

## Python and dependencies

Use **Python 3.11.17** locally and in Docker. The project requires >=3.11,<3.12; .python-version records the patch. Runtime pins include web, SDK, analytical and OTel dependencies. requirements-dev adds HTTP test and browser dependencies. No dependency-free core claim remains.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
PYTHONPATH=src .venv/bin/python -m vdir.serve
```

If needed, [uv-managed Python](https://docs.astral.sh/uv/guides/install-python/) can supply the interpreter:

```sh
uv python install 3.11.17
uv venv --python 3.11.17 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
```

On this Mac uv is project-local at .tools/uv-aarch64-apple-darwin/uv. .venv points to the installed .venv311; .venv39-legacy preserves the older environment. Apple system Python was not modified. The active local launcher at http://127.0.0.1:8000 uses Python 3.11.17. Check process liveness when resuming.

## Private configuration

A private .env is automatically loaded with override=False by the CLI/launcher/worker and default app factory. It is ignored and permissioned 0600 on this Mac. On a new checkout copy .env.example; never overwrite an existing credential file. VDIR_LOAD_DOTENV=0 disables file loading (tests/containers use this). Key/model values are not printed or added to logs.

- ANTHROPIC_API_KEY and VDIR_ANTHROPIC_MODEL enable explicit billable hosted runs. Current key is absent; no live generation occurred.
- VDIR_ACCESS_TOKEN must contain at least 32 characters before exposing a shared service. This is shared operator access, not individual authentication.
- VDIR_PUBLIC_ORIGIN declares the canonical HTTPS origin behind a TLS proxy.
- VDIR_SQL_ENGINE selects duckdb or sqlite for worker fallback; app jobs explicitly record their selected engine, default duckdb.
- VDIR_OTLP_ENDPOINT is an optional OTLP/HTTP URL including /v1/traces; empty disables remote export. Local span JSONL is always retained for investigator/job runs.

Each model run writes model-run.json and stream-events.jsonl in its evidence workspace. Failed investigators also write failed-investigation.json. CLI reports retain failure traces; the browser shows a sanitized failure. Parent timeout/transport failures may leave billing incomplete. Benchmark pricing requires an explicit verified model/rate profile; no profile means live dollar estimates are null.

## Executed Docker setup

Dockerfile has runtime and test stages pinned to python:3.11.17-slim. Test stage includes Chromium system dependencies/browser in a readable shared directory and runs unittest, browser workflow and all 38 benchmark cases as UID 10001. Runtime runs as UID 10001. Debian sources use HTTPS after a checked download mismatch during the initial build; package checksums remain enabled.

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

GitHub Actions definitions run pinned-Python unit/browser/benchmark checks, build and run the full test container, build runtime, and upload evidence. **Remote Actions have not run:** GitHub repository details/publication access are pending. A local passing container is not remote CI success.

Cloud deployment remains required and pending provider/account configuration. AWS remains proposed. Before release: individual authentication/authorization, durable distributed state/object artifacts, isolated per-investigation execution, TLS, monitoring, cancellation/recovery, load and failure testing, promotion/rollback, and realistic external data. No cloud resource or public deployment has been created.
