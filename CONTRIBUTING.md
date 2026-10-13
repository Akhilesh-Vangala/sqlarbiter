# Contributing

Use the [branch and release workflow](BRANCHING.md): short-lived work branch → pull request → required CI → squash merge into protected `main`.

Follow the [README quick start](README.md#run-locally). Python 3.11, Chromium and the separately locked dbt environment reproduce the application and integration checks.

## Verify a change

Run the [README verification commands](README.md#reproduce-checks-and-evaluation) appropriate to the change. The [CI workflow](.github/workflows/checks.yml) runs native tests, the actual test container and runtime build, and a dedicated dbt integration/browser job.

For agent changes, retain strict evidence citations, bounded calls, public corrective feedback and the independent private verification boundary. For queue/recovery changes, verify cancellation, ownership, unknown receipts and stale-version rejection. For dbt changes, run the real CLI integration and browser suite against all designed fixture outputs.

## Review expectations

- Describe the resulting behavior and the concrete failure it addresses.
- Report actual test commands and results; distinguish fixed diagnostics and mock transport from live model quality.
- Preserve immutable exact-version review and protected verified exports.
- Keep estimated spend accounting separate from provider invoice claims.
- Use focused conventional commits such as `feat(agent): ...`, `fix(worker): ...` or `docs(readme): ...`.
- Never commit credentials, generated reports, private data or local environments. Preserve earlier dated milestones and update the current handoff.

The [documentation index](docs/README.md) maps architecture, evidence and tradeoffs. Individual identity, distributed persistence, execution isolation, live evaluation and cloud delivery remain release work.
