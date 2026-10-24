import { callTool, uploadCsv } from "../api.js";
import { importer, nseLink } from "../importer.js";
import { $, empty, h, mount } from "../dom.js";
import { croreSigned, direction, number } from "../format.js";
import { hoverTip, kpi, legend, table, tipRows } from "../ui.js";

const ui = { data: null, wired: false, loaded: false };
const crore = croreSigned;
const parseDay = (s) => { const d = new Date(String(s).replace(/-/g, " ")); return Number.isNaN(d.getTime()) ? new Date(s) : d; };

function today(f) {
  const side = (label, v) => h("div", { class: "flow-card" },
    h("span", { class: "kpi__label" }, label),
    h("span", { class: `flow-card__net ${direction(v?.net)}` }, crore(v?.net)),
    h("div", { class: "flow-card__split" },
      h("span", {}, "Bought ", h("b", {}, `₹${number(v?.buy)} cr`)),
      h("span", {}, "Sold ", h("b", {}, `₹${number(v?.sell)} cr`))));
  return [
    h("div", { class: "flow-row" }, side("FII / FPI", f.fii), side("DII", f.dii),
      kpi("Combined net", h("span", { class: direction(f.combined_net) }, crore(f.combined_net)), `Session ${f.date ?? "—"}`)),
    h("ul", { class: "bullets" }, (f.summary ?? []).map((s) => h("li", {}, s))),
  ];
}

function history(f) {
  const rows = (f.history ?? []).filter((r) => r.date);
  if (rows.length < 2) return [empty("History starts today. Open the app on more trading days to build the chart.")];
  const vals = rows.flatMap((r) => [r.fii_net ?? 0, r.dii_net ?? 0]);
  const maxPos = Math.max(0, ...vals), maxNeg = Math.max(0, ...vals.map((v) => -v));
  const span = maxPos + maxNeg || 1;
  const zero = (maxPos / span) * 100;
  const sum = (k) => rows.reduce((a, r) => a + (r[k] ?? 0), 0);

  const bar = (v, cls) => {
    const hgt = (Math.abs(v ?? 0) / span) * 100;
    return h("span", { class: `fb__bar ${cls}`, style: v >= 0 ? `bottom:${100 - zero}%;height:${hgt}%` : `top:${zero}%;height:${hgt}%` });
  };
  const cols = rows.map((r) => {
    const col = h("div", { class: "fb__col", tabindex: "0", "aria-label": `${r.date}: FII ${crore(r.fii_net)}, DII ${crore(r.dii_net)}` },
      h("div", { class: "fb__plot" }, bar(r.fii_net, "fb__bar--fii"), bar(r.dii_net, "fb__bar--dii")),
      h("span", { class: "fb__x" }, parseDay(r.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })));
    hoverTip(col, () => tipRows(r.date, [["FII net", crore(r.fii_net), "var(--series-1)"], ["DII net", crore(r.dii_net), "var(--series-2)"]]));
    return col;
  });

  const tableWrap = h("div", { class: "table-wrap", id: "flows-table", hidden: true },
    table([
      { label: "Date", render: (r) => r.date, value: (r) => parseDay(r.date).getTime() },
      { label: "FII net (₹ cr)", align: "r", render: (r) => h("span", { class: direction(r.fii_net) }, number(r.fii_net)), value: (r) => r.fii_net },
      { label: "DII net (₹ cr)", align: "r", render: (r) => h("span", { class: direction(r.dii_net) }, number(r.dii_net)), value: (r) => r.dii_net },
    ], [...rows].reverse(), { label: "FII and DII daily net flows", initialSort: 0 }));

  return [
    h("div", { class: "kpi-row" },
      kpi(`FII, last ${rows.length} days`, h("span", { class: direction(sum("fii_net")) }, crore(sum("fii_net")))),
      kpi(`DII, last ${rows.length} days`, h("span", { class: direction(sum("dii_net")) }, crore(sum("dii_net"))))),
    legend([["FII / FPI net", "var(--series-1)"], ["DII net", "var(--series-2)"]]),
    h("div", { class: `fb${rows.length > 12 ? " fb--dense" : ""}`, role: "group", "aria-label": "Daily FII and DII net flows" },
      h("div", { class: "fb__zero", style: `top:calc(var(--fb-plot) * ${zero / 100})` }), cols),
    tableWrap,
  ];
}

function importPanel() {
  return importer({
    title: "Import FII / DII data from NSE",
    intro: "NSE doesn't allow automated access to this report, but you can download it yourself and drop it here. Each import adds to your history.",
    steps: [
      h("span", {}, "Open ", nseLink("https://www.nseindia.com/reports/fii-dii", "NSE's FII/DII report"), " in your browser."),
      "Click the CSV download icon next to the table.",
      "Drop the file here. Repeat on later days to grow the chart.",
    ],
    async onFile(file) {
      const d = await uploadCsv("api/import/fii-dii", file);
      show(d);
      $("#flows-import").hidden = true;
      $("#flows-import-btn").setAttribute("aria-expanded", "false");
      return `Imported ${d.imported_days} day(s); latest ${d.date}.`;
    },
  });
}

function toggleImport(force) {
  const panel = $("#flows-import");
  const open = force ?? panel.hidden;
  if (open && !panel.firstChild) panel.append(importPanel());
  panel.hidden = !open;
  $("#flows-import-btn").setAttribute("aria-expanded", String(open));
}

function show(f) {
  mount($("#flows-today"), [
    h("p", { class: `source-banner${String(f.source).startsWith("Imported") ? " source-banner--import" : ""}` }, `Source: ${f.source ?? "—"}`),
    ...today(f)]);
  mount($("#flows-history"), history(f));
}

async function load() {
  ui.loaded = true;
  try {
    show(await callTool("get_fii_dii"));
  } catch (err) {
    mount($("#flows-today"), h("p", { class: "notice" }, err.status === 404 ? "No FII/DII data yet. Import NSE's CSV to get started." : err.message), importPanel());
    mount($("#flows-history"), empty("Your history chart appears here after the first import."));
  }
}

export const flowsView = {
  title: "FII / DII",
  show() {
    if (!ui.wired) {
      ui.wired = true;
      $("#flows-import-btn").addEventListener("click", () => toggleImport());
      $("#flows-table-btn").addEventListener("click", (e) => {
        const t = document.getElementById("flows-table");
        if (!t) return;
        t.hidden = !t.hidden;
        e.currentTarget.setAttribute("aria-expanded", String(!t.hidden));
        e.currentTarget.textContent = t.hidden ? "View as table" : "Hide table";
      });
    }
    if (!ui.loaded) load();
  },
  refresh: load,
};
