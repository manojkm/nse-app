import { callTool, uploadCsv } from "../api.js";
import { importer, nseLink } from "../importer.js";
import { $, $$, empty, errorBox, h, mount, segmented, skeleton } from "../dom.js";
import { compact, integer, number, signedInt as signed } from "../format.js";
import { go } from "../router.js";
import { hoverTip, kpi, legend, table, tipRows, toneTag } from "../ui.js";

const ui = { symbol: "NIFTY", expiry: "", mode: "oi", data: null, wired: false, token: 0, selectSym: null };

const BUILDUP_TONE = { "Long build-up": "up", "Short covering": "up", "Short build-up": "down", "Long unwinding": "down" };
const buildupTag = (b) => (b && b !== "No change" ? h("span", { class: `tag tag--${BUILDUP_TONE[b] ?? "flat"}` }, b) : "—");

async function load() {
  const token = ++ui.token;
  const body = $("#oc-body");
  skeleton(body, "row", 6);
  let d;
  try {
    d = await callTool("get_option_chain", { symbol: ui.symbol, expiry: ui.expiry });
  } catch (err) {
    if (token !== ui.token) return;
    setExpiries([]);
    // Live NSE data is usually unavailable, so lead with the import rather than an error.
    mount(body, h("section", { class: "section card-surface" },
      h("p", { class: "notice" }, err.status === 404 ? `No ${ui.symbol} option chain yet. Import NSE's CSV to analyse it.` : err.message),
      importPanel()));
    return;
  }
  if (token !== ui.token) return;
  ui.data = d;
  ui.expiry = d.expiry;
  setExpiries(d.expiries, d.expiry);
  render();
}

const pcrLabel = (p) => (p === null || p === undefined ? "—" : p >= 1.3 ? "Bullish tilt" : p >= 0.9 ? "Balanced" : p >= 0.7 ? "Mild bearish tilt" : "Bearish tilt");

function setExpiries(list, value) {
  const sel = $("#oc-expiry");
  sel.replaceChildren(...(list ?? []).map((e) => h("option", { value: e }, e)));
  sel.closest("label").hidden = !sel.options.length;
  if (value) sel.value = value;
}

