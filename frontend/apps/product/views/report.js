import {
  el,
  title,
  button,
  link,
  icon,
  badge,
  money,
  table,
  download,
  modal,
  notify,
} from "../lib/dom.js";
import { state } from "../state.js";
import { steps, definition } from "./intake.js";

function finding(report) {
  const s = report.summary,
    impact = s.raw_eligible_total_cents - s.verified_total_cents;
  if (s.reported_total_cents !== null && s.difference_cents === 0)
    return [
      "The reported total matches your selected rules.",
      "The supplied reported figure agrees with the independently checked total. This confirms the declared calculation, not every possible business definition.",
    ];
  if (
    s.reported_total_cents !== null &&
    s.reported_total_cents === s.raw_eligible_total_cents &&
    impact !== 0
  )
    return [
      "Duplicate deliveries explain this difference under your rules.",
      `${s.duplicate_deliveries} exact repeated ${s.duplicate_deliveries === 1 ? "delivery was" : "deliveries were"} found. The ${money(Math.abs(impact))} duplicate impact reconciles the raw eligible sum with the verified total. Confirm that the selected key represents one logical business record.`,
    ];
  if (s.reported_total_cents !== null)
    return [
      "The reported total differs from the checked result.",
      `The verified total is ${money(s.difference_cents, true)} relative to the reported figure. Duplicate impact is ${money(impact, true)}. Review the definition and source; this narrow contract does not establish the cause of any remaining difference.`,
    ];
  if (s.duplicate_deliveries)
    return [
      "Repeated deliveries change how this metric should be counted.",
      `${s.duplicate_deliveries} exact repeated ${s.duplicate_deliveries === 1 ? "delivery was" : "deliveries were"} collapsed under the selected key. Their impact on eligible amounts is ${money(impact)}. Add the reported total to check whether this accounts for the discrepancy you’re investigating.`,
    ];
  return [
    "You now have an independently checked baseline.",
    "The generated SQL and separate reference computation agree. Add a reported total to compare against this baseline, or export the calculation and evidence for review.",
  ];
}
function chart(rows) {
  const selected = [...rows]
    .sort((a, b) => Math.abs(b.total_cents) - Math.abs(a.total_cents))
    .slice(0, 8);
  const maximum = Math.max(...selected.map((r) => Math.abs(r.total_cents)), 1);
  const negative = selected.some((r) => r.total_cents < 0);
  const ns = "http://www.w3.org/2000/svg";
  return el(
    "div",
    {
      class: "segment-chart",
      role: "list",
      "aria-label": "Largest verified segments by absolute value",
    },
    ...selected.map((r) => {
      const svg = document.createElementNS(ns, "svg");
      svg.setAttribute("viewBox", "0 0 100 12");
      svg.setAttribute("preserveAspectRatio", "none");
      svg.setAttribute("aria-hidden", "true");
      const width = (Math.abs(r.total_cents) / maximum) * (negative ? 48 : 100);
      const rect = document.createElementNS(ns, "rect");
      for (const [k, v] of Object.entries({
        x: negative ? (r.total_cents < 0 ? 50 - width : 50) : 0,
        y: 2,
        width,
        height: 8,
        rx: 1,
        fill: "#444",
      }))
        rect.setAttribute(k, String(v));
      svg.append(rect);
      if (negative) {
        const axis = document.createElementNS(ns, "line");
        for (const [k, v] of Object.entries({
          x1: 50,
          x2: 50,
          y1: 0,
          y2: 12,
          stroke: "#aaa",
          "stroke-width": 0.5,
        }))
          axis.setAttribute(k, String(v));
        svg.append(axis);
      }
      return el(
        "div",
        { class: "segment-row", role: "listitem" },
        el(
          "span",
          { class: "segment-label", title: r.segment || "(empty)" },
          r.segment || "(empty)",
        ),
        svg,
        el("span", { class: "segment-value" }, money(r.total_cents)),
      );
    }),
  );
}

