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

    def side(exchange: str) -> dict[str, Any]:
        suffix = ".NS" if exchange == "NSE" else ".BO"
        return {
            "high52Week": [{"ticker": r[0] + suffix, "company": r[1], "price": r[4], "52_week_high": r[8]} for r in near_high],
            "low52Week": [{"ticker": r[0] + suffix, "company": r[1], "price": r[4], "52_week_low": r[7]} for r in near_low],
        }

    return {"BSE_52WeekHighLow": side("BSE"), "NSE_52WeekHighLow": side("NSE")}


def price_shockers() -> list[dict[str, Any]]:
    rows = sorted(_STOCKS, key=lambda r: abs(r[5]), reverse=True)[:5]
    return [{k: v for k, v in _quote(r).items() if not k.startswith("52")} for r in rows]


def commodities() -> list[dict[str, Any]]:
    items = [
        ("GOLD", "10 GRMS", 76_412.0, 0.58, 1, "05 Dec 2026"),
        ("SILVER", "KGS", 91_850.0, -1.12, 30, "05 Dec 2026"),
        ("CRUDEOIL", "BBL", 5_812.0, 1.94, 100, "18 Nov 2026"),
        ("NATURALGAS", "MMBTU", 248.6, -2.31, 1250, "25 Nov 2026"),
        ("COPPER", "KGS", 862.35, 0.37, 2500, "28 Nov 2026"),
        ("ALUMINIUM", "KGS", 236.75, -0.73, 5000, "28 Nov 2026"),
        ("ZINC", "KGS", 281.10, 0.12, 5000, "28 Nov 2026"),
    ]
    out = []
    for i, (sym, unit, ltp, pct, size, expiry) in enumerate(items):
        change = round(ltp * pct / (100 + pct), 2)
        out.append({
            "contractId": f"DEMO{i:03d}",
            "commoditySymbol": sym,
            "expiryDate": expiry,
            "lastTradedPrice": ltp,
            "openingPrice": round(ltp - change * 0.5, 2),
            "highPrice": round(ltp * 1.009, 2),
            "lowPrice": round(ltp * 0.991, 2),
            "closingPrice": round(ltp - change, 2),
            "totalVolume": 1000 + i * 1371,
            "openInterest": 800 + i * 911,
            "priceUnit": unit,
            "contractSize": size,
            "priceChange": change,
            "percentageChange": pct,
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
    raise DemoNotFound(f"Demo mode has no data for /{endpoint}")
