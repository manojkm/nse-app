import { callTool } from "../api.js";
import { $, empty, h, mount, segmented } from "../dom.js";
import { money, pct, shortDate } from "../format.js";
import { section } from "../ui.js";

const ui = { status: "open", data: null, wired: false, loaded: false };

const fmtDate = (d) => (d ? shortDate(d, true) : null);
const band = (r) => (r.min_price && r.max_price ? `${money(r.min_price)} – ${money(r.max_price)}` : r.issue_price ? money(r.issue_price) : null);

function ipoCard(r) {
  const facts = [
    ["Price band", band(r)],
    ["Bidding", r.bidding_start_date ? `${fmtDate(r.bidding_start_date)} – ${fmtDate(r.bidding_end_date)}` : r.additional_text],
    ["Lot size", r.lot_size ? `${r.lot_size} shares` : null],
    ["Issue size", r.issue_size],
    ["Listed", fmtDate(r.listing_date)],
    ["Listing price", r.listing_price ? money(r.listing_price) : null],
    ["Current", r.current_price ? money(r.current_price) : null],
  ].filter(([, v]) => v);
  const gain = r.listing_gains ?? r.listing_gain;
  return h("article", { class: "ipo-card" },
    h("div", { class: "ipo-card__head" },
      h("div", {}, h("h3", {}, r.name ?? r.symbol ?? "—"), h("span", { class: "muted" }, r.symbol ?? "")),
      h("div", { class: "ipo-card__badges" },
        r.is_sme ? h("span", { class: "badge" }, "SME") : h("span", { class: "badge" }, "Mainboard"),
        gain !== undefined && gain !== null ? h("span", { class: `chip ${gain >= 0 ? "up" : "down"}` }, `Listing ${pct(gain)}`) : null)),
    h("dl", { class: "facts" }, facts.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])),
    typeof r.document_url === "string" && /^https?:\/\//.test(r.document_url)
      ? h("a", { href: r.document_url, target: "_blank", rel: "noopener noreferrer", class: "link-btn" }, "Offer document →") : null);
}

function renderIpos() {
  const list = ui.data?.[ui.status] ?? [];
  const rows = (Array.isArray(list) ? list : []).filter((r) => r && typeof r === "object");
  return rows.length ? rows.map(ipoCard) : [empty(`No ${ui.status} IPOs right now.`)];
}

const timeAgo = (iso) => {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const m = Math.round((Date.now() - t) / 60000);
  if (m < 60) return `${Math.max(1, m)} min ago`;
  if (m < 60 * 24) return `${Math.round(m / 60)} h ago`;
  return shortDate(iso, true);
};

function load() {
  ui.loaded = true;
  section($("#ipos"), "card", () => callTool("get_ipos"), (d) => { ui.data = d; return renderIpos(); }, 3);
  section($("#news"), "row", () => callTool("get_market_news"), (d) => {
    const items = (Array.isArray(d) ? d : d?.news ?? []).filter((n) => n && (n.title || n.headline));
    if (!items.length) return empty("No news right now.");
    return h("ul", { class: "news news--feed" }, items.map((n) => {
      const url = typeof n.url === "string" && /^https?:\/\//.test(n.url) ? n.url : null;
      const title = n.title || n.headline;
      return h("li", {},
        url ? h("a", { href: url, target: "_blank", rel: "noopener noreferrer", class: "news__title" }, title) : h("span", { class: "news__title" }, title),
        n.summary ? h("p", { class: "muted" }, n.summary) : null,
        h("div", { class: "news__meta" },
          h("span", {}, [n.source, timeAgo(n.pub_date || n.date)].filter(Boolean).join(" · ")),
          ...(Array.isArray(n.topics) ? n.topics.slice(0, 3).map((t) => h("span", { class: "tag tag--flat" }, t)) : [])));
    }));
  }, 5);
}

export const ipoView = {
  title: "IPO & News",
  show() {
    if (!ui.wired) {
      ui.wired = true;
      segmented($("#ipo-status"), "status", (s) => { ui.status = s; if (ui.data) mount($("#ipos"), renderIpos()); });
    }
    if (!ui.loaded) load();
  },
  refresh: load,
};
