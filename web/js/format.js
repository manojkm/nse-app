// Number formatting for Indian markets (lakh/crore grouping, ₹).

export const toNum = (v) => {
  if (v === null || v === undefined || v === "") return NaN;
  if (typeof v === "number") return v;
  return Number(String(v).replace(/[,₹%\s]/g, ""));
};

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2, minimumFractionDigits: 2 });
const dec = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const int = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

export const money = (v) => (Number.isFinite(toNum(v)) ? inr.format(toNum(v)) : "—");
export const number = (v) => (Number.isFinite(toNum(v)) ? dec.format(toNum(v)) : "—");
export const integer = (v) => (Number.isFinite(toNum(v)) ? int.format(toNum(v)) : "—");

/** 1,23,45,678 -> "1.23 Cr", 4,56,000 -> "4.56 L" */
export const compact = (v) => {
  const n = toNum(v);
  if (!Number.isFinite(n)) return "—";
  const a = Math.abs(n);
  if (a >= 1e7) return `${dec.format(n / 1e7)} Cr`;
  if (a >= 1e5) return `${dec.format(n / 1e5)} L`;
  return int.format(n);
};

export const direction = (v) => {
  const n = toNum(v);
  if (!Number.isFinite(n) || n === 0) return "flat";
  return n > 0 ? "up" : "down";
};

/** "+1.24%" with an arrow so direction never depends on color alone. */
export const pct = (v) => {
  const n = toNum(v);
  if (!Number.isFinite(n)) return "—";
  const arrow = n > 0 ? "▲" : n < 0 ? "▼" : "";
  return `${arrow} ${n > 0 ? "+" : ""}${dec.format(n)}%`.trim();
};

export const signed = (v) => {
  const n = toNum(v);
  if (!Number.isFinite(n)) return "—";
  return `${n > 0 ? "+" : ""}${dec.format(n)}`;
};

export const symbolOf = (ticker = "") => String(ticker).replace(/\.(NS|BO)$/i, "");

export const shortDate = (iso, long = false) => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleDateString("en-IN", long ? { day: "numeric", month: "short", year: "numeric" } : { month: "short", year: "2-digit" });
};

export const time = (d = new Date()) =>
  d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

/** Signed rupee crore, sign before the symbol: "+₹1,234.50 cr", "−₹2,236.55 cr". */
export const croreSigned = (v) => {
  const n = toNum(v);
  if (!Number.isFinite(n)) return "—";
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}₹${dec.format(Math.abs(n))} cr`;
};

/** Signed whole number with Indian grouping: "+45,186", "−2,534". */
export const signedInt = (v) => {
  const n = toNum(v);
  if (!Number.isFinite(n)) return "—";
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${int.format(Math.abs(Math.round(n)))}`;
};
