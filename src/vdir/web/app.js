"use strict";
const $ = (id) => document.getElementById(id);
let accessCode = "",
  cases = [],
  jobs = [],
  selected = null,
  current = null;
let configuration = null, selectedMetric = null, metricRequest = 0, metricRendered = "", setupReturnPath = "/", workflowReturnPath = "/workflows";
let spendStatus = null;
const tabPaths = {"Summary": "", "Evidence": "/evidence", "SQL & review": "/sql", "Agent activity": "/activity", "Metric definition": "/definition"};
let activeView = "home", returnPath = "/investigations", homeRendered = "", configured = false, refreshing = false;
let workflows = [], selectedWorkflow = null, workflowRendered = "", cancelTarget = null;
let activeTab = "Summary",
  rendered = "",
  historyRendered = "",
  tableRendered = "",
  busy = false,
  toastTimer;
const labels = {
  candidate: "Repair proposed",
  needs_information: "Needs information",
  no_change: "No change",
  unsupported: "Unsupported",
};
function node(tag, attrs = {}, ...children) {
  const value = document.createElement(tag);
  for (const [key, item] of Object.entries(attrs)) {
    if (key.startsWith("on")) value.addEventListener(key.slice(2), item);
    else if (key === "className") value.className = item;
    else if (key === "value") value.value = item;
    else if (key === "disabled") value.disabled = item;
    else value.setAttribute(key, item);
  }
  for (const child of children.flat())
    if (child !== null && child !== undefined)
      value.append(
        child instanceof Node ? child : document.createTextNode(String(child)),
      );
  return value;
}
function notify(message, error = false) {
  $("toast").textContent = message;
  $("toast").className = "toast" + (error ? " error" : "");
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("toast").hidden = true), 5500);
}
async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (accessCode) headers.Authorization = "Bearer " + accessCode;
  if (options.body) headers["Content-Type"] = "application/json";
  const response = await fetch("/api" + path, { ...options, headers });
  if (response.status === 401) {
    if (!$("auth-dialog").open) $("auth-dialog").showModal();
    throw new Error("Operator access code required");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "The request could not be completed",
    );
  }
  return options.download ? response.blob() : response.json();
}
const badge = (text, tone = "") =>
  node("span", { className: "badge " + tone }, text);
