"""Pure analytics on market data. No I/O, so everything here is easy to test.

The text summaries describe what the data shows. They are not investment advice.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Iterable


def num(v: Any) -> float | None:
    if v is None or v == "" or v == "-":
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def _parse_date(s: str) -> date | None:
    for fmt in ("%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d", "%d %b %Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


# =====================================================================
# Option chain
# =====================================================================

def _leg(d: dict[str, Any] | None) -> dict[str, float] | None:
    if not d:
        return None
    return {
        "oi": num(d.get("openInterest")) or 0.0,
        "oi_change": num(d.get("changeinOpenInterest")) or 0.0,
        "volume": num(d.get("totalTradedVolume")) or 0.0,
        "iv": num(d.get("impliedVolatility")) or 0.0,
        "ltp": num(d.get("lastPrice")) or 0.0,
        "change": num(d.get("change")) or 0.0,
    }


def normalize_option_chain(payload: Any) -> tuple[dict[str, dict[float, dict[str, Any]]], float | None, str]:
    """Accept NSE's current flat-leg shape, the nested CE/PE shape, or the legacy `records` shape.

    Returns ({expiry: {strike: {"CE": leg, "PE": leg}}}, spot, timestamp).
    """
    if not isinstance(payload, dict):
        raise ValueError("Option chain data is not in a recognised format.")
    container = payload.get("records") if isinstance(payload.get("records"), dict) else payload
    rows = container.get("data") or []
    spot = num(container.get("underlyingValue")) or num(payload.get("underlyingValue"))
    stamp = str(container.get("timestamp") or payload.get("timestamp") or "")
    chains: dict[str, dict[float, dict[str, Any]]] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue
        strike = num(row.get("strikePrice"))
        expiry = row.get("expiryDate") or row.get("expiryDates")
        if strike is None or not expiry:
            continue
        slot = chains.setdefault(str(expiry), {}).setdefault(strike, {"CE": None, "PE": None})
        if "optionType" in row and "CE" not in row and "PE" not in row:
            side = row.get("optionType")
            if side in ("CE", "PE"):
                slot[side] = _leg(row)
                spot = spot or num(row.get("underlyingValue"))
        else:
            for side in ("CE", "PE"):
                if isinstance(row.get(side), dict):
                    slot[side] = _leg(row[side])
                    spot = spot or num(row[side].get("underlyingValue"))
    if not chains:
        raise ValueError("No option contracts found for this symbol.")
    return chains, spot, stamp


def sorted_expiries(expiries: Iterable[str], today: date | None = None) -> list[str]:
    today = today or date.today()
    dated = [(e, _parse_date(e)) for e in expiries]
    upcoming = sorted([x for x in dated if x[1] and x[1] >= today], key=lambda x: x[1])
    past = sorted([x for x in dated if x[1] and x[1] < today], key=lambda x: x[1], reverse=True)
    unknown = [x for x in dated if not x[1]]
    return [e for e, _ in upcoming + past + unknown]


def max_pain(chain: dict[float, dict[str, Any]]) -> float | None:
    strikes = sorted(chain)
    if not strikes:
        return None
    best, best_loss = None, math.inf
    for k in strikes:
        loss = 0.0
        for s in strikes:
            ce, pe = chain[s]["CE"], chain[s]["PE"]
            if ce:
                loss += ce["oi"] * max(0.0, k - s)
            if pe:
                loss += pe["oi"] * max(0.0, s - k)
        if loss < best_loss:
            best, best_loss = k, loss
    return best


def buildup(price_change: float, oi_change: float) -> str:
    if oi_change > 0:
        return "Long build-up" if price_change > 0 else "Short build-up" if price_change < 0 else "Fresh positions"
    if oi_change < 0:
        return "Short covering" if price_change > 0 else "Long unwinding" if price_change < 0 else "Positions closed"
    return "No change"


def pcr_view(pcr: float | None) -> tuple[str, str]:
    if pcr is None:
        return "unknown", "Not enough open interest to compute PCR."
    if pcr >= 1.3:
        return "positive", "Put writers clearly outnumber call writers: traders expect support below. Very high PCR can also mean the market is stretched."
    if pcr >= 0.9:
        return "neutral", "Put and call open interest are fairly balanced: no strong directional bet."
    if pcr >= 0.7:
        return "neutral", "Slightly more call writing than put writing: mild caution from option sellers."
    return "negative", "Call writers dominate: traders expect resistance overhead."


def option_chain_analysis(payload: Any, symbol: str, expiry: str | None = None, strikes_each_side: int = 12,
                          today: date | None = None) -> dict[str, Any]:
    chains, spot, stamp = normalize_option_chain(payload)
    expiries = sorted_expiries(chains.keys(), today)
    if expiry and expiry not in chains:
        # Accept other date spellings of the same day.
        want = _parse_date(expiry)
        expiry = next((e for e in chains if _parse_date(e) == want), None)
    expiry = expiry or expiries[0]
    chain = chains[expiry]
    strikes = sorted(chain)

    ce_oi = sum(v["CE"]["oi"] for v in chain.values() if v["CE"])
    pe_oi = sum(v["PE"]["oi"] for v in chain.values() if v["PE"])
    ce_vol = sum(v["CE"]["volume"] for v in chain.values() if v["CE"])
    pe_vol = sum(v["PE"]["volume"] for v in chain.values() if v["PE"])
    pcr = round(pe_oi / ce_oi, 2) if ce_oi else None
    pcr_volume = round(pe_vol / ce_vol, 2) if ce_vol else None

    if spot is None:  # fall back to the strike where CE and PE premiums cross
        priced = [s for s in strikes if chain[s]["CE"] and chain[s]["PE"]]
        spot = min(priced, key=lambda s: abs(chain[s]["CE"]["ltp"] - chain[s]["PE"]["ltp"])) if priced else strikes[len(strikes) // 2]
    atm = min(strikes, key=lambda s: abs(s - spot))
    ai = strikes.index(atm)
    window = strikes[max(0, ai - strikes_each_side): ai + strikes_each_side + 1]

    def top(side: str, pred) -> list[dict[str, float]]:
        items = [(s, chain[s][side]) for s in strikes if chain[s][side] and pred(s)]
        items.sort(key=lambda x: x[1]["oi"], reverse=True)
        return [{"strike": s, "oi": leg["oi"], "oi_change": leg["oi_change"]} for s, leg in items[:3]]

    resistance = top("CE", lambda s: s >= spot) or top("CE", lambda s: True)
    support = top("PE", lambda s: s <= spot) or top("PE", lambda s: True)

    atm_ce, atm_pe = chain[atm]["CE"], chain[atm]["PE"]
    straddle = (atm_ce["ltp"] if atm_ce else 0) + (atm_pe["ltp"] if atm_pe else 0)
    expected_move_pct = round(straddle / spot * 100, 2) if spot and straddle else None

    rows = []
    for s in window:
        row: dict[str, Any] = {"strike": s, "is_atm": s == atm}
        for side in ("CE", "PE"):
            leg = chain[s][side]
            row[side] = None if not leg else {**leg, "buildup": buildup(leg["change"], leg["oi_change"])}
        rows.append(row)

    def strongest(side: str) -> dict[str, float] | None:
        legs = [(s, chain[s][side]) for s in strikes if chain[s][side]]
        if not legs:
            return None
        s, leg = max(legs, key=lambda x: x[1]["oi_change"])
        return {"strike": s, "oi_change": leg["oi_change"]} if leg["oi_change"] > 0 else None

    mp = max_pain(chain)
    tone, pcr_text = pcr_view(pcr)
    summary = [pcr_text]
    if resistance:
        summary.append(f"Biggest call open interest is at {resistance[0]['strike']:,.0f}, which acts as resistance.")
    if support:
        summary.append(f"Biggest put open interest is at {support[0]['strike']:,.0f}, which acts as support.")
    if mp is not None and spot:
        gap = (mp - spot) / spot * 100
        where = "right at the spot price" if abs(gap) < 0.05 else f"{gap:+.1f}% from spot"
        summary.append(f"Max pain is {mp:,.0f} ({where}), where option buyers lose the most at expiry.")
    if expected_move_pct:
        summary.append(f"The at-the-money straddle prices in a move of about ±{expected_move_pct}% by expiry.")

    return {
        "symbol": symbol.upper(),
        "expiry": expiry,
        "expiries": expiries,
        "timestamp": stamp,
        "spot": spot,
        "atm_strike": atm,
        "pcr": pcr,
        "pcr_volume": pcr_volume,
        "pcr_tone": tone,
        "total_call_oi": ce_oi,
        "total_put_oi": pe_oi,
        "max_pain": mp,
        "resistance": resistance,
        "support": support,
        "atm_straddle": round(straddle, 2) if straddle else None,
        "expected_move_pct": expected_move_pct,
        "fresh_call_writing": strongest("CE"),
        "fresh_put_writing": strongest("PE"),
        "summary": summary,
        "rows": rows,
    }


# =====================================================================
# FII / DII
# =====================================================================

def fii_dii_summary(rows: Any) -> dict[str, Any]:
    """NSE returns [{category: 'FII/FPI *', date, buyValue, sellValue, netValue}, {category: 'DII *', ...}] in ₹ crore."""
    if isinstance(rows, dict):
        rows = rows.get("data") or [rows]
    out: dict[str, Any] = {"date": None, "fii": None, "dii": None}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        cat = str(r.get("category", "")).upper()
        entry = {"buy": num(r.get("buyValue")), "sell": num(r.get("sellValue")), "net": num(r.get("netValue"))}
        if entry["net"] is None and entry["buy"] is not None and entry["sell"] is not None:
            entry["net"] = round(entry["buy"] - entry["sell"], 2)
        key = "fii" if ("FII" in cat or "FPI" in cat) else "dii" if "DII" in cat else None
        if key:
            out[key] = entry
            out["date"] = out["date"] or r.get("date")
    if not out["fii"] and not out["dii"]:
        raise ValueError("FII/DII data is not in a recognised format.")

    def word(net: float | None) -> str:
        if net is None:
            return "no data"
        return f"net bought ₹{abs(net):,.0f} cr" if net > 0 else f"net sold ₹{abs(net):,.0f} cr" if net < 0 else "were flat"

    fii_net = (out["fii"] or {}).get("net")
    dii_net = (out["dii"] or {}).get("net")
    out["combined_net"] = round((fii_net or 0) + (dii_net or 0), 2)
    text = [f"FIIs {word(fii_net)} and DIIs {word(dii_net)} in the cash market."]
    if fii_net is not None and dii_net is not None:
        if fii_net < 0 < dii_net:
            text.append("Domestic institutions absorbed foreign selling." if dii_net >= -fii_net else
                        "Domestic buying only partly offset foreign selling.")
        elif fii_net > 0 > dii_net:
            text.append("Foreign buying met domestic profit-taking.")
        elif fii_net > 0 and dii_net > 0:
            text.append("Both foreign and domestic institutions were buyers: broad institutional support.")
        elif fii_net < 0 and dii_net < 0:
            text.append("Both groups were sellers: institutional pressure on the market.")
    out["summary"] = text
    return out


def day_from_history(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Rebuild NSE-style rows from a saved history entry, for fii_dii_summary()."""
    return [{"category": "FII/FPI", "date": entry["date"], "buyValue": entry.get("fii_buy"), "sellValue": entry.get("fii_sell"),
             "netValue": entry.get("fii_net")},
            {"category": "DII", "date": entry["date"], "buyValue": entry.get("dii_buy"), "sellValue": entry.get("dii_sell"),
             "netValue": entry.get("dii_net")}]


