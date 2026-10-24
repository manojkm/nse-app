import { callTool } from "../api.js";
import { $, empty, h, mount } from "../dom.js";
import { croreSigned, direction, number } from "../format.js";
import { hoverTip, kpi, legend, section, table, tipRows } from "../ui.js";

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
    h("div", { class: "fb", role: "group", "aria-label": "Daily FII and DII net flows" },
      h("div", { class: "fb__zero", style: `top:calc(var(--fb-plot) * ${zero / 100})` }), cols),
    tableWrap,
  ];
}

async function load() {
  const f = await section($("#flows-today"), "row", () => callTool("get_fii_dii"), today, 3);
  if (f) mount($("#flows-history"), history(f));
  else mount($("#flows-history"), empty("No data yet."));
  ui.loaded = true;
}

export const flowsView = {
  title: "FII / DII",
  show() {
    if (!ui.wired) {
      ui.wired = true;
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
