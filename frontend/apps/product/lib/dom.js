/** Owned DOM primitives. User-controlled text never passes through HTML parsing. */
export function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (
      value === undefined ||
      value === null ||
      (value === false && !key.startsWith("aria-"))
    )
      continue;
    if (key.startsWith("on") && typeof value === "function")
      node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === "class") node.className = value;
    else if (key === "checked" || key === "disabled" || key === "hidden")
      node[key] = Boolean(value);
    else
      node.setAttribute(
        key,
        value === true && !key.startsWith("aria-") ? "" : String(value),
      );
  }
  for (const child of children.flat(Infinity)) {
    if (child !== undefined && child !== null && child !== false)
      node.append(
        child instanceof Node ? child : document.createTextNode(String(child)),
      );
  }
  return node;
}
export const $ = (query, base = document) => base.querySelector(query);
export function button(text, action, className = "primary", attributes = {}) {
  return el(
    "button",
    { type: "button", class: className, onclick: action, ...attributes },
    text,
  );
}
export function link(text, href, className = "", attributes = {}) {
  return el("a", { href, class: className, ...attributes }, text);
}
export function icon(name, className = "icon") {
  const paths = {
    grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
    file: "M5 3h9l5 5v13H5z M14 3v6h5 M8 13h8 M8 17h6",
    folder: "M3 6h7l2 3h9v11H3z M3 6V4h7l2 3",
    check: "M5 12l4 4L20 5",
    arrow: "M4 12h16 M14 6l6 6-6 6",
    upload: "M12 16V3 M6 9l6-6 6 6 M4 16v5h16v-5",
    clock: "M12 8v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
    search: "M15 15l6 6 M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0",
    settings: "M4 7h16 M4 17h16 M8 4v6 M16 14v6",
    help: "M9 8a3 3 0 0 1 6 0c0 2-3 2-3 5 M12 17v1 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
    shield: "M12 2l8 4v7c0 5-8 9-8 9s-8-4-8-9V6z M8 12l3 3 5-6",
    close: "M6 6l12 12 M18 6 6 18",
    back: "M20 12H4 M10 6l-6 6 6 6",
    download: "M12 3v13 M6 10l6 6 6-6 M4 17v4h16v-4",
    alert: "M12 3l10 18H2z M12 9v5 M12 17v1",
    account: "M4 21v-3a8 8 0 0 1 16 0v3 M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
  };
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  for (const [key, value] of Object.entries({
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "1.5",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "aria-hidden": "true",
    class: className,
  }))
    svg.setAttribute(key, value);
  const path = document.createElementNS(svg.namespaceURI, "path");
  path.setAttribute("d", paths[name] || paths.file);
  svg.append(path);
  return svg;
}
export function title(eyebrow, heading, description, actions = []) {
  return el(
    "div",
    { class: "page-heading" },
    el(
      "div",
      {},
      el("p", { class: "eyebrow" }, eyebrow),
      el("h1", { tabindex: "-1" }, heading),
      description && el("p", { class: "muted measure" }, description),
    ),
    el("div", { class: "actions" }, actions),
  );
}
export function badge(text, tone = "") {
  return el("span", { class: "badge " + tone }, text);
}
export function table(headers, rows, options = {}) {
  const head = el(
    "tr",
    {},
    headers.map((h) => el("th", { scope: "col" }, h)),
  );
  return el(
    "div",
    {
      class: "table-scroll",
      tabindex: "0",
      "aria-label": options.label || "Data table",
    },
    el(
      "table",
      {},
      options.caption && el("caption", { class: "sr-only" }, options.caption),
      el("thead", {}, head),
      el(
        "tbody",
        {},
        rows.map((row) =>
          el(
            "tr",
            {},
            row.map((v) => el("td", {}, v)),
          ),
        ),
      ),
    ),
  );
}
export function money(cents, signed = false) {
  if (cents === null || cents === undefined) return "Not provided";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    signDisplay: signed ? "exceptZero" : "auto",
  }).format(cents / 100);
}
export function readableDate(value) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
export function notify(text) {
  const node = $("#toast");
  node.textContent = text;
  node.hidden = false;
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => {
    node.hidden = true;
  }, 4500);
}
export function announce(text) {
  $("#announcer").textContent = text;
}
export function modal(heading, content, actions = []) {
  const dialog = $("#dialog"),
    previous = document.activeElement;
  dialog.replaceChildren(
    el(
      "div",
      { class: "dialog-heading" },
      el("h2", { id: "dialog-title" }, heading),
      button(icon("close"), () => dialog.close(), "icon-button", {
        "aria-label": "Close dialog",
      }),
    ),
    content,
    el("div", { class: "dialog-actions" }, actions),
  );
  dialog.addEventListener("close", () => previous?.focus(), { once: true });
  dialog.showModal();
  return dialog;
}
export function download(text, filename, type = "application/json") {
  const url = URL.createObjectURL(new Blob([text], { type })),
    anchor = link("", url, "", { download: filename });
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function field(label, control, hint, attributes = {}) {
  const id = control.id || "field-" + crypto.randomUUID();
  control.id = id;
  const hintId = id + "-hint";
  if (hint) control.setAttribute("aria-describedby", hintId);
  return el(
    "div",
    { class: "field", ...attributes },
    el("label", { for: id }, label),
    control,
    hint && el("p", { id: hintId, class: "hint" }, hint),
  );
}
export function inlineError(message) {
  return el("p", { class: "inline-error", role: "alert" }, message);
}