def merge_history(history: list[dict[str, Any]], day: dict[str, Any], keep: int = 120) -> list[dict[str, Any]]:
    """Add one day's FII/DII figures to a history list (deduped by date, oldest first)."""
    if not day.get("date"):
        return history
    fii, dii = day.get("fii") or {}, day.get("dii") or {}
    entry = {"date": day["date"], "fii_net": fii.get("net"), "dii_net": dii.get("net"),
             "fii_buy": fii.get("buy"), "fii_sell": fii.get("sell"), "dii_buy": dii.get("buy"), "dii_sell": dii.get("sell")}
    by_date = {h["date"]: h for h in history}
    by_date[entry["date"]] = entry
    ordered = sorted(by_date.values(), key=lambda h: _parse_date(h["date"]) or date.min)
    return ordered[-keep:]


# =====================================================================
# Volume profile (a daily-data stand-in for footprint charts)
# =====================================================================

def volume_profile(candles: list[dict[str, Any]], bins: int = 24, value_area: float = 0.7) -> dict[str, Any]:
    """Spread each day's volume across its high-low range to find where trading concentrated.

    Up-days (close >= open) count as buying volume and down-days as selling volume, a rough
    proxy for the bid/ask split that true footprint charts get from tick data.
    """
    rows = []
    for c in candles:
        hi, lo, vol = num(c.get("high")), num(c.get("low")), num(c.get("volume"))
        op, cl = num(c.get("open")), num(c.get("close"))
        if None in (hi, lo, vol, cl) or hi < lo or vol <= 0:
            continue
        rows.append((lo, hi, vol, (cl >= (op if op is not None else cl))))
    if len(rows) < 2:
        raise ValueError("Not enough price history to build a volume profile.")

    low = min(r[0] for r in rows)
    high = max(r[1] for r in rows)
    if high == low:
        high = low + 1
    width = (high - low) / bins
    buckets = [{"low": low + i * width, "high": low + (i + 1) * width, "up": 0.0, "down": 0.0} for i in range(bins)]

    for lo, hi, vol, up in rows:
        span = max(hi - lo, width / 10)
        for b in buckets:
            overlap = min(hi, b["high"]) - max(lo, b["low"])
            if hi == lo and b["low"] <= lo <= b["high"]:
                overlap = span
            if overlap > 0:
                share = vol * overlap / span
                b["up" if up else "down"] += share

    for b in buckets:
        b["volume"] = b["up"] + b["down"]
    total = sum(b["volume"] for b in buckets) or 1
    poc_i = max(range(bins), key=lambda i: buckets[i]["volume"])

    lo_i = hi_i = poc_i
    acc = buckets[poc_i]["volume"]
    while acc / total < value_area and (lo_i > 0 or hi_i < bins - 1):
        below = buckets[lo_i - 1]["volume"] if lo_i > 0 else -1
        above = buckets[hi_i + 1]["volume"] if hi_i < bins - 1 else -1
        if above >= below:
            hi_i += 1
            acc += above
        else:
            lo_i -= 1
            acc += below

    def mid(b): return round((b["low"] + b["high"]) / 2, 2)

    poc = mid(buckets[poc_i])
    vah, val = round(buckets[hi_i]["high"], 2), round(buckets[lo_i]["low"], 2)
    last = num(candles[-1].get("close"))
    if last is None:
        where = ""
    elif last > vah:
        where = "Price is above the value area: buyers have pushed it out of the range where most trading happened."
    elif last < val:
        where = "Price is below the value area: sellers have pushed it out of the range where most trading happened."
    else:
        where = "Price is inside the value area, the range where about 70% of volume traded."

    return {
        "bins": [{"low": round(b["low"], 2), "high": round(b["high"], 2), "mid": mid(b),
                  "volume": round(b["volume"]), "buy_volume": round(b["up"]), "sell_volume": round(b["down"]),
                  "in_value_area": lo_i <= i <= hi_i} for i, b in enumerate(buckets)],
        "poc": poc,
        "value_area_high": vah,
        "value_area_low": val,
        "last_close": last,
        "days": len(rows),
        "summary": [f"Most volume traded around ₹{poc:,.2f} (point of control).",
                    f"Value area: ₹{val:,.2f} – ₹{vah:,.2f}.", where],
    }


