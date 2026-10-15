import {
  el,
  title,
  button,
  link,
  icon,
  badge,
  field,
  modal,
  notify,
  download,
} from "../lib/dom.js";
import { state } from "../state.js";
import { cloud } from "../lib/api.js";
import { saved } from "../lib/storage.js";

export function login(ctx) {
  if (!state.account?.enabled)
    return el(
      "div",
      {},
      title(
        "ACCOUNT",
        "A workspace without a forced sign-up.",
        "You can investigate a file and choose device-only saving right now.",
      ),
      el(
        "section",
        { class: "panel auth-card" },
        icon("account"),
        el("h2", { class: "spaced" }, "Cloud accounts aren’t connected yet."),
        el(
          "p",
          { class: "muted spaced" },
          "Cross-device accounts require a real authentication service and database. This deployment won’t simulate a successful login or cloud save.",
        ),
        el(
          "div",
          { class: "actions spaced" },
          link("Continue on this device", "/workspace", "primary"),
          link("Storage settings", "/workspace/settings", "secondary"),
        ),
      ),
    );
  let signUp = false;
  const content = el("div", {});
  function draw() {
    const email = el("input", {
      id: "account-email",
      type: "email",
      autocomplete: "email",
      required: true,
      maxlength: "254",
    });
    const password = el("input", {
      id: "account-password",
      type: "password",
      autocomplete: signUp ? "new-password" : "current-password",
      required: true,
      minlength: signUp ? "12" : "1",
      maxlength: "128",
    });
    const error = el("p", {
        class: "inline-error",
        role: "alert",
        hidden: true,
      }),
      status = el("p", { class: "hint", role: "status" });
    const submit = el(
      "button",
      { type: "submit", class: "primary" },
      signUp ? "Create account" : "Sign in",
    );
    const form = el(
      "form",
      {
        onsubmit: async (event) => {
          event.preventDefault();
          submit.disabled = true;
          error.hidden = true;
          status.textContent = signUp
            ? "Creating your account…"
            : "Signing in…";
          try {
            const value = await cloud(signUp ? "/sign-up" : "/sign-in", {
              email: email.value,
              password: password.value,
            });
            password.value = "";
            if (value.confirmation_required) {
              status.textContent =
                "Check your email to confirm the account, then return here to sign in. No investigation data has been saved.";
              submit.disabled = false;
              return;
            }
            await ctx.refreshAccount();
            notify("Signed in. Choose a storage destination when saving work.");
            ctx.go("/workspace");
          } catch (err) {
            error.textContent = err.message;
            error.hidden = false;
            status.textContent = "";
            submit.disabled = false;
          }
        },
      },
      field("Email", email),
      field(
        "Password",
        password,
        signUp
          ? "Use at least 12 characters. Your provider may enforce additional password rules."
          : undefined,
      ),
      error,
      status,
      submit,
    );
    content.replaceChildren(
      el("h2", {}, signUp ? "Create your account." : "Welcome back."),
      el(
        "p",
        { class: "hint spaced" },
        "Cloud storage uses your authenticated account. Your password is not stored by VerifyOps.",
      ),
      form,
      state.account.signup_enabled &&
        button(
          signUp ? "Already have an account? Sign in" : "Create an account",
          () => {
            signUp = !signUp;
            draw();
          },
          "quiet",
        ),
    );
  }
  draw();
  return el(
    "div",
    {},
    title(
      "ACCOUNT",
      "Keep your work across devices.",
      "Sign in to a configured cloud workspace. Saving source files remains an explicit choice.",
    ),
    el("section", { class: "panel auth-card" }, content),
  );
}
export function settings(ctx) {
  return el(
    "div",
    {},
    title(
      "WORKSPACE SETTINGS",
      "Know where your work lives.",
      "Storage and account status are explicit. Nothing is uploaded to cloud history without a save action.",
    ),
    el(
      "section",
      { class: "panel" },
      el(
        "div",
        { class: "panel-heading" },
        el("h2", {}, "Storage & account"),
        badge(state.user ? "Signed in" : "Device workspace"),
      ),
      el(
        "div",
        { class: "settings-row" },
        el(
          "div",
          {},
          el("h3", {}, "This device"),
          el(
            "p",
            {},
            "Opt-in saved investigations use this browser’s IndexedDB. They do not sync across devices and may be removed by browser cleanup. Export a backup before relying on them.",
          ),
        ),
        badge(
          state.entries.filter((e) => e.storage === "device").length + " saved",
        ),
      ),
      el(
        "div",
        { class: "settings-row" },
        el(
          "div",
          {},
          el("h3", {}, "Cloud account"),
          el(
            "p",
            {},
            state.user
              ? "Signed in as " +
                  state.user.email +
                  ". Account rows are isolated by authenticated ownership."
              : state.account?.enabled
                ? "The account provider is configured. Sign in to access cloud projects and saved investigations."
                : "Not connected. A Supabase Auth project and its RLS-protected database must be configured before cross-device storage becomes available.",
          ),
        ),
        state.user
          ? button("Sign out", ctx.signOut, "secondary")
          : link(
              state.account?.enabled ? "Sign in" : "View account status",
              "/workspace/login",
              "secondary",
            ),
      ),
      el(
        "div",
        { class: "settings-row" },
        el(
          "div",
          {},
          el("h3", {}, "Source retention"),
          el(
            "p",
            {},
            "Unsaved files and reports remain in memory. Device saving includes the source after consent. Cloud saving asks separately whether to retain the source; report-only copies can be reviewed but require re-uploading the file to rerun.",
          ),
        ),
        badge("Explicit choice"),
      ),
    ),
    el(
      "section",
      { class: "panel" },
      el("h2", {}, "Data controls"),
      el(
        "div",
        { class: "settings-row" },
        el(
          "div",
          {},
          el("h3", {}, "Export device history"),
          el(
            "p",
            {},
            "The backup includes saved source files, rules and reports. Keep it somewhere you trust.",
          ),
        ),
        button(
          "Export device backup",
          async () => {
            try {
              const entries = await saved.list(),
                projects = await saved.projects();
              download(
                JSON.stringify(
                  {
                    format: "verifyops-device-backup-v1",
                    exportedAt: new Date().toISOString(),
                    entries,
                    projects,
                  },
                  null,
                  2,
                ),
                "verifyops-device-backup.json",
              );
            } catch (error) {
              notify(error.message);
            }
          },
          "secondary",
        ),
      ),
      el(
        "div",
        { class: "settings-row" },
        el(
          "div",
          {},
          el("h3", {}, "Restore a device backup"),
          el(
            "p",
            {},
            "Move work to another browser without a cloud account. Sources are validated and reports authenticated; existing snapshots stay unchanged.",
          ),
        ),
        field(
          "VerifyOps JSON backup",
          el("input", {
            type: "file",
            id: "backup-file",
            accept: ".json,application/json",
            onchange: (event) => {
              const file = event.target.files[0];
              ctx.restoreBackup(file);
              event.target.value = "";
            },
          }),
        ),
      ),
      el(
        "div",
        { class: "settings-row" },
        el(
          "div",
          {},
          el("h3", {}, "Remove saved work from this device"),
          el(
            "p",
            {},
            "Deletes saved investigations and projects in this browser. Account data is managed separately from the investigations list.",
          ),
        ),
        button(
          "Delete device history",
          () => {
            const confirm = el("input", {
                type: "checkbox",
                id: "confirm-delete-history",
              }),
              action = button(
                "Delete device history",
                async () => {
                  try {
                    await saved.clear();
                    document.getElementById("dialog").close();
                    await ctx.refresh();
                    ctx.render();
                    notify("Saved device history removed.");
                  } catch (error) {
                    notify(error.message);
                  }
                },
                "danger",
                { disabled: true },
              );
            confirm.addEventListener("change", () => {
              action.disabled = !confirm.checked;
            });
            modal(
              "Delete this device’s saved work?",
              el(
                "div",
                {},
                el(
                  "p",
                  {},
                  "This cannot be undone. Export a backup first if you need these records. Account data and the active unsaved investigation are not deleted.",
                ),
                el(
                  "label",
                  { class: "checkbox spaced" },
                  confirm,
                  "I understand that the saved device records will be permanently removed.",
                ),
              ),
              [
                button(
                  "Cancel",
                  () => document.getElementById("dialog").close(),
                  "secondary",
                ),
                action,
              ],
            );
          },
          "danger",
        ),
      ),
    ),
    el(
      "section",
      { class: "panel" },
      el("h2", {}, "Calculation scope"),
      el(
        "div",
        { class: "settings-row" },
        el(
          "div",
          {},
          el("h3", {}, "Current public verification"),
          el(
            "p",
            {},
            "Declared key, amount, eligibility and grouping; exact cents; generated SQL plus an independent reference. Live AI interpretation and warehouse writes are unavailable in this workspace.",
          ),
        ),
        link("Read the guide", "/workspace/guide", "secondary"),
      ),
    ),
  );
}
export function guide() {
  return el(
    "div",
    {},
    title(
      "QUICK GUIDE",
      "A trustworthy result starts with a precise question.",
      "Use this workflow for transaction/event metric reconciliation. The business definition remains yours to confirm.",
    ),
    el(
      "div",
      { class: "guide-grid" },
      ...[
        [
          "1. Choose the right export",
          "Use a UTF-8 CSV with one named header row, up to 400 KB and 5,000 records. Include a logical record ID and numeric amount. Remove fields that aren’t needed for the investigation.",
        ],
        [
          "2. Set the logical grain",
          "The key must represent one business record. Two identical deliveries with the same key can be collapsed. Different payloads with one key stop the run, so you can fix the source or select a more precise ID.",
        ],
        [
          "3. Confirm eligibility and units",
          "Dollars accept at most two decimals; cents must be integers. Use one currency. Optional status filtering uses a case-sensitive match after trimming whitespace. All other statuses are excluded.",
        ],
        [
          "4. Compare and review",
          "Add a reported total in dollars to quantify a discrepancy. Inspect grouped results, duplicate impact and independent checks. A verified calculation is conditional on the contract and does not prove the source system is complete.",
        ],
        [
          "5. Save or export deliberately",
          "Nothing enters history automatically. Device saves require consent and remain in this browser. Connected cloud accounts can save reports with optional source retention. Backups contain business data; store them carefully.",
        ],
        [
          "6. Make a downstream decision",
          "Export results and evidence for review. Generated SQL targets a normalized records table and must be adapted to your warehouse. No production patch, dbt macro, code upload or arbitrary SQL is executed here.",
        ],
      ].map(([heading, text]) =>
        el(
          "article",
          { class: "panel" },
          el("h2", {}, heading),
          el("p", {}, text),
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
          el("h2", {}, "Try the deeper engineering workflows"),
          el(
            "p",
            { class: "hint" },
            "The original guided agent/SQL investigation and recording remain available separately.",
          ),
        ),
        link("Open guided demo ↗", "/demo", "secondary"),
      ),
      el(
        "div",
        { class: "actions" },
        link(
          "Watch file-to-result recording",
          "/uploads/recording.html",
          "secondary",
        ),
        link(
          "Technical documentation ↗",
          "https://github.com/Akhilesh-Vangala/verifyops/tree/main/docs",
          "quiet",
          { target: "_blank", rel: "noreferrer" },
        ),
      ),
    ),
  );
}
