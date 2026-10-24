import { callTool } from "../api.js";
import { $, $$, empty, errorBox, h, mount, segmented, skeleton } from "../dom.js";
import { compact, croreSigned, direction, integer, money, number, pct, shortDate, toNum } from "../format.js";
import { byExchange, commodity, stock } from "../normalize.js";
import { go } from "../router.js";
import { chip, nameCell, section, table, toneTag } from "../ui.js";

const ui = { exchange: "NSE", w52Exchange: "NSE", w52Data: null, mfData: null, loaded: new Set(), io: null, wired: false };

const openStock = (name, symbol) => go("stock", name || symbol, symbol ? { s: symbol } : {});

// ---------------------------------------------------------------- indices, breadth, flows

function loadIndices() {
  return section($("#indices"), "index", () => callTool("get_indices"), (data) => {
    const rows = (data?.indices ?? (Array.isArray(data) ? data : [])).filter((r) => r && r.name);
    if (!rows.length) return empty("Index data unavailable.");
    const asOf = data?.date ? `Close of ${shortDate(data.date, true)}` : "";
    return rows.map((r) => h("div", { class: "index-card", title: [asOf, data?.source].filter(Boolean).join(" · ") },
      h("span", { class: "index-card__name" }, r.name),
      h("span", { class: "index-card__price num" }, number(r.price)),
      h("span", { class: "index-card__row" },
        h("span", { class: `index-card__chg ${direction(r.percentChange)}` }, pct(r.percentChange)),
        r.pe ? h("span", { class: "index-card__pe" }, `P/E ${number(r.pe)}`) : null)));
  }, 6);
}

const READING_TONE = { "broad advance": "positive", "broad decline": "negative", mixed: "neutral" };

function breadthBlock(adv, dec, unch, label) {
  const seg = (n, cls, name) => h("span", { class: `breadth__seg ${cls}`, style: `flex:${n}`, title: `${name}: ${integer(n)}` });
  return [
    h("div", { class: "breadth__nums" },
      h("span", { class: "up" }, h("b", {}, integer(adv)), " advancing"),
      h("span", { class: "muted" }, `${integer(unch)} unchanged`),
      h("span", { class: "down" }, h("b", {}, integer(dec)), " declining")),
    h("div", { class: "breadth__bar", role: "img", "aria-label": `${label}: ${adv} advancing, ${unch} unchanged, ${dec} declining` },
      seg(adv, "breadth__seg--up", "Advancing"), seg(unch, "breadth__seg--flat", "Unchanged"), seg(dec, "breadth__seg--down", "Declining")),
  ];
}

function loadBreadth() {
  return section($("#breadth"), "row", async () => {
    try { return { mood: await callTool("get_market_mood") }; } catch { return { breadth: await callTool("get_market_breadth") }; }
  }, ({ mood, breadth }) => {
    if (breadth) {
      const adv = toNum(breadth.advances), dec = toNum(breadth.declines), unch = toNum(breadth.unchanged) || 0;
      if (!Number.isFinite(adv + dec)) return empty("Breadth data unavailable.");
      return [...breadthBlock(adv, dec, unch, "Stocks"),
        h("p", { class: "breadth__summary" }, toneTag(breadth.tone, `A/D ${number(breadth.ad_ratio)}`), " ", breadth.summary ?? ""),
        h("p", { class: "source-note" }, `Session ${breadth.date ?? ""}`)];
    }
    const sb = mood.stock_breadth, vix = mood.india_vix, ib = mood.index_breadth;
    const out = [];
    if (sb) {
      out.push(...breadthBlock(toNum(sb.up), toNum(sb.down), toNum(sb.unchanged) || 0, "Stocks"),
        h("p", { class: "breadth__summary" }, toneTag(READING_TONE[sb.reading] ?? "neutral", sb.reading ?? ""), " ",
          `${Math.round(toNum(sb.up_pct))}% of ${integer(sb.stocks)} stocks rose${ib ? `; ${integer(ib.up)} of ${integer(ib.equity_indices)} indices were up` : ""}.`));
    }
    if (vix) {
      const dir = vix.vs_1w_ago?.direction;
      out.push(h("div", { class: "vix" },
        h("div", {}, h("span", { class: "kpi__label" }, "India VIX (fear gauge)"),
          h("div", { class: "vix__value" }, h("b", { class: "num" }, number(vix.level)), " ",
            h("span", { class: direction(vix.change_1d_pct) }, pct(vix.change_1d_pct)))),
        h("p", { class: "muted" },
          `${dir ? `${dir[0].toUpperCase()}${dir.slice(1)} over the past week` : ""}${vix.range?.percentile !== undefined ? `; higher than on ${Math.round(vix.range.percentile)}% of days in the past year` : ""}. Higher VIX means traders expect bigger swings.`)));
    }
    out.push(h("p", { class: "source-note" }, `Session ${mood.date ?? ""} · NSE official · descriptive, not a forecast`));
    return out.length > 1 ? out : empty("Breadth data unavailable.");
  }, 3);
}

