"use strict";
let config = null,
  selectedCase = "",
  activeTab = "result",
  busy = "",
  error = "";
const app = document.querySelector("#app");
const esc = (value) =>
  String(value == null ? "" : value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const json = (value) => `<pre>${esc(JSON.stringify(value, null, 2))}</pre>`;
const isRelay = () => config.project === "RelayOps";
const cacheKey = () => config.project.toLowerCase() + "-interactive-runs-v1";
function records() {
  try {
    const value = JSON.parse(sessionStorage.getItem(cacheKey()) || "[]");
    return Array.isArray(value)
      ? value.filter(
          (r) => r && typeof r.id === "string" && typeof r.case_id === "string",
        )
      : [];
  } catch {
    return [];
  }
}
function save(run) {
  const value = { ...run, viewed_at: new Date().toISOString() };
  sessionStorage.setItem(
    cacheKey(),
    JSON.stringify(
      [value, ...records().filter((r) => r.id !== value.id)].slice(0, 12),
    ),
  );
  return value;
}
function current() {
  const id = location.pathname.split("/")[3];
  return records().find((r) => r.id === id);
}
function go(path) {
  history.pushState({}, "", path);
  activeTab = "result";
  error = "";
  render();
  window.scrollTo(0, 0);
}
async function post(action, body) {
  const response = await fetch("/api/demo/" + action, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("The request did not complete. Start a new investigation.");
  }
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "The submitted input was not accepted.",
    );
  return data;
}
async function perform(label, action, body) {
  busy = label;
  error = "";
  render();
  try {
    const run = save(await post(action, body));
    go("/demo/runs/" + run.id);
  } catch (e) {
    error = e.message;
  } finally {
    busy = "";
    render();
  }
}
function table(columns, rows) {
  if (!columns?.length) return "";
  return `<div class="table-wrap"><table><thead><tr>${columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${(rows || []).map((row) => `<tr>${row.map((v) => `<td>${v == null ? "—" : esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function checks(value, heading) {
  return `<h3>${esc(heading)}</h3>${Object.entries(value || {})
    .map(
      ([name, passed]) =>
        `<div class="check-row"><span class="pill">${passed ? "PASS" : "REVIEW"}</span><div><strong>${esc(name.replaceAll("_", " "))}</strong></div></div>`,
    )
    .join("")}`;
}
function banner() {
  return `<div class="demo-note">Interactive synthetic sandbox · Guided investigator · No live model calls or external business effects</div>`;
}
function shell(content) {
  const name = config.project;
  return `<div class="shell"><aside class="sidebar"><a class="brand" href="/demo" data-go="/demo"><span class="brand-mark">${name[0]}</span>${name}</a><div class="sidebar-caption">OPERATIONS WORKSPACE</div><nav class="nav"><a href="/demo" data-go="/demo">New investigation</a><a href="/demo#history" data-go="/demo#history">Investigation history</a><a href="${isRelay() ? "/architecture" : "/metrics"}">${isRelay() ? "Architecture" : "Metric reference"}</a><a href="/demo/recording" data-go="/demo/recording">Watch recorded demo</a><a href="https://github.com/Akhilesh-Vangala/${name.toLowerCase()}" target="_blank" rel="noreferrer">GitHub + recordings ↗</a></nav><p class="sidebar-note">Reports stay in this browser session. Download evidence to keep a copy.<br><br>Private Docker deployments support the durable worker and full integration workflows.</p></aside><main class="workspace"><header class="topbar"><span>Workspace / ${location.pathname.includes("/runs/") ? "Investigation" : "Overview"}</span><span class="pill">Interactive demo</span></header>${banner()}${content}<footer class="footer">${name} · Original synthetic fixtures · Explicit verification and review</footer></main></div>`;
}
function statusUI() {
  return `${busy ? `<div class="progress" role="status">${esc(busy)}</div>` : ""}${error ? `<div class="error" role="alert">${esc(error)}</div>` : ""}`;
}
function home() {
  const relay = isRelay();
  return `<div class="heading"><div class="eyebrow">${relay ? "EVIDENCE TO VERIFIED ACTION" : "METRIC INCIDENT TO VERIFIED REPAIR"}</div><h1>${relay ? "Resolve the exception.<br>Check every effect." : "Investigate the mismatch.<br>Verify the repair."}</h1><p class="muted">${relay ? "Inspect an operational case, review a grounded proposal and execute the approved actions in an isolated sandbox." : "Run an investigation, inspect its source evidence and test the proposed SQL against independent regression snapshots."}</p></div><div class="stats"><div><span>Runnable cases</span><strong>${config.cases.length.toString().padStart(2, "0")}</strong></div><div><span>Your investigations</span><strong>${records().length.toString().padStart(2, "0")}</strong></div><div><span>Execution</span><strong class="word">${relay ? "Isolated effects" : "Guarded SQL"}</strong></div></div><div class="grid"><section><div class="card"><h2>Start a working investigation</h2><form id="start-form"><label for="case">Choose a synthetic case</label><select id="case" ${busy ? "disabled" : ""}>${config.cases.map((c) => `<option value="${esc(c.id)}" ${c.id === selectedCase ? "selected" : ""}>${esc(c.title)}</option>`).join("")}</select><p class="muted">${esc(config.cases.find((c) => c.id === selectedCase)?.description)}</p><button ${busy ? "disabled" : ""}>${busy ? "Investigation running…" : "Investigate case ↗"}</button></form>${statusUI()}</div><div class="card"><div class="eyebrow">EXPLORE THE CASES</div><h2>Different outcomes, same controls.</h2><div class="case-list">${config.cases.map((c) => `<button class="case-option" data-case="${esc(c.id)}" ${busy ? "disabled" : ""}><strong>${esc(c.title)}</strong><span>${esc(c.description)}</span></button>`).join("")}</div></div></section><aside><div class="card"><div class="eyebrow">THE WORKING JOURNEY</div><h2>${relay ? "From discrepancy to verified resolution." : "Evidence before acceptance."}</h2><ol class="flow">${(relay
    ? [
        ["Observe", "Read procurement, warehouse, billing and case records."],
        ["Propose", "Validate the exact action amounts and source version."],
        [
          "Simulate",
          "Execute on a private fixture copy and independently check effects.",
        ],
        [
          "Review + act",
          "Approve, execute and inspect confirmed receipts. Test acknowledgment loss and reconciliation.",
        ],
      ]
    : [
        [
          "Investigate",
          "Run the fixed diagnostic through bounded evidence tools.",
        ],
        [
          "Verify",
          "Replay source evidence and compare SQL outputs against independent references.",
        ],
        [
          "Challenge",
          "Edit the candidate SQL. Incorrect or unsafe repairs do not pass.",
        ],
        [
          "Review + export",
          "Record a version-bound sandbox decision and download the evidence.",
        ],
      ]
  )
    .map(([a, b]) => `<li><div><strong>${a}</strong><p>${b}</p></div></li>`)
    .join(
      "",
    )}</ol></div><div class="card"><h3>What this demo establishes</h3><p class="muted">These actions execute the existing ${relay ? "planner, policy, simulator and fixture executor" : "investigator, guarded query tools and independent verifier"} on the server. The guided mode is deterministic. Live model quality and persistent cloud operation are evaluated separately.</p></div></aside></div>`;
}
function historyPage() {
  return `<div class="heading"><div class="eyebrow">THIS BROWSER SESSION</div><h1>Investigation history</h1><p class="muted">Open a retained report, inspect its evidence or download a copy.</p></div><section class="card"><div class="section-heading"><h2>Your reports</h2><a class="button" href="/demo" data-go="/demo">New investigation ↗</a></div>${
    records().length
      ? records()
          .map(
            (r) =>
              `<a class="history-row" href="/demo/runs/${esc(r.id)}" data-go="/demo/runs/${esc(r.id)}"><div><strong>${esc(r.title)}</strong><small>${esc(new Date(r.viewed_at).toLocaleString())} · ${esc(r.id.slice(0, 8))}</small></div><span class="pill">${esc(r.stage)}</span></a>`,
          )
          .join("")
      : `<div class="empty">No investigations in this browser yet. Run a case to create a report.</div>`
  }</section>`;
}
function relayControls(r) {
  if (!r.plan.actions.length)
    return `<div class="callout">${r.plan.outcome === "needs_information" ? "Additional authoritative evidence is needed. No business actions were proposed." : "The case needs no business change. Source records are preserved."}</div>`;
  if (r.stage === "assessed")
    return `<div class="toolbar"><button data-action="approve" ${busy ? "disabled" : ""}>Approve sandbox proposal</button><button class="secondary" data-action="reject" ${busy ? "disabled" : ""}>Reject proposal</button></div>`;
  if (r.stage === "approved")
    return `<div class="review-summary">This exact proposal was approved in your sandbox branch.</div><div class="toolbar"><button data-action="execute" ${busy ? "disabled" : ""}>Execute approved actions</button><button class="secondary" data-action="lost-ack" ${busy ? "disabled" : ""}>Test lost acknowledgment</button></div>`;
  if (r.stage === "uncertain")
    return `<div class="callout notice"><strong>Acknowledgment uncertain.</strong> The hold may already have applied. Reconcile its observed state before continuing.</div><button data-action="reconcile" ${busy ? "disabled" : ""}>Reconcile and complete</button>`;
  return `<div class="review-summary">${r.stage === "executed" ? "Sandbox effects verified. Inspect the execution checks and receipts." : "Proposal rejected. This branch cannot execute actions."}</div>`;
}
function money(cents) {
  return (cents / 100).toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
  });
}
function relayResult(r) {
  const labels = {
    hold_invoice: "Hold disputed invoice amount",
    open_supplier_claim: "Open supplier shortage claim",
    reserve_replacement: "Reserve replacement stock",
    resolve_case: "Resolve the case",
  };
  return `<div class="eyebrow">${r.stage === "executed" ? "EXECUTED SANDBOX RESULT" : "CHECKED PROPOSAL"}</div><h2>${r.stage === "executed" ? "The sandbox case is resolved and verified." : r.stage === "uncertain" ? "An action needs reconciliation." : r.plan.outcome === "resolve" ? "A scoped resolution is ready for review." : r.plan.outcome === "no_change" ? "No change is required." : "Clarification is required before acting."}</h2><p class="muted">${esc(r.plan.explanation)}</p><div class="steps-summary"><div><div class="state-label">Confirmed shortage</div><div class="effect-number">${r.before.procurement.ordered_units - r.before.warehouse.received_units} units</div></div><div><div class="state-label">Current sandbox hold</div><div class="effect-number">${money(r.after.billing.held_cents)}</div></div></div><h3>Proposed business actions</h3>${table(
    ["Action", "Amount"],
    r.plan.actions.map((a) => [
      labels[a.kind],
      a.kind === "hold_invoice"
        ? money(a.amount)
        : a.kind === "resolve_case"
          ? "Resolved"
          : a.amount + " units",
    ]),
  )}<h3>Explicit sandbox review</h3>${relayControls(r)}<div class="callout">Only this synthetic fixture can change. Request replay rebuilds an isolated simulation; it does not resend an external supplier or financial action.</div>`;
}
function verifyTotal(result, r) {
  if (!result?.rows) return "No output";
  const values = result.rows.map((row) => row[row.length - 1]);
  if (values.some((v) => typeof v !== "number"))
    return result.rows.length + " rows";
  const n = values.reduce((a, b) => a + b, 0);
  return r.contract.output.includes("revenue_cents")
    ? money(n)
    : n.toLocaleString();
}
function verifyResult(r) {
  const passed = r.grading.passed;
  return `<div class="eyebrow">${passed ? "INDEPENDENTLY CHECKED FINDING" : "REPAIR DID NOT PASS"}</div><h2>${r.decision.status === "needs_information" ? "The source needs authoritative clarification." : r.decision.status === "no_change" ? "The current transformation needs no change." : passed ? "A candidate repair passes the regression checks." : "The candidate does not satisfy the reporting contract."}</h2><p class="muted">${esc(r.decision.explanation)}</p>${r.decision.required_fields ? `<div class="callout">Required evidence: ${esc(r.decision.required_fields.join(", "))}. Affected IDs: ${esc((r.decision.affected_ids || []).join(", "))}.</div>` : ""}<div class="steps-summary"><div><div class="state-label">Current output total</div><div class="effect-number">${verifyTotal(r.before, r)}</div></div><div><div class="state-label">Candidate output total</div><div class="effect-number">${verifyTotal(r.after, r)}</div></div></div><h3>Candidate output</h3>${r.after ? table(r.after.columns, r.after.rows) : `<p class="muted">No complete candidate output is available for this finding.</p>`}<h3>Version-bound sandbox decision</h3>${r.stage === "assessed" ? `<div class="toolbar"><button data-action="approve" ${busy || !passed ? "disabled" : ""}>Accept verified finding</button><button class="secondary" data-action="reject" ${busy ? "disabled" : ""}>Reject finding</button></div>` : `<div class="review-summary">This browser branch recorded: ${esc(r.stage)}.</div>`}<div class="callout">Acceptance records a sandbox decision. It does not write to a customer warehouse or merge a repository patch.</div>`;
}
function evidence(r) {
  const values = isRelay() ? r.evidence : r.evidence.filter((x) => x.ok);
  return `<h2>Executed source evidence</h2><p class="muted">${values.length} retained ${isRelay() ? "system observations" : "tool results"}. Inspect the data behind the proposal.</p>${values.map((v, i) => `<details ${i === 0 ? "open" : ""}><summary>${esc(isRelay() ? v.system : v.method)} · ${esc(v.evidence_id?.slice(0, 12))}</summary>${json(isRelay() ? v.data : v.result)}</details>`).join("")}`;
}
function verification(r) {
  if (isRelay())
    return `<h2>Independent state checks</h2>${checks(r.simulation.checks, "Counterfactual fixture simulation")}${r.execution ? checks(r.execution.checks, "Actual sandbox execution") : ""}${r.execution?.same_request_retry_no_duplicates ? `<div class="callout">A repeated execute call inside the same fixture request produced no duplicate effects.</div>` : ""}${r.execution?.reconciled_receipts ? `<div class="callout">${r.execution.reconciled_receipts} uncertain receipt reconciled against observed state before completion.</div>` : ""}<h3>Action receipts</h3>${
      r.receipts.length
        ? table(
            ["Action index", "Status"],
            r.receipts.map((v) => [v.action_index, v.status]),
          )
        : `<p class="muted">No action has been applied in the current response.</p>`
    }<h3>Business state before and after</h3><details><summary>Original fixture</summary>${json(r.before)}</details><details><summary>Current fixture</summary>${json(r.after)}</details>`;
  return `<h2>Independent regression checks</h2><p class="muted">${esc(r.grading.reason)}</p>${(r.grading.checks || []).map((c) => `<div class="check-row"><span class="pill">${c.passed ? "PASS" : "REVIEW"}</span><div><strong>${esc(c.snapshot_id)}</strong><p>Candidate output compared with an independent source calculation.</p></div></div>`).join("")}${r.decision.status === "needs_information" ? `<div class="callout">The check establishes that the investigator requested the required authoritative information, not that a repair exists.</div>` : ""}<h3>Reporting contract</h3>${json(r.contract)}<h3>Rejected tool feedback</h3>${r.evidence.some((e) => !e.ok) ? json(r.evidence.filter((e) => !e.ok)) : `<p class="muted">No rejected tool calls in this investigation.</p>`}`;
}
function sqlPanel(r) {
  return `<h2>Inspect and challenge the SQL</h2><h3>Current transformation</h3>${json(r.current_sql)}<label for="candidate-sql">Candidate SQL</label><textarea id="candidate-sql" rows="13" maxlength="6000" spellcheck="false">${esc(r.candidate_sql)}</textarea><div class="toolbar"><button data-action="verify" ${busy ? "disabled" : ""}>Verify edited SQL</button></div><p class="muted">Edits create a new report. Read-only query limits and independent regression checks still apply. Failed candidates cannot be accepted.</p>`;
}
function detail(r) {
  if (!r)
    return `<div class="heading"><h1>Report unavailable in this browser.</h1><p class="muted">Public demo history stays in the browser session that ran the investigation.</p><a class="button" href="/demo" data-go="/demo">Start a new investigation</a></div>`;
  const relay = isRelay(),
    tabs = relay
      ? [
          ["result", "Proposal + action"],
          ["evidence", "Source evidence"],
          ["checks", "Verification"],
          ["activity", "Activity"],
        ]
      : [
          ["result", "Finding"],
          ["evidence", "Source evidence"],
          ["sql", "SQL + revision"],
          ["checks", "Verification"],
          ["activity", "Activity"],
        ];
  const calls = relay ? r.evidence.length : r.evidence.length;
  const passed = relay
    ? (r.execution?.passed ?? r.simulation.passed)
    : r.grading.passed;
  let panel =
    activeTab === "result"
      ? relay
        ? relayResult(r)
        : verifyResult(r)
      : activeTab === "evidence"
        ? evidence(r)
        : activeTab === "checks"
          ? verification(r)
          : activeTab === "sql"
            ? sqlPanel(r)
            : `<h2>Executed activity</h2>${relay ? json({ graph: r.activity, events: r.events }) : json(r.evidence.map((e) => ({ sequence: e.sequence, method: e.method, evidence_id: e.evidence_id, ok: e.ok })))}`;
  return `<div class="heading"><a class="back" href="/demo#history" data-go="/demo#history">← Investigations</a><div class="eyebrow">INVESTIGATION / ${esc(r.id.slice(0, 8))}</div><div class="section-heading"><h1>${esc(r.title)}</h1><span class="pill">${esc(r.stage.replaceAll("_", " "))}</span></div><p class="muted">${esc(r.mode)} · ${relay ? "Four-system fixture" : "SQLite analytical sandbox"}</p></div><div class="stats"><div><span>Evidence results</span><strong>${calls}</strong></div><div><span>Outcome</span><strong class="word">${esc((relay ? r.plan.outcome : r.decision.status).replaceAll("_", " "))}</strong></div><div><span>${r.stage === "uncertain" ? "Execution acknowledgment" : "Verification"}</span><strong class="word">${r.stage === "uncertain" ? "Uncertain" : passed ? "Checks passed" : "Review required"}</strong></div></div><div class="grid"><section><div class="tabs">${tabs.map(([id, name]) => `<button data-tab="${id}" class="${activeTab === id ? "active" : ""}">${name}</button>`).join("")}</div><div class="card result-card">${panel}${statusUI()}</div></section><aside><div class="card"><div class="eyebrow">TRACEABLE RESULT</div><h3>Retain the evidence.</h3><p class="muted">The report includes the exact proposal, checks, source version and ${relay ? "sandbox receipts" : "executed evidence"}.</p><button class="secondary" data-action="export">Download report ↓</button><h3>${relay ? "Proposal version" : "Result version"}</h3><p class="checksum">${esc(r.version)}</p><small>Content version, not a customer-production attestation.</small></div><div class="card"><h3>Scope and persistence</h3><p class="muted">${esc(r.scope)}</p><a href="/demo" data-go="/demo">Start another case →</a></div></aside></div>`;
}
function recordingPage() {
  return `<div class="heading"><a class="back" href="/demo" data-go="/demo">← Workspace</a><div class="eyebrow">ACTUAL BROWSER WALKTHROUGH</div><h1>${config.project} in action.</h1><p class="muted">A continuous recording of the working synthetic application. Browser interactions are automated; no live model call, customer feedback or external business effect.</p></div><section class="card"><video class="walkthrough" controls preload="metadata" poster="/demo-assets/poster.png" src="/demo-assets/walkthrough.webm">Your browser does not support this video. Download the recording below.</video><div class="toolbar"><a class="button secondary" href="/demo-assets/walkthrough.webm" download>Download continuous recording ↓</a><a class="button" href="/demo" data-go="/demo">Run it yourself ↗</a></div></section>`;
}
function render() {
  if (!config) return;
  document.title = config.project + " · Interactive workspace";
  let content;
  if (location.pathname === "/demo/recording") content = recordingPage();
  else if (location.pathname.startsWith("/demo/runs/"))
    content = detail(current());
  else content = location.hash === "#history" ? historyPage() : home();
  app.innerHTML = shell(content);
}
function download(run) {
  const value = { ...run };
  delete value.token;
  delete value.viewed_at;
  const url = URL.createObjectURL(
    new Blob(
      [
        JSON.stringify(
          {
            format: config.project.toLowerCase() + "-sandbox-report-v1",
            exported_at: new Date().toISOString(),
            report: value,
          },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    ),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = config.project.toLowerCase() + "-" + run.id + ".json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
document.addEventListener("change", (event) => {
  if (event.target.id === "case") {
    selectedCase = event.target.value;
    render();
  }
});
document.addEventListener("submit", (event) => {
  if (event.target.id === "start-form") {
    event.preventDefault();
    if (!busy)
      perform("Reading sources and checking the proposal…", "investigate", {
        case_id: document.querySelector("#case").value,
      });
  }
});
document.addEventListener("click", (event) => {
  const target = event.target.closest(
    "[data-go],[data-case],[data-tab],[data-action]",
  );
  if (!target) return;
  if (target.hasAttribute("data-go")) {
    event.preventDefault();
    go(target.dataset.go);
    return;
  }
  if (target.hasAttribute("data-case")) {
    selectedCase = target.dataset.case;
    render();
    document.querySelector("#case")?.focus();
    return;
  }
  if (target.hasAttribute("data-tab")) {
    activeTab = target.dataset.tab;
    render();
    return;
  }
  const action = target.dataset.action,
    r = current();
  if (!r || busy) return;
  if (action === "export") {
    download(r);
    return;
  }
  const token = r.token;
  if (action === "approve" || action === "reject")
    perform(
      "Checking this exact result and recording your decision…",
      "review",
      { token, action },
    );
  else if (action === "execute" || action === "lost-ack")
    perform(
      "Applying approved actions and checking the resulting fixture…",
      "execute",
      {
        token,
        failure_mode: action === "lost-ack" ? "acknowledgment_loss" : "none",
      },
    );
  else if (action === "reconcile")
    perform(
      "Reconciling the uncertain receipt and completing verified actions…",
      "reconcile",
      { token },
    );
  else if (action === "verify")
    perform(
      "Executing the revised query and independent regression checks…",
      "verify",
      { token, candidate_sql: document.querySelector("#candidate-sql").value },
    );
});
window.addEventListener("popstate", () => {
  activeTab = "result";
  error = "";
  render();
});
fetch("/api/demo/config", { credentials: "same-origin" })
  .then(async (response) => {
    if (!response.ok)
      throw new Error("The interactive workspace is unavailable.");
    config = await response.json();
    selectedCase = config.cases[0].id;
    const chosen = new URLSearchParams(location.search).get("case");
    if (config.cases.some((c) => c.id === chosen)) selectedCase = chosen;
    render();
  })
  .catch((e) => {
    app.innerHTML = `<div class="loading"><h1>Unable to open the workspace</h1><p>${esc(e.message)}</p><a href="/demo">Reload the demo</a></div>`;
  });
