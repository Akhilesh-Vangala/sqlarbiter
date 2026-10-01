# Product routes and optional accounts

`api.py` serves the public product frontend and explicit workspace routes. `accounts.py` delegates optional sessions to a configured Supabase provider and saves owner-isolated snapshots through user-token PostgREST. Missing configuration is an explicit disabled state. No service/admin key, cross-user global history or client-asserted verified report is accepted.

[Workflow, contracts, storage, security and verification](../../../../docs/product/WORKSPACE.md) · [SQL migration](../../../../infrastructure/supabase/migrations/001_product_workspace.sql).
