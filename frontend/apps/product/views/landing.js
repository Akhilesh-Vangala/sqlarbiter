import { el, link, button, icon, badge } from "../lib/dom.js";

export function brand(href = "/") {
  return link(
    [
      el("span", { class: "brand-symbol", "aria-hidden": "true" }, "v/"),
      "VerifyOps",
    ],
    href,
    "brand",
    { id: "brand" },
  );
}

export function landing(ctx) {
  const example = el(
    "div",
    {
      class: "hero-proof",
      "aria-label": "Illustrative sample report, not a report from your data",
    },
    el(
      "div",
      { class: "proof-top" },
      el("span", {}, "REVENUE RECONCILIATION"),
      badge("Sample report"),
    ),
    el(
      "div",
      { class: "proof-body" },
      el("p", { class: "eyebrow" }, "THE VERIFIED TOTAL"),
      el("strong", { class: "proof-amount" }, "$200.00"),
      el(
        "p",
        { class: "hint" },
        "Computed from eligible, unique transactions.",
      ),
      el(
        "div",
        { class: "proof-rows" },
        el("div", {}, "Reported total", el("strong", {}, "$325.50")),
        el("div", {}, "Duplicate delivery impact", el("strong", {}, "$125.50")),
      ),
      ...[
        "Exact duplicate deliveries identified",
        "Selected eligibility rules applied",
        "SQL and independent reference agree",
      ].map((text) => el("div", { class: "proof-line" }, icon("check"), text)),
    ),
    el(
      "div",
      { class: "proof-footer" },
      "An inspectable result. A clear reason. Evidence you can keep.",
    ),
  );
  return el(
    "div",
    { class: "marketing" },
    el(
      "header",
      { class: "marketing-header" },
      brand(),
      el(
        "nav",
        { "aria-label": "Main navigation" },
        link("How it works", "#how-it-works"),
        link("Documentation", "/workspace/guide"),
        link("Open workspace", "/workspace", "primary"),
      ),
    ),
    el(
      "main",
      { id: "main", class: "marketing-main" },
      el(
        "section",
        { class: "marketing-hero" },
        el(
          "div",
          {},
          badge("DATA RELIABILITY, WITH EVIDENCE", "outline"),
          el("h1", {}, "Find the number you can stand behind."),
          el(
            "p",
            { class: "lead" },
            "Turn a suspicious metric into a checked result. Bring a transaction export, define what counts, and see exactly where the numbers diverge.",
          ),
          el(
            "div",
            { class: "actions" },
            link(
              ["Investigate your data", icon("arrow")],
              "/uploads?new=1",
              "primary",
            ),
            button("Try a sample file", ctx.sample, "secondary"),
          ),
          el(
            "p",
            { class: "hint" },
            "Start without an account. Your file is processed only when you run a check.",
          ),
        ),
        example,
      ),
      el(
        "div",
        { class: "marketing-divider" },
        ...[
          ["shield", "Independently checked totals"],
          ["file", "Your rules, made explicit"],
          ["download", "Downloadable evidence"],
        ].map(([name, text]) => el("span", {}, icon(name), text)),
      ),
      el(
        "section",
        { id: "how-it-works", class: "marketing-section" },
        el("p", { class: "eyebrow" }, "FROM QUESTION TO CONFIDENCE"),
        el("h2", {}, "A careful investigation. A clear next step."),
        el(
          "p",
          {},
          "You stay in control of the metric definition. Every result includes the data scope, calculation and checks that produced it.",
        ),
        el(
          "div",
          { class: "marketing-steps" },
          ...[
            [
              "01 / BRING THE SOURCE",
              "Start with your export.",
              "Upload a data file and inspect its records. Find missing values, review column types and see the source before making assumptions.",
            ],
            [
              "02 / DEFINE WHAT COUNTS",
              "Make the metric precise.",
              "Choose the record key, amount and eligibility rules. Conflicting records are surfaced for review, never silently repaired.",
            ],
            [
              "03 / REVIEW THE EVIDENCE",
              "Understand the difference.",
              "Compare the verified total to the reported figure. Inspect duplicate impact and grouped results, then export a report or save your work.",
            ],
          ].map(([step, heading, text]) =>
            el(
              "article",
              {},
              el("span", { class: "step-label" }, step),
              el("h3", {}, heading),
              el("p", {}, text),
            ),
          ),
        ),
      ),
      el(
        "section",
        { class: "marketing-section" },
        el("p", { class: "eyebrow" }, "BUILT FOR REVIEW"),
        el("h2", {}, "Evidence comes with the answer."),
        el(
          "p",
          {},
          "An independently recomputed reference must agree with the generated SQL. The result is conditional on your declared rules: it does not guess your business definition or apply changes to a warehouse.",
        ),
        el(
          "div",
          { class: "marketing-steps" },
          ...[
            [
              "Exact arithmetic",
              "Amounts are reconciled in integer cents, with malformed values highlighted before a result is published.",
            ],
            [
              "Recoverable work",
              "Choose whether to save a draft or report on this device. Keep a portable backup, and resume without starting over.",
            ],
            [
              "Honest boundaries",
              "The public workspace uses rule-based verification. Live AI reasoning, warehouse writes and monitored customer operations remain separate capabilities.",
            ],
          ].map(([heading, text]) =>
            el("article", {}, el("h3", {}, heading), el("p", {}, text)),
          ),
        ),
      ),
      el(
        "section",
        { class: "marketing-cta" },
        el(
          "div",
          {},
          el("h2", {}, "Bring the metric that doesn’t add up."),
          el(
            "p",
            {},
            "Start with a file you’re authorized to share. We’ll make the checks explicit.",
          ),
        ),
        link(
          ["Start an investigation", icon("arrow")],
          "/uploads?new=1",
          "primary",
        ),
      ),
      el(
        "footer",
        { class: "marketing-footer" },
        el("span", {}, "VerifyOps · Evidence-backed data reliability"),
        el(
          "div",
          { class: "actions" },
          link("Data handling", "/workspace/settings"),
          link("Engineering demo", "/demo"),
          link(
            "GitHub ↗",
            "https://github.com/Akhilesh-Vangala/verifyops",
            "",
            { target: "_blank", rel: "noreferrer" },
          ),
        ),
      ),
    ),
  );
}