function loadFlowsMini() {
  // nseindia.com often declines automated requests; show that calmly rather than as an error.
  return section($("#flows-mini"), "row", () => callTool("get_fii_dii").catch((err) => ({ unavailable: err.message })), (f) => {
    if (f.unavailable) return [h("p", { class: "muted" }, "FII/DII data isn't available right now."), h("p", { class: "source-note" }, f.unavailable)];
    const tile = (label, v) => h("div", { class: "flow-mini" },
      h("span", { class: "kpi__label" }, label),
      h("span", { class: `flow-mini__value ${direction(v?.net)}` }, croreSigned(v?.net)),
      h("span", { class: "kpi__sub" }, v ? `Buy ₹${compact(v.buy)} cr · Sell ₹${compact(v.sell)} cr` : ""));
    return [
      h("div", { class: "flow-mini__row" }, tile("FII / FPI net", f.fii), tile("DII net", f.dii)),
      h("p", { class: "breadth__summary" }, (f.summary ?? []).join(" ")),
      h("p", { class: "source-note" }, `As of ${f.date ?? "—"} · nseindia.com`),
    ];
  }, 3);
}

// ---------------------------------------------------------------- movers

function stockCard(raw) {
  const row = stock(raw);
  return h("button", {
    type: "button", class: "stock-card", dataset: { symbol: row.title },
    "aria-label": `${row.name}, ${money(row.price)}, ${pct(row.change)}. Show details.`,
    onclick: () => openStock(row.name, row.symbol),
  },
  h("span", { class: "stock-card__sym" }, row.title),
  h("span", { class: "stock-card__name" }, row.name),
  h("span", { class: "stock-card__row" }, h("span", { class: "stock-card__price" }, money(row.price)), chip(row.change)));
}

export let firstGainer = null;

function loadMovers() {
  const gainers = $("#gainers");
  const losers = $("#losers");
  skeleton(gainers, "card", 3);
  skeleton(losers, "card", 3);
  return callTool("get_trending_stocks")
    .then((data) => {
      const t = data?.trending_stocks ?? data ?? {};
      const g = t.top_gainers ?? [];
      const l = t.top_losers ?? [];
      if (g[0]) firstGainer = stock(g[0]);
      mount(gainers, g.length ? g.map(stockCard) : empty("No gainers right now."));
      mount(losers, l.length ? l.map(stockCard) : empty("No losers right now."));
    })
    .catch((err) => {
      mount(gainers, errorBox(err.message, loadMovers));
      mount(losers);
    });
}

// ---------------------------------------------------------------- lazy sections

const loaders = {
  active: () => section($("#active-table"), "row",
    () => callTool(ui.exchange === "NSE" ? "get_nse_most_active" : "get_bse_most_active"),
    (data) => {
      const rows = byExchange(data, ui.exchange).map(stock);
      return rows.length ? table([
        { label: "Stock", render: (r) => nameCell(r.title, r.subtitle), value: (r) => r.title },
        { label: "Price", align: "r", render: (r) => money(r.price), value: (r) => toNum(r.price) },
        { label: "Change", align: "r", render: (r) => chip(r.change), value: (r) => toNum(r.change) },
        { label: "Volume", align: "r", render: (r) => compact(r.volume), value: (r) => toNum(r.volume) },
      ], rows, { label: `${ui.exchange} most active`, initialSort: 3, onRow: (r) => openStock(r.name, r.symbol) })
        : empty("No data. The market may be closed.");
    }),

  week52: () => section($("#w52"), "row", () => callTool("get_52_week_high_low"), (data) => {
    ui.w52Data = data;
    return renderW52();
  }),

  shockers: () => section($("#shockers-table"), "row", () => callTool("get_price_shockers"), (data) => {
    const list = byExchange(data, "NSE").map(stock);
    return list.length ? table([
      { label: "Stock", render: (r) => nameCell(r.title, r.subtitle), value: (r) => r.title },
      { label: "Price", align: "r", render: (r) => money(r.price), value: (r) => toNum(r.price) },
      { label: "Change", align: "r", render: (r) => chip(r.change), value: (r) => Math.abs(toNum(r.change)) },
      { label: "Volume", align: "r", hideSm: true, render: (r) => compact(r.volume), value: (r) => toNum(r.volume) },
    ], list, { label: "Price shockers", initialSort: 2, onRow: (r) => openStock(r.name, r.symbol) })
      : empty("No sharp moves right now.");
  }),

  commodities: () => section($("#commodities-table"), "row", () => callTool("get_commodities"), (data) => {
    const rows = (Array.isArray(data) ? data : []).map(commodity);
    return rows.length ? table([
      { label: "Contract", render: (r) => nameCell(r.symbol, r.expiry ? `Exp ${r.expiry}` : ""), value: (r) => r.symbol },
      { label: "LTP", align: "r", render: (r) => h("span", {}, money(r.price), r.unit ? h("span", { class: "muted" }, ` /${r.unit}`) : null), value: (r) => toNum(r.price) },
      { label: "Change", align: "r", render: (r) => chip(r.change), value: (r) => toNum(r.change) },
      { label: "Open int.", align: "r", hideSm: true, render: (r) => integer(r.openInterest), value: (r) => toNum(r.openInterest) },
    ], rows, { label: "Commodity futures" }) : empty("No commodity data right now.");
  }),

  funds: () => section($("#mf-table"), "row", () => callTool("get_mutual_funds"), (data) => {
    ui.mfData = data;
    const select = $("#mf-category");
    const options = [];
    for (const [group, cats] of Object.entries(data || {})) {
      if (cats && typeof cats === "object") for (const cat of Object.keys(cats)) options.push(`${group}|${cat}`);
    }
    const current = select.value;
    select.replaceChildren(...options.map((v) => h("option", { value: v }, v.replace("|", " · "))));
    if (options.includes(current)) select.value = current;
    return renderFunds();
  }),
};

