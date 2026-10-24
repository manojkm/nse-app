// Dependency-free SVG line chart with crosshair tooltip, keyboard support and direct end labels.

import { money, shortDate } from "./format.js";

const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs = {}) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
};

function niceTicks(min, max, count = 5) {
  const span = max - min || Math.abs(max) || 1;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const start = Math.floor(min / step) * step;
  const ticks = [];
  for (let v = start; v <= max + step * 0.5; v += step) ticks.push(+v.toFixed(10));
  return ticks;
}

const axisMoney = (v) =>
  v >= 1e5 ? `₹${(v / 1e5).toFixed(1)}L` : v >= 1e3 ? `₹${(v / 1e3).toFixed(v >= 1e4 ? 0 : 1)}k` : `₹${Math.round(v)}`;

/**
 * @param {HTMLElement} plot
 * @param {HTMLElement} tooltip
 * @param {{label:string, color:string, points:{t:Date, v:number}[]}[]} series  first series is primary
 */
export function lineChart(plot, tooltip, series) {
  let width = 0;
  let height = 0;
  let activeIndex = -1;
  const primary = series[0];
  const byTime = series.map((s) => new Map(s.points.map((p) => [p.t.getTime(), p.v])));

  const all = series.flatMap((s) => s.points);
  const tMin = Math.min(...primary.points.map((p) => p.t));
  const tMax = Math.max(...primary.points.map((p) => p.t));
  const visible = all.filter((p) => p.t >= tMin && p.t <= tMax).map((p) => p.v);
  const ticks = niceTicks(Math.min(...visible), Math.max(...visible));
  const yMin = ticks[0];
  const yMax = ticks.at(-1);

  const root = svg("svg", { role: "img", tabindex: "0", "aria-label": `${primary.label} chart. Use arrow keys to read values.` });
  plot.replaceChildren(root);

  const pad = { top: 12, right: 64, bottom: 28, left: 52 };
  const x = (t) => pad.left + ((t - tMin) / (tMax - tMin || 1)) * (width - pad.left - pad.right);
  const y = (v) => pad.top + (1 - (v - yMin) / (yMax - yMin || 1)) * (height - pad.top - pad.bottom);

  let crosshair, dots;

  function draw() {
    width = plot.clientWidth;
    height = plot.clientHeight;
    if (!width || !height) return;
    root.setAttribute("viewBox", `0 0 ${width} ${height}`);
    root.replaceChildren();
    pad.right = width < 480 ? 12 : 64;

    // Grid + y axis
    const grid = svg("g");
    for (const t of ticks) {
      grid.append(svg("line", { class: "grid-line", x1: pad.left, x2: width - pad.right, y1: y(t), y2: y(t) }));
      const label = svg("text", { class: "axis-label", x: pad.left - 8, y: y(t) + 4, "text-anchor": "end" });
      label.textContent = axisMoney(t);
      grid.append(label);
    }
    // X labels
    const xCount = Math.max(2, Math.floor((width - pad.left - pad.right) / 110));
    const long = tMax - tMin < 1000 * 60 * 60 * 24 * 70;
    for (let i = 0; i <= xCount; i++) {
      const t = tMin + ((tMax - tMin) * i) / xCount;
      const label = svg("text", { class: "axis-label", x: x(t), y: height - 8, "text-anchor": i === 0 ? "start" : i === xCount ? "end" : "middle" });
      label.textContent = long ? new Date(t).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : shortDate(t);
      grid.append(label);
    }
    root.append(grid);

    // Area under the primary series
    const pts = primary.points;
    const base = y(yMin);
    const area = `M${x(pts[0].t)},${base} ` + pts.map((p) => `L${x(p.t)},${y(p.v)}`).join(" ") + ` L${x(pts.at(-1).t)},${base} Z`;
    root.append(svg("path", { class: "area", d: area, style: `fill:${primary.color}` }));

    // Lines (secondary first so the price line sits on top)
    [...series].reverse().forEach((s) => {
      const inRange = s.points.filter((p) => p.t >= tMin && p.t <= tMax);
      if (!inRange.length) return;
      const d = inRange.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
      root.append(svg("path", { class: "series", d, style: `stroke:${s.color}` }));
    });

    // Direct end labels (desktop only), nudged apart so they never overlap.
    if (pad.right > 20) {
      const ends = series
        .map((s) => ({ s, p: s.points.filter((p) => p.t <= tMax).at(-1) }))
        .filter((e) => e.p)
        .map((e) => ({ ...e, y: y(e.p.v) }))
        .sort((a, b) => a.y - b.y);
      for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14;
      for (const e of ends) {
        const t = svg("text", { class: "end-label", x: width - pad.right + 8, y: e.y + 4 });
        t.textContent = e.s.short || e.s.label;
        root.append(t);
      }
    }

    // Hover layer
    crosshair = svg("line", { class: "crosshair", y1: pad.top, y2: height - pad.bottom, visibility: "hidden" });
    root.append(crosshair);
    dots = series.map((s) => {
      const c = svg("circle", { class: "hover-dot", r: 4.5, style: `fill:${s.color}`, visibility: "hidden" });
      root.append(c);
      return c;
    });
    if (activeIndex >= 0) show(activeIndex);
  }

  function nearestIndex(px) {
    const pts = primary.points;
    let lo = 0;
    let hi = pts.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (x(pts[mid].t) < px) lo = mid;
      else hi = mid;
    }
    return Math.abs(x(pts[lo].t) - px) <= Math.abs(x(pts[hi].t) - px) ? lo : hi;
  }

  function show(i) {
    activeIndex = i;
    const p = primary.points[i];
    const cx = x(p.t);
    crosshair.setAttribute("x1", cx);
    crosshair.setAttribute("x2", cx);
    crosshair.setAttribute("visibility", "visible");

    const rows = [];
    series.forEach((s, si) => {
      const v = byTime[si].get(p.t.getTime());
      const dot = dots[si];
      if (v === undefined) {
        dot.setAttribute("visibility", "hidden");
        return;
      }
      dot.setAttribute("cx", cx);
      dot.setAttribute("cy", y(v));
      dot.setAttribute("visibility", "visible");
      rows.push({ s, v });
    });

    const date = document.createElement("div");
    date.className = "tt-date";
    date.textContent = p.t.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
    tooltip.replaceChildren(
      date,
      ...rows.map(({ s, v }) => {
        const row = document.createElement("div");
        row.className = "tt-row";
        const sw = document.createElement("span");
        sw.className = "legend__swatch";
        sw.style.background = s.color;
        const name = document.createElement("span");
        name.textContent = s.label;
        const val = document.createElement("b");
        val.textContent = money(v);
        row.append(sw, name, val);
        return row;
      }),
    );
    tooltip.hidden = false;
    const tw = tooltip.offsetWidth;
    const left = cx + 14 + tw > width ? cx - 14 - tw : cx + 14;
    tooltip.style.transform = `translate(${Math.max(0, left)}px, ${pad.top}px)`;
  }

  function hide() {
    activeIndex = -1;
    crosshair?.setAttribute("visibility", "hidden");
    dots?.forEach((d) => d.setAttribute("visibility", "hidden"));
    tooltip.hidden = true;
  }

  root.addEventListener("pointermove", (e) => {
    const rect = root.getBoundingClientRect();
    show(nearestIndex(e.clientX - rect.left));
  });
  root.addEventListener("pointerleave", hide);
  root.addEventListener("blur", hide);
  root.addEventListener("keydown", (e) => {
    const last = primary.points.length - 1;
    const step = e.shiftKey ? 10 : 1;
    let i = activeIndex < 0 ? last : activeIndex;
    if (e.key === "ArrowLeft") i = Math.max(0, i - step);
    else if (e.key === "ArrowRight") i = Math.min(last, i + step);
    else if (e.key === "Home") i = 0;
    else if (e.key === "End") i = last;
    else if (e.key === "Escape") return hide();
    else return;
    e.preventDefault();
    show(i);
  });

  const ro = new ResizeObserver(() => draw());
  ro.observe(plot);
  draw();
  return { destroy: () => ro.disconnect() };
}
