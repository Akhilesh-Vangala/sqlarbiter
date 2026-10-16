import { importFile } from "./lib/imports.js";
import {
  el,
  $,
  button,
  link,
  icon,
  badge,
  modal,
  field,
  notify,
  announce,
  download,
  table,
} from "./lib/dom.js";
import { request, verify, cloud, Problem } from "./lib/api.js";
import { saved } from "./lib/storage.js";
import { state, newDraft, payload } from "./state.js";
import { landing, brand } from "./views/landing.js";
import {
  dashboard,
  history as historyView,
  projects,
} from "./views/dashboard.js";
import { intake, issueBox } from "./views/intake.js";
import { reportView } from "./views/report.js";
import { settings, login, guide } from "./views/account.js";

let epoch = 0,
  previewEpoch = 0;
const ctx = {
  render,
  go,
  sample,
  loadFile,
  advance,
  run,
  stop,
  save,
  clear,
  problem,
  preview,
  refresh,
  open,
  remove,
  createProject,
  removeProject,
  exportReport,
  refreshAccount,
  signOut,
  restoreBackup,
};
function contractMatches(a, b) {
  return ["mapping", "options"].every(
    (k) =>
      JSON.stringify(Object.entries(a?.[k] || {}).sort()) ===
      JSON.stringify(Object.entries(b?.[k] || {}).sort()),
  );
}
function isInvestigation(path = location.pathname) {
  return (
    path === "/uploads" ||
    path === "/workspace/new" ||
    path.startsWith("/workspace/investigations/")
  );
}
function userProblem(error) {
  if (error.name === "AbortError") return;
  state.issues = {
    message: error.message || String(error),
    issues: error.issues || [],
    hint: error.hint || "",
  };
  state.busy = false;
  render();
  $("#error")?.focus();
  announce(state.issues.message);
}
function problem(text) {
  userProblem(new Error(text));
}
function shell(content) {
  const path = location.pathname;
  const nav = [
    ["grid", "Overview", "/workspace"],
    ["file", "Investigations", "/workspace/history"],
    ["folder", "Projects", "/workspace/projects"],
    ["help", "Quick guide", "/workspace/guide"],
    ["settings", "Settings", "/workspace/settings"],
  ];
  return el(
    "div",
    { class: "app-shell" },
    el(
      "aside",
      { class: "sidebar" },
      brand(),
      el("p", { class: "eyebrow" }, "DATA RELIABILITY WORKSPACE"),
      el(
        "nav",
        { class: "app-nav", "aria-label": "Workspace navigation" },
        ...nav.map(([name, title, href]) =>
          link([icon(name), title], href, "", {
            "aria-current":
              path === href ||
              (href === "/workspace/history" &&
                path.startsWith("/workspace/investigations/"))
                ? "page"
                : undefined,
          }),
        ),
      ),
      el(
        "div",
        { class: "sidebar-foot" },
        badge(state.user ? "Account connected" : "Device workspace"),
        el("p", {}, "Save deliberately. Keep evidence with every decision."),
        link("Engineering demo ↗", "/demo", "text-link"),
      ),
    ),
    el(
      "div",
      { class: "workspace" },
      el(
        "header",
        { class: "workspace-bar" },
        el(
          "span",
          {},
          "Workspace / " +
            (isInvestigation()
              ? "Investigation"
              : path.split("/").at(-1) === "workspace"
                ? "Overview"
                : path.split("/").at(-1)),
        ),
        el(
          "div",
          { class: "actions" },
          button(
            [icon("search"), el("span", {}, "Find work"), el("kbd", {}, "⌘ K")],
            commands,
            "command-button",
            { "aria-label": "Search workspace" },
          ),
          badge(state.user ? "Account" : "This device"),
          link(state.user ? "Account" : "Sign in", "/workspace/login", "quiet"),
        ),
      ),
      el(
        "main",
        { id: "main" },
        state.storageError &&
          !isInvestigation() &&
          el("p", { class: "inline-error" }, state.storageError),
        content,
        el(
          "footer",
          { class: "workspace-footer" },
          el(
            "span",
            {},
            "VerifyOps · Explicit rules · Independent verification",
          ),
          el(
            "div",
            { class: "actions" },
            link("Data handling", "/workspace/settings"),
            link(
              "Engineering documentation ↗",
              "https://github.com/Akhilesh-Vangala/verifyops/tree/main/docs",
              "",
              { target: "_blank", rel: "noreferrer" },
            ),
          ),
        ),
      ),
    ),
  );
}
function render(focusHeading = false) {
  const activeId = document.activeElement?.id,
    path = location.pathname;
  let content;
  if (path === "/") {
    document.title = "VerifyOps · Find the number you can stand behind";
    $("#app").replaceChildren(landing(ctx));
  } else {
    if (isInvestigation()) {
      state.draft ||= newDraft();
      content =
        state.draft.report && state.draft.stage === 3
          ? reportView(ctx)
          : intake(ctx);
    } else if (path === "/workspace") content = dashboard(ctx);
    else if (path === "/workspace/history") content = historyView(ctx);
    else if (path === "/workspace/projects") content = projects(ctx);
    else if (path.startsWith("/workspace/projects/"))
      content = historyView(ctx, path.split("/").at(-1));
    else if (path === "/workspace/settings") content = settings(ctx);
    else if (path === "/workspace/guide") content = guide();
    else if (path === "/workspace/login")
      content = state.user
        ? el(
            "section",
            { class: "panel" },
            el("h1", {}, "You’re signed in."),
            el("p", { class: "muted spaced" }, state.user.email),
            button("Sign out", signOut, "secondary", {
              class: "secondary spaced",
            }),
          )
        : login(ctx);
    else
      content = el(
        "section",
        { class: "panel empty" },
        el("h1", {}, "This page isn’t available."),
        el(
          "p",
          { class: "muted spaced" },
          "Return to your workspace to find saved work.",
        ),
        link("Open workspace", "/workspace", "primary"),
      );
    document.title =
      (isInvestigation() ? state.draft.title : path.split("/").at(-1)) +
      " · VerifyOps";
    $("#app").replaceChildren(shell(content));
  }
  if (focusHeading) {
    $("h1")?.setAttribute("tabindex", "-1");
    $("h1")?.focus({ preventScroll: true });
  } else if (activeId)
    document.getElementById(activeId)?.focus({ preventScroll: true });
}
function go(path, replace = false) {
  const target = new URL(path, location.origin);
  if (target.searchParams.has("new") && state.draft?.csv && state.draft.dirty) {
    modal(
      "Start a new investigation?",
      el(
        "p",
        {},
        "The current unsaved file and results will leave memory. Save a snapshot or export a backup first if you want to keep them.",
      ),
      [
        button("Keep current work", () => $("#dialog").close(), "secondary"),
        button("Start new", () => {
          $("#dialog").close();
          state.draft = newDraft();
          go(target.pathname, replace);
        }),
      ],
    );
    return;
  }
  if (target.searchParams.has("new")) state.draft = newDraft();
  if (state.busy && target.pathname !== location.pathname) stop(false);
  window.history[replace ? "replaceState" : "pushState"]({}, "", path);
  state.route = target.pathname;
  state.issues = null;
  if (target.pathname.startsWith("/workspace/investigations/")) {
    open(
      target.pathname.split("/").at(-1),
      target.searchParams.get("storage") || "device",
      false,
    );
    return;
  }
  render(true);
  window.scrollTo({ top: 0 });
}
async function refresh() {
  state.storageError = "";
  try {
    state.entries = (await saved.list()).map((e) => ({
      ...e,
      storage: "device",
      status: e.report ? "completed" : "draft",
    }));
    state.projects = (await saved.projects()).map((p) => ({
      ...p,
      storage: "device",
    }));
  } catch (error) {
    state.entries = [];
    state.projects = [];
    state.storageError = error.message;
  }
  state.cloudReady = false;
  if (state.user) {
    try {
      const [entries, projects] = await Promise.all([
        cloud("/investigations"),
        cloud("/projects"),
      ]);
      state.entries.push(
        ...entries.map((e) => ({
          ...e,
          storage: "cloud",
          savedAt: e.created_at,
          createdAt: e.created_at,
          projectId: e.project_id,
        })),
      );
      state.projects.push(...projects.map((p) => ({ ...p, storage: "cloud" })));
      state.cloudReady = true;
    } catch {
      state.storageError =
        "Account history couldn’t be loaded. Device work is still available; retry after checking the cloud connection.";
    }
  }
  state.entries.sort((a, b) =>
    String(b.savedAt || b.createdAt).localeCompare(
      String(a.savedAt || a.createdAt),
    ),
  );
}
async function refreshAccount() {
  try {
    state.user = state.account?.enabled ? await cloud("/me") : null;
  } catch {
    state.user = null;
  }
  await refresh();
}
async function loadFile(file, kind = "upload") {
  const current = ++epoch;
  state.controller?.abort();
  state.issues = null;
  state.draft ||= newDraft();
  const restore = state.draft.requiredSourceHash;
  const beforeImport = structuredClone(state.draft);
  const previous = restore ? beforeImport : null;
  if (file.size > 400000 || !/\.(csv|tsv|xlsx|json|jsonl)$/i.test(file.name)) {
    problem("Choose CSV, TSV, Excel .xlsx, JSON or JSONL, up to 400 KB.");
    return;
  }
  state.busy = true;
  if (state.draft.storage !== "memory" && !restore)
    state.draft = { ...structuredClone(state.draft), id: crypto.randomUUID() };
  state.draft.report = null;
  state.draft.profile = null;
  state.draft.stage = 0;
  state.draft.filename = file.name.slice(0, 160);
  state.draft.sourceKind = kind;
  state.draft.storage = "memory";
  state.draft.dirty = true;
  state.previewRows = [];
  state.previewSearch = "";
  state.previewOffset = 0;
  render();
  state.controller = new AbortController();
  try {
    const imported = await importFile(
      file,
      (body) =>
        request("/api/uploads/import", body, {
          signal: state.controller.signal,
        }),
      state.controller.signal,
    );
    if (current !== epoch) return;
    const text = imported.csv,
      profile = imported.profile;
    state.draft.csv = text;
    state.draft.importSource = imported.source;

    if (restore && profile.sha256 !== restore) {
      state.draft = previous;
      throw Error(
        "This file differs from the saved source. Upload the original file, or start a new investigation for a different export.",
      );
    }
    state.draft.profile = profile;
    state.draft.requiredSourceHash = null;
    if (restore) {
      state.draft.mapping = previous.mapping;
      state.draft.options = previous.options;
      state.draft.id = crypto.randomUUID();
      state.draft.stage = 1;
    } else {
      state.draft.mapping = {};
      state.draft.options = { unit: "dollars" };
      for (const key of ["key", "amount", "group", "status"]) {
        const suggestion = profile.columns.find((c) =>
          (state.capability?.suggest?.[key] || []).includes(
            c.name.trim().toLowerCase(),
          ),
        );
        if (suggestion) state.draft.mapping[key] = suggestion.id;
      }
      if (state.draft.mapping.status)
        state.draft.options.eligible_status = "completed";
    }
    if (kind === "sample") {
      state.draft.options.reported_total = "325.50";
      state.draft.title = "Sample · Revenue reconciliation";
    } else if (
      state.draft.title === "Untitled investigation" ||
      state.draft.title.startsWith("Sample ·")
    )
      state.draft.title = file.name
        .replace(/\.(csv|tsv|xlsx|json|jsonl)$/i, "")
        .slice(0, 100);
    announce(
      "File inspected. " + profile.rows + " records are ready for review.",
    );
  } catch (error) {
    if (current === epoch) {
      state.draft = beforeImport;
      if (error.name !== "AbortError") userProblem(error);
      else announce("Import cancelled. Previous work is preserved.");
    }
  } finally {
    if (current === epoch) {
      state.busy = false;
      render();
    }
  }
}
async function sample() {
  if (state.busy) return;
  if (state.draft?.csv && state.draft.dirty) {
    modal(
      "Replace the current file with a sample?",
      el(
        "p",
        {},
        "Save or export your current investigation first if you need it.",
      ),
      [
        button("Keep current file", () => $("#dialog").close(), "secondary"),
        button("Use sample", () => {
          $("#dialog").close();
          state.draft = newDraft();
          sample();
        }),
      ],
    );
    return;
  }
  state.draft = newDraft();
  go("/uploads");
  try {
    const response = await fetch("/api/uploads/template");
    if (!response.ok)
      throw Error("The sample file couldn’t be loaded. Try again.");
    await loadFile(
      new File([await response.text()], "verifyops-sample.csv", {
        type: "text/csv",
      }),
      "sample",
    );
  } catch (error) {
    problem(error.message);
  }
}
function advance(stage) {
  const draft = state.draft;
  if (stage > 0 && (!draft.profile || !draft.csv)) {
    if (!draft.csv) draft.stage = 0;
    problem("Choose and inspect a valid source file first.");
    render();
    return;
  }
  if (stage === 2) {
    if (!draft.mapping.key || !draft.mapping.amount) {
      problem("Choose a logical key and amount column before continuing.");
      return;
    }
    if (draft.mapping.key === draft.mapping.amount) {
      problem("Logical key and amount must be different columns.");
      return;
    }
    if (draft.mapping.status && !draft.options.eligible_status?.trim()) {
      problem(
        "Choose which status to include, or leave the eligibility column unmapped.",
      );
      return;
    }
  }
  state.issues = null;
  draft.stage = stage;
  render(true);
  window.scrollTo({ top: 0 });
}
async function run() {
  if (state.busy) return;
  const current = ++epoch;
  state.busy = true;
  state.issues = null;
  state.draft.report = null;
  state.draft.stage = 3;
  state.draft.dirty = true;
  state.controller = new AbortController();
  state.stages = [];
  render(true);
  window.scrollTo({ top: 0 });
  try {
    const report = await verify(
      payload(),
      (event) => {
        if (current !== epoch) return;
        state.stages.push(event);
        const node = document.querySelector(`[data-stage="${event.stage}"]`);
        if (!node) return;
        node.dataset.state = event.state;
        node
          .querySelector(".stage-icon")
          .replaceChildren(
            event.state === "complete"
              ? icon("check")
              : el("span", { class: "spinner" }),
          );
        node.querySelector(".stage-state").textContent = event.state;
        $("#processing-status").textContent =
          event.state === "complete"
            ? "Completed: " + node.querySelector("h3").textContent
            : "Working: " + node.querySelector("h3").textContent;
      },
      state.controller.signal,
    );
    if (current !== epoch) return;
    state.draft.report = report;
    state.draft.authentic = true;
    state.draft.restored = false;
    state.reportTab = "overview";
    state.busy = false;
    render(true);
    announce("Verification complete. Independent checks passed.");
  } catch (error) {
    if (current === epoch) {
      state.draft.stage = 1;
      userProblem(error);
    }
  }
}
function stop(showMessage = true) {
  ++epoch;
  state.controller?.abort();
  state.busy = false;
  if (state.draft) state.draft.stage = 2;
  if (showMessage) {
    render();
    notify(
      "Stopped waiting. The bounded server calculation may finish; no data is changed or saved.",
    );
  }
}
function clear() {
  const apply = () => {
    ++epoch;
    state.controller?.abort();
    state.draft = newDraft();
    state.issues = null;
    state.busy = false;
    state.previewRows = [];
    state.previewSearch = "";
    state.previewOffset = 0;
    $("#dialog").close();
    if (!isInvestigation()) go("/uploads");
    else {
      window.history.replaceState({}, "", "/uploads");
      render(true);
    }
  };
  if (state.draft?.csv)
    modal(
      "Clear this investigation?",
      el(
        "p",
        {},
        "Removes the active source, rules and result from memory. Saved history is kept. Export or save the current work first if you need it.",
      ),
      [
        button("Keep working", () => $("#dialog").close(), "secondary"),
        button("Clear active investigation", apply, "danger", {
          id: "confirm-clear",
        }),
      ],
    );
  else apply();
}
async function preview() {
  const current = ++previewEpoch,
    draft = state.draft;
  if (!draft?.csv) return;
  try {
    const result = await request("/api/uploads/preview", {
      csv: draft.csv,
      offset: state.previewOffset,
      search: state.previewSearch,
      rows: state.previewRows,
    });
    if (current !== previewEpoch) return;
    const node = $("#preview-content");
    if (!node) return;
    node.replaceChildren(
      table(
        ["Record", ...result.headers],
        result.rows.map((r) => [r.row, ...r.cells]),
        { label: "Source record preview" },
      ),
    );
    node.firstChild.classList.add("data-preview");
    node.querySelectorAll("tbody tr").forEach((row, index) => {
      if (state.previewRows.includes(result.rows[index].row))
        row.dataset.issue = "true";
    });
    $("#preview-count").textContent = result.matches
      ? `${state.previewOffset + 1}–${Math.min(state.previewOffset + 25, result.matches)} of ${result.matches} matching records`
      : "No matching records";
    $("#preview-prev").disabled = state.previewOffset === 0;
    $("#preview-next").disabled = state.previewOffset + 25 >= result.matches;
  } catch (error) {
    notify(error.message);
  }
}
function exportReport() {
  if (state.draft?.report)
    download(
      JSON.stringify(state.draft.report, null, 2),
      "verifyops-evidence.json",
    );
}
function save() {
  const draft = state.draft;
  if (!draft?.csv || state.busy) return;
  const destination = el(
    "select",
    { id: "save-destination", class: "simple-input" },
    el("option", { value: "device" }, "This device · browser storage"),
    el(
      "option",
      { value: "cloud", disabled: !state.user || !state.cloudReady },
      state.user && state.cloudReady
        ? "My cloud account"
        : "Cloud account · not available",
    ),
  );
  const consent = el("input", { type: "checkbox", id: "save-consent" }),
    source = el("input", { type: "checkbox", id: "save-source" });
  const sourceLabel = el(
    "label",
    { class: "checkbox spaced", hidden: true },
    source,
    "Also save the source CSV in my cloud account so I can resume or rerun across devices.",
  );
  const explanation = el(
    "p",
    { class: "spaced" },
    "This device save includes your source CSV, rules and any completed report. It stays in this browser, may be cleared by browser cleanup, and does not sync to another device.",
  );
  const error = el("p", {
    class: "inline-error spaced",
    hidden: true,
    role: "alert",
  });
  const candidateId = crypto.randomUUID();
  const action = button(
    draft.report ? "Save report snapshot" : "Save draft snapshot",
    async () => {
      if (!consent.checked) return;
      action.disabled = true;
      error.hidden = true;
      const value = {
        ...structuredClone(draft),
        id: candidateId,
        parentId: draft.storage !== "memory" ? draft.id : null,
        stage: draft.report ? 3 : draft.stage,
        dirty: false,
      };
      try {
        const project = state.projects.find((p) => p.id === draft.projectId);
        if (project && project.storage !== destination.value)
          throw Error(
            "This project belongs to a different storage location. Cancel and choose a project in the destination, or select No project before saving.",
          );
        if (destination.value === "device") await saved.put(value, true);
        else
          await cloud("/investigations", {
            id: candidateId,
            title: draft.title,
            filename: draft.filename,
            project_id:
              state.projects.find((p) => p.id === draft.projectId)?.storage ===
              "cloud"
                ? draft.projectId
                : null,
            parent_id: draft.storage === "cloud" ? draft.id : null,
            status: draft.report ? "completed" : "draft",
            upload: payload(),
            retain_source: source.checked,
            consent: true,
          });
        draft.id = candidateId;
        draft.storage = destination.value === "cloud" ? "cloud" : "device";
        draft.dirty = false;
        draft.savedAt = new Date().toISOString();
        $("#dialog").close();
        await refresh();
        go(
          "/workspace/investigations/" + draft.id + "?storage=" + draft.storage,
          true,
        );
        notify(
          "Saved a " +
            (draft.report ? "report" : "draft") +
            " snapshot " +
            (draft.storage === "device"
              ? "on this device."
              : "to your account."),
        );
      } catch (err) {
        error.textContent = err.message;
        error.hidden = false;
        action.disabled = false;
      }
    },
    "primary",
    { id: "confirm-save", disabled: true },
  );
  consent.addEventListener("change", () => {
    action.disabled = !consent.checked;
  });
  destination.addEventListener("change", () => {
    consent.checked = false;
    action.disabled = true;
    sourceLabel.hidden = destination.value !== "cloud";
    explanation.textContent =
      destination.value === "device"
        ? "The device copy includes the source CSV, selected rules and report. It remains in this browser and can be removed by browser cleanup."
        : "This saves the investigation and report to your authenticated cloud account. Source retention is a separate choice. Without the original source, a saved draft requires re-uploading the file to continue.";
  });
  modal(
    "Save this investigation deliberately.",
    el(
      "div",
      {},
      field("Storage destination", destination),
      explanation,
      sourceLabel,
      el(
        "label",
        { class: "checkbox spaced" },
        consent,
        "I consent to saving this investigation, including the business data described above, in the selected location.",
      ),
      error,
      el(
        "p",
        { class: "hint spaced" },
        "Each save is a new snapshot. An existing saved result is not silently overwritten.",
      ),
    ),
    [button("Cancel", () => $("#dialog").close(), "secondary"), action],
  );
}
async function open(id, storage = "device", navigate = true) {
  if (!/^[0-9a-f-]{36}$/.test(id)) {
    problem("This saved investigation ID is invalid.");
    return;
  }
  try {
    let value =
      storage === "cloud"
        ? await cloud("/investigations/" + id)
        : await saved.get(id);
    if (!value)
      throw Error(
        "This investigation is not available in the selected storage location.",
      );
    const draft = value.upload
      ? {
          ...value,
          csv: value.upload.csv || "",
          mapping: value.upload.mapping,
          options: value.upload.options,
          profile: value.profile,
          projectId: value.project_id,
          createdAt: value.created_at,
        }
      : value;
    draft.storage = storage;
    draft.dirty = false;
    draft.restored = true;
    draft.stage = draft.report ? 3 : Math.min(draft.stage || 0, 2);
    state.draft = draft;
    if (draft.csv)
      draft.profile = await request("/api/uploads/profile", { csv: draft.csv });
    if (draft.report) {
      try {
        const checked = await request("/api/uploads/check-report", {
          report: draft.report,
        });
        draft.authentic =
          checked.verified &&
          (!draft.csv || draft.profile.sha256 === draft.report.source_sha256) &&
          contractMatches(draft, draft.report.contract);
        if (!draft.authentic)
          throw Error(
            "The saved report could not be authenticated. Re-run the original source before trusting a result.",
          );
      } catch (error) {
        draft.report = null;
        draft.stage = draft.csv ? 1 : 0;
        state.issues = {
          message: error.message,
          issues: [],
          hint: "Reload the original file and rerun verification. No saved result has been marked as freshly verified.",
        };
      }
    }
    if (!draft.profile && draft.report)
      draft.profile = {
        columns: Object.entries(draft.report.column_bindings).map(
          ([id, name]) => ({ id, name }),
        ),
        rows: draft.report.summary.source_rows,
      };
    if (!draft.csv) {
      if (draft.report)
        draft.profile = {
          rows: draft.report.summary.source_rows,
          preview: [],
          columns: Object.entries(draft.report.column_bindings).map(
            ([id, name]) => ({ id, name }),
          ),
        };
      draft.requiredSourceHash =
        draft.report?.source_sha256 ||
        draft.source_sha256 ||
        draft.profile?.sha256;
      if (!draft.report) {
        draft.stage = 0;
        state.issues = {
          message:
            "Upload the original file to continue this saved investigation.",
          issues: [],
          hint: "Source storage was not enabled for this snapshot. The source fingerprint must match before saved rules are restored.",
        };
      }
    }
    if (navigate)
      window.history.pushState(
        {},
        "",
        "/workspace/investigations/" + id + "?storage=" + storage,
      );
    render(true);
    window.scrollTo({ top: 0 });
  } catch (error) {
    state.draft = newDraft();
    state.issues = {
      message: error.message,
      issues: [],
      hint: "Check the selected device/account, or return to saved investigations.",
    };
    render(true);
  }
}
function remove(entry) {
  modal(
    "Delete this saved investigation?",
    el(
      "p",
      {},
      "The saved snapshot will be removed from " +
        (entry.storage === "cloud" ? "your cloud account" : "this browser") +
        ". Export evidence first if you need it. This does not change your source system.",
    ),
    [
      button("Keep it", () => $("#dialog").close(), "secondary"),
      button(
        "Delete snapshot",
        async () => {
          try {
            if (entry.storage === "cloud")
              await cloud("/investigations/delete", { id: entry.id });
            else await saved.remove(entry.id);
            $("#dialog").close();
            await refresh();
            render();
            notify("Saved snapshot removed.");
          } catch (error) {
            notify(error.message);
          }
        },
        "danger",
      ),
    ],
  );
}
function createProject() {
  const name = el("input", {
      id: "project-name",
      class: "simple-input",
      maxlength: "80",
      placeholder: "e.g. October revenue",
    }),
    destination = el(
      "select",
      { class: "simple-input", id: "project-storage" },
      el("option", { value: "device" }, "This device"),
      el(
        "option",
        { value: "cloud", disabled: !state.cloudReady },
        "Cloud account",
      ),
    );
  const consent = el("input", { type: "checkbox", id: "project-consent" }),
    error = el("p", { class: "inline-error", role: "alert", hidden: true });
  const action = button("Create project", async () => {
    if (!name.value.trim() || !consent.checked) {
      error.textContent = "Enter a name and confirm the storage choice.";
      error.hidden = false;
      return;
    }
    action.disabled = true;
    try {
      const value = {
        id: crypto.randomUUID(),
        name: name.value.trim(),
        createdAt: new Date().toISOString(),
      };
      if (destination.value === "device") await saved.project(value);
      else
        await cloud("/projects", {
          id: value.id,
          name: value.name,
          consent: true,
        });
      $("#dialog").close();
      await refresh();
      render();
      notify("Project created.");
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
      action.disabled = false;
    }
  });
  modal(
    "Create a project",
    el(
      "div",
      {},
      field("Project name", name),
      field("Storage", destination),
      el(
        "label",
        { class: "checkbox spaced" },
        consent,
        "Save this project name in the selected location.",
      ),
      error,
    ),
    [button("Cancel", () => $("#dialog").close(), "secondary"), action],
  );
}
function removeProject(project) {
  modal(
    "Delete this project?",
    el(
      "p",
      {},
      "Remove or move its saved investigations first. The project name will be removed from " +
        (project.storage === "cloud" ? "your account." : "this device."),
    ),
    [
      button("Cancel", () => $("#dialog").close(), "secondary"),
      button(
        "Delete project",
        async () => {
          try {
            if (project.storage === "cloud")
              await cloud("/projects/delete", { id: project.id });
            else await saved.removeProject(project.id);
            $("#dialog").close();
            await refresh();
            render();
            notify("Project removed.");
          } catch (error) {
            notify(error.message);
          }
        },
        "danger",
      ),
    ],
  );
}
async function signOut() {
  try {
    const status = await cloud("/sign-out", {});
    state.user = null;
    if (state.draft?.storage === "cloud") state.draft = newDraft();
    await refresh();
    notify(
      status.provider_revoked
        ? "Signed out. Account work is no longer shown."
        : "Signed out on this browser. Provider session revocation was unavailable; its existing access token may remain valid until expiry.",
    );
    go("/workspace");
  } catch (error) {
    notify(error.message);
  }
}
function restoreBackup(file) {
  if (
    !file ||
    file.size > 24_000_000 ||
    !file.name.toLowerCase().endsWith(".json")
  ) {
    notify("Choose a VerifyOps JSON backup no larger than 24 MB.");
    return;
  }
  const consent = el("input", { type: "checkbox", id: "restore-consent" });
  const status = el("p", { class: "hint spaced", role: "status" });
  const action = button(
    "Restore device backup",
    async () => {
      if (!consent.checked) return;
      action.disabled = true;
      let rejected = 0;
      try {
        const value = JSON.parse(await file.text());
        if (
          value.format !== "verifyops-device-backup-v1" ||
          !Array.isArray(value.entries) ||
          !Array.isArray(value.projects) ||
          value.entries.length > 50 ||
          value.projects.length > 20
        )
          throw Error(
            "This is not a supported VerifyOps backup, or it exceeds the device limits.",
          );
        const ids = new Map();
        const projects = value.projects.map((p) => {
          if (
            typeof p.id !== "string" ||
            ids.has(p.id) ||
            typeof p.name !== "string" ||
            !p.name.trim() ||
            p.name.length > 80
          )
            throw Error("A backup project is invalid.");
          const id = crypto.randomUUID();
          ids.set(p.id, id);
          return {
            id,
            name: p.name.trim(),
            storage: "device",
            createdAt: new Date().toISOString(),
          };
        });
        const entries = [];
        for (const [index, entry] of value.entries.entries()) {
          status.textContent = `Inspecting saved source ${index + 1} of ${value.entries.length}…`;
          if (
            typeof entry.csv !== "string" ||
            typeof entry.title !== "string" ||
            !entry.title.trim() ||
            entry.title.length > 100 ||
            typeof entry.filename !== "string" ||
            entry.filename.length > 160
          )
            throw Error(
              "A saved investigation has invalid source or metadata.",
            );
          const inspected = await request("/api/uploads/profile", {
            csv: entry.csv,
            mapping: entry.mapping,
            options: entry.options,
          });
          let report = null;
          if (entry.report) {
            const checked = await request("/api/uploads/check-report", {
              report: entry.report,
            });
            if (
              checked.verified &&
              inspected.sha256 === entry.report.source_sha256 &&
              contractMatches(entry, entry.report.contract)
            )
              report = entry.report;
            else rejected++;
          }
          entries.push({
            id: crypto.randomUUID(),
            title: entry.title.trim(),
            filename: entry.filename,
            csv: entry.csv,
            mapping: entry.mapping || {},
            options: entry.options || {},
            profile: inspected,
            report,
            stage: report ? 3 : 1,
            projectId: ids.get(entry.projectId) || "",
            sourceKind: "restored backup",
            storage: "device",
            dirty: false,
            createdAt: new Date().toISOString(),
            savedAt: new Date().toISOString(),
          });
        }
        await saved.restore(entries, projects);
        $("#dialog").close();
        await refresh();
        go("/workspace/history");
        notify(
          `Restored ${entries.length} snapshots as new device copies.` +
            (rejected
              ? ` ${rejected} unverifiable reports returned to drafts; rerun their sources.`
              : ""),
        );
      } catch (error) {
        status.textContent = error.message;
        action.disabled = false;
      }
    },
    "primary",
    { disabled: true, id: "confirm-restore" },
  );
  consent.addEventListener("change", () => {
    action.disabled = !consent.checked;
  });
  modal(
    "Restore work on this device",
    el(
      "div",
      {},
      el(
        "p",
        {},
        "The selected backup may contain business data. Its sources will be sent to this deployment for bounded validation; saved reports must authenticate before they appear as checked results. Existing snapshots are preserved. Unverifiable reports return to drafts.",
      ),
      el(
        "label",
        { class: "checkbox spaced" },
        consent,
        "I consent to validating these saved sources and storing new copies in this browser.",
      ),
      status,
    ),
    [button("Cancel", () => $("#dialog").close(), "secondary"), action],
  );
}
function commands() {
  const input = el("input", {
      type: "search",
      class: "simple-input",
      placeholder: "Search pages or saved work",
      "aria-label": "Search pages or saved work",
    }),
    results = el("div", { class: "command-list" });
  function draw() {
    const needle = input.value.toLowerCase();
    const pages = [
      ["Overview", "/workspace"],
      ["New investigation", "/uploads?new=1"],
      ["Saved investigations", "/workspace/history"],
      ["Projects", "/workspace/projects"],
      ["Guide", "/workspace/guide"],
      ["Settings", "/workspace/settings"],
      ...state.entries.map((e) => [
        e.title || e.filename,
        "/workspace/investigations/" + e.id + "?storage=" + e.storage,
      ]),
    ];
    results.replaceChildren(
      ...pages
        .filter(([title]) => title.toLowerCase().includes(needle))
        .slice(0, 12)
        .map(([title, href]) =>
          button(
            [icon("file"), title],
            () => {
              $("#dialog").close();
              go(href);
            },
            "",
          ),
        ),
    );
    if (!results.children.length)
      results.append(
        el(
          "p",
          { class: "hint" },
          "No matching pages or saved investigations.",
        ),
      );
  }
  input.addEventListener("input", draw);
  draw();
  modal("Find work", el("div", {}, input, results));
  input.focus();
}
document.addEventListener("click", (event) => {
  const anchor = event.target.closest("a[href]");
  if (
    !anchor ||
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey ||
    anchor.target ||
    anchor.hasAttribute("download")
  )
    return;
  const url = new URL(anchor.href, location.origin);
  if (
    url.origin !== location.origin ||
    url.hash ||
    url.pathname === "/demo" ||
    url.pathname.startsWith("/demo/") ||
    url.pathname === "/uploads/recording.html" ||
    url.pathname.startsWith("/api/")
  )
    return;
  if (
    url.pathname === "/" ||
    url.pathname === "/uploads" ||
    url.pathname.startsWith("/workspace")
  ) {
    event.preventDefault();
    go(url.pathname + url.search);
  }
});
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    commands();
  }
});
window.addEventListener("popstate", () => {
  if (state.busy) stop(false);
  if (location.pathname.startsWith("/workspace/investigations/"))
    open(
      location.pathname.split("/").at(-1),
      new URLSearchParams(location.search).get("storage") || "device",
      false,
    );
  else render(true);
});
window.addEventListener("beforeunload", (event) => {
  if (state.draft?.csv && state.draft.dirty) {
    event.preventDefault();
    event.returnValue = "";
  }
});
async function boot() {
  // Confirmation links may include provider fragments. They are never persisted
  // or exchanged for a browser session; sign-in requires the user's password.
  if (location.hash.includes("access_token="))
    window.history.replaceState({}, "", location.pathname + location.search);
  const [capability, account] = await Promise.allSettled([
    request("/api/uploads/capabilities"),
    request("/api/account/config"),
  ]);
  state.capability =
    capability.status === "fulfilled" ? capability.value : null;
  state.account =
    account.status === "fulfilled" ? account.value : { enabled: false };
  await refreshAccount();
  if (location.pathname.startsWith("/workspace/investigations/"))
    await open(
      location.pathname.split("/").at(-1),
      new URLSearchParams(location.search).get("storage") || "device",
      false,
    );
  else render();
  if (!state.capability)
    notify(
      "The verification service is unavailable. Saved work remains available; retry when connected.",
    );
}
boot().catch((error) => {
  $("#app").replaceChildren(
    el(
      "main",
      { id: "main", class: "panel empty" },
      el("h1", {}, "The workspace couldn’t open."),
      el("p", { class: "muted spaced" }, error.message),
      button("Retry", () => location.reload()),
    ),
  );
});