function overview(report, ctx) {
  const main = el(
    "section",
    { class: "panel" },
    el(
      "div",
      { class: "panel-heading" },
      el(
        "div",
        {},
        el("h2", {}, "Where the verified total comes from"),
        el(
          "p",
          { class: "hint" },
          "Largest segments by absolute value. Exact amounts remain in the table.",
        ),
      ),
      badge(report.results.length + " segments"),
    ),
    report.results.length
      ? chart(report.results)
      : el(
          "p",
          { class: "muted" },
          "No records satisfy the selected eligibility rule. The verified total is zero.",
        ),
  );
  let offset = 0,
    descending = true;
  const body = el("div", {}),
    label = el("span", {});
  const prev = button(
      "← Previous",
      () => {
        offset = Math.max(0, offset - 10);
        draw();
      },
      "quiet",
    ),
    next = button(
      "Next →",
      () => {
        offset += 10;
        draw();
      },
      "quiet",
    );
  function draw() {
    const sorted = [...report.results].sort((a, b) =>
      descending
        ? b.total_cents - a.total_cents
        : a.total_cents - b.total_cents,
    );
    body.replaceChildren(
      table(
        ["Segment", "Verified amount", "Exact cents"],
        sorted
          .slice(offset, offset + 10)
          .map((r) => [
            r.segment || "(empty)",
            money(r.total_cents),
            String(r.total_cents),
          ]),
        { label: "Verified grouped results" },
      ),
    );
    label.textContent = sorted.length
      ? `${offset + 1}–${Math.min(offset + 10, sorted.length)} of ${sorted.length}`
      : "0 segments";
    prev.disabled = offset === 0;
    next.disabled = offset + 10 >= sorted.length;
  }
  draw();
  main.append(
    el(
      "div",
      { class: "preview-controls" },
      el("span", {}, "All segments"),
      button(
        "Sort amount ↕",
        () => {
          descending = !descending;
          offset = 0;
          draw();
        },
        "quiet",
      ),
    ),
    body,
    el("div", { class: "pager" }, label, prev, next),
  );
  const sidebar = el(
    "aside",
    { class: "stack" },
    el(
      "section",
      { class: "panel" },
      el("h2", {}, "What to do next"),
      el(
        "div",
        { class: "next-action" },
        el(
          "h3",
          {},
          report.summary.reported_total_cents === null
            ? "Compare with the reported figure"
            : "Review the metric definition",
        ),
        el(
          "p",
          {},
          report.summary.reported_total_cents === null
            ? "Add the dashboard total to quantify the discrepancy. Your source and mappings stay available."
            : "Confirm the logical key, eligibility status and amount unit before changing a downstream report.",
        ),
        button("Edit rules & rerun", () => ctx.advance(1), "secondary", {
          class: "secondary spaced",
        }),
      ),
      el(
        "div",
        { class: "next-action" },
        el("h3", {}, "Share evidence, not just a number"),
        el(
          "p",
          {},
          "Download the checked aggregate and evidence report. The SQL targets a normalized input table and needs adaptation before warehouse use.",
        ),
        button("Download evidence", () => ctx.exportReport(), "quiet", {
          id: "download-json-side",
        }),
      ),
    ),
    el(
      "div",
      { class: "help-card" },
      el("h3", {}, "The boundary of this result"),
      el(
        "p",
        {},
        "The calculation is verified against the rules you supplied. It does not infer missing business definitions, certify the source system or deploy a warehouse repair.",
      ),
    ),
  );
  return el("div", { class: "result-grid" }, main, sidebar);
}
function quality(report, ctx) {
  const q = report.data_quality || {},
    s = report.summary;
  return el(
    "section",
    { class: "panel" },
    el(
      "div",
      { class: "panel-heading" },
      el(
        "div",
        {},
        el("h2", {}, "Records that shaped the result"),
        el(
          "p",
          { class: "hint" },
          "Nothing is silently imputed. A conflicting key or invalid amount withholds the entire result.",
        ),
      ),
    ),
    table(
      ["Check", "Observed", "How it affects the metric"],
      [
        [
          "Source records",
          s.source_rows,
          "Every parsed record in the supplied file.",
        ],
        [
          "Unique logical records",
          s.unique_records,
          "One original payload per selected logical key.",
        ],
        [
          "Exact duplicate deliveries",
          s.duplicate_deliveries,
          "Repeated identical payloads excluded from the canonical calculation.",
        ],
        [
          "Eligible unique records",
          s.eligible_unique_records ?? "See contract",
          "Records retained after the declared eligibility rule.",
        ],
        [
          "Excluded source records",
          s.excluded_source_rows ?? "See contract",
          "Records whose status does not match the selected value.",
        ],
        [
          "Duplicate impact",
          money(
            q.duplicate_impact_cents ??
              s.raw_eligible_total_cents - s.verified_total_cents,
          ),
          "Raw eligible sum minus verified total; may be negative for repeated refunds.",
        ],
      ],
      { label: "Data-quality accounting" },
    ),
    el("h3", { class: "spaced" }, "Duplicate delivery examples"),
    q.duplicates?.length
      ? table(
          ["Repeated record", "Original record", "Eligible", "Impact"],
          q.duplicates.map((r) => [
            r.row,
            r.original_row,
            r.eligible ? "Yes" : "No",
            money(r.impact_cents),
          ]),
          { label: "Duplicate record locations" },
        )
      : el(
          "p",
          { class: "hint spaced" },
          "No exact duplicate deliveries were found under this key.",
        ),
    q.duplicate_examples_capped &&
      el(
        "p",
        { class: "hint spaced" },
        "Showing the first 20 examples. Summary counts cover the complete supplied file.",
      ),
    state.draft.csv &&
      button(
        "Inspect the source file",
        () => {
          state.draft.stage = 0;
          state.previewRows = [];
          ctx.render();
        },
        "secondary",
        { class: "secondary spaced" },
      ),
  );
}
function calculation(report) {
  const bindings = Object.entries(report.column_bindings).map(([id, name]) => [
    id,
    name,
  ]);
  return el(
    "div",
    { class: "stack" },
    el(
      "section",
      { class: "panel" },
      el("h2", {}, "Independent checks"),
      ...Object.entries(report.checks).map(([name, passed]) =>
        el(
          "div",
          { class: "check-row" },
          icon(passed ? "check" : "alert"),
          el(
            "div",
            {},
            el("strong", {}, name.replaceAll("_", " ")),
            el(
              "p",
              {},
              passed
                ? "Passed for this supplied source and contract."
                : "Failed; do not treat this result as verified.",
            ),
          ),
        ),
      ),
    ),
    el(
      "section",
      { class: "panel" },
      el(
        "div",
        { class: "panel-heading" },
        el(
          "div",
          {},
          el("h2", {}, "Generated contract SQL"),
          el(
            "p",
            { class: "hint" },
            "Runs against the normalized in-memory records table. This is not an automatic production dbt patch.",
          ),
        ),
        button(
          "Download SQL",
          () =>
            download(
              "-- SQLArbiter normalized contract query.\n-- Requires records with cN column bindings, __amount_cents and __eligible.\n-- Adapt to your warehouse and review before use.\n" +
                report.sql +
                "\n",
              "sqlarbiter-contract.sql",
              "text/plain",
            ),
          "secondary",
        ),
      ),
      el("pre", {}, report.sql),
      el("h3", { class: "spaced" }, "Source column bindings"),
      table(["Normalized column", "Source header"], bindings, {
        label: "SQL source bindings",
      }),
      el(
        "p",
        { class: "hint spaced" },
        "__amount_cents is the validated integer-cents amount. __eligible is 1 only when the declared status rule passes.",
      ),
    ),
  );
}
export function reportView(ctx) {
  const draft = state.draft,
    report = draft.report,
    summary = report.summary;
  const [heading, explanation] = finding(report),
    selected = state.reportTab || "overview";
  const tabs = el("div", {
    class: "tabs",
    role: "tablist",
    "aria-label": "Report sections",
  });
  for (const [id, name] of [
    ["overview", "Overview"],
    ["quality", "Data quality"],
    ["calculation", "SQL & checks"],
  ]) {
    const tab = button(
      name,
      () => {
        state.reportTab = id;
        ctx.render();
        document.getElementById("tab-" + id)?.focus();
      },
      "",
      {
        id: "tab-" + id,
        role: "tab",
        "aria-selected": selected === id,
        "aria-controls": "report-panel",
        tabindex: selected === id ? "0" : "-1",
      },
    );
    tab.addEventListener("keydown", (event) => {
      const ids = ["overview", "quality", "calculation"];
      if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        const index = ids.indexOf(id);
        state.reportTab =
          event.key === "Home"
            ? ids[0]
            : event.key === "End"
              ? ids[2]
              : ids[(index + (event.key === "ArrowRight" ? 1 : 2)) % 3];
        ctx.render();
        document.getElementById("tab-" + state.reportTab)?.focus();
      }
    });
    tabs.append(tab);
  }
  const evidence = el(
    "details",
    { id: "evidence" },
    el("summary", {}, "Complete evidence JSON"),
    el("pre", {}, JSON.stringify(report, null, 2)),
  );
  const copy = button(
    "Copy report summary",
    async () => {
      try {
        await navigator.clipboard.writeText(
          `${draft.title}\nVerified total: ${money(summary.verified_total_cents)}\nReported total: ${money(summary.reported_total_cents)}\nDifference: ${money(summary.difference_cents, true)}\n${explanation}\nSource SHA-256: ${report.source_sha256}`,
        );
        notify("Summary copied.");
      } catch {
        notify("Clipboard unavailable. Download the evidence report instead.");
      }
    },
    "secondary",
  );
  return el(
    "div",
    { id: "output" },
    title(
      "INVESTIGATION REPORT",
      draft.title || "Checked result",
      draft.filename + " · " + summary.source_rows + " source records",
      [
        button("Edit rules & rerun", () => ctx.advance(1), "secondary", {
          disabled: !draft.csv,
        }),
        button("Save investigation", ctx.save, "primary"),
        button("Clear workspace", ctx.clear, "quiet", { id: "clear" }),
      ],
    ),
    steps(3),
    el(
      "section",
      { class: "finding-hero" },
      el("p", { class: "eyebrow" }, "THE FINDING"),
      el("h2", {}, heading),
      el("p", {}, explanation),
      el(
        "span",
        { id: "verification" },
        badge(
          draft.restored && !draft.authentic
            ? "Saved copy · recheck authenticity"
            : "Independent checks passed",
        ),
      ),
    ),
    el(
      "div",
      { class: "stats", id: "summary" },
      ...[
        [
          "Verified total",
          money(summary.verified_total_cents),
          "Independent reference and SQL agree",
        ],
        [
          "Reported total",
          money(summary.reported_total_cents),
          "The figure you supplied for comparison",
        ],
        [
          "Adjustment to reported total",
          money(summary.difference_cents, true),
          "Verified minus reported; no changes applied",
        ],
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
    tabs,
    el(
      "div",
      {
        id: "report-panel",
        role: "tabpanel",
        "aria-labelledby": "tab-" + selected,
      },
      selected === "overview"
        ? overview(report, ctx)
        : selected === "quality"
          ? quality(report, ctx)
          : calculation(report),
    ),
    el(
      "section",
      { class: "panel spaced" },
      el(
        "div",
        { class: "panel-heading" },
        el(
          "div",
          {},
          el("h2", {}, "Keep the evidence with the decision."),
          el(
            "p",
            { class: "hint" },
            "Exports contain this checked report. They do not write to your warehouse.",
          ),
        ),
        badge(
          draft.storage === "memory"
            ? "Not saved"
            : draft.storage === "cloud"
              ? "Account copy"
              : "Saved on this device",
        ),
      ),
      el(
        "div",
        { class: "actions" },
        button(
          [icon("download"), "Download evidence JSON"],
          ctx.exportReport,
          "secondary",
          { id: "download-json" },
        ),
        button(
          [icon("download"), "Download results CSV"],
          () =>
            download(
              report.csv,
              "sqlarbiter-results.csv",
              "text/csv;charset=utf-8",
            ),
          "primary",
          { id: "download-csv" },
        ),
        copy,
        button(
          "Inspect source & rules",
          () =>
            modal(
              "Source and definition",
              el(
                "div",
                {},
                el("p", {}, draft.filename),
                definition(draft),
                el(
                  "p",
                  { class: "mono spaced" },
                  "SHA-256 " + report.source_sha256,
                ),
                el("p", { class: "hint spaced" }, report.scope),
              ),
            ),
          "quiet",
        ),
      ),
      el(
        "div",
        { class: "report-source" },
        el("strong", {}, "Source fingerprint"),
        el("span", { class: "mono" }, report.source_sha256),
      ),
      evidence,
    ),
    el(
      "div",
      { class: "trust-strip" },
      el("span", {}, icon("shield"), "Explicit contract · exact cents"),
      el("span", {}, icon("check"), "Independent computation"),
      el("span", {}, icon("file"), "No warehouse writes"),
    ),
  );
}
