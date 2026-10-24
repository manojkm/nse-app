// Shared UI building blocks: tables, chips, KPI tiles, tooltips, async sections.

import { $, empty, errorBox, h, mount, skeleton } from "./dom.js";
import { direction, pct } from "./format.js";

export const chip = (v) => h("span", { class: `chip ${direction(v)}` }, pct(v));

const TONE = {
  positive: { icon: "▲", word: "Positive" },
  negative: { icon: "▼", word: "Negative" },
  neutral: { icon: "●", word: "Neutral" },
  unknown: { icon: "?", word: "Unavailable" },
};
/** Tone badge: icon + word, so meaning never relies on color alone. */
export const toneTag = (tone, text) =>
  h("span", { class: `tone tone--${tone || "unknown"}` }, h("span", { "aria-hidden": "true" }, TONE[tone]?.icon ?? "●"), text ?? TONE[tone]?.word ?? "");

export const nameCell = (title, subtitle) =>
  h("span", { class: "cell-name" }, h("strong", {}, title), subtitle ? h("span", {}, subtitle) : null);

export const kpi = (label, value, sub, tone) =>
  h("div", { class: `kpi${tone ? ` kpi--${tone}` : ""}` },
    h("span", { class: "kpi__label" }, label),
    h("span", { class: "kpi__value" }, value),
    sub ? h("span", { class: "kpi__sub" }, sub) : null);

export const card = (title, subtitle, ...body) =>
  h("section", { class: "section card-surface" },
    h("div", { class: "section__head" }, h("h2", {}, title), subtitle ? h("p", { class: "muted" }, subtitle) : null),
    ...body);

export const sourceNote = (text) => h("p", { class: "source-note" }, text);

/** Load data into a container with skeleton, error + retry handling. */
export async function section(target, kind, load, render, count) {
  skeleton(target, kind, count ?? (kind === "card" ? 3 : 5));
  try {
    const data = await load();
    mount(target, render(data));
    return data;
  } catch (err) {
    mount(target, errorBox(err.message, () => section(target, kind, load, render, count)));
    return null;
  }
}

/**
 * Sortable table. columns: [{ label, align, value(row), render(row), hideSm, class(row) }]
 */
export function table(columns, rows, { onRow, label, initialSort, rowClass } = {}) {
  let sortIdx = initialSort ?? -1;
  let sortDir = -1;
  const tbody = h("tbody");
  const cls = (c) => [c.align === "r" ? "r" : c.align === "c" ? "c" : "", c.hideSm ? "hide-sm" : ""].join(" ").trim() || undefined;
  const ths = columns.map((c, i) => {
    if (!c.value) return h("th", { scope: "col", class: cls(c) }, c.label);
    return h("th", { scope: "col", class: cls(c), "aria-sort": i === sortIdx ? "descending" : "none" },
      h("button", { class: "sort-btn", type: "button", onclick: () => sortBy(i) }, c.label));
  });

  function sortBy(i) {
    sortDir = i === sortIdx ? -sortDir : -1;
    sortIdx = i;
    ths.forEach((th, j) => th.hasAttribute("aria-sort") && th.setAttribute("aria-sort", j === i ? (sortDir > 0 ? "ascending" : "descending") : "none"));
    render();
  }

  function render() {
    const sorted = [...rows];
    if (sortIdx >= 0) {
      const get = columns[sortIdx].value;
      sorted.sort((a, b) => {
        const av = get(a), bv = get(b);
        if (typeof av === "string") return sortDir * av.localeCompare(bv);
        return sortDir * ((Number.isFinite(av) ? av : -Infinity) - (Number.isFinite(bv) ? bv : -Infinity));
      });
    }
    tbody.replaceChildren(...sorted.map((row) => {
      const cells = columns.map((c, ci) => {
        let content = c.render(row);
        if (ci === 0 && onRow) content = h("button", { class: "row-btn", type: "button", onclick: (e) => { e.stopPropagation(); onRow(row); } }, content);
        return h("td", { class: [cls(c), c.class?.(row)].filter(Boolean).join(" ") || undefined }, content);
      });
      return h("tr", { class: [onRow ? "is-clickable" : "", rowClass?.(row) ?? ""].join(" ").trim() || undefined, onclick: onRow ? () => onRow(row) : undefined }, cells);
    }));
  }
  render();
  return h("table", { "aria-label": label }, h("thead", {}, h("tr", {}, ths)), tbody);
}

// ---------------------------------------------------------------- floating tooltip for HTML marks

let tipEl;
function tip() {
  if (!tipEl) {
    tipEl = h("div", { class: "float-tip", role: "status", hidden: true });
    document.body.append(tipEl);
  }
  return tipEl;
}

/** Attach a hover/focus tooltip. content() returns nodes or text, built with textContent only. */
export function hoverTip(el, content) {
  const show = (x, y) => {
    const t = tip();
    t.replaceChildren(...[content()].flat());
    t.hidden = false;
    const r = t.getBoundingClientRect();
    const left = Math.min(window.innerWidth - r.width - 8, Math.max(8, x + 14));
    const top = y - r.height - 12 < 8 ? y + 16 : y - r.height - 12;
    t.style.transform = `translate(${left}px, ${top}px)`;
  };
  el.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
  el.addEventListener("pointerleave", () => (tip().hidden = true));
  el.addEventListener("focus", () => { const r = el.getBoundingClientRect(); show(r.left + r.width / 2, r.top); });
  el.addEventListener("blur", () => (tip().hidden = true));
}

export const tipRows = (title, rows) => [
  h("div", { class: "tt-date" }, title),
  ...rows.map(([label, value, color]) => h("div", { class: "tt-row" },
    color ? h("span", { class: "legend__swatch", style: `background:${color}` }) : null,
    h("span", {}, label), h("b", {}, value))),
];

export const legend = (items) => h("div", { class: "legend" },
  items.map(([label, color]) => h("span", { class: "legend__item" }, h("span", { class: "legend__swatch legend__swatch--block", style: `background:${color}` }), label)));

export { $, empty, errorBox, h, mount, skeleton };