# =====================================================================
# Analyst view
# =====================================================================

RATING_LABELS = {1: "Buy", 2: "Outperform", 3: "Hold", 4: "Underperform", 5: "Sell"}


def rating_label(mean: float | None) -> str:
    if mean is None:
        return "No rating"
    return RATING_LABELS[min(5, max(1, int(mean + 0.5)))]


def _snapshots(value: Any, inner: str) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get(inner) or []
    return [v for v in (value or []) if isinstance(v, dict)]


def analyst_view(raw: Any, price: float | None) -> dict[str, Any]:
    if not isinstance(raw, dict) or not (raw.get("priceTarget") or raw.get("recommendation")):
        raise ValueError("No analyst coverage found for this stock.")
    pt = raw.get("priceTarget") or {}
    rec = raw.get("recommendation") or {}
    mean_target = num(pt.get("Mean"))
    stats = _snapshots(rec.get("Statistics"), "Statistic")
    dist = {RATING_LABELS.get(int(num(s.get("Recommendation")) or 0), "Other"): int(num(s.get("NumberOfAnalysts")) or 0) for s in stats}
    mean_rating = num(rec.get("Mean"))

    targets = {s.get("Age"): num(s.get("Mean")) for s in _snapshots(raw.get("priceTargetSnapshots"), "PriceTargetSnapshot")}
    ratings = {s.get("Age"): num(s.get("Mean")) for s in _snapshots(raw.get("recommendationSnapshots"), "RecommendationSnapshot")}
    ages = ["NinetyDaysAgo", "SixtyDaysAgo", "ThirtyDaysAgo", "OneWeekAgo"]
    trend = [{"age": a, "target_mean": targets.get(a), "rating_mean": ratings.get(a)} for a in ages if a in targets or a in ratings]
    trend.append({"age": "Now", "target_mean": mean_target, "rating_mean": mean_rating})

    upside = round((mean_target / price - 1) * 100, 1) if mean_target and price else None
    older = next((t for t in trend if t["rating_mean"] is not None), None)
    shift = None
    if older and older["age"] != "Now" and mean_rating is not None and older["rating_mean"] is not None:
        d = older["rating_mean"] - mean_rating  # lower = more bullish
        shift = "improving" if d > 0.1 else "worsening" if d < -0.1 else "stable"

    summary = [f"Consensus: {rating_label(mean_rating)} ({mean_rating:.2f} on a 1 = Buy to 5 = Sell scale) from "
               f"{int(num(rec.get('NumberOfRecommendations')) or sum(dist.values()))} analysts."] if mean_rating else []
    if upside is not None:
        summary.append(f"Average target ₹{mean_target:,.0f} implies {upside:+.1f}% from the current price.")
    if shift:
        summary.append(f"Analyst sentiment over the last 90 days is {shift}.")

    return {
        "rating_mean": mean_rating,
        "rating_label": rating_label(mean_rating),
        "analysts": int(num(rec.get("NumberOfRecommendations")) or sum(dist.values())),
        "distribution": {k: dist.get(k, 0) for k in RATING_LABELS.values()},
        "target": {"mean": mean_target, "median": num(pt.get("Median")), "high": num(pt.get("High")),
                   "low": num(pt.get("Low")), "estimates": int(num(pt.get("NumberOfEstimates")) or 0)},
        "upside_pct": upside,
        "sentiment_trend": shift,
        "trend": trend,
        "summary": summary,
    }