function renderW52() {
  const side = ui.w52Data?.[`${ui.w52Exchange}_52WeekHighLow`] ?? {};
  const list = (title, cls, raw, key) => {
    const rows = (Array.isArray(raw) ? raw : []).filter((r) => r && typeof r === "object").map(stock);
    return h("div", {},
      h("h3", { class: `eyebrow ${cls}` }, title),
      rows.length ? h("ul", {}, rows.slice(0, 6).map((r) => h("li", {},
        h("button", { class: "row-btn cell-name", type: "button", onclick: () => openStock(r.name, r.symbol) },
          h("strong", {}, r.title), r.subtitle ? h("span", {}, r.subtitle) : null),
        h("span", { class: "r num" }, money(r.price), h("div", { class: "muted" }, `52W ${money(r[key])}`)))))
        : empty("None right now (often empty when the market is closed)."));
  };
  return [
    list("▲ Near 52-week high", "eyebrow--up", side.high52Week, "yearHigh"),
    list("▼ Near 52-week low", "eyebrow--down", side.low52Week, "yearLow"),
  ];
}

function renderFunds() {
  const [group, cat] = ($("#mf-category").value || "").split("|");
  const rows = ui.mfData?.[group]?.[cat] ?? [];
  if (!rows.length) return empty("No funds in this category.");
  const ret = (k) => ({ label: k.replace("_year_return", "Y").replace("_month_return", "M"), align: "r",
    render: (r) => h("span", { class: direction(r[k]) }, Number.isFinite(toNum(r[k])) ? `${number(r[k])}%` : "—"), value: (r) => toNum(r[k]) });
  return table([
    { label: "Fund", render: (r) => h("span", { class: "cell-name" }, h("strong", {}, r.fund_name)), value: (r) => r.fund_name },
    { label: "NAV", align: "r", render: (r) => money(r.latest_nav), value: (r) => toNum(r.latest_nav) },
    { ...ret("1_year_return") },
    { ...ret("3_year_return"), hideSm: true },
    { ...ret("5_year_return"), hideSm: true },
    { label: "Rating", align: "r", hideSm: true, value: (r) => toNum(r.star_rating),
      render: (r) => { const n = Math.round(toNum(r.star_rating)) || 0; return h("span", { class: "stars", "aria-label": `${n} of 5 stars` }, "★".repeat(n) + "☆".repeat(Math.max(0, 5 - n))); } },
  ], rows, { label: "Mutual funds", initialSort: 2 });
}

function wire() {
  if (ui.wired) return;
  ui.wired = true;
  segmented($("#active-exchange"), "exchange", (x) => { ui.exchange = x; loaders.active(); });
  segmented($("#w52-exchange"), "exchange", (x) => { ui.w52Exchange = x; if (ui.w52Data) mount($("#w52"), renderW52()); });
  $("#mf-category").addEventListener("change", () => mount($("#mf-table"), renderFunds()));
  ui.io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const key = e.target.dataset.lazy;
      ui.io.unobserve(e.target);
      ui.loaded.add(key);
      loaders[key]();
    }
  }, { rootMargin: "200px" });
  $$("[data-lazy]").forEach((el) => ui.io.observe(el));
}

let mounted = false;
export const market = {
  title: "Market",
  async show() {
    wire();
    if (mounted) return;
    mounted = true;
    await this.refresh(true);
  },
  async refresh(first = false) {
    await Promise.allSettled([loadIndices(), loadBreadth(), loadFlowsMini(), loadMovers(),
      ...(first ? [] : [...ui.loaded].map((k) => loaders[k]()))]);
  },
};
