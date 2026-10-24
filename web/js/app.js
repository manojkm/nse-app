import { callTool, state } from "./api.js";
import { lineChart } from "./chart.js";
import { $, $$, empty, errorBox, h, mount, segmented, skeleton, toast } from "./dom.js";
import { compact, direction, integer, money, number, pct, shortDate, symbolOf, time, toNum } from "./format.js";

const store = {
  get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};

const ui = {
  selected: null,       // { query, symbol }
  period: "1yr",
  exchange: "NSE",
  w52Exchange: "NSE",
  w52Data: null,
  mfData: null,
  chart: null,
  loaded: new Set(),    // lazy sections already loaded
};

const chip = (v) => h("span", { class: `chip ${direction(v)}` }, pct(v));

// ---------------------------------------------------------------- generic table

/**
 * columns: [{ label, align, value(row) -> sortable, render(row) -> node|string, hideSm }]
 */
function table(columns, rows, { onRow, label, initialSort } = {}) {
  let sortIdx = initialSort ?? -1;
  let sortDir = -1;
  const tbody = h("tbody");
  const ths = columns.map((c, i) => {
    const cls = [c.align === "r" ? "r" : "", c.hideSm ? "hide-sm" : ""].join(" ").trim() || undefined;
    if (!c.value) return h("th", { scope: "col", class: cls }, c.label);
    return h("th", { scope: "col", class: cls, "aria-sort": i === sortIdx ? "descending" : "none" },
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
        return h("td", { class: [c.align === "r" ? "r" : "", c.hideSm ? "hide-sm" : ""].join(" ").trim() || undefined }, content);
      });
      return h("tr", { class: onRow ? "is-clickable" : undefined, onclick: onRow ? () => onRow(row) : undefined }, cells);
    }));
  }
  render();
  return h("table", { "aria-label": label }, h("thead", {}, h("tr", {}, ths)), tbody);
}

const nameCell = (symbol, company) => h("span", { class: "cell-name" }, h("strong", {}, symbol), h("span", {}, company));

async function section(target, kind, load, render) {
  skeleton(target, kind, kind === "card" ? 3 : 5);
  try {
    const data = await load();
    mount(target, render(data));
  } catch (err) {
    mount(target, errorBox(err.message, () => section(target, kind, load, render)));
  }
}

// ---------------------------------------------------------------- movers

function stockCard(row) {
  const symbol = symbolOf(row.ric || row.ticker_id || row.ticker);
  const company = row.company_name || row.company;
  const card = h("button", {
    type: "button", class: "stock-card", dataset: { symbol },
    "aria-label": `${company}, ${money(row.price)}, ${pct(row.percent_change)}. Show details.`,
    onclick: () => openStock(company, symbol),
  },
  h("span", { class: "stock-card__sym" }, symbol),
  h("span", { class: "stock-card__name" }, company),
  h("span", { class: "stock-card__row" }, h("span", { class: "stock-card__price" }, money(row.price)), chip(row.percent_change)));
  return card;
}

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
      mount(gainers, g.length ? g.map(stockCard) : empty("No gainers right now."));
      mount(losers, l.length ? l.map(stockCard) : empty("No losers right now."));
      markSelected();
      if (!ui.selected && g[0]) openStock(g[0].company_name || g[0].company, symbolOf(g[0].ric || g[0].ticker_id), { scroll: false });
    })
    .catch((err) => {
      mount(gainers, errorBox(err.message, loadMovers));
      mount(losers);
      if (!ui.selected) openStock("Reliance", "RELIANCE", { scroll: false });
    });
}

function markSelected() {
  $$(".stock-card").forEach((c) => c.setAttribute("aria-current", String(c.dataset.symbol === ui.selected?.symbol)));
}

// ---------------------------------------------------------------- stock detail