# =====================================================================
# Scorecard
# =====================================================================

def _series(hist: Any, metric: str) -> list[tuple[str, float]]:
    for ds in (hist or {}).get("datasets", []) if isinstance(hist, dict) else []:
        if ds.get("metric") == metric:
            out = []
            for v in ds.get("values", []):
                if isinstance(v, (list, tuple)) and len(v) >= 2 and num(v[1]) is not None:
                    out.append((str(v[0]), num(v[1])))
            return out
    return []


def scorecard(*, price: float | None, history: Any = None, analyst: dict[str, Any] | None = None,
              week52: dict[str, Any] | None = None, volume: dict[str, Any] | None = None) -> dict[str, Any]:
    signals: list[dict[str, Any]] = []

    def add(key, label, tone, value, detail):
        signals.append({"key": key, "label": label, "tone": tone, "value": value, "detail": detail})

    prices = _series(history, "Price")
    dma50 = _series(history, "DMA50")
    dma200 = _series(history, "DMA200")
    last = price if price is not None else (prices[-1][1] if prices else None)

    if last and dma50 and dma200:
        d50, d200 = dma50[-1][1], dma200[-1][1]
        above = (last > d50) + (last > d200)
        tone = "positive" if above == 2 and d50 > d200 else "negative" if above == 0 else "neutral"
        cross = "50-day above 200-day (uptrend)" if d50 > d200 else "50-day below 200-day (downtrend)"
        add("trend", "Trend", tone, f"{above}/2 averages",
            f"Price is {'above' if last > d50 else 'below'} its 50-day (₹{d50:,.0f}) and "
            f"{'above' if last > d200 else 'below'} its 200-day (₹{d200:,.0f}) average; {cross}.")
    else:
        add("trend", "Trend", "unknown", "—", "Moving-average data unavailable.")

    if len(prices) > 60 and last:
        r3 = (last / prices[-63][1] - 1) * 100 if len(prices) >= 63 else None
        r12 = (last / prices[0][1] - 1) * 100
        tone = "positive" if r12 > 10 else "negative" if r12 < -10 else "neutral"
        add("momentum", "Momentum", tone, f"{r12:+.1f}% 1Y",
            f"1-year return {r12:+.1f}%" + (f", 3-month {r3:+.1f}%." if r3 is not None else "."))
    else:
        add("momentum", "Momentum", "unknown", "—", "Not enough price history.")

    pos = None
    if week52:
        pos = num(week52.get("position_in_range_pct"))
        hi, lo = num(week52.get("52w_high") or week52.get("high")), num(week52.get("52w_low") or week52.get("low"))
        if pos is None and hi and lo and last and hi > lo:
            pos = (last - lo) / (hi - lo) * 100
    if pos is not None:
        tone = "positive" if pos >= 70 else "negative" if pos <= 25 else "neutral"
        add("range", "52-week position", tone, f"{pos:.0f}%",
            f"Price sits {pos:.0f}% of the way from its 52-week low to its high.")
    else:
        add("range", "52-week position", "unknown", "—", "52-week data unavailable.")

    if volume and num(volume.get("last_vs_avg_pct")) is not None:
        v = num(volume["last_vs_avg_pct"])
        spikes = volume.get("volume_spike_days") or []
        tone = "positive" if v > 50 else "neutral"
        add("volume", "Volume", tone, f"{v:+.0f}% vs avg",
            f"Latest volume is {v:+.0f}% versus its average; {len(spikes) if isinstance(spikes, list) else spikes} spike day(s) recently.")
    else:
        add("volume", "Volume", "unknown", "—", "Volume analysis unavailable.")

    if analyst and analyst.get("rating_mean") is not None:
        m = analyst["rating_mean"]
        up = analyst.get("upside_pct")
        tone = "positive" if m <= 2.2 and (up is None or up > 5) else "negative" if m >= 3.3 or (up is not None and up < -5) else "neutral"
        add("analysts", "Analysts", tone, analyst["rating_label"],
            f"Consensus {analyst['rating_label']} from {analyst.get('analysts', 0)} analysts" +
            (f"; average target implies {up:+.1f}%." if up is not None else "."))
    else:
        add("analysts", "Analysts", "unknown", "—", "No analyst coverage available.")

    known = [s for s in signals if s["tone"] != "unknown"]
    pos_n = sum(s["tone"] == "positive" for s in known)
    neg_n = sum(s["tone"] == "negative" for s in known)
    if not known:
        overall = "Not enough data"
    elif pos_n > neg_n and pos_n >= len(known) / 2:
        overall = "Mostly positive"
    elif neg_n > pos_n and neg_n >= len(known) / 2:
        overall = "Mostly negative"
    else:
        overall = "Mixed"
    return {
        "overall": overall,
        "positive": pos_n,
        "negative": neg_n,
        "available": len(known),
        "signals": signals,
        "note": "Signals summarise data; they are not a recommendation to buy or sell.",
    }