export function importPanel() {
  return importer({
    title: "Import an option chain from NSE",
    intro: "NSE doesn't allow automated access to option chains, but you can download the table yourself and drop it here.",
    steps: [
      h("span", {}, "Open ", nseLink("https://www.nseindia.com/option-chain", "nseindia.com/option-chain"), " in your browser."),
      "Pick the index or stock and the expiry.",
      "Click “Download (.csv)” above the table.",
      "Drop the file here. Adding the spot price makes max pain and ATM more accurate.",
    ],
    fields: [
      { name: "symbol", label: "Symbol (if not in file name)", placeholder: ui.symbol },
      { name: "spot", label: "Spot price (optional)", placeholder: "e.g. 24853.15", inputmode: "decimal" },
    ],
    async onFile(file, v) {
      const d = await uploadCsv("api/import/option-chain", file, { symbol: v.symbol, spot: v.spot });
      ui.symbol = d.symbol;
      ui.data = d;
      ui.expiry = d.expiry;
      ui.token++;
      history.replaceState(null, "", `#/options/${encodeURIComponent(d.symbol)}`);
      $$("#oc-symbols button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.symbol === d.symbol)));
      setExpiries(d.expiries ?? [d.expiry], d.expiry);
      $("#oc-import").hidden = true;
      $("#oc-import-btn").setAttribute("aria-expanded", "false");
      render();
      return `Imported ${d.symbol} (${d.rows?.length ?? 0} strikes shown).`;
    },
  });
}

function render() {
  const d = ui.data;
  const spot = d.spot;
  const r1 = d.resistance?.[0], s1 = d.support?.[0];
  const mpGap = d.max_pain && spot ? ((d.max_pain - spot) / spot) * 100 : null;
  const pts = d.expected_move_pct && spot ? (spot * d.expected_move_pct) / 100 : null;

  const kpis = h("div", { class: "kpi-grid" },
    kpi("Spot", number(spot), d.spot_estimated ? "Estimated from option prices" : `${d.symbol} · ATM ${integer(d.atm_strike)}`),
    kpi("Put-call ratio", number(d.pcr), h("span", {}, toneTag(d.pcr_tone, pcrLabel(d.pcr)),
      d.pcr_volume ? ` · Vol PCR ${number(d.pcr_volume)}` : "")),
    kpi("Max pain", integer(d.max_pain), mpGap === null ? "" : Math.abs(mpGap) < 0.05 ? "At spot" : `${mpGap > 0 ? "+" : "−"}${Math.abs(mpGap).toFixed(1)}% from spot`),
    kpi("Expected move", d.expected_move_pct ? `±${number(d.expected_move_pct)}%` : "—", pts ? `±${integer(pts)} pts by expiry (ATM straddle ${number(d.atm_straddle)})` : ""),
    kpi("Resistance", r1 ? integer(r1.strike) : "—", r1 ? `Call OI ${compact(r1.oi)}${d.resistance[1] ? ` · next ${integer(d.resistance[1].strike)}` : ""}` : "", "down"),
    kpi("Support", s1 ? integer(s1.strike) : "—", s1 ? `Put OI ${compact(s1.oi)}${d.support[1] ? ` · next ${integer(d.support[1].strike)}` : ""}` : "", "up"));

  const summary = h("section", { class: "section card-surface" },
    h("div", { class: "section__head" }, h("h2", {}, "What the option chain says")),
    h("ul", { class: "bullets" }, (d.summary ?? []).map((s) => h("li", {}, s))),
    d.fresh_call_writing || d.fresh_put_writing ? h("p", { class: "muted" },
      d.fresh_call_writing ? `Most fresh call writing today: ${integer(d.fresh_call_writing.strike)} (+${compact(d.fresh_call_writing.oi_change)} OI). ` : "",
      d.fresh_put_writing ? `Most fresh put writing: ${integer(d.fresh_put_writing.strike)} (+${compact(d.fresh_put_writing.oi_change)} OI).` : "") : null,
    h("p", { class: "source-note" }, `Expiry ${d.expiry}${d.timestamp ? ` · as of ${d.timestamp}` : ""} · ${d.source ?? ""}. Educational analysis, not trading advice.`));

  const chartCard = h("section", { class: "section card-surface" },
    h("div", { class: "section__head section__head--row" },
      h("h2", {}, "Open interest by strike"),
      h("div", { class: "segmented segmented--sm", role: "group", "aria-label": "Measure", id: "oc-mode" },
        h("button", { type: "button", "data-mode": "oi", "aria-pressed": String(ui.mode === "oi") }, "Total OI"),
        h("button", { type: "button", "data-mode": "chg", "aria-pressed": String(ui.mode === "chg") }, "Change in OI"))),
    legend([["Calls (resistance)", "var(--call)"], ["Puts (support)", "var(--put)"]]),
    oiChart(d));

  const chainCard = h("section", { class: "section card-surface" },
    h("div", { class: "section__head" }, h("h2", {}, "Option chain"),
      h("p", { class: "muted" }, "Build-up: price and OI both up = long build-up; price down, OI up = short build-up; price up, OI down = short covering; both down = long unwinding.")),
    h("div", { class: "table-wrap" }, chainTable(d)));

  const imported = String(d.source ?? "").startsWith("Imported");
  const banner = h("div", { class: `source-banner${imported ? " source-banner--import" : ""}` },
    h("span", {}, imported ? "📄 " : "● ", d.source ?? ""),
    imported ? h("button", { type: "button", class: "link-btn", onclick: () => toggleImport(true) }, "Import a newer file") : null);
  mount($("#oc-body"), banner, kpis, h("div", { class: "grid-2 grid-2--wide-left" }, chartCard, summary), chainCard);
  segmented($("#oc-mode"), "mode", (m) => { ui.mode = m; render(); });
}

function oiChart(d) {
  const key = ui.mode === "oi" ? "oi" : "oi_change";
  const rows = d.rows ?? [];
  const max = Math.max(1, ...rows.flatMap((r) => [Math.abs(r.CE?.[key] ?? 0), Math.abs(r.PE?.[key] ?? 0)]));
  const spot = d.spot;
  let spotPlaced = false;
  const out = [];
  rows.forEach((r) => {
    if (!spotPlaced && spot && r.strike > spot) {
      out.push(h("div", { class: "oi__spot", "aria-hidden": "true" }, h("span", {}, `Spot ${number(spot)}`)));
      spotPlaced = true;
    }
    const bar = (side) => {
      const v = r[side]?.[key] ?? 0;
      return h("span", { class: `oi__bar oi__bar--${side.toLowerCase()}${v < 0 ? " oi__bar--neg" : ""}`, style: `width:${(Math.abs(v) / max) * 100}%` });
    };
    const row = h("div", { class: `oi__row${r.is_atm ? " oi__row--atm" : ""}`, tabindex: "0",
      "aria-label": `Strike ${r.strike}: call OI ${integer(r.CE?.oi)}, change ${signed(r.CE?.oi_change)}; put OI ${integer(r.PE?.oi)}, change ${signed(r.PE?.oi_change)}` },
    h("span", { class: "oi__side oi__side--ce" }, bar("CE")),
    h("span", { class: "oi__strike num" }, integer(r.strike)),
    h("span", { class: "oi__side oi__side--pe" }, bar("PE")));
    hoverTip(row, () => tipRows(`Strike ${integer(r.strike)}${r.is_atm ? " (ATM)" : ""}`, [
      ["Call OI", `${integer(r.CE?.oi)} (${signed(r.CE?.oi_change)})`, "var(--call)"],
      ["Put OI", `${integer(r.PE?.oi)} (${signed(r.PE?.oi_change)})`, "var(--put)"],
      ["Call / Put LTP", `${number(r.CE?.ltp)} / ${number(r.PE?.ltp)}`]]));
    out.push(row);
  });
  return h("div", { class: "oi", role: "group", "aria-label": `${ui.mode === "oi" ? "Open interest" : "Change in open interest"} by strike; calls left, puts right` },
    h("div", { class: "oi__head", "aria-hidden": "true" }, h("span", {}, "◀ Calls"), h("span", {}, "Strike"), h("span", {}, "Puts ▶")), out,
    ui.mode === "chg" ? h("p", { class: "source-note" }, "Faded bars are OI that was reduced today.") : null);
}

function chainTable(d) {
  const spot = d.spot;
  return table([
    { label: "Call OI", align: "r", render: (r) => compact(r.CE?.oi), class: (r) => (r.strike < spot ? "itm" : "") },
    { label: "Chg OI", align: "r", hideSm: true, render: (r) => h("span", { class: (r.CE?.oi_change ?? 0) >= 0 ? "up" : "down" }, signed(r.CE?.oi_change)), class: (r) => (r.strike < spot ? "itm" : "") },
    { label: "LTP", align: "r", render: (r) => number(r.CE?.ltp), class: (r) => (r.strike < spot ? "itm" : "") },
    { label: "Build-up", hideSm: true, render: (r) => buildupTag(r.CE?.buildup), class: (r) => (r.strike < spot ? "itm" : "") },
    { label: "Strike", align: "c", render: (r) => h("strong", {}, integer(r.strike)), class: () => "strike-cell" },
    { label: "Build-up", hideSm: true, render: (r) => buildupTag(r.PE?.buildup), class: (r) => (r.strike > spot ? "itm" : "") },
    { label: "LTP", align: "r", render: (r) => number(r.PE?.ltp), class: (r) => (r.strike > spot ? "itm" : "") },
    { label: "Chg OI", align: "r", hideSm: true, render: (r) => h("span", { class: (r.PE?.oi_change ?? 0) >= 0 ? "up" : "down" }, signed(r.PE?.oi_change)), class: (r) => (r.strike > spot ? "itm" : "") },
    { label: "Put OI", align: "r", render: (r) => compact(r.PE?.oi), class: (r) => (r.strike > spot ? "itm" : "") },
  ], d.rows ?? [], { label: `${d.symbol} option chain, calls left and puts right`, rowClass: (r) => (r.is_atm ? "atm-row" : "") });
}

function toggleImport(force) {
  const panel = $("#oc-import");
  const open = force ?? panel.hidden;
  if (open && !panel.firstChild) panel.append(importPanel());
  panel.hidden = !open;
  $("#oc-import-btn").setAttribute("aria-expanded", String(open));
  if (open) panel.scrollIntoView({ block: "nearest" });
}

function wire() {
  if (ui.wired) return;
  ui.wired = true;
  $("#oc-import-btn").addEventListener("click", () => toggleImport());
  ui.selectSym = segmented($("#oc-symbols"), "symbol", (s) => go("options", s));
  $("#oc-stock-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const s = $("#oc-stock").value.trim().toUpperCase();
    if (s) go("options", s);
  });
  $("#oc-expiry").addEventListener("change", (e) => { ui.expiry = e.target.value; load(); });
}

export const optionsView = {
  title: "Options",
  show(arg) {
    wire();
    const sym = (arg || ui.symbol || "NIFTY").toUpperCase();
    $$("#oc-symbols button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.symbol === sym)));
    if (sym === ui.symbol && ui.data) return;
    if (sym !== ui.symbol) ui.expiry = "";
    ui.symbol = sym;
    ui.data = null;
    load();
  },
  refresh() { ui.data = null; load(); },
};