async function openStock(query, symbolHint, { scroll = true } = {}) {
  if (!query) return;
  const detail = $("#detail");
  ui.selected = { query, symbol: symbolHint || query.toUpperCase() };
  markSelected();
  $("#detail-title").textContent = query;
  $("#detail-symbol").textContent = "";
  $("#detail-industry").textContent = "Loading…";
  skeleton($("#detail-quote"), "row", 1);
  skeleton($("#detail-stats"), "row", 1);
  $("#detail-extra").replaceChildren();
  if (scroll) detail.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });

  let data;
  try {
    data = await callTool("get_stock_data", { name: query });
  } catch (err) {
    $("#detail-industry").textContent = "Company";
    mount($("#detail-quote"));
    mount($("#detail-stats"), errorBox(err.status === 404 ? `Couldn't find “${query}”. Try the full company name or NSE symbol.` : err.message,
      () => openStock(query, symbolHint)));
    clearChart("No chart available.");
    return;
  }
  if (ui.selected?.query !== query) return; // a newer selection won

  const symbol = data.tickerId || symbolHint || query;
  ui.selected = { query, symbol };
  markSelected();
  renderDetail(data, symbol);
  if (scroll) detail.focus({ preventScroll: true });
  loadChart();
}

function renderDetail(d, symbol) {
  const nse = d.currentPrice?.NSE;
  const bse = d.currentPrice?.BSE;
  const change = d.percentChange;
  $("#detail-title").textContent = d.companyName || symbol;
  $("#detail-industry").textContent = d.industry || "Company";
  $("#detail-symbol").textContent = `NSE: ${symbol}`;
  document.title = `${symbol} ${money(nse ?? bse)} · NSE · BSE Live`;

  mount($("#detail-quote"),
    h("span", { class: "detail__price" }, money(nse ?? bse)),
    chip(change),
    bse !== undefined && nse !== undefined ? h("span", { class: "detail__alt" }, `BSE ${money(bse)}`) : null);

  const lo = toNum(d.yearLow), hi = toNum(d.yearHigh), now = toNum(nse ?? bse);
  const stats = [];
  if (Number.isFinite(lo) && Number.isFinite(hi) && hi > lo) {
    const posPct = Math.min(100, Math.max(0, ((now - lo) / (hi - lo)) * 100));
    stats.push(h("div", { class: "stat stat--range" },
      h("span", { class: "stat__label" }, "52-week range"),
      h("div", { class: "range", role: "img", "aria-label": `Current price is ${Math.round(posPct)}% of the way from the 52-week low to the high` },
        h("div", { class: "range__bar" }, h("span", { class: "range__marker", style: `left:${posPct}%` })),
        h("div", { class: "range__ends" }, h("span", {}, money(lo)), h("span", {}, money(hi))))));
  }
  const m = d.keyMetrics || {};
  const metric = (label, value) => value !== undefined && value !== null && value !== "" &&
    h("div", { class: "stat" }, h("span", { class: "stat__label" }, label), h("span", { class: "stat__value" }, value));
  stats.push(
    metric("From 52W high", Number.isFinite(hi) && Number.isFinite(now) ? pct(((now - hi) / hi) * 100) : undefined),
    metric("From 52W low", Number.isFinite(lo) && Number.isFinite(now) ? pct(((now - lo) / lo) * 100) : undefined),
    metric("Market cap", findMetric(m, /market ?cap/i)),
    metric("P/E", findMetric(m, /^p\/?e|pPerEBasic|peRatio/i)),
  );
  mount($("#detail-stats"), stats);

  const extra = [];
  const about = d.companyProfile?.companyDescription;
  if (about) extra.push(h("p", { class: "muted" }, about.length > 360 ? `${about.slice(0, 360).trim()}…` : about));
  const news = (Array.isArray(d.recentNews) ? d.recentNews : []).slice(0, 4);
  if (news.length) {
    extra.push(h("h3", { class: "eyebrow" }, "Recent news"),
      h("ul", { class: "news" }, news.map((n) => {
        const title = n.headline || n.title || "Untitled";
        const url = typeof n.url === "string" && /^https?:\/\//.test(n.url) ? n.url : null;
        return h("li", {}, url ? h("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, title) : title,
          n.date ? h("div", { class: "muted" }, shortDate(n.date, true)) : null);
      })));
  }
  $("#detail-extra").replaceChildren(...extra);
}

/** keyMetrics is deeply nested in the live API; find the first value whose key/displayName matches. */
function findMetric(obj, re, depth = 0) {
  if (!obj || typeof obj !== "object" || depth > 4) return undefined;
  for (const [k, v] of Object.entries(obj)) {
    if (v && typeof v === "object") {
      if ((re.test(v.key || "") || re.test(v.displayName || "")) && v.value !== undefined) return number(v.value);
      const found = findMetric(v, re, depth + 1);
      if (found) return found;
    } else if (re.test(k) && (typeof v === "number" || /^-?[\d.,]+$/.test(String(v)))) {
      return number(v);
    }
  }
  return undefined;
}

// ---------------------------------------------------------------- chart

const SERIES = {
  Price: { color: "var(--series-1)", label: "Price", short: "Price" },
  DMA50: { color: "var(--series-2)", label: "50-day avg", short: "50 DMA" },
  DMA200: { color: "var(--series-3)", label: "200-day avg", short: "200 DMA" },
};

function clearChart(message) {
  ui.chart?.destroy();
  ui.chart = null;
  $("#chart-plot").replaceChildren(empty(message));
  $("#chart").removeAttribute("aria-busy");
  $("#chart-legend").replaceChildren();
  $("#chart-table").replaceChildren();
}

async function loadChart() {
  const sel = ui.selected;
  if (!sel) return;
  const period = ui.period;
  const plot = $("#chart-plot");
  $("#chart").setAttribute("aria-busy", "true");
  $("#chart-tooltip").hidden = true;
  plot.replaceChildren(h("div", { class: "skeleton skeleton--chart" }));

  let data;
  try {
    data = await callTool("get_historical_data", { stock_name: sel.symbol, period, filter: "price" });
  } catch (err) {
    if (ui.selected !== sel || ui.period !== period) return;
    ui.chart?.destroy();
    plot.replaceChildren(errorBox(err.message, loadChart));
    $("#chart").removeAttribute("aria-busy");
    return;
  }
  if (ui.selected !== sel || ui.period !== period) return;

  const series = (data?.datasets ?? [])
    .filter((ds) => SERIES[ds.metric])
    .map((ds) => ({
      ...SERIES[ds.metric],
      points: (ds.values ?? [])
        .map(([d, v]) => ({ t: new Date(d), v: toNum(v) }))
        .filter((p) => Number.isFinite(p.v) && !Number.isNaN(p.t.getTime())),
    }))
    .filter((s) => s.points.length > 1)
    .sort((a, b) => (a.label === "Price" ? -1 : b.label === "Price" ? 1 : 0));

  if (!series.length || series[0].label !== "Price") return clearChart("No price history for this period.");

  ui.chart?.destroy();
  ui.chart = lineChart(plot, $("#chart-tooltip"), series);
  $("#chart").removeAttribute("aria-busy");

  $("#chart-legend").replaceChildren(...series.map((s) =>
    h("span", { class: "legend__item" }, h("span", { class: "legend__swatch", style: `background:${s.color}` }), s.label)));

  const p = series[0].points;
  const change = ((p.at(-1).v - p[0].v) / p[0].v) * 100;
  $("#chart-caption").textContent = `${sel.symbol} price from ${shortDate(p[0].t, true)} to ${shortDate(p.at(-1).t, true)}: ${money(p[0].v)} to ${money(p.at(-1).v)} (${pct(change)}).`;

  // Table view (newest first)
  const lookup = series.map((s) => new Map(s.points.map((pt) => [pt.t.getTime(), pt.v])));
  const rows = [...p].reverse().slice(0, 260);
  $("#chart-table").replaceChildren(table(
    [{ label: "Date", render: (r) => shortDate(r.t, true) },
      ...series.map((s, i) => ({ label: s.label, align: "r", render: (r) => money(lookup[i].get(r.t.getTime())) }))],
    rows, { label: `${sel.symbol} price history` }));
}

// ---------------------------------------------------------------- lazy sections

const loaders = {
  active: () => section($("#active-table"), "row",
    () => callTool(ui.exchange === "NSE" ? "get_nse_most_active" : "get_bse_most_active"),
    (rows) => (rows?.length ? table([
      { label: "Stock", render: (r) => nameCell(symbolOf(r.ticker), r.company), value: (r) => symbolOf(r.ticker) },
      { label: "Price", align: "r", render: (r) => money(r.price), value: (r) => toNum(r.price) },
      { label: "Change", align: "r", render: (r) => chip(r.percent_change), value: (r) => toNum(r.percent_change) },
      { label: "Volume", align: "r", render: (r) => compact(r.volume), value: (r) => toNum(r.volume) },
    ], rows, { label: `${ui.exchange} most active`, initialSort: 3, onRow: (r) => openStock(r.company, symbolOf(r.ticker)) })
      : empty("No data. The market may be closed."))),

  week52: () => section($("#w52"), "row", () => callTool("get_52_week_high_low"), (data) => {
    ui.w52Data = data;
    return renderW52();
  }),

  shockers: () => section($("#shockers-table"), "row", () => callTool("get_price_shockers"),
    (rows) => {
      const list = Array.isArray(rows) ? rows : rows?.NSE_PriceShocker ?? rows?.BSE_PriceShocker ?? [];
      return list.length ? table([
        { label: "Stock", render: (r) => nameCell(symbolOf(r.ticker), r.company), value: (r) => symbolOf(r.ticker) },
        { label: "Price", align: "r", render: (r) => money(r.price), value: (r) => toNum(r.price) },
        { label: "Change", align: "r", render: (r) => chip(r.percent_change), value: (r) => Math.abs(toNum(r.percent_change)) },
        { label: "Day range", align: "r", hideSm: true, render: (r) => `${number(r.low)} – ${number(r.high)}` },
      ], list, { label: "Price shockers", initialSort: 2, onRow: (r) => openStock(r.company, symbolOf(r.ticker)) })
        : empty("No sharp moves right now.");
    }),

  commodities: () => section($("#commodities-table"), "row", () => callTool("get_commodities"),
    (rows) => (rows?.length ? table([
      { label: "Contract", render: (r) => nameCell(r.commoditySymbol, r.expiryDate ? `Exp ${r.expiryDate}` : ""), value: (r) => r.commoditySymbol },
      { label: "LTP", align: "r", render: (r) => h("span", {}, money(r.lastTradedPrice), h("span", { class: "muted" }, r.priceUnit ? ` /${r.priceUnit}` : "")), value: (r) => toNum(r.lastTradedPrice) },
      { label: "Change", align: "r", render: (r) => chip(r.percentageChange), value: (r) => toNum(r.percentageChange) },
      { label: "Open int.", align: "r", hideSm: true, render: (r) => integer(r.openInterest), value: (r) => toNum(r.openInterest) },
    ], rows, { label: "Commodity futures" }) : empty("No commodity data right now."))),

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
  const list = (title, cls, rows, key) => h("div", {},
    h("h3", { class: `eyebrow ${cls}` }, title),
    rows?.length ? h("ul", {}, rows.slice(0, 6).map((r) => h("li", {},
      h("button", { class: "row-btn cell-name", type: "button", onclick: () => openStock(r.company, symbolOf(r.ticker)) },
        h("strong", {}, symbolOf(r.ticker)), h("span", {}, r.company)),
      h("span", { class: "r num" }, money(r.price), h("div", { class: "muted" }, `52W ${money(r[key])}`)))))
      : empty("None right now (often empty when the market is closed)."));
  return [
    list("▲ Near 52-week high", "eyebrow--up", side.high52Week, "52_week_high"),
    list("▼ Near 52-week low", "eyebrow--down", side.low52Week, "52_week_low"),
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

function setupLazy() {
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const key = e.target.dataset.lazy;
      io.unobserve(e.target);
      ui.loaded.add(key);
      loaders[key]();
    }
  }, { rootMargin: "200px" });
  $$("[data-lazy]").forEach((el) => io.observe(el));
}

