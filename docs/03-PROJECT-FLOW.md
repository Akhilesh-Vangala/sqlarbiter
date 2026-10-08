# Flow

CLI loads known candidates or a supplied file, executes each on fresh snapshots, compares grouped integer-cent outputs and prints checks. Supplied candidate exits nonzero on failure; demonstration intentionally includes failing candidates.

--investigate creates one public-evidence workspace per scenario. Fixed or hosted-model investigation reads tools and proposes candidate/no-change/needs-information outcomes with evidence IDs. The evaluator re-executes the trace to reject fabricated results or references, then checks candidate meaning on evaluator-owned sources. Reports and traces are saved; execution failures are failed outcomes. No repair is applied to a production system.

Implemented browser flow: select scenario → idempotently enqueue → atomically claim work → collect evidence/propose outcome → independent replay/regression grade → inspect result → verify edited candidate as a new job → record exact-version approval/rejection → export. Healthy inputs and missing evidence produce no-change/clarification. Process failures/interruption remain visible.

Planned: realistic incident intake, competing-hypothesis/impact reports, OS-isolated verification, controlled promotion and observed outcome. Approval currently records a review only.

Passing checks is not authorization. Operational business-rule validation differs from agreement with hidden benchmark references.

Implemented October 8: [one-off metric workflows and owner-fenced cancellation](12-WORKFLOWS-AND-CANCELLATION.md), including workflow-to-member navigation and source-cited graph findings.
