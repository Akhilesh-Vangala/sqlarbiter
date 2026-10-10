# Contributing

Use the [branch and release workflow](../docs/development/BRANCHING.md): short-lived work branch → pull request → required CI → squash merge into protected `main`.

Follow the [README quick start](../README.md#quick-start). Python 3.12, Chromium, PostgreSQL for the production adapter and the separately locked dbt environment reproduce the application and integration checks.

## Verify a change

Run the [development verification commands](../docs/development/DEVELOPMENT.md) appropriate to the change. The [CI workflow](workflows/checks.yml) runs native tests, the test container and runtime build, and a dedicated dbt integration and browser job.

For agent changes, retain strict evidence citations, bounded calls, public corrective feedback and the independent private verification boundary. For queue/recovery changes, verify cancellation, ownership, unknown receipts and stale-version rejection. For dbt changes, run the real CLI integration and browser suite against all designed fixture outputs.

## Review expectations

- Describe the resulting behavior and the concrete failure it addresses.
- Report the test commands run and their results. Label fixed-diagnostic and mock-transport results as such.
- Preserve immutable exact-version review and protected verified exports.
- Keep estimated spend accounting separate from provider invoice claims.
- Use focused conventional commits such as `feat(agent): ...`, `fix(worker): ...` or `docs(readme): ...`.
- Never commit credentials, generated reports, private data, or local environments.

The [documentation index](../docs/README.md) maps architecture, evidence, and tradeoffs.
