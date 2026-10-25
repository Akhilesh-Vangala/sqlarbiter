# Public availability and no-credit checks

The canonical application is https://sqlarbiter.vercel.app/. Vercel serves the application independently of a local Mac or terminal. Do not stop or remove the existing production deployment to prepare a replacement. Test a preview first, pass the exact-head required CI and protected merge, then verify the promoted source and actual upload/result workflows. Retain the previous ready deployment for an explicit rollback if the replacement fails; do not repeatedly redeploy to conceal a failure.

## Synthetic monitor

[Public application health](../../.github/workflows/public-health.yml) checks the canonical application twice an hour, at minutes 17 and 47 UTC. It can also be dispatched manually. The standard-library [probe](../../scripts/checks/public_health.py) requires no provider key or third-party monitoring account. It exercises the actual home script, declared capabilities, CSV/TSV/XLSX/JSON/JSONL parsing, observed SSE stages, exact domain results, independent checks, report authenticity/tamper rejection, invalid-source rejection, cross-origin rejection and video range delivery. RelayOps additionally exercises explicit approval and four temporary-snapshot receipts. Only tiny original synthetic fixtures are submitted. No customer source, authorization cookies, reports or raw response payloads appear in the retained health summary. Failures exit nonzero and retain a seven-day artifact; GitHub notification delivery depends on the owner's configured notification preferences. No messages or issues are sent automatically.

```sh
python3 scripts/checks/public_health.py
```

The probe has per-request and aggregate deadlines, bounded responses, and same-origin redirect checks. It does not retry a failed observation. Latencies are individual observations.

GitHub schedules can be delayed or dropped during high load, and public-repository schedules can be disabled after 60 days of inactivity. Scheduled workflows execute from the default branch. These limits come from [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Stream recovery

Progress uses a 32-event mailbox with coalesced loop wakeups and an independent terminal slot. A progress burst cannot drop the final result or error. A 25-second response deadline returns a failure. Closing the browser or exceeding the deadline suppresses late report delivery when the calculation has not finished. No business-system writes run on this public path.