function outcome(job) {
  if (job.status === "cancelled") return {text: "Cancelled", tone: ""};
  if (job.status === "cancelling") return {text: "Cancelling", tone: "wait"};
  if (job.status === "paused")
    return { text: "Awaiting guidance", tone: "wait" };
  if (job.status !== "completed")
    return {
      text: job.status.replaceAll("_", " "),
      tone:
        job.status === "failed" || job.status === "interrupted"
          ? "bad"
          : "wait",
    };
  const result = job.result
    ? {
        status: job.result.response.decision.status,
        passed: job.result.grading.passed,
      }
    : job.outcome;
  if (!result.passed) return { text: "Verification failed", tone: "bad" };
  return {
    text: labels[result.status] || result.status,
    tone: result.status === "needs_information" ? "wait" : "good",
  };
}
function title(caseId) {
  return cases.find((item) => item.id === caseId)?.title || caseId;
}
function time(value) {
  return new Date(value * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}
function dateTime(value) {
  return new Date(value * 1000).toLocaleString([], {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}
function mode(job) {
  if (job.request.kind === "verification") return "SQL revision";
  if (job.request.investigator === "langgraph") return "Checkpointed AI";
  if (job.request.investigator === "anthropic") return "Hosted AI";
  return "Rule-based workflow";
}
const views = ["home", "investigations", "runs", "detail", "workflows", "new-investigation", "new-workflow", "metrics", "metric", "settings", "not-found"];
const pageTitles = {home: "Workspace overview", investigations: "Investigations", runs: "Run history", detail: "Investigation", workflows: "Workflows", "new-investigation": "New investigation", "new-workflow": "New workflow", metrics: "Metrics", metric: "Metric definition", settings: "Workspace settings", "not-found": "Page not found"};
function showView(view) {
  activeView = view;
  for (const name of views) $(name + "-view").hidden = name !== view;
  const nested = ["detail", "metric", "new-investigation", "new-workflow"].includes(view) || view === "workflows" && selectedWorkflow;
  $("workspace-stats").hidden = view !== "home";
  $("page-navigation").hidden = !nested;
  $("page-actions").hidden = ["new-investigation", "new-workflow", "not-found"].includes(view);
  $("page-eyebrow").hidden = nested;
  $("page-title").textContent = view === "workflows" && selectedWorkflow ? "Workflow details" : pageTitles[view];
  document.title = "VDIR — " + $("page-title").textContent;
  $("breadcrumb-view").textContent = $("page-title").textContent;
  const parent = view === "detail" || view === "new-investigation" ? ["Investigations", "/investigations"] : view === "metric" ? ["Metrics", "/metrics"] : view === "new-workflow" || selectedWorkflow ? ["Workflows", "/workflows"] : null;
  $("breadcrumb-parent").hidden = !parent; $("breadcrumb-separator").hidden = !parent;
  if (parent) { $("breadcrumb-parent").textContent = parent[0]; $("breadcrumb-parent").href = parent[1]; }
  $("page-description").textContent = {home: "From metric discrepancy to a verified, reviewable repair.", investigations: "Find a run and open its complete evidence and review record.", runs: "Review recent investigation outcomes and their recorded versions.", detail: "Inspect evidence, verification and operator review.", workflows: selectedWorkflow ? "Review each metric outcome and manage remaining work." : "Named metric reviews, individual outcomes and visible exceptions.", "new-investigation": "Choose a metric, method and analytical engine for a new run.", "new-workflow": "Select the metrics to investigate in a single bounded review.", metrics: "Browse reporting definitions, source schemas and current SQL.", metric: "Understand the reporting contract before starting an investigation.", settings: "Actual workspace configuration, available methods and review behavior.", "not-found": "This workspace route is not available."}[view];
  const navView = {detail: "investigations", "new-investigation": "investigations", "new-workflow": "workflows", metric: "metrics"}[view] || view;
  document.querySelectorAll("a[data-view]").forEach(link => {
    const active = link.dataset.view === navView;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  });
  $("workflow-list-panel").hidden = Boolean(selectedWorkflow);
  $("workflow-detail").hidden = !selectedWorkflow;
  $("workflows-view").classList.toggle("workflow-detail-page", Boolean(selectedWorkflow));
  if (view === "settings" && configuration) api("/spend").then(value => {spendStatus = value; renderSettings();}).catch(() => {spendStatus = null; renderSettings();});
}
function allowedReturn(path) {
  return ["/", "/runs", "/investigations", "/workflows", "/metrics", "/settings"].includes(path) || /^\/(workflows\/[a-f0-9]{32}|metrics\/case-\d{3})$/.test(path || "");
}
function route(focus = false) {
  const legacy = new URLSearchParams(location.search).get("job");
  const match = location.pathname.match(/^\/investigations\/([a-f0-9]{32})(\/(evidence|sql|activity|definition))?$/);
  const workflowMatch = location.pathname.match(/^\/workflows\/([a-f0-9]{32})$/);
  const metricMatch = location.pathname.match(/^\/metrics\/(case-\d{3})$/);
  selectedWorkflow = workflowMatch?.[1] || null;
  if (selectedMetric !== (metricMatch?.[1] || null)) metricRendered = "";
  selectedMetric = metricMatch?.[1] || null;
  const id = match?.[1] || (legacy && /^[a-f0-9]{32}$/.test(legacy) ? legacy : null);
  if (legacy && id) history.replaceState(history.state, "", "/investigations/" + id);
  const pages = {"/": "home", "/investigations": "investigations", "/investigations/new": "new-investigation", "/runs": "runs", "/workflows": "workflows", "/workflows/new": "new-workflow", "/metrics": "metrics", "/settings": "settings"};
  let view = id ? "detail" : workflowMatch ? "workflows" : metricMatch ? "metric" : pages[location.pathname] || "not-found";
  if (["#runs", "#investigations"].includes(location.hash)) { view = location.hash.slice(1); history.replaceState(history.state, "", "/" + view); }
  if (id !== selected) {
    selected = id; current = null; rendered = "";
    $("run-context").replaceChildren();
    $("detail").replaceChildren(node("div", {className: "empty-detail", role: "status"}, node("h2", {}, "Loading investigation…")));
  }
  activeTab = Object.keys(tabPaths).find(tab => tabPaths[tab] === (match?.[2] || "")) || "Summary";
  if (view === "detail") {
    returnPath = allowedReturn(history.state?.returnPath) ? history.state.returnPath : "/investigations";
    $("back-button").textContent = "← Back to " + ({"/": "home", "/runs": "run history", "/investigations": "investigations"}[returnPath] || (returnPath.startsWith("/metrics") ? "metric" : "workflow"));
    $("page-context").textContent = activeTab === "Summary" ? "INVESTIGATION RECORD" : activeTab.toUpperCase();
  } else if (["new-investigation", "new-workflow"].includes(view)) {
    setupReturnPath = allowedReturn(history.state?.returnPath) ? history.state.returnPath : view === "new-investigation" ? "/investigations" : "/workflows";
    $("back-button").textContent = "← Back to " + (setupReturnPath === "/" ? "home" : setupReturnPath.startsWith("/metrics") ? "metric" : setupReturnPath.startsWith("/workflows") ? "workflows" : "investigations");
    $("page-context").textContent = "RUN SETUP";
    const preselected = new URLSearchParams(location.search).get("metric");
    if (view === "new-investigation" && cases.some(item => item.id === preselected)) { $("incident").value = preselected; $("incident").dispatchEvent(new Event("change")); }
  } else if (view === "metric" || selectedWorkflow) {
    $("back-button").textContent = "← Back to " + (view === "metric" ? "metrics" : "workflows");
    $("page-context").textContent = view === "metric" ? "REPORTING DEFINITION" : "WORKFLOW RECORD";
  }
  showView(view); renderHistory(); renderWorkflows();
  if (view === "detail" && current) renderDetail(current);
  if (view === "metric") refreshMetric();
  if (focus) { $("page-title").focus({preventScroll: true}); window.scrollTo(0, 0); }
}
function navigate(path, state = {}) {
  if (location.pathname + location.search !== path) history.pushState(state, "", path);
  route(true);
  refreshDetail().catch(detailError);
  refreshWorkflow().catch(error => notify(error.message, true));
}
function detailError(error) {
  if (activeView !== "detail") return;
  rendered = ""; current = null;
  $("detail").replaceChildren(node("div", {className: "empty-detail", role: "alert"}, node("h2", {}, "Unable to load investigation"), node("p", {}, error.message), node("button", {className: "secondary", onclick: () => refreshDetail().catch(detailError)}, "Try again")));
}
function renderHome() {
  const fingerprint = JSON.stringify([jobs.slice(0, 5), cases]);
  if (homeRendered === fingerprint) return;
  homeRendered = fingerprint;
  $("home-recent").replaceChildren(...(jobs.length ? jobs.slice(0, 5).map(job => {
    const state = outcome(job);
    return node("button", {className: "home-run", onclick: () => select(job.id)},
      node("span", {className: "home-run-icon", "aria-hidden": "true"}, "↗"),
      node("span", {}, node("strong", {}, title(job.request.case_id)), node("small", {}, mode(job) + " · " + dateTime(job.created_at))), badge(state.text, state.tone));
  }) : [node("div", {className: "home-empty"}, node("span", {className: "empty-icon", "aria-hidden": "true"}, "+"), node("h3", {}, "Your first investigation starts here"), node("p", {}, "Choose a metric scenario to collect evidence and review its outcome."), node("button", {className: "secondary", onclick: openInvestigation}, "Choose a scenario"))]));
  $("scenario-cards").replaceChildren(...cases.map((item, index) => node("button", {className: "scenario-card", onclick: () => {
    $("incident").value = item.id; $("incident").dispatchEvent(new Event("change")); openInvestigation(item.id);
  }}, node("span", {className: "scenario-number"}, String(index + 1).padStart(2, "0")), node("span", {className: "scenario-title"}, item.title), node("span", {className: "scenario-copy"}, item.description), node("span", {className: "scenario-open"}, "Investigate scenario ↗"))));
}
function openInspector(kind, job = current) {
  if (!job) return;
  $("inspector-title").textContent = kind === "evidence" ? "Evidence explorer" : "Run details & audit";
  $("inspector-eyebrow").textContent = title(job.request.case_id) + " · " + job.id.slice(0, 8);
  $("inspector-content").replaceChildren(kind === "evidence" && job.result ? evidence(job)
    : node("div", {}, node("p", {className: "section-title"}, "RUN ID"), node("pre", {}, job.id), node("p", {className: "section-title"}, "RESULT VERSION"), node("pre", {}, job.result_version || "Not available yet"), node("p", {className: "section-title"}, "SOURCE VERSION"), node("pre", {}, job.request.input_version), node("p", {className: "section-title"}, "AUDIT EVENTS"), events(job)));
  $("inspector-dialog").showModal();
}
function renderContext(job) {
  const details = [["Investigator", mode(job)], ["Analytical engine", job.request.engine === "sqlite" ? "SQLite" : "DuckDB"], ["Created", dateTime(job.created_at)], ["Updated", dateTime(job.updated_at)]];
  const passed = job.result?.grading.passed;
  $("run-context").replaceChildren(node("div", {className: "context-card"}, node("h2", {}, "Run context"), node("dl", {className: "workspace-details"}, details.map(([label, value]) => node("div", {}, node("dt", {}, label), node("dd", {}, value))))),
    node("div", {className: "context-card"}, node("h2", {}, "Resolution progress"), node("ol", {className: "resolution-steps"},
      node("li", {}, node("strong", {}, "01 · Investigation"), node("span", {}, job.result ? "Finding recorded" : job.status)),
      node("li", {}, node("strong", {}, "02 · Independent verification"), node("span", {}, job.result ? passed ? "Available checks passed" : "Checks failed" : "Awaiting result")),
      node("li", {}, node("strong", {}, "03 · Operator review"), node("span", {}, job.review ? "Review " + job.review.action : "No decision recorded"))),
      node("p", {className: "notice"}, "Approval records a decision. Production execution is not connected.")),
    node("div", {className: "context-card context-actions"}, node("button", {className: "secondary", onclick: () => openInspector("evidence", job), disabled: !job.result}, "Open evidence explorer"), node("button", {className: "secondary", onclick: () => openInspector("audit", job)}, "Run details & audit"), job.request.parent_id ? node("button", {className: "text-button", onclick: () => select(job.request.parent_id)}, "← Open parent investigation") : null));
  if (["queued", "running", "cancelling"].includes(job.status)) $("run-context").append(node("div", {className: "context-card"}, node("button", {className: "secondary danger", disabled: job.status === "cancelling", onclick: () => openCancellation("jobs", job.id, title(job.request.case_id))}, job.status === "cancelling" ? "Cancellation requested" : "Cancel run")));
}
function renderCommands() {
  const query = $("command-search").value.trim().toLowerCase();
  const pages = [{title: "Home", path: "/"}, {title: "Investigations", path: "/investigations"}, {title: "New investigation", path: "/investigations/new"}, {title: "Run history", path: "/runs"}, {title: "Workflows", path: "/workflows"}, {title: "New workflow", path: "/workflows/new"}, {title: "Metrics", path: "/metrics"}, {title: "Settings", path: "/settings"}].filter(item => item.title.toLowerCase().includes(query));
  const found = jobs.filter(job => (title(job.request.case_id) + " " + job.id).toLowerCase().includes(query)).slice(0, 10);
  $("command-results").replaceChildren(...pages.map(item => node("button", {className: "command-result", onclick: () => { $("command-dialog").close(); navigate(item.path); }}, node("span", {}, item.title), node("small", {}, "Page →"))),
    ...found.map(job => node("button", {className: "command-result", onclick: () => { $("command-dialog").close(); select(job.id); }}, node("span", {}, title(job.request.case_id), node("small", {}, job.id.slice(0, 8) + " · " + mode(job))), badge(outcome(job).text))),
    ...(!pages.length && !found.length ? [node("p", {className: "notice"}, "No matching pages or recent runs.")] : []));
}
function openCommands() { $("command-search").value = ""; renderCommands(); $("command-dialog").showModal(); $("command-search").focus(); }
function openCancellation(kind, id, name) {
  cancelTarget = {kind, id};
  $("cancel-title").textContent = kind === "workflows" ? "Cancel remaining workflow work" : "Cancel investigation";
  $("cancel-description").textContent = name + ": queued work will stop immediately; active local execution will be stopped by the worker.";
  $("cancel-reason").value = "";
  $("cancel-dialog").showModal();
}
function renderWorkflows() {
  $("workflow-count").textContent = workflows.length;
  const fingerprint = JSON.stringify([workflows, selectedWorkflow, cases]);
  if (fingerprint === workflowRendered) return;
  workflowRendered = fingerprint;
  $("workflow-list").replaceChildren(...(workflows.length ? workflows.map(flow => node("button", {className: "workflow-card" + (flow.id === selectedWorkflow ? " selected" : ""), onclick: () => navigate("/workflows/" + flow.id)},
    node("strong", {}, flow.name), node("span", {}, badge(flow.status.replaceAll("_", " "), flow.counts.attention ? "wait" : "")),
    node("small", {}, `${flow.counts.terminal}/${flow.counts.total} runs finished · ${dateTime(flow.created_at)}`)))
    : [node("p", {className: "empty-workflows"}, "No workflows yet. Select Run workflow to group metric investigations.")]));
  const selectedFlow = workflows.find(flow => flow.id === selectedWorkflow);
  if (selectedFlow) renderWorkflowDetail(selectedFlow);
  else $("workflow-detail").replaceChildren(node("div", {className: "home-card workflow-empty"}, node("div", {className: "empty-icon", "aria-hidden": "true"}, "≡"), node("h2", {}, selectedWorkflow ? "Loading workflow…" : "A complete metric review, in one place"), node("p", {}, "Select a workflow to inspect each investigation, or create a bounded set of metric checks."), node("button", {className: "primary", onclick: openWorkflow}, "Create workflow")));
}
function renderWorkflowDetail(flow) {
  const counts = flow.counts;
  $("workflow-detail").replaceChildren(node("section", {className: "home-card"},
    node("div", {className: "workflow-header"}, node("div", {}, node("p", {className: "eyebrow"}, "MULTI-METRIC INVESTIGATION"), node("h2", {}, flow.name), node("p", {className: "notice"}, dateTime(flow.created_at) + " · " + flow.engine + " · " + flow.investigator)), badge(flow.status.replaceAll("_", " "))),
    node("div", {className: "workflow-metrics"}, [["Investigations", counts.total], ["Resolved by checks", counts.resolved], ["Need attention", counts.attention], ["Cancelled", counts.cancelled]].map(([label, value]) => node("div", {}, node("strong", {}, value), node("span", {}, label)))),
    node("div", {className: "workflow-progress"}, node("label", {for: "workflow-progress"}, `${counts.terminal} of ${counts.total} runs finished`), node("progress", {id: "workflow-progress", value: counts.terminal, max: counts.total}, `${counts.terminal}/${counts.total}`)),
    node("div", {className: "workflow-members"}, flow.jobs.map((job, index) => {
      const state = outcome(job);
      return node("button", {className: "workflow-member", onclick: () => select(job.id)}, node("span", {className: "member-number"}, String(index + 1).padStart(2, "0")), node("span", {className: "member-title"}, node("strong", {}, title(job.request.case_id)), node("small", {}, job.id.slice(0, 8) + " · " + mode(job))), badge(state.text, state.tone), node("span", {"aria-hidden": "true"}, "↗"));
    })),
    node("div", {className: "workflow-footer"}, node("p", {className: "notice"}, "Resolved counts mean the recorded candidate or healthy transformation passed the available independent checks. Review and execution remain separate."),
      counts.running + counts.queued ? node("button", {className: "secondary danger", onclick: () => openCancellation("workflows", flow.id, flow.name)}, "Cancel remaining work") : null)));
}
async function refreshWorkflow() {
  if (!selectedWorkflow || activeView !== "workflows") return;
  const id = selectedWorkflow;
  let flow;
  try { flow = await api("/workflows/" + encodeURIComponent(id)); }
  catch (error) {
    if (selectedWorkflow === id && activeView === "workflows") $("workflow-detail").replaceChildren(node("div", {className: "home-card"}, node("h2", {}, "Workflow unavailable"), node("p", {className: "notice"}, error.message), node("button", {className: "secondary", onclick: () => refreshWorkflow().catch(error => notify(error.message, true))}, "Retry loading workflow")));
    return;
  }
  if (selectedWorkflow !== id || activeView !== "workflows") return;
  // Existing list renders cover the common recent-workflow case without stealing focus.
  if (!workflows.some(item => item.id === id)) renderWorkflowDetail(flow);
}
function renderMetrics() {
  const query = $("metric-search").value.trim().toLowerCase();
  const visible = cases.filter(item => (item.title + " " + item.metric + " " + item.description).toLowerCase().includes(query));
  $("metric-count").textContent = cases.length + " metrics";
  $("metric-catalog").replaceChildren(...(visible.length ? visible.map(item => node("a", {className: "metric-card", href: "/metrics/" + item.id, "data-route": ""},
    node("div", {className: "metric-card-top"}, badge("Sample metric"), node("span", {"aria-hidden": "true"}, "↗")),
    node("h2", {}, item.title), node("p", {}, item.description), node("code", {}, item.metric), node("span", {className: "metric-card-footer"}, "View definition & sources →")))
    : [node("div", {className: "home-card page-empty"}, node("h2", {}, "No matching metrics"), node("p", {}, "Try a different name or clear your search."))]));
}
function renderSettings() {
  if (!configuration) return;
  const available = configuration.hosted_available;
  const rows = [["Environment", "Development workspace"], ["Operator", configuration.operator], ["Default analytical engine", configuration.default_engine === "duckdb" ? "DuckDB" : "SQLite"], ["Rule-based investigation", "Available"], ["Hosted AI investigation", available ? "Configured; live evaluation pending" : "Not configured"], ["Checkpointed AI investigation", available ? "Configured; live evaluation pending" : "Not configured"], ["Metric scenarios", String(cases.length)]];
  if (spendStatus) {
    const money = value => "$" + Number(value).toFixed(2);
    rows.push(["AI allowance per run", money(spendStatus.run_limit_usd)], ["Shared AI allowance", money(spendStatus.total_limit_usd)], ["Accounted and reserved", money(spendStatus.accounted_usd)], ["Remaining allowance", money(spendStatus.remaining_usd)], ["Unresolved requests", String((spendStatus.states.unknown?.requests || 0) + (spendStatus.states.reserved?.requests || 0))]);
  }
  $("settings-configuration").replaceChildren(node("dl", {className: "settings-rows"}, rows.map(([label, value]) => node("div", {}, node("dt", {}, label), node("dd", {}, value)))), node("div", {className: "settings-note"}, "Configuration is read from the running service. Allowances cover this workspace's API requests; unresolved requests stay reserved and provider billing can differ. Model quality and cloud deployment are separate release checks."));
  $("settings-access").textContent = configuration.access_mode === "shared_operator" ? "A shared operator access code protects this service. Individual user accounts are not connected." : "Local loopback access on this machine. Individual user accounts are not connected.";
}
async function refreshMetric() {
  if (activeView !== "metric" || !selectedMetric || !configuration) return;
  const id = selectedMetric, sequence = ++metricRequest;
  if (metricRendered === id) return;
  $("metric-content").replaceChildren(node("div", {className: "home-card page-empty", role: "status"}, node("h2", {}, "Loading metric definition…")));
  try {
    const metric = await api("/incidents/" + encodeURIComponent(id));
    if (sequence !== metricRequest || selectedMetric !== id || activeView !== "metric") return;
    metricRendered = id;
    document.title = "VDIR — " + metric.title;
    $("metric-content").replaceChildren(node("div", {className: "metric-layout"},
      node("div", {className: "metric-main"},
        node("section", {className: "home-card metric-overview"}, node("div", {className: "metric-card-top"}, badge("Sample metric"), node("code", {}, metric.id)), node("h2", {}, metric.title), node("p", {}, metric.description), node("div", {className: "content-actions"}, node("button", {className: "primary", onclick: () => openInvestigation(metric.id)}, "Investigate this metric"))),
        node("section", {className: "home-card metric-section"}, node("h2", {}, "Reporting contract"), node("p", {className: "notice"}, "This authoritative development definition is the basis for independent checks."), node("pre", {}, JSON.stringify(metric.contract, null, 2))),
        node("section", {className: "home-card metric-section"}, node("h2", {}, "Current transformation"), node("p", {className: "notice"}, "Investigate this SQL before proposing a repair."), node("pre", {}, metric.current_sql))),
      node("aside", {className: "metric-sources"}, node("section", {className: "home-card metric-section"}, node("h2", {}, "Source tables"), ...Object.entries(metric.schema).map(([table, columns]) => node("details", {className: "schema-table"}, node("summary", {}, table, node("small", {}, columns.length + " columns")), node("pre", {}, columns.join("\n"))))),
        node("section", {className: "home-card metric-section"}, node("h2", {}, "Evidence version"), node("dl", {className: "workspace-details"}, node("div", {}, node("dt", {}, "Snapshot"), node("dd", {}, metric.snapshot_id))), node("code", {className: "version-value"}, metric.input_version), node("p", {className: "notice"}, "This page exposes the current public schema and definition. Private regression snapshots are not included.")))));
  } catch (error) {
    if (sequence !== metricRequest || selectedMetric !== id || activeView !== "metric") return;
    $("metric-content").replaceChildren(node("div", {className: "home-card page-empty", role: "alert"}, node("h2", {}, "Metric unavailable"), node("p", {}, error.message), node("button", {className: "secondary", onclick: refreshMetric}, "Retry loading metric")));
  }
}

function openInvestigation(metric = null) {
  const origin = ["new-investigation", "new-workflow"].includes(activeView) ? setupReturnPath : activeView === "detail" ? returnPath : location.pathname;
  navigate("/investigations/new" + (typeof metric === "string" ? "?metric=" + encodeURIComponent(metric) : ""), {returnPath: origin});
}
function openWorkflow() {
  const origin = ["new-investigation", "new-workflow"].includes(activeView) ? setupReturnPath : activeView === "detail" ? returnPath : location.pathname;
  navigate("/workflows/new", {returnPath: origin});
}
function emptyDetail() {
  $("detail").replaceChildren(
    node(
      "div",
      { className: "empty-detail" },
      node("div", { className: "empty-icon", "aria-hidden": "true" }, "≡"),
      node("h2", {}, "No investigation selected"),
      node(
        "p",
        {},
        "Select a run from the queue to inspect its evidence, or start a new investigation.",
      ),
      node(
        "button",
        { className: "secondary", onclick: openInvestigation },
        "Start an investigation",
      ),
    ),
  );
}
function renderHistory() {
  const query = $("history-search").value.trim().toLowerCase();
  const filter = $("history-filter").value;
  const fingerprint = JSON.stringify([jobs, selected, query, filter, cases]);
  if (fingerprint === historyRendered) return;
  historyRendered = fingerprint;
  const visible = jobs.filter((job) => {
    const state = outcome(job);
    const matches = (title(job.request.case_id) + " " + job.id).toLowerCase().includes(query);
    const status = filter === "all"
      || (filter === "review" && job.outcome?.status === "candidate" && job.outcome?.passed)
      || (filter === "input" && ["Awaiting guidance", "Needs information"].includes(state.text))
      || (filter === "active" && ["queued", "running"].includes(job.status))
      || (filter === "failed" && state.tone === "bad");
    return matches && status;
  });
  $("run-count").textContent = visible.length;
  $("queue-scope").textContent = `${visible.length} of ${jobs.length} recent runs · latest 50`;
  $("job-list").replaceChildren(
    ...(visible.length
      ? visible.map((job) => {
          const state = outcome(job);
          return node(
            "button",
            {
              className: "run-row" + (job.id === selected ? " selected" : ""),
              onclick: () => select(job.id),
              "aria-label": title(job.request.case_id) + " " + state.text,
              "aria-pressed": String(job.id === selected),
            },
            node(
              "span",
              { className: "run-id" },
              job.id.slice(0, 8) + " · " + mode(job),
            ),
            node(
              "span",
              { className: "run-row-title" },
              title(job.request.case_id),
            ),
            node(
              "span",
              { className: "run-row-sub" },
              badge(state.text, state.tone),
              node("span", { title: dateTime(job.created_at) }, time(job.created_at)),
            ),
          );
        })
      : [
          node(
            "p",
            { className: "empty-history" },
            jobs.length ? "No runs match these filters." : "No investigations yet. Start a new run to collect evidence.",
          ),
        ]),
  );
}
function renderRunTable() {
  const query = $("runs-search").value.trim().toLowerCase();
  const fingerprint = JSON.stringify([jobs, query, cases]);
  if (fingerprint === tableRendered) return;
  tableRendered = fingerprint;
  const visible = jobs.filter((job) => (title(job.request.case_id) + " " + job.id).toLowerCase().includes(query));
  $("runs-table").replaceChildren(visible.length
    ? node("table", { className: "runs-table" },
        node("thead", {}, node("tr", {}, ["Investigation", "Method", "Outcome", "Created"].map((label) => node("th", { scope: "col" }, label)))),
        node("tbody", {}, visible.map((job) => {
          const state = outcome(job);
          return node("tr", {},
            node("td", {}, node("button", { className: "run-link", onclick: () => select(job.id) }, title(job.request.case_id), node("span", {}, job.id.slice(0, 8)))),
            node("td", { className: "muted" }, mode(job)),
            node("td", {}, badge(state.text, state.tone)),
            node("td", { className: "muted" }, dateTime(job.created_at)));
        })))
    : node("p", { className: "empty-history" }, jobs.length ? "No runs match your search." : "No investigation runs have been recorded."));
}
async function select(id) {
  const origin = activeView === "detail" ? returnPath : activeView === "new-investigation" ? setupReturnPath : location.pathname;
  history.pushState({returnPath: origin}, "", "/investigations/" + encodeURIComponent(id));
  route(true);
  await refreshDetail();
}
function checks(result) {
  const items = result.grading.checks || [];
  if (!items.length)
    return node("p", { className: "notice" }, result.grading.reason);
  return node(
    "table",
    { className: "checks" },
    node(
      "thead",
      {},
      node(
        "tr",
        {},
        node("th", {}, "Source snapshot"),
        node("th", {}, "Independent check"),
      ),
    ),
    node(
      "tbody",
      {},
      items.map((item) =>
        node(
          "tr",
          {},
          node("td", {}, item.snapshot_id),
          node(
            "td",
            { className: item.passed ? "check-mark" : "fail-mark" },
            item.passed ? "✓ Passed" : "✕ Failed",
          ),
        ),
      ),
    ),
  );
}
function events(job) {
  return node(
    "ul",
    { className: "event-list" },
    job.events.map((event) =>
      node(
        "li",
        {},
        node("span", {}, event.name.replaceAll("_", " ") + " · " + event.actor),
        node("time", {}, time(event.created_at)),
        event.payload?.reason ? node("p", {className: "audit-reason"}, event.payload.reason) : null,
      ),
    ),
  );
}
async function download(job) {
  try {
    const blob = await api("/jobs/" + job.id + "/report", { download: true });
    const url = URL.createObjectURL(blob);
    const link = node("a", {
      href: url,
      download: "investigation-" + job.id.slice(0, 8) + ".json",
    });
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    notify(error.message, true);
  }
}
function summary(job) {
  const result = job.result,
    decision = result.response.decision;
  const box = node("div", {
    className:
      "outcome-card " +
      (!result.grading.passed
        ? "bad"
        : decision.status === "needs_information"
          ? "wait"
          : ""),
  });
  if (!result.grading.passed)
    box.append(
      node("strong", {}, "This candidate did not pass verification"),
      node(
        "p",
        {},
        "Review the failed checks before preparing a new revision. Approval is blocked.",
      ),
    );
  else if (decision.status === "candidate")
    box.append(
      node("strong", {}, "Checked against independent source references"),
      node(
        "p",
        {},
        "The candidate passed the available scenario snapshots. Review the exact SQL before recording approval.",
      ),
    );
  else if (decision.status === "no_change")
    box.append(
      node("strong", {}, "The current transformation passes these checks"),
      node(
        "p",
        {},
        "No repair is proposed. The current SQL satisfies the declared metric contract on the available snapshots.",
      ),
    );
  else
    box.append(
      node("strong", {}, "Authoritative information is needed"),
      node(
        "p",
        {},
        "Affected records: " + (decision.affected_ids || []).join(", "),
      ),
      node(
        "p",
        {},
        "Required fields: " + (decision.required_fields || []).join(", "),
      ),
    );
  return node(
    "div",
    {},
    node("p", { className: "section-title" }, "INVESTIGATION FINDING"),
    node("p", { className: "diagnosis" }, decision.explanation),
    box,
    node("p", { className: "section-title" }, "VERIFICATION"),
    checks(result),
    node(
      "div",
      { className: "content-actions" },
      node(
        "button",
        { className: "secondary", onclick: () => download(job) },
        "Export report ↓",
      ),
      node(
        "button",
        {
          className: "secondary",
          onclick: () => {
            activeTab = "Evidence";
            renderDetail(job, true);
          },
        },
        "Inspect evidence →",
      ),
    ),
    node("details", { className: "audit-details" },
      node("summary", {}, "Audit trail & result version"),
      node("div", { className: "version" }, "Result version", node("code", {}, job.result_version)),
      events(job)),
  );
}
function evidence(job) {
  const references = new Set(job.result.response.decision.evidence_ids || []);
  return node(
    "div",
    {},
    node(
      "p",
      { className: "notice" },
      "Actual diagnostic calls, replayed against the source evidence. Cited records support the submitted decision.",
    ),
    job.result.response.trace.map((record) => {
      const body = node("div", { className: "evidence-body" });
      if (record.params.sql) body.append(node("pre", {}, record.params.sql));
      if (
        record.ok &&
        Array.isArray(record.result?.columns) &&
        Array.isArray(record.result?.rows)
      )
        body.append(
          node(
            "div",
            { className: "table-scroll" },
            node(
              "table",
              { className: "checks" },
              node(
                "thead",
                {},
                node(
                  "tr",
                  {},
                  record.result.columns.map((name) => node("th", {}, name)),
                ),
              ),
              node(
                "tbody",
                {},
                record.result.rows.map((row) =>
                  node(
                    "tr",
                    {},
                    row.map((value) =>
                      node("td", {}, value === null ? "NULL" : value),
                    ),
                  ),
                ),
              ),
            ),
          ),
        );
      else
        body.append(
          node(
            "pre",
            {},
            record.ok ? JSON.stringify(record.result, null, 2) : record.error,
          ),
        );
      if (record.ok && record.result?.truncated)
        body.append(
          node(
            "p",
            { className: "notice" },
            "Partial result: row or cell limits were reached. Narrow the query before drawing conclusions.",
          ),
        );
      return node(
        "details",
        { className: "evidence-item" },
        node(
          "summary",
          {},
          node(
            "span",
            { className: "evidence-seq" },
            String(record.sequence).padStart(2, "0"),
          ),
          node("span", { className: "evidence-name" }, record.method),
          references.has(record.evidence_id) ? badge("cited") : null,
          !record.ok ? badge("rejected", "bad") : null,
          node("span", { className: "evidence-id" }, record.evidence_id),
        ),
        body,
      );
    }),
  );
}
async function post(path, body, idempotent = false) {
  return api(path, {
    method: "POST",
    headers: idempotent ? { "Idempotency-Key": crypto.randomUUID() } : {},
    body: JSON.stringify(body),
  });
}
function agentActivity(job) {
  const workflow = job.result.response.agent_workflow;
  const body = node("div", {}, node("p", { className: "notice" },
    "Recorded investigation steps and public test plans. Public SQL prechecks cover execution and completeness; independent correctness checks remain in Summary."));
  if (workflow.plans.length) {
    body.append(node("p", { className: "section-title" }, "HYPOTHESIS PLANS"));
    for (const plan of workflow.plans) {
      body.append(node("details", { className: "workflow-plan" },
        node("summary", {}, "Plan " + plan.revision + " · " + plan.objective),
        node("div", { className: "evidence-body" },
          plan.hypotheses.map((hypothesis) => node("div", { className: "workflow-hypothesis" },
            node("p", {}, node("strong", {}, hypothesis.id + " · "), hypothesis.claim),
            node("p", { className: "notice" }, "Expected signal: " + hypothesis.expected_signal),
            node("pre", {}, hypothesis.test_sql))),
          node("p", { className: "notice" }, "Supporting evidence: " + plan.evidence_ids.join(", ")))));
    }
  } else body.append(node("p", { className: "notice" }, "No repair hypothesis plan was recorded for this outcome."));
  const assessment = workflow.public_precheck;
  if (workflow.findings?.length) {
    body.append(node("p", {className: "section-title"}, "FINDINGS LEDGER"), node("p", {className: "notice"}, "Model interpretations of executed hypothesis tests. These do not establish semantic correctness."));
    workflow.findings.forEach(finding => body.append(node("div", {className: "finding-card"}, node("div", {}, node("strong", {}, `Plan ${finding.plan_revision} · ${finding.hypothesis_id}`), badge(finding.assessment)), node("p", {}, finding.summary), node("code", {}, finding.evidence_ids.join(", ")))));
  }
  if (workflow.working_memory) body.append(node("details", {className: "memory-details"}, node("summary", {}, "Working memory & evidence index"), node("div", {className: "evidence-body"}, node("p", {className: "notice"}, workflow.working_memory.scope), node("pre", {}, JSON.stringify(workflow.working_memory.evidence_index, null, 2)))));
  body.append(node("div", { className: "outcome-card" },
    node("strong", {}, assessment.status === "passed" ? "Public SQL precheck passed"
      : assessment.status === "rejected" ? "Public SQL precheck rejected" : "No SQL precheck required"),
    node("p", {}, assessment.scope || "No SQL candidate was submitted."),
    assessment.evidence_id ? node("p", {}, "Evidence: " + assessment.evidence_id) : null));
  const stages = {model: "Model response", evidence: "Evidence tool", plan: "Hypothesis plan",
    decision: "Decision validation", precheck: "Public SQL precheck", feedback: "Correction feedback", clarification: "Operator guidance", findings: "Findings ledger"};
  body.append(node("p", { className: "section-title" }, "RECORDED ACTIVITY"),
    node("ol", { className: "workflow-timeline" }, workflow.activity.map((event) => node("li", {},
      node("div", { className: "workflow-event-head" },
        node("strong", {}, stages[event.stage] || event.stage),
        node("span", {}, "Round " + event.round)),
      node("p", {}, event.status.replaceAll("_", " ") + (event.tool ? " · " + event.tool : "")),
      event.evidence_id ? node("code", {}, event.evidence_id) : null,
      event.issues ? node("p", {}, event.issues.join(" ")) : null))),
    node("p", { className: "notice" }, "Decision corrections used: " + workflow.corrections + " of 2"));
  return body;
}
function sqlReview(job) {
  const result = job.result,
    decision = result.response.decision;
  const body = node(
    "div",
    {},
  );
  const original = node("div", {}, node("p", { className: "section-title" }, "CURRENT TRANSFORMATION"),
    node("pre", { className: "sql-block" }, result.current_sql));
  if (decision.status !== "candidate") {
    body.append(original);
    body.append(
      node(
        "p",
        { className: "notice" },
        "No repair candidate was proposed for this investigation.",
      ),
    );
    return body;
  }
  const editor = node("textarea", {
    className: "sql-editor",
    "aria-label": "Candidate SQL",
    spellcheck: "false",
    value: decision.candidate_sql,
  });
  const approve = node(
    "button",
    { className: "primary", disabled: !result.grading.passed || !!job.review },
    "Approve this version",
  );
  const reject = node(
    "button",
    { className: "secondary danger", disabled: !!job.review },
    "Reject candidate",
  );
  const hint = node(
    "p",
    { className: "notice" },
    "Approval records review only. No transformation is applied to a business system.",
  );
  const note = node("textarea", {
    rows: "2",
    "aria-label": "Review note",
    placeholder: "Add context for this review…",
    disabled: !!job.review,
  });
  const verify = node(
    "button",
    {
      className: "secondary verification-button",
      onclick: async () => {
        verify.disabled = true;
        try {
          const next = await post(
            "/jobs/" + job.id + "/candidates",
            { parent_version: job.result_version, candidate_sql: editor.value },
            true,
          );
          await select(next.id);
          await refresh();
          notify("Candidate revision queued for independent verification");
        } catch (error) {
          notify(error.message, true);
          verify.disabled = false;
        }
      },
    },
    "Verify candidate revision",
  );
  editor.addEventListener("input", () => {
    const edited = editor.value !== decision.candidate_sql;
    approve.disabled = edited || !result.grading.passed || !!job.review;
    reject.disabled = edited || !!job.review;
    hint.textContent = edited
      ? "This SQL has changed. Verify a new revision before reviewing it."
      : "Approval records review only. No transformation is applied to a business system.";
  });
  async function review(action) {
    approve.disabled = true;
    reject.disabled = true;
    try {
      current = await post("/jobs/" + job.id + "/review", {
        version: job.result_version,
        action,
        note: note.value,
      });
      renderDetail(current, true);
      notify("Review recorded for this exact result version");
    } catch (error) {
      notify(error.message, true);
      renderDetail(job, true);
    }
  }
  approve.addEventListener("click", () => review("approved"));
  reject.addEventListener("click", () => review("rejected"));
  const candidate = node("div", {}, node(
      "div",
      { className: "editor-label" },
      node("p", { className: "section-title" }, "PROPOSED CANDIDATE"),
      badge(
        result.grading.passed ? "Verified" : "Verification failed",
        result.grading.passed ? "good" : "bad",
      ),
    ), editor);
  body.append(
    node("div", { className: "sql-comparison" }, original, candidate),
    verify,
    checks(result),
  );
  if (job.review)
    body.append(
      node(
        "div",
        { className: "reviewed" },
        "Review " + job.review.action + " · " + job.review.actor,
        node("p", {}, job.review.note || "No review note added."),
        node("p", {}, "Bound to result " + job.review.version.slice(0, 16)),
      ),
    );
  else
    body.append(
      node("label", { className: "review-note" }, "Review note", note),
      node("div", { className: "content-actions" }, approve, reject),
    );
  body.append(hint);
  return body;
}
function renderDetail(job, force = false) {
  if (activeTab === "Agent activity" && job.result && !job.result.response.agent_workflow) {
    activeTab = "Summary";
    history.replaceState(history.state, "", "/investigations/" + job.id);
    notify("Agent activity is available on checkpointed AI investigations.");
  }
  const fingerprint = JSON.stringify([
    job.id,
    job.updated_at,
    job.review,
    activeTab,
  ]);
  if (!force && rendered === fingerprint) return;
  rendered = fingerprint;
  current = job;
  if (activeView === "detail") { document.title = "VDIR — " + title(job.request.case_id) + " · " + activeTab; $("breadcrumb-view").textContent = activeTab; }
  renderContext(job);
  const state = outcome(job),
    wrapper = node("div");
  wrapper.append(
    node(
      "div",
      { className: "detail-head" },
      node(
        "div",
        { className: "detail-title-line" },
        node("h2", {}, title(job.request.case_id)),
        badge(state.text, state.tone),
      ),
      node(
        "div",
        { className: "detail-meta" },
        node("code", {}, job.id.slice(0, 8)),
        node(
          "span",
          {},
          mode(job),
        ),
        node("span", {}, job.request.engine === "sqlite" ? "SQLite" : "DuckDB"),
        node("span", {}, dateTime(job.created_at)),
      ),
      node("p", { className: "incident-context" }, cases.find((item) => item.id === job.request.case_id)?.description || ""),
      job.review ? node("p", { className: "review-status" },
        "Review " + job.review.action + " · " + job.review.actor + " · " + dateTime(job.review.created_at)) : null,
    ),
  );
  if (!job.result) {
    wrapper.append(
      node(
        "div",
        { className: "tab-content" },
        node(
          "p",
          { className: "section-title" },
          job.status === "queued"
            ? "WAITING FOR WORKER"
            : job.status === "running"
              ? "COLLECTING EVIDENCE AND CHECKING OUTCOME"
              : "INVESTIGATION STOPPED",
        ),
        node(
          "p",
          { className: "diagnosis" },
          job.error ||
            "This run is saved. The worker will produce an evidence trace and independent verification result.",
        ),
        ["queued", "running"].includes(job.status)
          ? node("div", { className: "progress-line" }, node("span"))
          : null,
        events(job),
      ),
    );
  } else {
    const tabs = ["Summary", "Evidence",
      ...(job.result.response.agent_workflow ? ["Agent activity"] : []),
      "SQL & review", "Metric definition"];
    wrapper.append(
      node(
        "div",
        {
          className: "tabs",
          role: "tablist",
          "aria-label": "Investigation views",
        },
        tabs.map((tab) =>
          node(
            "a",
            {
              className: "tab" + (tab === activeTab ? " selected" : ""),
              role: "tab",
              href: "/investigations/" + job.id + tabPaths[tab],
              id: "tab-" + tabs.indexOf(tab),
              "aria-controls": "investigation-tab-content",
              "aria-selected": String(tab === activeTab),
              tabindex: tab === activeTab ? "0" : "-1",
              onclick: (event) => {
                if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                event.preventDefault();
                navigate("/investigations/" + job.id + tabPaths[tab], {returnPath});
                renderDetail(job, true);
                $("tab-" + tabs.indexOf(tab)).focus();
              },
              onkeydown: (event) => {
                if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
                event.preventDefault();
                const index = tabs.indexOf(activeTab);
                const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1
                  : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
                navigate("/investigations/" + job.id + tabPaths[tabs[next]], {returnPath});
                renderDetail(job, true);
                $("tab-" + next).focus();
              },
            },
            tab,
          ),
        ),
      ),
    );
    const content =
      activeTab === "Summary"
        ? summary(job)
        : activeTab === "Evidence"
          ? evidence(job)
          : activeTab === "Agent activity"
            ? agentActivity(job)
          : activeTab === "SQL & review"
            ? sqlReview(job)
            : node(
                "div",
                {},
                node(
                  "p",
                  { className: "section-title" },
                  "AUTHORITATIVE METRIC CONTRACT",
                ),
                node("pre", {}, JSON.stringify(job.result.contract, null, 2)),
                node(
                  "p",
                  { className: "notice" },
                  "Source and execution version: " + job.result.input_version,
                ),
              );
    wrapper.append(
      node("div", { className: "tab-content", role: "tabpanel", id: "investigation-tab-content", "aria-labelledby": "tab-" + tabs.indexOf(activeTab) }, content),
    );
    if (job.status === "paused") {
      const continuation = job.events.find(
        (event) => event.name === "continuation_created",
      );
      const panel = node("div", { className: "tab-content" });
      if (continuation) {
        panel.append(
          node(
            "button",
            {
              className: "secondary",
              onclick: () => select(continuation.payload.child_id),
            },
            "View continuation →",
          ),
        );
      } else {
        const guidance = node("textarea", {
          id: "graph-guidance",
          rows: "3",
          maxlength: "2000",
        });
        const button = node(
          "button",
          {
            className: "primary",
            onclick: async () => {
              button.disabled = true;
              try {
                const child = await post(
                  "/jobs/" + encodeURIComponent(job.id) + "/resume",
                  {
                    parent_version: job.result_version,
                    guidance: guidance.value,
                  },
                  true,
                );
                await select(child.id);
                await refresh();
              } catch (error) {
                notify(error.message, true);
              } finally {
                button.disabled = false;
              }
            },
          },
          "Resume investigation",
        );
        panel.append(
          node(
            "label",
            { for: "graph-guidance" },
            "Investigation guidance",
            guidance,
          ),
          node(
            "p",
            { className: "notice" },
            "Continue with additional guidance. Changing source data or the metric definition requires a new incident. Continuing uses the configured AI model.",
          ),
          button,
        );
      }
      wrapper.append(panel);
    }
  }
  $("detail").replaceChildren(wrapper);
}
async function refreshDetail() {
  if (selected) {
    const id = selected;
    const job = await api("/jobs/" + encodeURIComponent(id));
    if (id !== selected || (current?.id === id && current.updated_at > job.updated_at)) return;
    renderDetail(job);
  }
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
  const [runs, totals, flows] = await Promise.all([api("/jobs"), api("/stats"), api("/workflows")]);
  jobs = runs;
  workflows = flows;
  $("completed-count").textContent = totals.completed;
  $("verified-count").textContent = totals.verified_candidates;
  renderHistory();
  renderRunTable();
  renderHome();
  renderWorkflows();
  await refreshDetail();
  await refreshWorkflow();
  } finally { refreshing = false; }
}
async function initialize() {
  const [settings, incidentList] = await Promise.all([
    api("/config"),
    api("/incidents"),
  ]);
  configuration = settings;
  cases = incidentList;
  configured = configuration.hosted_available;
  $("operator-name").textContent = configuration.operator;
  $("home-provider").textContent = configured ? "Configured. Live quality evaluation is pending." : "Not configured. Rule-based investigations are available.";
  $("scenario-count").textContent = cases.length;
  $("incident").replaceChildren(
    ...cases.map((item) => node("option", { value: item.id }, item.title)),
  );
  const hosted = $("investigator").querySelector('[value="anthropic"]');
  hosted.disabled = !configuration.hosted_available;
  hosted.textContent = configuration.hosted_available
    ? "Hosted AI investigator"
    : "Hosted AI · not configured";
  const graph = $("investigator").querySelector('[value="langgraph"]');
  graph.disabled = !configuration.hosted_available;
  graph.textContent = configuration.hosted_available
    ? "Checkpointed AI · LangGraph"
    : "Checkpointed AI · not configured";
  $("scenario-description").textContent = cases[0]?.description || "";
  $("workflow-scenarios").replaceChildren(node("legend", {}, "Metric scenarios"), ...cases.map(item => node("label", {className: "workflow-checkbox"}, node("input", {type: "checkbox", name: "workflow-case", value: item.id}), node("span", {}, item.title))));
  $("workflow-scenarios").querySelectorAll("input").forEach(input => input.checked = true);
  for (const name of ["anthropic", "langgraph"]) {
    const option = $("workflow-investigator").querySelector(`[value="${name}"]`);
    option.disabled = !configured;
    option.textContent = name === "langgraph" ? configured ? "Checkpointed AI · LangGraph" : "Checkpointed AI · not configured" : configured ? "Hosted AI investigator" : "Hosted AI · not configured";
  }
  renderMetrics(); renderSettings(); route();
  await refresh();
  if (!selected) emptyDetail();
}
$("investigation-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  busy = true;
  $("run-button").disabled = true;
  try {
    const job = await post(
      "/jobs",
      { case_id: $("incident").value, investigator: $("investigator").value, engine: $("engine").value },
      true,
    );
    await select(job.id);
    await refresh();
  } catch (error) {
    notify(error.message, true);
  } finally {
    busy = false;
    $("run-button").disabled = false;
  }
});
$("incident").addEventListener(
  "change",
  () =>
    ($("scenario-description").textContent =
      cases.find((item) => item.id === $("incident").value)?.description || ""),
);
$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  accessCode = $("access-code").value;
  $("auth-error").textContent = "";
  try {
    await initialize();
    $("auth-dialog").close();
    $("access-code").value = "";
  } catch (error) {
    $("auth-error").textContent = error.message;
  }
});
$("auth-dialog").addEventListener("cancel", (event) => event.preventDefault());
$("about-button").addEventListener("click", () => navigate("/settings"));
$("new-investigation").addEventListener("click", openInvestigation);
$("investigation-cancel").addEventListener("click", () => navigate(setupReturnPath));
$("metric-search").addEventListener("input", renderMetrics);
$("history-search").addEventListener("input", renderHistory);
$("history-filter").addEventListener("change", renderHistory);
$("runs-search").addEventListener("input", renderRunTable);
$("readiness-details").addEventListener("click", () => navigate("/settings"));
$("workflow-launch").addEventListener("click", openWorkflow);
$("workflow-dismiss").addEventListener("click", () => navigate(setupReturnPath));
$("workflow-form").addEventListener("submit", async event => {
  event.preventDefault();
  const caseIds = [...$("workflow-scenarios").querySelectorAll("input:checked")].map(input => input.value);
  if (!caseIds.length) { notify("Select at least one metric scenario.", true); return; }
  $("workflow-submit").disabled = true;
  try {
    const flow = await post("/workflows", {name: $("workflow-name").value, case_ids: caseIds, investigator: $("workflow-investigator").value, engine: $("workflow-engine").value}, true);
    workflows = [flow, ...workflows.filter(item => item.id !== flow.id)];
    navigate("/workflows/" + flow.id); await refresh();
  } catch (error) { notify(error.message, true); }
  finally { $("workflow-submit").disabled = false; }
});
$("cancel-close").addEventListener("click", () => $("cancel-dialog").close());
$("cancel-dismiss").addEventListener("click", () => $("cancel-dialog").close());
$("cancel-form").addEventListener("submit", async event => {
  event.preventDefault();
  const target = cancelTarget;
  if (!target) return;
  $("cancel-confirm").disabled = true;
  try {
    await post("/" + target.kind + "/" + encodeURIComponent(target.id) + "/cancel", {reason: $("cancel-reason").value || "Operator requested cancellation"});
    $("cancel-dialog").close(); notify("Cancellation recorded."); await refresh();
  } catch (error) { notify(error.message, true); }
  finally { $("cancel-confirm").disabled = false; }
});
$("back-button").addEventListener("click", () => navigate(activeView === "detail" ? returnPath : activeView === "metric" ? "/metrics" : activeView === "workflows" ? "/workflows" : setupReturnPath));
$("inspector-close").addEventListener("click", () => $("inspector-dialog").close());
$("command-button").addEventListener("click", openCommands);
$("command-close").addEventListener("click", () => $("command-dialog").close());
$("command-search").addEventListener("input", renderCommands);
document.addEventListener("keydown", event => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    if (document.querySelector("dialog[open]")) return;
    event.preventDefault(); openCommands();
  }
});
document.addEventListener("click", event => {
  const link = event.target.closest("a[data-view], a[data-route], a.brand");
  if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault(); navigate(link.getAttribute("href"));
});
window.addEventListener("popstate", () => { route(true); refreshDetail().catch(detailError); refreshWorkflow().catch(error => notify(error.message, true)); });
window.addEventListener("hashchange", () => { route(); refreshDetail().catch(detailError); });
route();
initialize().catch((error) => {
  if (!$("auth-dialog").open) { notify(error.message, true); detailError(error); }
});
setInterval(() => {
  if (!$("auth-dialog").open) refresh().catch(() => {});
}, 1500);
