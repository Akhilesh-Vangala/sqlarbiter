# SQLArbiter frontend

Native browser applications served by the FastAPI backend. No separate Node service.

| App | Route | Responsibility |
| --- | --- | --- |
| [product](apps/product/) | `/uploads`, `/workspace`, and `/` on the public deployment | Landing, guided intake, checked reports, saved history, account views |
| [demo](apps/demo/) | `/demo` | Guided investigation sandbox and recording player |
| [workbench](apps/workbench/) | `/` locally, `/investigations`, `/workflows`, `/dbt`, `/metrics`, `/settings` | Operator queue, investigations, workflows, dbt, settings |
| [uploads](apps/uploads/) | `/uploads/recording.html` | Recording player for the upload journey |

[Layout](../docs/development/LAYOUT.md).
