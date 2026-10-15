# VerifyOps frontend

- [Guided application](apps/demo/): index.html and nested assets/scripts, assets/styles and assets/media.
- [Private workbench](apps/workbench/): operator assets; server-owned HTML remains in the backend where appropriate.

These are native browser applications served by Python. Folder separation does not introduce an extra Node service or change backend authority. [Full layout](../docs/development/LAYOUT.md).

- [Product workspace](apps/product/): landing, dashboard, guided own-data intake, checked reports, explicit saved history, projects and account/settings views.
- [Upload recording](apps/uploads/): hosted video/player and historical compatibility assets; `/uploads` now opens the product frontend.
