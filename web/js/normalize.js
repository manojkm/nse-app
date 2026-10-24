// IndianAPI uses different field names across endpoints and API versions
// (e.g. `company` vs `displayName`, `percent_change` vs `percentChange`).
// These helpers map every known variant to one shape the UI can rely on.

const pick = (row, ...keys) => {
  for (const k of keys) {
    const v = row?.[k];
    if (v !== undefined && v !== null && v !== "") return v;
  }
  return undefined;
};

/** Internal ids like "S0003057" are not tradable symbols, so ignore them. */
const realSymbol = (v) => {
  if (!v) return "";
  const s = String(v).replace(/\.(NS|BO|NSE|BSE)$/i, "");
  return /^S\d{5,}$/.test(s) ? "" : s;
};

export function stock(row) {
  const symbol = realSymbol(pick(row, "ric", "ticker", "symbol", "nseCode", "ticker_id", "tickerId"));
  const name = pick(row, "company", "company_name", "companyName", "displayName", "name") ?? symbol;
  return {
    symbol,
    name,
    title: symbol || name,
    subtitle: symbol ? name : "",
    price: pick(row, "price", "ltp", "lastPrice"),
    change: pick(row, "percent_change", "percentChange", "per_change", "pChange"),
    netChange: pick(row, "net_change", "netChange", "change"),
    volume: pick(row, "volume", "totalVolume"),
    high: pick(row, "high", "dayHigh"),
    low: pick(row, "low", "dayLow"),
    yearHigh: pick(row, "52_week_high", "yearHigh", "year_high", "high52"),
    yearLow: pick(row, "52_week_low", "yearLow", "year_low", "low52"),
  };
}

export function commodity(row) {
  return {
    symbol: pick(row, "product", "commoditySymbol", "symbol") ?? "—",
    expiry: pick(row, "expiry", "expiryDate", "product_month", "contractMonth"),
    price: pick(row, "last_traded_price", "lastTradedPrice", "ltp"),
    unit: pick(row, "priceUnit", "unit"),
    change: pick(row, "per_change", "percentageChange", "percent_change"),
    netChange: pick(row, "change", "priceChange"),
    openInterest: pick(row, "open_interest", "openInterest"),
  };
}

/** Accepts a plain list or {NSE_X: [...], BSE_X: [...]} and returns the rows for one exchange. */
export function byExchange(data, exchange = "NSE") {
  if (Array.isArray(data)) return data;
  if (!data || typeof data !== "object") return [];
  const keys = Object.keys(data);
  const key = keys.find((k) => k.toUpperCase().startsWith(exchange)) ?? keys.find((k) => Array.isArray(data[k]));
  const rows = key ? data[key] : [];
  return Array.isArray(rows) ? rows.filter((r) => r && typeof r === "object") : [];
}
