import { callTool, state } from "./api.js";
import { $, $$, toast } from "./dom.js";
import { integer, time } from "./format.js";
import { go, onRoute } from "./router.js";
import { flowsView } from "./views/flows.js";
import { ipoView } from "./views/ipo.js";
import { market } from "./views/market.js";
import { optionsView } from "./views/options.js";
import { stockView } from "./views/stock.js";

const VIEWS = { market, stock: stockView, options: optionsView, flows: flowsView, ipo: ipoView };
let current = "market";

const store = {
  get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};

function route({ view, arg, params }) {
  if (!VIEWS[view]) return go("market");
  current = view;
  $$("[data-view]").forEach((el) => (el.hidden = el.dataset.view !== view));
  $$("[data-nav]").forEach((a) => (a.dataset.nav === view ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
  if (view !== "stock") document.title = `${VIEWS[view].title} · NSE · BSE Live`;
  window.scrollTo({ top: 0 });
  Promise.resolve(VIEWS[view].show(arg, params)).finally(stamp);
}

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

async function refresh() {
  const btn = $("#refresh-btn");
  btn.classList.add("is-spinning");
  btn.disabled = true;
  try {
    await VIEWS[current].refresh();
  } finally {
    btn.classList.remove("is-spinning");
    btn.disabled = false;
    stamp();
  }
}

function setup() {
  $("#theme-btn").addEventListener("click", () => {
    const root = document.documentElement;
    const isDark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = isDark ? "light" : "dark";
    store.set("theme", root.dataset.theme);
  });

  const input = $("#search-input");
  $("#search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.blur();
    go("stock", q, /^[A-Za-z0-9&-]{2,20}$/.test(q) ? { s: q.toUpperCase() } : {});
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !e.target.closest("input, textarea, select")) { e.preventDefault(); input.focus(); }
  });

  const box = $("#auto-refresh");
  box.checked = store.get("autoRefresh") === "1";
  let timer;
  const apply = () => {
    clearInterval(timer);
    if (box.checked) timer = setInterval(() => { if (!document.hidden && marketStatus()) refresh(); }, 60_000);
  };
  box.addEventListener("change", () => {
    store.set("autoRefresh", box.checked ? "1" : "0");
    apply();
    toast(box.checked ? "Auto-refresh on for the current tab while the market is open. Each refresh uses API quota." : "Auto-refresh off.");
  });
  apply();

  $("#refresh-btn").addEventListener("click", refresh);
  $("#usage-btn").addEventListener("click", async () => {
    const out = $("#usage");
    out.textContent = "Checking…";
    try {
      const u = await callTool("get_api_usage");
      const used = u.total_requests ?? u.used, limit = u.hard_limit ?? u.limit;
      out.textContent = limit ? `${integer(used)} of ${integer(limit)} IndianAPI requests used (${integer(u.remaining_requests ?? limit - used)} left)` : `${integer(used)} requests used`;
    } catch (err) {
      out.textContent = err.message;
    }
  });
  document.addEventListener("demo-change", () => { $("#demo-badge").hidden = !state.demo; stamp(); });
  $("#mcp-url").textContent = new URL("mcp", location.href).href;

  marketStatus();
  setInterval(marketStatus, 30_000);
}

setup();
onRoute(route);
