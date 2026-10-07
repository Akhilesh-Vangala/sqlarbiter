"use strict";
const $ = (id) => document.getElementById(id);
let accessCode = "",
  cases = [],
  jobs = [],
  selected = new URLSearchParams(location.search).get("job"),
  current = null;
let activeTab = "Summary",
  rendered = "",
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
function emptyDetail() {
  $("detail").replaceChildren(
    node(
      "div",
      { className: "empty-detail" },
      node("div", { className: "empty-icon", "aria-hidden": "true" }, "⌁"),
      node("h2", {}, "A clear path from signal to solution."),
      node(
        "p",
        {},
        "Select a metric scenario above to start.\n",
        node("br"),
        "Your evidence, findings and verification will appear here.",
      ),
      node(
        "div",
        { className: "empty-steps" },
        node("span", {}, "01  Investigate"),
        node("span", {}, "02  Verify"),
        node("span", {}, "03  Review"),
      ),
    ),
  );
}
function renderHistory() {
  $("run-count").textContent = jobs.length;
  $("job-list").replaceChildren(
    ...(jobs.length
      ? jobs.map((job) => {
          const state = outcome(job);
          return node(
            "button",
            {
              className: "run-row" + (job.id === selected ? " selected" : ""),
              onclick: () => select(job.id),
              "aria-label": title(job.request.case_id) + " " + state.text,
            },
            node(
              "span",
              { className: "run-id" },
              job.id.slice(0, 8) +
                " / " +
                (job.request.kind === "verification"
                  ? "CANDIDATE REVISION"
                  : "INVESTIGATION"),
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
              node("span", {}, time(job.created_at)),
            ),
          );
        })
      : [
          node(
            "p",
            { className: "empty-history" },
            "Your investigations will appear here.",
          ),
        ]),
  );
}
async function select(id) {
  selected = id;
  activeTab = "Summary";
  rendered = "";
  window.history.replaceState({}, "", "?job=" + encodeURIComponent(id));
  renderHistory();
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
    node(
      "div",
      { className: "version" },
      "Result version",
      node("code", {}, job.result_version),
    ),
    events(job),
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
      if (record.ok && Array.isArray(record.result?.columns) && Array.isArray(record.result?.rows))
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
        body.append(node("p", { className: "notice" }, "Partial result: row or cell limits were reached. Narrow the query before drawing conclusions."));
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
function sqlReview(job) {
  const result = job.result,
    decision = result.response.decision;
  const body = node(
    "div",
    {},
    node("p", { className: "section-title" }, "CURRENT TRANSFORMATION"),
    node("pre", { className: "sql-block" }, result.current_sql),
  );
  if (decision.status !== "candidate") {
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
      className: "secondary",
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
  body.append(
    node(
      "div",
      { className: "editor-label" },
      node("p", { className: "section-title" }, "PROPOSED CANDIDATE"),
      badge(
        result.grading.passed ? "Verified" : "Verification failed",
        result.grading.passed ? "good" : "bad",
      ),
    ),
    editor,
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
  const fingerprint = JSON.stringify([
    job.id,
    job.updated_at,
    job.review,
    activeTab,
  ]);
  if (!force && rendered === fingerprint) return;
  rendered = fingerprint;
  current = job;
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
          job.request.kind === "verification"
            ? "Operator candidate revision"
            : job.request.investigator === "anthropic"
              ? "Hosted AI"
              : "Fixed diagnostic workflow",
        ),
        node("span", {}, time(job.created_at)),
      ),
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
    const tabs = ["Summary", "Evidence", "SQL & review", "Contract"];
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
            "button",
            {
              className: "tab" + (tab === activeTab ? " selected" : ""),
              role: "tab",
              "aria-selected": String(tab === activeTab),
              onclick: () => {
                activeTab = tab;
                renderDetail(job, true);
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
      node("div", { className: "tab-content", role: "tabpanel" }, content),
    );
  }
  $("detail").replaceChildren(wrapper);
}
async function refreshDetail() {
  if (selected) {
    const job = await api("/jobs/" + encodeURIComponent(selected));
    renderDetail(job);
  }
}
async function refresh() {
  const [runs, totals] = await Promise.all([api("/jobs"), api("/stats")]);
  jobs = runs;
  $("completed-count").textContent = totals.completed;
  $("verified-count").textContent = totals.verified_candidates;
  renderHistory();
  await refreshDetail();
}
async function initialize() {
  const [configuration, incidentList] = await Promise.all([
    api("/config"),
    api("/incidents"),
  ]);
  cases = incidentList;
  $("scenario-count").textContent = cases.length;
  $("incident").replaceChildren(
    ...cases.map((item) => node("option", { value: item.id }, item.title)),
  );
  const hosted = $("investigator").querySelector('[value="anthropic"]');
  hosted.disabled = !configuration.hosted_available;
  hosted.textContent = configuration.hosted_available
    ? "Hosted AI investigator"
    : "Hosted AI · not configured";
  $("scenario-description").textContent = cases[0]?.description || "";
  await refresh();
  if (!selected) emptyDetail();
}
$("run-button").addEventListener("click", async () => {
  if (busy) return;
  busy = true;
  $("run-button").disabled = true;
  try {
    const job = await post(
      "/jobs",
      { case_id: $("incident").value, investigator: $("investigator").value },
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
$("about-button").addEventListener("click", () =>
  $("about-dialog").showModal(),
);
$("about-close").addEventListener("click", () => $("about-dialog").close());
emptyDetail();
initialize().catch((error) => {
  if (!$("auth-dialog").open) notify(error.message, true);
});
setInterval(() => {
  if (!$("auth-dialog").open) refresh().catch(() => {});
}, 1500);