// ---------------------------------------------------------------- chrome

function marketStatus() {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata", weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false,
  }).formatToParts(new Date()).map((p) => [p.type, p.value]));
  const mins = Number(parts.hour) * 60 + Number(parts.minute);
  const weekday = !["Sat", "Sun"].includes(parts.weekday);
  const open = weekday && mins >= 9 * 60 + 15 && mins < 15 * 60 + 30;
  const pre = weekday && mins >= 9 * 60 && mins < 9 * 60 + 15;
  const el = $("#market-status");
  el.dataset.state = open ? "open" : "closed";
  $(".pill__label", el).textContent = open ? "Market open" : pre ? "Pre-open" : "Market closed";
  el.setAttribute("aria-label", $(".pill__label", el).textContent);
  return open;
}

function stamp() {
  $("#updated-at").textContent = `Updated ${time()} IST${state.demo ? " · sample data" : ""}`;
}

async function refreshAll() {
  const btn = $("#refresh-btn");
  btn.classList.add("is-spinning");
  btn.disabled = true;
  await Promise.allSettled([
    loadMovers(),
    ui.selected ? openStock(ui.selected.query, ui.selected.symbol, { scroll: false }) : null,
    ...[...ui.loaded].map((k) => loaders[k]()),
  ]);
  btn.classList.remove("is-spinning");
  btn.disabled = false;
  stamp();
}

