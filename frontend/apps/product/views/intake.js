import {
  el,
  button,
  link,
  icon,
  title,
  badge,
  field,
  table,
  download,
} from "../lib/dom.js";
import { state } from "../state.js";

const RULES = [
  [
    "key",
    "Logical record key",
    "Choose the ID of one business record. Exact repeated rows can be collapsed; different payloads with the same ID require review.",
    true,
  ],
  [
    "amount",
    "Amount",
    "Use one currency throughout the export. Dollars accept two decimals; cents must be integers.",
    true,
  ],
  [
    "group",
    "Break down by",
    "Optional. Group the checked total by a column such as category, region or customer.",
    false,
  ],
  [
    "status",
    "Eligibility status",
    "Optional. Include only one explicitly selected status; leave unmapped to include every record.",
    false,
  ],
];
export function steps(active) {
  return el(
    "ol",
    { class: "wizard-steps", "aria-label": "Investigation steps" },
    ...["Source", "Business rules", "Review", "Results"].map((name, index) =>
      el(
        "li",
        {
          class: index === active ? "active" : index < active ? "complete" : "",
          "aria-current": index === active ? "step" : undefined,
        },
        el(
          "span",
          { class: "step-number" },
          index < active ? "✓" : String(index + 1).padStart(2, "0"),
        ),
        name,
      ),
    ),
  );
}
export function issueBox(ctx) {
  const issue = state.issues;
  if (!issue) return null;
  return el(
    "section",
    { class: "issue-box", id: "error", role: "alert", tabindex: "-1" },
    el(
      "div",
      { class: "panel-heading" },
      el(
        "div",
        {},
        el("p", { class: "eyebrow" }, "REVIEW NEEDED"),
        el("h2", {}, "Let’s fix this before publishing a result."),
      ),
      icon("alert"),
    ),
    el("p", {}, issue.message),
    issue.hint && el("p", { class: "muted" }, issue.hint),
    issue.issues?.length
      ? el(
          "ul",
          { class: "issue-list" },
          ...issue.issues.map((i) =>
            el(
              "li",
              {},
              `${i.row ? "Record " + i.row + (i.column ? " · " + i.column : "") : i.field || "Contract"}: ${i.message}`,
            ),
          ),
        )
      : null,
    el(
      "div",
      { class: "actions" },
      state.draft?.profile &&
        issue.issues?.some((i) => i.row > 1) &&
        button(
          "Inspect affected records",
          () => {
            state.previewRows = [
              ...new Set(issue.issues.map((i) => i.row).filter((n) => n > 1)),
            ];
            state.draft.stage = 0;
            state.previewOffset = 0;
            ctx.render();
            ctx.preview();
          },
          "secondary",
        ),
      issue.issues?.length &&
        button(
          "Download issue list",
          () =>
            download(
              JSON.stringify(
                {
                  message: issue.message,
                  hint: issue.hint,
                  issues: issue.issues,
                  source_sha256: state.draft?.profile?.sha256,
                },
                null,
                2,
              ),
              "verifyops-issues.json",
            ),
          "quiet",
        ),
      button(
        "Dismiss",
        () => {
          state.issues = null;
          ctx.render();
        },
        "quiet",
      ),
    ),
  );
}
function filePreview(ctx) {
  const draft = state.draft,
    profile = draft.profile;
  const search = el("input", {
    type: "search",
    value: state.previewSearch,
    placeholder: "Find a value in this file",
    "aria-label": "Search source records",
    maxlength: "120",
  });
  const preview = el(
    "div",
    { id: "preview-content" },
    table(
      ["Record", ...profile.columns.map((c) => c.name)],
      profile.preview.map((r) => [r.row, ...r.cells]),
      { label: "Source preview, first ten records" },
    ),
  );
  preview.firstChild.classList.add("data-preview");
  const count = el(
      "span",
      { id: "preview-count" },
      "First " + profile.preview.length + " of " + profile.rows + " records",
    ),
    pagination = el(
      "div",
      { class: "actions" },
      button(
        "← Previous",
        () => {
          state.previewOffset = Math.max(0, state.previewOffset - 25);
          ctx.preview();
        },
        "quiet",
        { id: "preview-prev", disabled: true },
      ),
      button(
        "Next →",
        () => {
          state.previewOffset += 25;
          ctx.preview();
        },
        "quiet",
        { id: "preview-next", disabled: profile.rows <= 25 },
      ),
    );
  let timer;
  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      state.previewSearch = search.value;
      state.previewOffset = 0;
      state.previewRows = [];
      ctx.preview();
    }, 300);
  });
  return el(
    "section",
    { class: "spaced" },
    el(
      "div",
      { class: "panel-heading" },
      el(
        "div",
        {},
        el("h2", {}, "Inspect the source."),
        el(
          "p",
          { class: "hint" },
          "Record numbers include the header as record 1. No source rows are changed.",
        ),
      ),
      badge(profile.columns.length + " columns"),
    ),
    el(
      "div",
      { class: "preview-controls" },
      el("div", { class: "search-field" }, icon("search"), search),
      state.previewRows.length
        ? button(
            "Show all records",
            () => {
              state.previewRows = [];
              state.previewOffset = 0;
              ctx.preview();
            },
            "secondary",
          )
        : el("span", {}, "Scroll horizontally to inspect every field"),
    ),
    preview,
    el("div", { class: "preview-controls" }, count, pagination),
    el(
      "details",
      {},
      el("summary", {}, "Column quality & suggested types"),
      table(
        ["Column", "Missing", "Unique values", "Numeric values", "Example"],
        profile.columns.map((c) => [
          c.name,
          c.missing,
          c.distinct,
          c.numeric + " / " + profile.rows,
          c.samples[0] || "(empty)",
        ]),
        { label: "Column quality" },
      ),
    ),
  );
}
function source(ctx) {
  const draft = state.draft;
  const input = el("input", {
    type: "file",
    id: "file",
    accept: ".csv,text/csv",
    disabled: state.busy,
    "aria-label": "Choose a CSV file",
    onchange: (e) => {
      if (e.target.files[0]) ctx.loadFile(e.target.files[0]);
    },
  });
  const dropzone = el(
    "div",
    { class: "dropzone", id: "dropzone" },
    el("div", { class: "upload-mark" }, icon("upload")),
    el("h3", {}, "Drop your transaction CSV here."),
    el("p", { class: "hint" }, "Or choose a file from your device."),
    input,
    el("p", { class: "hint" }, "UTF-8 CSV · Up to 400 KB · 5,000 records"),
  );
  for (const name of ["dragover", "dragenter"])
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      if (!state.busy) dropzone.classList.add("dragging");
    });
  dropzone.addEventListener("dragleave", () =>
    dropzone.classList.remove("dragging"),
  );
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragging");
    if (state.busy) return;
    if (event.dataTransfer.files.length !== 1) {
      ctx.problem("Choose one CSV file at a time.");
      return;
    }
    ctx.loadFile(event.dataTransfer.files[0]);
  });
  const project = el(
    "select",
    { id: "project-select" },
    el("option", { value: "" }, "Unassigned"),
    ...state.projects.map((p) =>
      el(
        "option",
        { value: p.id, selected: p.id === draft.projectId },
        p.name + (p.storage === "cloud" ? " · Account" : " · This device"),
      ),
    ),
  );
  project.addEventListener("change", () => {
    draft.projectId = project.value;
    draft.dirty = true;
  });
  const name = el("input", {
    id: "investigation-title",
    value: draft.title,
    maxlength: "100",
    autocomplete: "off",
  });
  name.addEventListener("input", () => {
    draft.title = name.value;
    draft.dirty = true;
  });
  return el(
    "section",
    { class: "panel" },
    el(
      "div",
      { class: "panel-heading" },
      el(
        "div",
        {},
        el("h2", {}, "Start with the data behind the metric."),
        el(
          "p",
          { class: "hint" },
          "We’ll inspect the file before you choose the calculation.",
        ),
      ),
      draft.sourceKind === "sample" && badge("Sample data"),
    ),
    el(
      "div",
      { class: "upload-grid" },
      el(
        "div",
        {},
        dropzone,
        draft.filename &&
          el(
            "div",
            { class: "file-summary spaced", id: "file-info" },
            icon("file"),
            el(
              "div",
              {},
              el("strong", {}, draft.filename),
              el(
                "p",
                {},
                draft.profile && draft.csv
                  ? `${draft.profile.rows} records · ${draft.profile.columns.length} columns · Ready to map`
                  : state.busy
                    ? "Inspecting the selected file…"
                    : "Review file issues before continuing",
              ),
            ),
            draft.profile && icon("check"),
          ),
      ),
      el(
        "aside",
        { class: "help-card" },
        el("h3", {}, "What works well here"),
        el(
          "p",
          {},
          "Transaction, payment or event exports with a logical record ID and a numeric amount.",
        ),
        el(
          "ul",
          {},
          el("li", {}, "One named header row."),
          el("li", {}, "Plain numbers, with no currency symbols."),
          el("li", {}, "Only data you are authorized to share."),
        ),
        button("Use the sample export", ctx.sample, "secondary", {
          disabled: state.busy,
        }),
        link("Download CSV template ↗", "/api/uploads/template", "text-link", {
          download: "verifyops-template.csv",
        }),
      ),
    ),
    draft.profile && draft.csv && filePreview(ctx),
    el(
      "div",
      { class: "form-grid" },
      field(
        "Investigation name",
        name,
        "Use a name you’ll recognize when you return.",
      ),
      field(
        "Project",
        project,
        "Optional. Projects are saved only after you confirm a storage choice.",
      ),
    ),
    el(
      "div",
      { class: "callout" },
      icon("shield"),
      el(
        "p",
        {},
        "Your selected file is sent to VerifyOps for bounded processing. It stays out of saved history unless you explicitly save it. Remove unnecessary confidential or personal fields before uploading.",
      ),
    ),
    el(
      "div",
      { class: "wizard-footer" },
      link([icon("back"), "Workspace"], "/workspace", "quiet"),
      button(
        ["Review business rules", icon("arrow")],
        () => ctx.advance(1),
        "primary",
        {
          id: "review-rules",
          disabled: !draft.profile || !draft.csv || state.busy,
        },
      ),
    ),
  );
}
function rules(ctx) {
  const draft = state.draft,
    profile = draft.profile;
  const mappings = RULES.map(([key, label, hint, required]) => {
    const select = el(
      "select",
      { id: "mapping-" + key, "data-mapping": key, required },
      el("option", { value: "" }, required ? "Choose a column…" : "None"),
      ...profile.columns.map((c) =>
        el(
          "option",
          { value: c.id, selected: draft.mapping[key] === c.id },
          c.name,
        ),
      ),
    );
    select.addEventListener("change", () => {
      if (select.value) draft.mapping[key] = select.value;
      else delete draft.mapping[key];
      if (key === "status" && !select.value)
        delete draft.options.eligible_status;
      draft.report = null;
      draft.dirty = true;
      ctx.render();
    });
    return field(label + (required ? " *" : ""), select, hint);
  });
  const unit = el(
    "select",
    { id: "unit", "data-option": "unit" },
    el(
      "option",
      { value: "dollars", selected: draft.options.unit !== "cents" },
      "Dollars · up to 2 decimals",
    ),
    el(
      "option",
      { value: "cents", selected: draft.options.unit === "cents" },
      "Integer cents",
    ),
  );
  unit.addEventListener("change", () => {
    draft.options.unit = unit.value;
    draft.report = null;
    draft.dirty = true;
  });
  const options = [
    field(
      "Source amount unit",
      unit,
      "The final report uses dollars and exact integer cents.",
    ),
  ];
  if (draft.mapping.status) {
    const status = el("input", {
      id: "eligible-status",
      "data-option": "eligible_status",
      value: draft.options.eligible_status || "",
      maxlength: "120",
      placeholder: "e.g. completed",
    });
    status.addEventListener("input", () => {
      draft.options.eligible_status = status.value;
      draft.report = null;
      draft.dirty = true;
    });
    options.push(
      field(
        "Include only this status *",
        status,
        "Case-sensitive after trimming surrounding whitespace. Every other status is excluded.",
      ),
    );
  }
  const reported = el("input", {
    id: "reported-total",
    "data-option": "reported_total",
    value: draft.options.reported_total || "",
    inputmode: "decimal",
    maxlength: "30",
    placeholder: "e.g. 325.50",
  });
  reported.addEventListener("input", () => {
    if (reported.value) draft.options.reported_total = reported.value;
    else delete draft.options.reported_total;
    draft.report = null;
    draft.dirty = true;
  });
  options.push(
    field(
      "Reported total to compare · optional",
      reported,
      "Enter the dashboard or report total in dollars. Leave blank to establish a checked baseline.",
    ),
  );
  const form = el(
    "form",
    {
      id: "form",
      onsubmit: (event) => {
        event.preventDefault();
        ctx.advance(2);
      },
    },
    el("div", { class: "form-grid" }, mappings),
    el("hr", { class: "rule" }),
    el("div", { class: "form-grid" }, options),
    el(
      "div",
      { class: "wizard-footer" },
      button(
        [icon("back"), "Back to source"],
        () => ctx.advance(0),
        "secondary",
      ),
      el(
        "button",
        { class: "primary", type: "submit", id: "review-definition" },
        "Review definition",
        icon("arrow"),
      ),
    ),
  );
  return el(
    "section",
    { class: "panel", id: "contract" },
    el(
      "div",
      { class: "panel-heading" },
      el(
        "div",
        {},
        el("h2", {}, "Tell us what one correct record means."),
        el(
          "p",
          { class: "hint" },
          "Suggested mappings are starting points. Confirm every business rule.",
        ),
      ),
      badge(draft.filename),
    ),
    form,
  );
}
export function definition(draft) {
  const name = (key) =>
    draft.profile.columns.find((c) => c.id === draft.mapping[key])?.name;
  return el(
    "div",
    { class: "definition" },
    "Sum ",
    el("code", {}, name("amount")),
    " as ",
    el(
      "strong",
      {},
      draft.options.unit === "cents" ? "integer cents" : "dollars",
    ),
    ", keeping one exact delivery per ",
    el("code", {}, name("key")),
    ". ",
    draft.mapping.status
      ? [
          "Include records where ",
          el("code", {}, name("status")),
          " is ",
          el("strong", {}, draft.options.eligible_status),
          ". ",
        ]
      : "Include every status. ",
    draft.mapping.group
      ? ["Break down the total by ", el("code", {}, name("group")), "."]
      : "Return one overall total.",
  );
}
function review(ctx) {
  const draft = state.draft,
    confirm = el("input", { type: "checkbox", id: "confirm-rules" });
  const run = el(
    "button",
    { type: "submit", class: "primary", id: "analyze", disabled: true },
    "Run verification",
    icon("arrow"),
  );
  confirm.addEventListener("change", () => {
    run.disabled = !confirm.checked;
  });
  return el(
    "section",
    { class: "panel" },
    el("p", { class: "eyebrow" }, "CONFIRM THE SCOPE"),
    el("h2", { class: "spaced" }, "Here is the metric we’ll verify."),
    definition(draft),
    el(
      "div",
      { class: "form-grid" },
      el(
        "div",
        {},
        el("p", { class: "eyebrow" }, "SOURCE"),
        el("p", { class: "spaced" }, draft.filename),
        el(
          "p",
          { class: "hint" },
          draft.profile.rows +
            " records · " +
            draft.profile.columns.length +
            " columns",
        ),
      ),
      el(
        "div",
        {},
        el("p", { class: "eyebrow" }, "REPORTED TOTAL"),
        el(
          "p",
          { class: "spaced" },
          draft.options.reported_total
            ? "$" + draft.options.reported_total
            : "Not provided · establish a checked baseline",
        ),
        el(
          "p",
          { class: "hint" },
          "Changing the definition will require a new verification.",
        ),
      ),
    ),
    el(
      "div",
      { class: "callout" },
      icon("help"),
      el(
        "p",
        {},
        "Only exact repeated rows are collapsed. Different records sharing a key stop the run for clarification. The result checks your selected contract; it does not infer unstated business rules or update a warehouse.",
      ),
    ),
    el(
      "form",
      {
        onsubmit: (event) => {
          event.preventDefault();
          if (confirm.checked) ctx.run();
        },
      },
      el(
        "label",
        { class: "checkbox spaced" },
        confirm,
        "I reviewed the key, amount, status and currency assumptions. These rules describe the metric I want to check.",
      ),
      el(
        "div",
        { class: "wizard-footer" },
        button([icon("back"), "Edit rules"], () => ctx.advance(1), "secondary"),
        run,
      ),
    ),
  );
}
const STAGES = [
  [
    "source",
    "Inspect source records",
    "Validate the file structure and input bounds.",
  ],
  [
    "contract",
    "Validate the business contract",
    "Check amounts, logical keys and conflicting records.",
  ],
  [
    "reference",
    "Compute an independent reference",
    "Aggregate eligible unique records in exact integer cents.",
  ],
  [
    "sql",
    "Execute the generated SQL",
    "Run the declared contract in a separate in-memory database.",
  ],
  [
    "reconcile",
    "Reconcile both calculations",
    "Require the grouped SQL output and reference to agree.",
  ],
  [
    "report",
    "Prepare the checked report",
    "Publish findings, calculation scope and exportable evidence.",
  ],
];
export function processing(ctx) {
  return el(
    "section",
    { class: "panel", "aria-busy": "true" },
    el(
      "div",
      { class: "panel-heading" },
      el(
        "div",
        {},
        el("h2", {}, "Checking the number from both sides."),
        el(
          "p",
          { class: "hint", role: "status", id: "processing-status" },
          "Waiting for observed verification stages…",
        ),
      ),
      badge("Verification in progress"),
    ),
    el(
      "div",
      { class: "progress-list" },
      ...STAGES.map(([id, name, description]) =>
        el(
          "div",
          {
            class: "progress-stage",
            "data-stage": id,
            "data-state": "pending",
          },
          el("span", { class: "stage-icon", "aria-hidden": "true" }, "·"),
          el("div", {}, el("h3", {}, name), el("p", {}, description)),
          el("span", { class: "sr-only stage-state" }, "Pending"),
        ),
      ),
    ),
    el(
      "div",
      { class: "wizard-footer" },
      el(
        "p",
        { class: "hint" },
        "Progress reflects server events. Your source file is never modified.",
      ),
      button("Stop waiting", ctx.stop, "secondary"),
    ),
  );
}
export function intake(ctx) {
  const draft = state.draft;
  return el(
    "div",
    {},
    title(
      "NEW INVESTIGATION",
      draft.title === "Untitled investigation"
        ? "Start with the source."
        : draft.title,
      "A guided path from your export to an independently checked result.",
      [
        link("Watch upload demo", "/uploads/recording.html", "quiet"),
        button("Save draft", ctx.save, "secondary", {
          disabled: !draft.csv || state.busy,
        }),
        button("Clear workspace", ctx.clear, "quiet", {
          id: "clear",
          disabled: state.busy,
        }),
      ],
    ),
    steps(draft.stage),
    issueBox(ctx),
    draft.stage === 0
      ? source(ctx)
      : draft.stage === 1
        ? rules(ctx)
        : draft.stage === 2
          ? review(ctx)
          : processing(ctx),
  );
}
