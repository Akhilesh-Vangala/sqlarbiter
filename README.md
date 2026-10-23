# VerifyOps

A checkpointed LangGraph investigator proposes a SQL repair for a metric discrepancy. Independent regression checks and a real dbt pipeline decide whether that repair can be accepted. The model does not grade its own fix.

[Open the app](https://verifyops.vercel.app/) · [Upload a file](https://verifyops.vercel.app/uploads) · [Architecture](docs/architecture/OVERVIEW.md) · [What the checks measure](docs/evaluation/README.md) · [Run locally](docs/operations/DEVELOPMENT.md)

<p align="center"><a href="https://github.com/Akhilesh-Vangala/verifyops/actions/workflows/checks.yml"><img src="https://github.com/Akhilesh-Vangala/verifyops/actions/workflows/checks.yml/badge.svg" alt="Required engineering checks"></a> &nbsp; Python · LangGraph · FastAPI · PostgreSQL</p>

The public app uses synthetic fixtures and does not call a model. Live model quality is not a result of this repository.

## Architecture

Read-only evidence tools feed the agent. A separate verifier runs source computations and dbt builds. An operator accepts or rejects that exact checked version.

![System map: web workbench, persistent jobs, LangGraph investigator, independent verification, operator review](docs/assets/diagrams/verifyops-architecture.svg)

| Component | Responsibility |
| --- | --- |
| Frontend | Landing, guided intake, report views, device projects/history |
| Backend | FastAPI, typed contracts, LangGraph orchestration, review gates |
| Independent checking | Source computations, regressions, restricted dbt patch checks |
| Runtime | PostgreSQL workers; fixtures/workspace remain same-node |

## Repository layout

```text
verifyops/
├── backend/          src, tests, agents, dbt, data
├── frontend/         demo, product, uploads, workbench
├── infrastructure/   containers, kubernetes, terraform
├── scripts/
├── docs/
└── .github/
```

## Run locally

```sh
git clone https://github.com/Akhilesh-Vangala/verifyops.git
cd verifyops
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements/development.txt
PYTHONPATH=backend/src .venv/bin/python -m vdir.cli.serve
```

Open **http://127.0.0.1:8000**. [Full development guide](docs/operations/DEVELOPMENT.md).

## Checks

```sh
PYTHONPATH=backend/src VDIR_LOAD_DOTENV=0 python -m unittest discover -s backend/tests -v
python scripts/checks/check_repository.py
```

Public demos use guided synthetic fixtures (no live inference claim). Live model quality and customer production certification remain out of scope. [Evaluation](docs/evaluation/README.md) · [Demo notes](docs/DEMO.md)