function setupTheme() {
  $("#theme-btn").addEventListener("click", () => {
    const root = document.documentElement;
    const isDark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = isDark ? "light" : "dark";
    store.set("theme", root.dataset.theme);
  });
}

function setupAutoRefresh() {
  const box = $("#auto-refresh");
  box.checked = store.get("autoRefresh") === "1";
  let timer;
  const apply = () => {
    clearInterval(timer);
    if (box.checked) timer = setInterval(() => { if (!document.hidden && marketStatus()) refreshAll(); }, 60_000);
  };
  box.addEventListener("change", () => {
    store.set("autoRefresh", box.checked ? "1" : "0");
    apply();
    toast(box.checked ? "Auto-refresh on while the market is open. Each refresh uses API quota." : "Auto-refresh off.");
  });
  apply();
}

function setupSearch() {
  const input = $("#search-input");
  $("#search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (q) { openStock(q); input.blur(); }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !e.target.closest("input, textarea, select")) { e.preventDefault(); input.focus(); }
  });
}

function init() {
  setupTheme();
  setupSearch();
  setupAutoRefresh();
  marketStatus();
  setInterval(marketStatus, 30_000);
  $("#mcp-url").textContent = new URL("mcp", location.href).href;

  segmented($("#period-group"), "period", (p) => { ui.period = p; loadChart(); });
  segmented($("#active-exchange"), "exchange", (x) => { ui.exchange = x; loaders.active(); });
  segmented($("#w52-exchange"), "exchange", (x) => { ui.w52Exchange = x; if (ui.w52Data) mount($("#w52"), renderW52()); });
  $("#mf-category").addEventListener("change", () => mount($("#mf-table"), renderFunds()));
  $("#refresh-btn").addEventListener("click", refreshAll);
  $("#chart-table-btn").addEventListener("click", (e) => {
    const wrap = $("#chart-table");
    wrap.hidden = !wrap.hidden;
    e.currentTarget.setAttribute("aria-expanded", String(!wrap.hidden));
    e.currentTarget.textContent = wrap.hidden ? "View as table" : "Hide table";
  });
  document.addEventListener("demo-change", () => { $("#demo-badge").hidden = !state.demo; stamp(); });

  loadMovers().finally(stamp);
  setupLazy();
}

init();
