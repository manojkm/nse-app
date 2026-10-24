"""Deterministic sample data for demo mode.

Shapes follow the IndianAPI documentation (https://indianapi.in/documentation/indian-stock-market).
Prices are illustrative only, not market quotes.
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta
from typing import Any

from .api_errors import DemoNotFound

# symbol, company, industry, sector, price, pct change, volume, 52w low, 52w high
_STOCKS: list[tuple[str, str, str, str, float, float, int, float, float]] = [
    ("RELIANCE", "Reliance Industries", "Oil & Gas Operations", "Energy", 1428.40, 1.24, 9_812_400, 1114.85, 1608.80),
    ("TCS", "Tata Consultancy Services", "Software & Programming", "Technology", 3412.15, -0.86, 2_104_300, 2991.60, 4592.25),
    ("HDFCBANK", "HDFC Bank", "Regional Banks", "Financial", 1987.60, 0.42, 7_455_100, 1588.05, 2027.30),
    ("INFY", "Infosys", "Software & Programming", "Technology", 1531.90, -1.72, 6_320_900, 1307.00, 2006.45),
    ("ICICIBANK", "ICICI Bank", "Regional Banks", "Financial", 1402.25, 0.95, 8_120_000, 1186.00, 1500.00),
    ("TATAMOTORS", "Tata Motors", "Auto & Truck Manufacturers", "Consumer Cyclical", 684.30, 3.41, 15_982_000, 535.75, 1179.00),
    ("SBIN", "State Bank of India", "Regional Banks", "Financial", 812.70, 2.18, 12_406_500, 680.00, 912.00),
    ("BHARTIARTL", "Bharti Airtel", "Communications Services", "Telecom", 1915.05, -0.31, 3_908_200, 1422.60, 2045.80),
    ("ITC", "ITC", "Tobacco", "Consumer Non-Cyclical", 412.55, -2.64, 11_230_700, 390.15, 528.50),
    ("LT", "Larsen & Toubro", "Construction Services", "Capital Goods", 3624.80, 1.07, 1_802_600, 2965.30, 3963.50),
    ("BPCL", "Bharat Petroleum", "Oil & Gas Operations", "Energy", 318.45, -3.18, 18_726_562, 234.01, 376.00),
    ("ADANIENT", "Adani Enterprises", "Misc. Capital Goods", "Conglomerates", 2389.10, 4.62, 4_115_800, 2025.00, 3203.25),
]


def _quote(row: tuple, exchange: str = "NSE") -> dict[str, Any]:
    sym, company, _industry, _sector, price, pct, volume, low, high = row
    net = round(price * pct / (100 + pct), 2)
    suffix = ".NS" if exchange == "NSE" else ".BO"
    return {
        "ticker": sym + suffix,
        "company": company,
        "price": price,
        "percent_change": pct,
        "net_change": net,
        "high": round(price * 1.012, 2),
        "low": round(price * 0.986, 2),
        "open": round(price - net * 0.6, 2),
        "volume": volume if exchange == "NSE" else volume // 9,
        "52_week_high": high,
        "52_week_low": low,
    }


def _trending_row(row: tuple) -> dict[str, Any]:
    q = _quote(row)
    # Trending returns strings in the real API.
    return {
        "ticker_id": row[0],
        "company_name": row[1],
        "price": f"{q['price']:.2f}",
        "percent_change": f"{q['percent_change']:.2f}",
        "net_change": f"{q['net_change']:.2f}",
        "high": f"{q['high']:.2f}",
        "low": f"{q['low']:.2f}",
        "open": f"{q['open']:.2f}",
        "volume": str(q["volume"]),
        "year_high": f"{row[8]:.2f}",
        "year_low": f"{row[7]:.2f}",
        "exchange_type": "NSI",
        "overall_rating": "Bullish" if row[5] > 0 else "Bearish",
        "ric": row[0] + ".NS",
    }


def _by_change(reverse: bool) -> list[tuple]:
    return sorted(_STOCKS, key=lambda r: r[5], reverse=reverse)


def trending() -> dict[str, Any]:
    return {
        "trending_stocks": {
            "top_gainers": [_trending_row(r) for r in _by_change(True)[:3]],
            "top_losers": [_trending_row(r) for r in _by_change(False)[:3]],
        }
    }


def most_active(exchange: str) -> list[dict[str, Any]]:
    rows = sorted(_STOCKS, key=lambda r: r[6], reverse=True)
    return [
        {k: v for k, v in _quote(r, exchange).items() if k in ("ticker", "company", "price", "percent_change", "net_change", "volume")}
        for r in rows
    ]


def week52() -> dict[str, Any]:
    near_high = sorted(_STOCKS, key=lambda r: r[4] / r[8], reverse=True)[:4]
    near_low = sorted(_STOCKS, key=lambda r: r[4] / r[7])[:4]

    def row(r, key, value):
        return {"tickerId": f"S{_STOCKS.index(r):07d}", "displayName": r[1], "price": f"{r[4]:.2f}",
                "percentChange": f"{r[5]:.2f}", key: f"{value:.2f}", "volume": str(r[6])}

    side = {
        "high52Week": [row(r, "yearHigh", r[8]) for r in near_high],
        "low52Week": [row(r, "yearLow", r[7]) for r in near_low],
    }
    return {"BSE_52WeekHighLow": side, "NSE_52WeekHighLow": side}


def price_shockers() -> dict[str, Any]:
    rows = sorted(_STOCKS, key=lambda r: abs(r[5]), reverse=True)[:5]
    items = [
        {"tickerId": f"S{i:07d}", "displayName": r[1], "price": f"{r[4]:.2f}", "percentChange": f"{r[5]:.2f}",
         "averagePrice": f"{r[4] * 0.97:.2f}", "deviation": f"{abs(r[5]) * 3:.2f}", "volume": str(r[6]),
         "overallRating": "Bullish" if r[5] > 0 else "Bearish"}
        for i, r in enumerate(rows)
    ]
    return {"BSE_PriceShocker": items, "NSE_PriceShocker": items}


def commodities() -> list[dict[str, Any]]:
    items = [
        ("GOLD", 76_412.0, 0.58, "05 Dec 2026"),
        ("SILVER", 91_850.0, -1.12, "05 Dec 2026"),
        ("CRUDEOIL", 5_812.0, 1.94, "18 Nov 2026"),
        ("NATURALGAS", 248.6, -2.31, "25 Nov 2026"),
        ("COPPER", 862.35, 0.37, "28 Nov 2026"),
        ("ALUMINIUM", 236.75, -0.73, "28 Nov 2026"),
        ("ZINC", 281.10, 0.12, "28 Nov 2026"),
    ]
    out = []
    for i, (sym, ltp, pct, expiry) in enumerate(items):
        change = round(ltp * pct / (100 + pct), 2)
        out.append({
            "product": sym, "expiry": expiry, "product_month": "NOV2026",
            "last_traded_price": f"{ltp:.2f}", "open_price": f"{ltp - change * 0.5:.2f}",
            "high_price": f"{ltp * 1.009:.2f}", "low_price": f"{ltp * 0.991:.2f}", "close_price": f"{ltp - change:.2f}",
            "total_quantity_traded": str(1000 + i * 1371), "open_interest": str(800 + i * 911),
            "change": change, "per_change": pct,
        })
    return out


def mutual_funds() -> dict[str, Any]:
    def fund(name, nav, chg, size, r1y, r3y, r5y, stars):
        return {
            "fund_name": name, "latest_nav": nav, "percentage_change": chg, "asset_size": size,
            "1_month_return": round(r1y / 12, 2), "3_month_return": round(r1y / 4, 2),
            "6_month_return": round(r1y / 2, 2), "1_year_return": r1y,
            "3_year_return": r3y, "5_year_return": r5y, "star_rating": stars,
        }

    return {
        "Equity": {
            "Large Cap": [
                fund("SBI Bluechip Fund Direct Growth", 98.42, 0.45, 50_412, 14.2, 15.8, 17.1, 4),
                fund("ICICI Prudential Bluechip Fund Direct Growth", 112.65, 0.38, 63_221, 16.9, 18.3, 19.4, 5),
            ],
            "Mid Cap": [
                fund("HDFC Mid-Cap Opportunities Direct Growth", 198.14, 0.92, 79_870, 22.6, 25.1, 27.9, 5),
                fund("Kotak Emerging Equity Direct Growth", 141.37, 0.71, 49_150, 19.8, 21.4, 24.6, 4),
            ],
        },
        "Debt": {
            "Short Duration": [
                fund("Axis Short Duration Fund Direct Growth", 32.18, 0.02, 9_420, 8.1, 6.9, 7.0, 4),
            ],
        },
    }


def search_mutual_funds(query: str) -> list[dict[str, Any]]:
    names = [f["fund_name"] for cat in mutual_funds().values() for funds in cat.values() for f in funds]
    q = query.lower()
    return [
        {"id": f"MF{i:06d}", "schemeName": n, "isin": f"INFDEMO{i:05d}", "schemeType": "Open Ended Investment Company"}
        for i, n in enumerate(names)
        if q in n.lower()
    ]


def search_industry(query: str) -> list[dict[str, Any]]:
    q = query.lower()
    return [
        {
            "id": f"S{i:07d}", "commonName": r[1], "mgIndustry": r[2], "mgSector": r[3], "stockType": "Equity",
            "exchangeCodeNsi": r[0], "nseRic": r[0] + ".NS", "bseRic": r[0] + ".BO",
            "activeStockTrends": {"overallRating": "Bullish" if r[5] > 0 else "Bearish"},
        }
        for i, r in enumerate(_STOCKS)
        if q in r[2].lower() or q in r[3].lower()
    ]


def _find(name: str) -> tuple:
    q = name.strip().lower()
    for r in _STOCKS:
        if q in (r[0].lower(), r[1].lower()):
            return r
    for r in _STOCKS:
        if q and (q in r[0].lower() or q in r[1].lower()):
            return r
    raise DemoNotFound(f"No demo stock matches '{name}'. Try one of: {', '.join(r[0] for r in _STOCKS)}")


def stock(name: str) -> dict[str, Any]:
    r = _find(name)
    sym, company, industry, sector, price, pct, *_rest, low, high = r
    return {
        "tickerId": sym,
        "companyName": company + " Ltd",
        "industry": industry,
        "companyProfile": {
            "companyDescription": f"{company} is a listed company in the {sector.lower()} sector. (Demo profile.)",
            "exchangeCodeNse": sym,
        },
        "currentPrice": {"NSE": f"{price:.2f}", "BSE": f"{price + 0.35:.2f}"},
        "percentChange": f"{pct:.2f}",
        "yearHigh": f"{high:.2f}",
        "yearLow": f"{low:.2f}",
        "recentNews": [
            {"headline": f"{company} shares move {abs(pct):.1f}% in today's session", "date": date.today().isoformat()},
        ],
    }


def historical(name: str, period: str = "1yr") -> dict[str, Any]:
    r = _find(name)
    days = {"1m": 30, "6m": 182, "1yr": 365, "3yr": 3 * 365, "5yr": 5 * 365, "10yr": 3650, "max": 3650}.get(period, 365)
    step = 1 if days <= 365 else 7
    rng = random.Random(r[0] + period)
    end = date(2026, 10, 23)
    n = days // step
    # Random walk ending on the current price.
    walk = [0.0]
    for _ in range(n - 1):
        walk.append(walk[-1] + rng.gauss(0.0004 * step, 0.014 * math.sqrt(step)))
    final = walk[-1]
    prices = [round(r[4] * math.exp(w - final), 2) for w in walk]
    dates = [(end - timedelta(days=(n - 1 - i) * step)).isoformat() for i in range(n)]

    def sma(window: int) -> list[list]:
        w = max(1, window // step)
        out = []
        for i in range(w - 1, n):
            out.append([dates[i], f"{sum(prices[i - w + 1:i + 1]) / w:.2f}"])
        return out

    return {
        "datasets": [
            {"metric": "Price", "label": "Price on NSE", "values": [[d, f"{p:.2f}"] for d, p in zip(dates, prices)],
             "meta": {"is_weekly": step > 1}},
            {"metric": "DMA50", "label": "50 DMA", "values": sma(50), "meta": {}},
            {"metric": "DMA200", "label": "200 DMA", "values": sma(200), "meta": {}},
        ]
    }


def historical_stats(name: str, stats: str) -> dict[str, Any]:
    r = _find(name)
    quarters = ["Sep 2025", "Dec 2025", "Mar 2026", "Jun 2026", "Sep 2026"]
    base = r[4] * 40
    sales = {q: round(base * (1 + 0.03 * i)) for i, q in enumerate(quarters)}
    profit = {q: round(v * 0.18) for q, v in sales.items()}
    return {"Sales": sales, "Net Profit": profit, "_note": f"Demo {stats} for {r[0]}"}


def target_price(stock_id: str) -> dict[str, Any]:
    r = _find(stock_id)
    p = r[4]
    return {
        "priceTarget": {"CurrencyCode": "INR", "Mean": round(p * 1.12, 2), "High": round(p * 1.35, 2),
                        "Low": round(p * 0.86, 2), "Median": round(p * 1.1, 2), "NumberOfEstimates": 32},
        "priceTargetSnapshots": {"PriceTargetSnapshot": [
            {"Age": a, "Mean": round(p * f, 2)} for a, f in (("OneWeekAgo", 1.115), ("ThirtyDaysAgo", 1.09), ("SixtyDaysAgo", 1.07), ("NinetyDaysAgo", 1.05))]},
        "recommendationSnapshots": {"RecommendationSnapshot": [
            {"Age": a, "Mean": m} for a, m in (("OneWeekAgo", 2.32), ("ThirtyDaysAgo", 2.41), ("SixtyDaysAgo", 2.55), ("NinetyDaysAgo", 2.62))]},
        "recommendation": {"Mean": 2.3, "NumberOfRecommendations": 34, "Statistics": {"Statistic": [
            {"Recommendation": 1, "NumberOfAnalysts": 9}, {"Recommendation": 2, "NumberOfAnalysts": 13},
            {"Recommendation": 3, "NumberOfAnalysts": 8}, {"Recommendation": 4, "NumberOfAnalysts": 3},
            {"Recommendation": 5, "NumberOfAnalysts": 1}]}},
    }


def forecasts(stock_id: str, measure_code: str, **_: Any) -> dict[str, Any]:
    r = _find(stock_id)
    return {"stock": r[0], "measureCode": measure_code, "periods": [
        {"fiscalYear": 2026 + i, "mean": round(r[4] / 22 * (1.1 ** i), 2)} for i in range(3)]}


def respond(endpoint: str, params: dict[str, Any]) -> Any:
    """Route an IndianAPI endpoint + params to the matching sample payload."""
    match endpoint:
        case "trending":
            return trending()
        case "NSE_most_active":
            return most_active("NSE")
        case "BSE_most_active":
            return most_active("BSE")
        case "fetch_52_week_high_low_data":
            return week52()
        case "price_shockers":
            return price_shockers()
        case "commodities":
            return commodities()
        case "mutual_funds":
            return mutual_funds()
        case "mutual_fund_search":
            return search_mutual_funds(params.get("query", ""))
        case "industry_search":
            return search_industry(params.get("query", ""))
        case "stock":
            return stock(params.get("name", ""))
        case "historical_data":
            return historical(params.get("stock_name", ""), params.get("period", "1yr"))
        case "historical_stats":
            return historical_stats(params.get("stock_name", ""), params.get("stats", ""))
        case "stock_target_price":
            return target_price(params.get("stock_id", ""))
        case "stock_forecasts":
            return forecasts(**params)
        case "indices":
            return indices()
        case "ipo":
            return ipo()
        case "news":
            return news()
        case "usage":
            return usage()
    raise DemoNotFound(f"Demo mode has no data for /{endpoint}")


# ---------------------------------------------------------------- IndianAPI extras

def indices() -> dict[str, Any]:
    rows = [("NIFTY 50", 24_853.15, 0.42, "NSI"), ("SENSEX", 81_224.75, 0.38, "BSE"), ("NIFTY BANK", 55_310.40, 0.71, "NSI"),
            ("NIFTY IT", 35_102.85, -1.12, "NSI"), ("NIFTY MIDCAP 100", 57_420.30, 0.95, "NSI"), ("INDIA VIX", 12.84, -3.10, "NSI")]
    return {"indices": [{"name": n, "price": f"{p:.2f}", "percentChange": f"{c:.2f}", "netChange": f"{p * c / (100 + c):.2f}",
                         "tickerId": f"I{i:04d}", "exchangeType": x} for i, (n, p, c, x) in enumerate(rows)]}


def ipo() -> dict[str, Any]:
    return {
        "open": [{"symbol": "DEMOTECH", "name": "Demo Technologies", "status": "open", "is_sme": False, "min_price": 412, "max_price": 434,
                  "bidding_start_date": "2026-10-22", "bidding_end_date": "2026-10-27", "lot_size": 34, "issue_size": "₹1,250 Cr"}],
        "upcoming": [{"symbol": "SAMPLEFIN", "name": "Sample Finance", "status": "upcoming", "is_sme": False,
                      "additional_text": "Bidding dates yet to be announced"},
                     {"symbol": "MINIGREEN", "name": "Mini Green Energy", "status": "upcoming", "is_sme": True,
                      "bidding_start_date": "2026-10-30", "bidding_end_date": "2026-11-03", "min_price": 95, "max_price": 100}],
        "listed": [{"symbol": "EXAMPLECO", "name": "Example Consumer", "status": "listed", "is_sme": False, "issue_price": 310,
                    "listing_price": 362, "listing_gains": 16.8, "current_price": 377, "listing_date": "2026-10-14"}],
    }


def news() -> list[dict[str, Any]]:
    items = [
        ("IT stocks slip as US tech guidance softens", ["IT", "Earnings"]),
        ("Banks lead gains after strong quarterly loan growth", ["Banking"]),
        ("Crude prices rise on supply concerns; oil marketers under pressure", ["Energy", "Commodities"]),
        ("FPIs turn net sellers for third straight session", ["FII", "Flows"]),
        ("Auto sales hit festive-season record", ["Auto"]),
    ]
    return [{"title": t, "summary": "Sample headline for demo mode.", "url": "https://indianapi.in/", "pub_date": f"2026-10-24T0{i + 8}:15:00",
             "source": "Demo News", "topics": topics} for i, (t, topics) in enumerate(items)]


def usage() -> dict[str, Any]:
    return {"total_requests": 214, "hard_limit": 1000, "remaining_requests": 786, "endpoint_usage": {"/trending": 61, "/stock": 48}}


# ---------------------------------------------------------------- nseindia.com (FII/DII, options)

def fii_dii() -> list[dict[str, Any]]:
    return [
        {"category": "DII **", "date": "24-Oct-2026", "buyValue": "15234.56", "sellValue": "11987.21", "netValue": "3247.35"},
        {"category": "FII/FPI **", "date": "24-Oct-2026", "buyValue": "12876.40", "sellValue": "15112.95", "netValue": "-2236.55"},
    ]


def fii_dii_history() -> list[dict[str, Any]]:
    rng = random.Random("fii")
    out, d = [], date(2026, 10, 24)
    while len(out) < 20:
        if d.weekday() < 5:
            out.append({"date": d.strftime("%d-%b-%Y"), "fii_net": round(rng.gauss(-600, 1800), 2), "dii_net": round(rng.gauss(900, 1300), 2)})
        d -= timedelta(days=1)
    return list(reversed(out))


def option_expiries() -> list[str]:
    return ["28-Oct-2026", "04-Nov-2026", "25-Nov-2026"]


def option_chain(symbol: str) -> dict[str, Any]:
    sym = symbol.strip().upper()
    spots = {"NIFTY": (24_853.15, 50), "BANKNIFTY": (55_310.40, 100), "FINNIFTY": (26_120.6, 50), "MIDCPNIFTY": (12_940.2, 25)}
    if sym in spots:
        spot, step = spots[sym]
    else:
        r = _find(sym)
        spot = r[4]
        step = 10 ** max(0, len(str(int(spot))) - 2) * (5 if str(int(spot))[0] in "56789" else 2.5) / 10 * 4
        step = max(1.0, round(step))
    rng = random.Random(sym)
    atm = round(spot / step) * step
    data = []
    for ei, expiry in enumerate(option_expiries()):
        t = (4 + ei * 10) / 365
        for i in range(-30, 31):
            k = atm + i * step
            for side in ("CE", "PE"):
                moneyness = (k - spot) / spot
                otm = moneyness if side == "CE" else -moneyness
                iv = 13 + 40 * moneyness ** 2 * 100 + rng.uniform(-0.5, 0.5)
                tv = spot * iv / 100 * math.sqrt(t) * 0.4 * math.exp(-((otm / (iv / 100 * math.sqrt(t) + 1e-9)) ** 2) / 2)
                intrinsic = max(0.0, -otm * spot)
                ltp = round(max(0.05, intrinsic + tv), 2)
                # Writers pile into round strikes away from spot: calls above, puts below.
                base = math.exp(-abs(i) / 9) * 9e4
                writing = 2.4 if (side == "CE" and i > 0) or (side == "PE" and i < 0) else 0.7
                round_bonus = 1.8 if k % (step * 10) == 0 else 1.25 if k % (step * 2) == 0 else 1
                oi = int(base * writing * round_bonus * rng.uniform(0.7, 1.3) / (1 + ei))
                coi = int(oi * rng.uniform(-0.15, 0.35))
                data.append({
                    "strikePrice": k, "expiryDate": expiry, "optionType": side, "openInterest": oi, "changeinOpenInterest": coi,
                    "totalTradedVolume": int(oi * rng.uniform(2, 9)), "impliedVolatility": round(iv, 2), "lastPrice": ltp,
                    "change": round(ltp * rng.uniform(-0.25, 0.25), 2), "underlyingValue": spot, "underlying": sym,
                })
    return {"data": data, "timestamp": "24-Oct-2026 15:30:00"}


# ---------------------------------------------------------------- NSE official MCP (Bhavcopy)

def nse_history(symbol: str, months: int = 3) -> dict[str, Any]:
    r = _find(symbol)
    rng = random.Random(r[0] + "ohlc")
    days, d = [], date(2026, 10, 23)
    while len(days) < months * 21:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    days.reverse()
    walk = [0.0]
    for _ in days[1:]:
        walk.append(walk[-1] + rng.gauss(0, 0.015))
    closes = [r[4] * math.exp(w - walk[-1]) for w in walk]
    data, prev = [], closes[0]
    for day, close in zip(days, closes):
        op = prev * (1 + rng.gauss(0, 0.004))
        hi = max(op, close) * (1 + abs(rng.gauss(0, 0.007)))
        lo = min(op, close) * (1 - abs(rng.gauss(0, 0.007)))
        vol = int(r[6] * rng.uniform(0.5, 1.6) * (1.8 if abs(close / prev - 1) > 0.02 else 1))
        data.append({"date": day.isoformat(), "open": round(op, 2), "high": round(hi, 2), "low": round(lo, 2),
                     "close": round(close, 2), "prevClose": round(prev, 2), "volume": vol})
        prev = close
    return {"symbol": r[0], "from_date": data[0]["date"], "to_date": data[-1]["date"], "trading_days": len(data), "data": data}


def breadth() -> dict[str, Any]:
    return {"date": "2026-10-23", "total_stocks": 2_412, "advances": 1_486, "declines": 851, "unchanged": 75,
            "ad_ratio": 1.75, "total_volume": 4_812_334_120}


def volume_analysis(symbol: str) -> dict[str, Any]:
    h = nse_history(symbol, 3)["data"]
    vols = [x["volume"] for x in h]
    avg = sum(vols) / len(vols)
    spikes = [x["date"] for x in h if x["volume"] > 2 * avg]
    return {"symbol": h and _find(symbol)[0], "avg_volume": round(avg), "max_volume": max(vols), "min_volume": min(vols),
            "last_volume": vols[-1], "last_vs_avg_pct": round((vols[-1] / avg - 1) * 100, 1), "volume_spike_days": spikes,
            "recent_5_days": [{"date": x["date"], "volume": x["volume"]} for x in h[-5:]]}


def nse_week52(symbol: str) -> dict[str, Any]:
    r = _find(symbol)
    pos = (r[4] - r[7]) / (r[8] - r[7]) * 100
    return {"symbol": r[0], "last_close": r[4], "52w_high": r[8], "52w_high_date": "2026-06-11", "52w_low": r[7],
            "52w_low_date": "2026-01-27", "position_in_range_pct": round(pos, 1),
            "from_52w_high_pct": round((r[4] / r[8] - 1) * 100, 1), "from_52w_low_pct": round((r[4] / r[7] - 1) * 100, 1)}


def compare(symbols: list[str], months: int = 6) -> dict[str, Any]:
    stocks = []
    for sym in symbols:
        try:
            r = _find(sym)
        except DemoNotFound:
            continue
        rng = random.Random(r[0] + str(months))
        ret = rng.uniform(-18, 32)
        stocks.append({"symbol": r[0], "start_price": round(r[4] / (1 + ret / 100), 2), "end_price": r[4],
                       "return_pct": round(ret, 2), "max_drawdown": round(-rng.uniform(4, 22), 2), "trading_days": months * 21})
    stocks.sort(key=lambda s: s["return_pct"], reverse=True)
    return {"from_date": "2026-04-23", "to_date": "2026-10-23", "months": months, "stocks": stocks}


def corporate_actions(symbol: str) -> dict[str, Any]:
    r = _find(symbol)
    actions = [
        {"exDate": "2026-08-12", "actionType": "DIVIDEND", "purpose": "Final Dividend - Rs 10 Per Share", "adjustmentFactor": 1},
        {"exDate": "2025-08-14", "actionType": "DIVIDEND", "purpose": "Final Dividend - Rs 9 Per Share", "adjustmentFactor": 1},
        {"exDate": "2024-10-28", "actionType": "BONUS", "purpose": "Bonus 1:1", "adjustmentFactor": 0.5},
    ]
    return {"symbol": r[0], "count": len(actions), "actions": actions}


def lookup(query: str) -> dict[str, Any]:
    q = query.lower()
    res = [{"symbol": r[0], "last_close": r[4], "pct_change": r[5], "last_date": "2026-10-23"}
           for r in _STOCKS if q in r[0].lower() or q in r[1].lower()]
    return {"count": len(res), "results": res}
