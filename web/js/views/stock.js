import { callTool } from "../api.js";
import { lineChart } from "../chart.js";
import { $, empty, errorBox, h, mount, segmented, skeleton } from "../dom.js";
import { compact, direction, integer, money, number, pct, shortDate, toNum } from "../format.js";
import { firstGainer } from "./market.js";
import { go } from "../router.js";
import { chip, hoverTip, legend, section, table, tipRows, toneTag } from "../ui.js";

const ui = { query: null, symbol: null, price: null, period: "1yr", vpMonths: "3", chart: null, wired: false, token: 0 };

const isSymbol = (s) => typeof s === "string" && /^[A-Z0-9&-]{2,20}$/.test(s);

// ---------------------------------------------------------------- detail

async function load(query, hint) {
  const token = ++ui.token;
  ui.query = query;
  ui.symbol = isSymbol(hint) ? hint : null;
  $("#detail-title").textContent = query;
  $("#detail-symbol").textContent = "";
  $("#detail-industry").textContent = "Loading…";
  skeleton($("#detail-quote"), "row", 1);
  skeleton($("#detail-stats"), "row", 1);
  $("#detail-extra").replaceChildren();
  ["#scorecard", "#analyst", "#volume-profile", "#corp-actions"].forEach((s) => skeleton($(s), "row", 3));
  $("#compare").replaceChildren();

  let data;
  try {
    data = await callTool("get_stock_data", { name: query });
  } catch (err) {
    if (token !== ui.token) return;
    $("#detail-industry").textContent = "Company";
    mount($("#detail-quote"));
    mount($("#detail-stats"), errorBox(err.status === 404 ? `Couldn't find “${query}”. Try the full company name or NSE symbol.` : err.message, () => load(query, hint)));
    clearChart("No chart available.");
    if (ui.symbol) loadInsights(token); else ["#scorecard", "#analyst", "#volume-profile", "#corp-actions"].forEach((s) => mount($(s), empty("Needs a valid company.")));
    return;
  }
  if (token !== ui.token) return;

  const sym = [data.tickerId, data.companyProfile?.exchangeCodeNse, hint, query.toUpperCase().replace(/\s+/g, "")].find(isSymbol);
  ui.symbol = sym || query;
  ui.price = toNum(data.currentPrice?.NSE ?? data.currentPrice?.BSE);
  renderDetail(data);
  $("#compare-input").value = ui.symbol;
  loadChart();
  loadInsights(token);
}

