import {
  el,
  title,
  button,
  link,
  icon,
  badge,
  table,
  readableDate,
} from "../lib/dom.js";
import { state } from "../state.js";

export function emptyState(heading, description, actions, name = "file") {
  return el(
    "div",
    { class: "empty" },
    el("div", { class: "empty-icon" }, icon(name)),
    el("h2", {}, heading),
    el("p", {}, description),
    el("div", { class: "actions" }, actions),
  );
}
function recent(entry, ctx) {
  return el(
    "div",
    { class: "recent-item" },
    el("div", { class: "recent-icon" }, icon("file")),
    el(
      "div",
      { class: "recent-title" },
      link(
        el("strong", {}, entry.title || entry.filename || "Investigation"),
        "/workspace/investigations/" + entry.id + "?storage=" + entry.storage,
      ),
      el(
        "p",
        {},
        `${entry.filename || "Source export"} · ${readableDate(entry.savedAt || entry.createdAt)} · ${entry.storage === "cloud" ? "Account" : "This device"}`,
      ),
    ),
    badge(
      entry.status === "completed" || entry.report ? "Saved result" : "Draft",
    ),
    button(
      icon("arrow"),
      () => ctx.open(entry.id, entry.storage),
      "icon-button",
      { "aria-label": "Open " + (entry.title || "investigation") },
    ),
  );
}
export function dashboard(ctx) {
  const completed = state.entries.filter(
    (e) => e.report || e.status === "completed",
  );
  const page = el(
    "div",
    {},
    title(
      "YOUR WORKSPACE",
      "Make the next number trustworthy.",
      "Start an investigation, pick up a saved draft, or revisit the evidence behind an earlier result.",
      [
        link(
          [icon("upload"), "New investigation"],
          "/uploads?new=1",
          "primary",
        ),
      ],
    ),
    el(
      "div",
      { class: "stats" },
      ...[
        [
          "Saved investigations",
          state.entries.length,
          "Only work you explicitly saved",
        ],
        [
          "Completed reports",
          completed.length,
          "Saved results, available for review",
        ],
        ["Projects", state.projects.length, "Organize related investigations"],
      ].map(([label, value, help]) =>
        el(
          "div",
          { class: "stat" },
          el("span", { class: "stat-label" }, label),
          el("strong", {}, value),
          el("small", {}, help),
        ),
      ),
    ),
    el(
      "div",
      { class: "dashboard-grid" },
      el(
        "section",
        { class: "panel" },
        el(
          "div",
          { class: "panel-heading" },
          el(
            "div",
            {},
            el("h2", {}, "Recent investigations"),
            el(
              "p",
              { class: "hint" },
              "A draft is never presented as a completed check.",
            ),
          ),
          link("View all →", "/workspace/history", "quiet"),
        ),
        state.entries.length
          ? el(
              "div",
              { class: "recent-list" },
              ...state.entries.slice(0, 5).map((e) => recent(e, ctx)),
            )
          : emptyState(
              "Your first investigation starts here.",
              "Bring a CSV to check a metric, or use the sample to learn the workflow. Nothing is saved until you choose to keep it.",
              [
                link("Upload a CSV", "/uploads?new=1", "primary"),
                button("Explore the sample", ctx.sample, "secondary"),
              ],
            ),
      ),
      el(
        "aside",
        { class: "stack" },
        el(
          "article",
          { class: "start-card" },
          icon("shield"),
          el("h2", {}, "A discrepancy worth investigating?"),
          el(
            "p",
            {},
            "Verify transaction totals, identify replayed deliveries and inspect eligibility rules before making a decision.",
          ),
          link(
            ["Start with your data", icon("arrow")],
            "/uploads?new=1",
            "secondary",
          ),
        ),
        el(
          "div",
          { class: "help-card" },
          el("h3", {}, "Your storage, your choice."),
          el(
            "p",
            {},
            state.user
              ? "Account storage is connected. You can still choose device-only saving for individual investigations."
              : "Device-only saving keeps work in this browser. Cloud accounts become available after a real account service is connected.",
          ),
          link("Review data settings →", "/workspace/settings", "text-link"),
        ),
      ),
    ),
  );
  if (state.storageError)
    page.prepend(
      el("p", { class: "inline-error", role: "alert" }, state.storageError),
    );
  return page;
}
export function history(ctx, projectId) {
  const content = el("div", {}),
    controls = el("div", { class: "filter-bar" });
  const search = el("input", {
    type: "search",
    placeholder: "Search title or filename",
    "aria-label": "Search saved investigations",
  });
  const filter = el(
    "select",
    { class: "simple-input", "aria-label": "Investigation status" },
    el("option", { value: "all" }, "All statuses"),
    el("option", { value: "completed" }, "Saved results"),
    el("option", { value: "draft" }, "Drafts"),
  );
  const count = el("span", { class: "hint" });
  function render() {
    const needle = search.value.toLowerCase();
    const entries = state.entries.filter(
      (e) =>
        (!projectId || (e.projectId || e.project_id) === projectId) &&
        `${e.title} ${e.filename}`.toLowerCase().includes(needle) &&
        (filter.value === "all" ||
          (filter.value === "completed") ===
            Boolean(e.report || e.status === "completed")),
    );
    count.textContent =
      entries.length +
      " saved investigation" +
      (entries.length === 1 ? "" : "s");
    content.replaceChildren(
      entries.length
        ? table(
            ["Investigation", "Status", "Location", "Saved", "Actions"],
            entries.map((e) => [
              link(
                el("strong", {}, e.title || e.filename),
                "/workspace/investigations/" + e.id + "?storage=" + e.storage,
              ),
              badge(
                e.report || e.status === "completed" ? "Saved result" : "Draft",
              ),
              e.storage === "cloud" ? "Account" : "This device",
              readableDate(e.savedAt || e.createdAt),
              el(
                "div",
                { class: "actions" },
                button("Open", () => ctx.open(e.id, e.storage), "quiet"),
                button("Delete", () => ctx.remove(e), "quiet", {
                  "aria-label": "Delete " + (e.title || "investigation"),
                }),
              ),
            ]),
            { label: "Saved investigations" },
          )
        : emptyState(
            needle || filter.value !== "all"
              ? "No investigations match."
              : "No saved investigations yet.",
            needle
              ? "Try another filename or clear the status filter."
              : "Save a draft or completed report to return to it here.",
            [link("Start an investigation", "/uploads?new=1", "primary")],
          ),
    );
  }
  search.addEventListener("input", render);
  filter.addEventListener("change", render);
  controls.append(
    el("div", { class: "search-field" }, icon("search"), search),
    el("div", { class: "actions" }, filter, count),
  );
  render();
  return el(
    "div",
    {},
    title(
      "INVESTIGATIONS",
      projectId ? "Project investigations" : "A record of the work you kept.",
      "Device-only entries stay in this browser. Account entries require a connected cloud account.",
      [link("New investigation", "/uploads?new=1", "primary")],
    ),
    el("section", { class: "panel" }, controls, content),
  );
}
export function projects(ctx) {
  return el(
    "div",
    {},
    title(
      "PROJECTS",
      "Keep related investigations together.",
      "Organize work by metric, reporting cycle or business question.",
      [button("Create project", ctx.createProject)],
    ),
    state.projects.length
      ? el(
          "div",
          { class: "project-grid" },
          ...state.projects.map((p) =>
            el(
              "article",
              { class: "project-card" },
              icon("folder"),
              el("h3", {}, p.name),
              el(
                "p",
                {},
                state.entries.filter(
                  (e) => (e.projectId || e.project_id) === p.id,
                ).length +
                  " saved investigations · " +
                  (p.storage === "cloud" ? "Account" : "This device"),
              ),
              el(
                "div",
                { class: "actions" },
                link(
                  "Open project →",
                  "/workspace/projects/" + p.id,
                  "secondary",
                ),
                button("Delete", () => ctx.removeProject(p), "quiet", {
                  "aria-label": "Delete project " + p.name,
                }),
              ),
            ),
          ),
        )
      : el(
          "section",
          { class: "panel" },
          emptyState(
            "Give the work a home.",
            "A project groups related investigations. Creating a device project stores its name in this browser after your confirmation.",
            [button("Create your first project", ctx.createProject)],
            "folder",
          ),
        ),
  );
}
