# VerifyOps repository layout

The checkout separates browser code, backend authority, reproducible tooling and documentation. Run commands from the repository root unless a command states otherwise.

| Directory/file | Responsibility |
| --- | --- |
| `backend/src/vdir/` | API, agent workflow, typed contracts, verification and persistent-runtime services. |
| `backend/investigator_runtime/` | Exportable investigator code; evaluator reference data stays outside this runtime. |
| `backend/tests/` | Backend regression and integration cases. |
| `frontend/public/` | Guided public pages, JavaScript/CSS, poster and continuous WebM recording. |
| `frontend/workbench/` | Private native workbench styles/behavior; Python routes still render the server-owned HTML where appropriate. |
| `tests/e2e/` | Browser journeys across both sides of the application. |
| `scripts/` | Structural checks, benchmarks, deployment smoke and reproducible capture. |
| `docs/architecture/` | Current system/agent flow and authority boundaries. |
| `docs/operations/` | Development, deployment and public/private operating boundaries. |
| `docs/evaluation/` | Evaluation design, limits and linked engineering evidence. |
| `docs/project/` | Current handoff, release gates and progress; dated predecessors live under `history/`. |
| `docs/assets/`, `docs/demos/` | Documentation figures, actual capture previews and provenance manifests. |
| `compose.yaml`, `vercel.json` | Root deployment wiring; the Vercel launcher remains at the root for framework discovery. |

The Ops applications intentionally retain native HTML/CSS/JavaScript delivery. A separate frontend directory expresses ownership and asset packaging; it does not imply a separate React service or require a JavaScript build step.

## Reorganization compatibility

Source moves update ASGI imports, asset resolution, dependency locks, test discovery, Docker context/copies, CI, source exports and Vercel includes. Existing HTTP routes, data directories and ignored runtime histories remain in place. Changing source paths changes runtime/source fingerprints: old results remain readable, but a stale checked proposal or checkpoint is not silently approved/resumed under changed source. Start a fresh investigation when version checks reject continuation.

The current paths supersede the dated commands in historical records. [Current quick start](../../README.md#run-locally) · [Branch workflow](../../BRANCHING.md).