function renderDetail(d) {
  const nse = d.currentPrice?.NSE;
  const bse = d.currentPrice?.BSE;
  const symbol = ui.symbol;
  $("#detail-title").textContent = d.companyName || symbol;
  $("#detail-industry").textContent = d.industry || "Company";
  $("#detail-symbol").textContent = isSymbol(symbol) ? `NSE: ${symbol}` : "";
  document.title = `${symbol} ${money(nse ?? bse)} · NSE · BSE Live`;

  mount($("#detail-quote"),
    h("span", { class: "detail__price" }, money(nse ?? bse)),
    chip(d.percentChange),
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
  if (about) extra.push(h("p", { class: "muted" }, about.length > 480 ? `${about.slice(0, 480).trim()}…` : about));
  const news = (Array.isArray(d.recentNews) ? d.recentNews : []).slice(0, 5);
  if (news.length) {
    extra.push(h("h3", { class: "eyebrow" }, "Recent news"),
      h("ul", { class: "news" }, news.map((n) => {
        const title = n.headline || n.title || "Untitled";
        const url = typeof n.url === "string" && /^https?:\/\//.test(n.url) ? n.url : null;
        return h("li", {}, url ? h("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, title) : title,
          n.date ? h("div", { class: "muted" }, shortDate(n.date, true)) : null);
      })));
  }
  $("#detail-extra").replaceChildren(...(extra.length ? extra : [empty("No profile or news available.")]));
}

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

// ---------------------------------------------------------------- price chart

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
  const token = ui.token, period = ui.period, symbol = ui.symbol;
  const plot = $("#chart-plot");
  $("#chart").setAttribute("aria-busy", "true");
  $("#chart-tooltip").hidden = true;
  plot.replaceChildren(h("div", { class: "skeleton skeleton--chart" }));
  let data;
  try {
    data = await callTool("get_historical_data", { stock_name: symbol, period, filter: "price" });
  } catch (err) {
    if (token !== ui.token || period !== ui.period) return;
    ui.chart?.destroy();
    plot.replaceChildren(errorBox(err.message, loadChart));
    $("#chart").removeAttribute("aria-busy");
    return;
  }
  if (token !== ui.token || period !== ui.period) return;

  const series = (data?.datasets ?? [])
    .filter((ds) => SERIES[ds.metric])
    .map((ds) => ({ ...SERIES[ds.metric], points: (ds.values ?? []).map(([d, v]) => ({ t: new Date(d), v: toNum(v) }))
      .filter((p) => Number.isFinite(p.v) && !Number.isNaN(p.t.getTime())) }))
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
  $("#chart-caption").textContent = `${symbol} price from ${shortDate(p[0].t, true)} to ${shortDate(p.at(-1).t, true)}: ${money(p[0].v)} to ${money(p.at(-1).v)} (${pct(change)}).`;
  const lookup = series.map((s) => new Map(s.points.map((pt) => [pt.t.getTime(), pt.v])));
  $("#chart-table").replaceChildren(table(
    [{ label: "Date", render: (r) => shortDate(r.t, true) },
      ...series.map((s, i) => ({ label: s.label, align: "r", render: (r) => money(lookup[i].get(r.t.getTime())) }))],
    [...p].reverse().slice(0, 260), { label: `${symbol} price history` }));
}

// ---------------------------------------------------------------- insights

function loadInsights(token) {
  const sym = ui.symbol;
  const price = Number.isFinite(ui.price) ? ui.price : undefined;
  callTool("get_stock_scorecard", { symbol: sym, price })
    .then((d) => { if (token === ui.token) { renderScorecard(d); renderAnalyst(d.analyst, d.price ?? price, d.errors?.analysts); } })
    .catch((err) => {
      if (token !== ui.token) return;
      mount($("#scorecard"), errorBox(err.message, () => loadInsights(ui.token)));
      mount($("#analyst"), errorBox(err.message));
    });
  loadProfile();
  section($("#corp-actions"), "row", () => callTool("get_corporate_actions", { symbol: sym }), (d) => {
    const rows = d?.actions ?? [];
    return rows.length ? table([
      { label: "Ex-date", render: (r) => shortDate(r.exDate, true), value: (r) => new Date(r.exDate).getTime() },
      { label: "Type", render: (r) => h("span", { class: `tag tag--${String(r.actionType).toLowerCase()}` }, r.actionType ?? "—") },
      { label: "Details", render: (r) => r.purpose ?? "—" },
    ], rows, { label: "Corporate actions", initialSort: 0 }) : empty("No corporate actions in the last 5 years.");
  }, 3);
}

function renderScorecard(d) {
  $("#score-overall").replaceChildren(toneTag(
    d.overall === "Mostly positive" ? "positive" : d.overall === "Mostly negative" ? "negative" : d.overall === "Mixed" ? "neutral" : "unknown",
    `${d.overall}${d.available ? ` · ${d.positive}/${d.available}` : ""}`));
  mount($("#scorecard"),
    h("ul", { class: "signals" }, d.signals.map((s) => h("li", { class: `signal signal--${s.tone}` },
      h("div", { class: "signal__head" }, h("span", { class: "signal__label" }, s.label), toneTag(s.tone, s.value)),
      h("p", { class: "signal__detail" }, s.detail)))),
    h("p", { class: "source-note" }, d.note));
}

const RATING_COLORS = { Buy: "var(--div-1)", Outperform: "var(--div-2)", Hold: "var(--div-mid)", Underperform: "var(--div-4)", Sell: "var(--div-5)" };

function renderAnalyst(a, price, error) {
  if (!a) {
    $("#analyst-consensus").replaceChildren();
    mount($("#analyst"), empty(error ? `Analyst data unavailable: ${error}` : "No analyst coverage for this stock."));
    return;
  }
  const tone = a.rating_mean <= 2.2 ? "positive" : a.rating_mean >= 3.3 ? "negative" : "neutral";
  $("#analyst-consensus").replaceChildren(toneTag(tone, a.rating_label));
  const total = Object.values(a.distribution).reduce((x, y) => x + y, 0) || 1;

  const bar = h("div", { class: "stack-bar", role: "img", "aria-label": Object.entries(a.distribution).map(([k, v]) => `${k} ${v}`).join(", ") },
    Object.entries(a.distribution).filter(([, v]) => v > 0).map(([k, v]) => {
      const seg = h("span", { class: "stack-bar__seg", tabindex: "0", style: `flex:${v};background:${RATING_COLORS[k]}`, "aria-label": `${k}: ${v} analysts` },
        v / total > 0.08 ? String(v) : "");
      hoverTip(seg, () => tipRows(k, [["Analysts", String(v), RATING_COLORS[k]], ["Share", `${Math.round((v / total) * 100)}%`]]));
      return seg;
    }));

  const t = a.target;
  let targetViz = null;
  if (t?.low && t?.high && t.high > t.low) {
    const lo = Math.min(t.low, price ?? t.low), hi = Math.max(t.high, price ?? t.high);
    const pos = (v) => `${((v - lo) / (hi - lo)) * 100}%`;
    targetViz = h("div", { class: "target" },
      h("div", { class: "target__track" },
        h("span", { class: "target__range", style: `left:${pos(t.low)};right:calc(100% - ${pos(t.high)})` }),
        h("span", { class: "target__mark target__mark--mean", style: `left:${pos(t.mean)}`, title: `Average target ${money(t.mean)}` }),
        Number.isFinite(price) ? h("span", { class: "target__mark target__mark--price", style: `left:${pos(price)}`, title: `Current ${money(price)}` }) : null),
      h("div", { class: "target__labels" },
        h("span", {}, `Low ${money(t.low)}`), h("span", {}, `High ${money(t.high)}`)),
      h("div", { class: "target__legend" },
        h("span", {}, h("i", { class: "dot dot--mean" }), `Avg target ${money(t.mean)}`),
        Number.isFinite(price) ? h("span", {}, h("i", { class: "dot dot--price" }), `Price ${money(price)}`) : null));
  }

  mount($("#analyst"),
    h("div", { class: "kpi-row" },
      h("div", { class: "kpi" }, h("span", { class: "kpi__label" }, "Upside to avg target"),
        h("span", { class: `kpi__value ${direction(a.upside_pct)}` }, a.upside_pct === null ? "—" : pct(a.upside_pct))),
      h("div", { class: "kpi" }, h("span", { class: "kpi__label" }, "Analysts"), h("span", { class: "kpi__value" }, integer(a.analysts))),
      h("div", { class: "kpi" }, h("span", { class: "kpi__label" }, "90-day trend"),
        h("span", { class: "kpi__value kpi__value--sm" }, a.sentiment_trend ? a.sentiment_trend[0].toUpperCase() + a.sentiment_trend.slice(1) : "—"))),
    h("h3", { class: "eyebrow" }, "Rating breakdown"),
    bar,
    legend(Object.keys(RATING_COLORS).map((k) => [`${k} ${a.distribution[k] ?? 0}`, RATING_COLORS[k]])),
    targetViz ? h("h3", { class: "eyebrow" }, "Target price range") : null,
    targetViz,
    h("p", { class: "muted" }, (a.summary ?? []).join(" ")));
}

// ---------------------------------------------------------------- volume profile

function loadProfile() {
  const token = ui.token;
  return section($("#volume-profile"), "row", () => callTool("get_volume_profile", { symbol: ui.symbol, months: ui.vpMonths }), (vp) => {
    if (token !== ui.token) return [];
    const bins = [...vp.bins].reverse(); // high prices on top
    const max = Math.max(...bins.map((b) => b.volume)) || 1;
    const last = vp.last_close;
    const lastIdx = Number.isFinite(last) ? bins.findIndex((b) => last >= b.low && last <= b.high) : -1;
    const rows = bins.map((b, i) => {
      const isPoc = b.mid === vp.poc;
      const row = h("div", { class: `vp__row${b.in_value_area ? " vp__row--va" : ""}${isPoc ? " vp__row--poc" : ""}`, tabindex: "0",
        "aria-label": `${money(b.low)} to ${money(b.high)}: volume ${compact(b.volume)}${isPoc ? ", point of control" : ""}` },
      h("span", { class: "vp__price num" }, number(b.mid)),
      h("span", { class: "vp__bar" },
        h("span", { class: "vp__buy", style: `width:${(b.buy_volume / max) * 100}%` }),
        h("span", { class: "vp__sell", style: `width:${(b.sell_volume / max) * 100}%` })),
      h("span", { class: "vp__tag" }, isPoc ? "POC" : i === lastIdx ? "◀ Last" : ""));
      hoverTip(row, () => tipRows(`${money(b.low)} – ${money(b.high)}`, [
        ["Buy-day volume", compact(b.buy_volume), "var(--buy)"], ["Sell-day volume", compact(b.sell_volume), "var(--sell)"],
        ["Total", compact(b.volume)], ...(b.in_value_area ? [["In value area", "Yes"]] : [])]));
      return row;
    });
    return [
      h("div", { class: "kpi-row" },
        h("div", { class: "kpi" }, h("span", { class: "kpi__label" }, "Point of control"), h("span", { class: "kpi__value" }, money(vp.poc))),
        h("div", { class: "kpi" }, h("span", { class: "kpi__label" }, "Value area"), h("span", { class: "kpi__value kpi__value--sm" }, `${money(vp.value_area_low)} – ${money(vp.value_area_high)}`)),
        h("div", { class: "kpi" }, h("span", { class: "kpi__label" }, "Last close"), h("span", { class: "kpi__value" }, money(last)))),
      legend([["Volume on up days (buying)", "var(--buy)"], ["Volume on down days (selling)", "var(--sell)"], ["Value area (70% of volume)", "var(--va)"]]),
      h("div", { class: "vp", role: "group", "aria-label": `Volume profile over ${vp.days} trading days` }, rows),
      h("p", { class: "muted" }, (vp.summary ?? []).join(" ")),
      h("p", { class: "source-note" }, `${vp.days} trading days · NSE official end-of-day data. True footprint charts need tick-level order flow, which isn't publicly available.`),
    ];
  }, 6);
}

// ---------------------------------------------------------------- compare

function runCompare(e) {
  e?.preventDefault();
  const symbols = $("#compare-input").value.trim();
  if (!symbols) return;
  section($("#compare"), "row", () => callTool("compare_stocks", { symbols, months: $("#compare-months").value }), (d) => {
    const rows = d?.stocks ?? [];
    if (!rows.length) return empty("No matching NSE symbols.");
    const maxAbs = Math.max(...rows.map((r) => Math.abs(toNum(r.return_pct)) || 0), 1);
    return [
      h("div", { class: "cmp", role: "group", "aria-label": "Returns by stock" }, rows.map((r) => {
        const v = toNum(r.return_pct);
        const w = (Math.abs(v) / maxAbs) * 50;
        const row = h("div", { class: "cmp__row", tabindex: "0", "aria-label": `${r.symbol}: ${pct(v)} return, max drawdown ${pct(r.max_drawdown)}` },
          h("span", { class: "cmp__sym" }, r.symbol),
          h("span", { class: "cmp__track" }, h("span", { class: `cmp__bar ${v >= 0 ? "cmp__bar--up" : "cmp__bar--down"}`,
            style: v >= 0 ? `left:50%;width:${w}%` : `right:50%;width:${w}%` })),
          h("span", { class: `cmp__val ${direction(v)}` }, pct(v)));
        hoverTip(row, () => tipRows(r.symbol, [["Return", pct(v)], ["Max drawdown", pct(r.max_drawdown)],
          ["Start", money(r.start_price)], ["End", money(r.end_price)]]));
        return row;
      })),
      h("p", { class: "source-note" }, `${shortDate(d.from_date, true)} – ${shortDate(d.to_date, true)} · unadjusted for splits/bonuses · NSE official data`),
    ];
  }, 3);
}

// ---------------------------------------------------------------- view

function wire() {
  if (ui.wired) return;
  ui.wired = true;
  segmented($("#period-group"), "period", (p) => { ui.period = p; loadChart(); });
  segmented($("#vp-months"), "months", (m) => { ui.vpMonths = m; loadProfile(); });
  $("#chart-table-btn").addEventListener("click", (e) => {
    const wrap = $("#chart-table");
    wrap.hidden = !wrap.hidden;
    e.currentTarget.setAttribute("aria-expanded", String(!wrap.hidden));
    e.currentTarget.textContent = wrap.hidden ? "View as table" : "Hide table";
  });
  $("#compare-form").addEventListener("submit", runCompare);
}

export const stockView = {
  title: "Stock",
  show(arg, params) {
    wire();
    const query = arg || ui.query || firstGainer?.name || "Reliance";
    const hint = params.s || (!arg ? (ui.symbol || firstGainer?.symbol || "RELIANCE") : "");
    if (!arg) return go("stock", query, { s: hint });
    if (query === ui.query) return;
    load(query, hint);
  },
  refresh() { if (ui.query) { const q = ui.query; ui.query = null; load(q, ui.symbol); } },
};
