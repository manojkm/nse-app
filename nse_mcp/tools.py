"""The market-data tools, defined once and shared by the MCP server and the REST API."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

from . import analytics
from .analytics import num
from .api_errors import APIError
from .sources import Sources

Period = Literal["1m", "6m", "1yr", "3yr", "5yr", "10yr", "max"]
HistoryFilter = Literal["default", "price", "pe", "sm", "evebitda", "ptb", "mcs"]
Stats = Literal[
    "quarter_results", "yoy_results", "balancesheet", "cashflow", "ratios",
    "shareholding_pattern_quarterly", "shareholding_pattern_yearly",
]
MeasureCode = Literal["EPS", "CPS", "CPX", "DPS", "EBI", "EBT", "GPS", "GRM", "NAV", "NDT", "NET", "PRE", "ROA", "ROE", "SAL"]
PeriodType = Literal["Annual", "Interim"]
DataType = Literal["Actuals", "Estimates"]
DataAge = Literal["OneWeekAgo", "ThirtyDaysAgo", "SixtyDaysAgo", "NinetyDaysAgo", "Current"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    title: str
    description: str
    group: str
    fn: Callable[..., Awaitable[Any]]  # first arg is the Sources bundle

    @property
    def signature(self) -> inspect.Signature:
        """The tool's user-facing parameters (without the data source)."""
        sig = inspect.signature(self.fn, eval_str=True)
        return sig.replace(parameters=list(sig.parameters.values())[1:])


TOOLS: dict[str, ToolSpec] = {}


def tool(name: str, title: str, group: str, description: str):
    def register(fn: Callable[..., Awaitable[Any]]):
        TOOLS[name] = ToolSpec(name, title, description, group, fn)
        return fn

    return register


# ---- Market ----

@tool("get_trending_stocks", "Trending stocks", "Market",
      "Top gaining and losing stocks on NSE/BSE right now, with price, % change, volume and 52-week range.")
async def get_trending_stocks(ctx: Sources) -> Any:
    return await ctx.indian.get("trending")


@tool("get_nse_most_active", "NSE most active", "Market", "Most actively traded NSE stocks, ranked by volume.")
async def get_nse_most_active(ctx: Sources) -> Any:
    return await ctx.indian.get("NSE_most_active")


@tool("get_bse_most_active", "BSE most active", "Market", "Most actively traded BSE stocks, ranked by volume.")
async def get_bse_most_active(ctx: Sources) -> Any:
    return await ctx.indian.get("BSE_most_active")


@tool("get_52_week_high_low", "52-week highs & lows", "Market",
      "Stocks at or near their 52-week high or low on BSE and NSE. May be empty while the market is closed.")
async def get_52_week_high_low(ctx: Sources) -> Any:
    return await ctx.indian.get("fetch_52_week_high_low_data")


@tool("get_price_shockers", "Price shockers", "Market", "Stocks with sharp price moves in a short period.")
async def get_price_shockers(ctx: Sources) -> Any:
    return await ctx.indian.get("price_shockers")


@tool("get_commodities", "Commodity futures", "Market",
      "Live commodity futures (gold, silver, crude oil, etc.): price, change, volume and open interest.")
async def get_commodities(ctx: Sources) -> Any:
    return await ctx.indian.get("commodities")


# ---- Company research ----

@tool("get_stock_data", "Company details", "Research",
      "Full details for one company by name or symbol (e.g. 'Reliance', 'TCS'): NSE/BSE price, % change, "
      "52-week range, profile, financials, analyst view, shareholding and recent news.")
async def get_stock_data(ctx: Sources, name: str) -> Any:
    return await ctx.indian.get("stock", {"name": name})


@tool("search_industry", "Search by industry", "Research",
      "Find listed companies in an industry or sector (e.g. 'software', 'banks').")
async def search_industry(ctx: Sources, query: str) -> Any:
    return await ctx.indian.get("industry_search", {"query": query})


@tool("get_historical_data", "Price history", "Research",
      "Historical price (with 50/200-day moving averages), volume or valuation ratios for a stock.")
async def get_historical_data(ctx: Sources, stock_name: str, period: Period = "1yr", filter: HistoryFilter = "price") -> Any:
    return await ctx.indian.get("historical_data", {"stock_name": stock_name, "period": period, "filter": filter})


@tool("get_historical_stats", "Financial statements", "Research",
      "Quarterly/annual results, balance sheet, cash flow, ratios or shareholding pattern for a stock.")
async def get_historical_stats(ctx: Sources, stock_name: str, stats: Stats) -> Any:
    return await ctx.indian.get("historical_stats", {"stock_name": stock_name, "stats": stats})


@tool("get_analyst_recommendations", "Analyst targets", "Research",
      "Analyst target prices and buy/hold/sell recommendation breakdown for a stock "
      "(1 = Buy, 2 = Outperform, 3 = Hold, 4 = Underperform, 5 = Sell).")
async def get_analyst_recommendations(ctx: Sources, stock_id: str) -> Any:
    return await ctx.indian.get("stock_target_price", {"stock_id": stock_id})


@tool("get_stock_forecasts", "Forecasts", "Research",
      "Analyst forecasts or actuals for one measure (EPS, revenue, ROE, ...) of a stock.")
async def get_stock_forecasts(
    ctx: Sources,
    stock_id: str,
    measure_code: MeasureCode = "EPS",
    period_type: PeriodType = "Annual",
    data_type: DataType = "Estimates",
    age: DataAge = "Current",
) -> Any:
    return await ctx.indian.get("stock_forecasts", {
        "stock_id": stock_id, "measure_code": measure_code, "period_type": period_type,
        "data_type": data_type, "age": age,
    })


# ---- Funds ----

@tool("get_mutual_funds", "Mutual funds", "Funds",
      "Latest mutual fund NAVs and 1M-5Y returns, grouped by category (Equity, Debt, Hybrid...).")
async def get_mutual_funds(ctx: Sources) -> Any:
    return await ctx.indian.get("mutual_funds")


@tool("search_mutual_funds", "Search mutual funds", "Funds", "Search mutual fund schemes by name.")
async def search_mutual_funds(ctx: Sources, query: str) -> Any:
    return await ctx.indian.get("mutual_fund_search", {"query": query})


# ---- Market pulse (IndianAPI + NSE official) ----

KEY_INDICES = ["Nifty 50", "Nifty Bank", "Nifty Next 50", "Nifty IT", "Nifty Midcap 100", "Nifty Smallcap 100",
               "Nifty Financial Services", "Nifty Auto", "Nifty Pharma", "Nifty FMCG", "Nifty Metal"]


@tool("get_indices", "Market indices", "Market",
      "Latest close and % change for key NSE indices (NIFTY 50, BANK, IT, Midcap, Smallcap, sectors) plus India VIX, "
      "with P/E. From NSE's official end-of-day data; falls back to IndianAPI.")
async def get_indices(ctx: Sources) -> Any:
    try:
        snap = await ctx.official.index_snapshot("today", "")
        rows = {str(r.get("indexName", "")).lower(): r for r in (snap or {}).get("indices", []) if isinstance(r, dict)}
        picked = [rows[n.lower()] for n in KEY_INDICES if n.lower() in rows]
        if not picked:
            raise APIError("No index data from NSE.")
        out = [{"name": r["indexName"], "price": r.get("close"), "percentChange": r.get("pctChange"),
                "netChange": r.get("pointsChange"), "pe": r.get("pe")} for r in picked]
        try:
            vix = (await ctx.official.market_mood("today")).get("india_vix") or {}
            if vix.get("level") is not None:
                out.insert(1, {"name": "India VIX", "price": vix["level"], "percentChange": vix.get("change_1d_pct")})
        except Exception:  # noqa: BLE001 - VIX is a nice-to-have
            pass
        return {"indices": out, "date": snap.get("date"), "source": "NSE official (end of day)"}
    except Exception as nse_err:  # noqa: BLE001
        try:
            data = await ctx.indian.get("indices")
            return data | {"source": "IndianAPI"} if isinstance(data, dict) else data
        except APIError:
            raise APIError(f"Index data unavailable: {nse_err}", status=502) from nse_err


@tool("get_market_mood", "Market mood", "Market",
      "Factual read of the day: India VIX level and trend, how many indices and stocks rose vs fell, and benchmark changes. "
      "Descriptive only, not a forecast. From NSE's official data.")
async def get_market_mood(ctx: Sources, date: str = "today") -> Any:
    return await ctx.official.market_mood(date or "today")


@tool("get_market_breadth", "Market breadth", "Market",
      "Advances vs declines across all NSE stocks for a day (from NSE's official data). "
      "An advance/decline ratio above 1.5 is broad strength; below 0.7 is broad weakness.")
async def get_market_breadth(ctx: Sources, date: str = "") -> Any:
    data = await ctx.official.breadth(date)
    if isinstance(data, dict):
        ratio = num(data.get("ad_ratio"))
        if ratio is not None:
            data = {**data, "tone": "positive" if ratio >= 1.5 else "negative" if ratio <= 0.7 else "neutral",
                    "summary": (f"{data.get('advances', '?')} stocks rose and {data.get('declines', '?')} fell "
                                f"(A/D ratio {ratio:.2f}): " + ("broad buying." if ratio >= 1.5 else "broad selling." if ratio <= 0.7 else "mixed market."))}
    return data


@tool("get_ipos", "IPOs", "Market", "Open, upcoming and recently listed IPOs (mainboard and SME), with price band, dates and listing gains.")
async def get_ipos(ctx: Sources) -> Any:
    return await ctx.indian.get("ipo")


@tool("get_market_news", "Market news", "Market", "Latest Indian market news headlines with source, time and topics.")
async def get_market_news(ctx: Sources) -> Any:
    return await ctx.indian.get("news", {"page_no": 1, "size": 20})


@tool("get_api_usage", "API usage", "Market", "How many IndianAPI requests you have used and have left on your plan.")
async def get_api_usage(ctx: Sources) -> Any:
    return await ctx.indian.get("usage")


# ---- Institutional flows & derivatives (nseindia.com; usually blocked for automated requests) ----

@tool("get_fii_dii", "FII / DII flows", "Flows",
      "Latest daily FII/FPI and DII buy, sell and net values (₹ crore) in the cash market, with a plain-English "
      "summary and saved history. Tries nseindia.com first (often blocked for automated requests), then the "
      "most recent day imported from NSE's CSV download.")
async def get_fii_dii(ctx: Sources) -> Any:
    try:
        raw = await ctx.nse.fii_dii()
        day = analytics.fii_dii_summary(raw)
        history = ctx.save_fii_day(day)
        return {**day, "history": history, "source": "nseindia.com (live)"}
    except (APIError, ValueError) as live_err:
        history = ctx.fii_history()
        latest = next((h for h in reversed(history) if h.get("fii_net") is not None or h.get("dii_net") is not None), None)
        if not latest:
            raise APIError(f"{live_err} No imported FII/DII data yet: download the CSV from NSE's FII/DII page "
                           "and import it in the FII / DII tab.", status=404) from live_err
        day = analytics.fii_dii_summary(analytics.day_from_history(latest))
        return {**day, "history": history, "source": "Imported CSV"}


@tool("get_option_chain", "Option chain analysis", "Derivatives",
      "Option chain for an index (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY) or F&O stock, with put-call ratio, max pain, "
      "open-interest support/resistance, OI build-up per strike, ATM straddle and expected move. "
      "Leave expiry empty for the nearest one. Tries nseindia.com first (often blocked for automated requests), "
      "then the latest CSV the user imported from NSE's option-chain page.")
async def get_option_chain(ctx: Sources, symbol: str = "NIFTY", expiry: str = "") -> Any:
    sym = symbol.strip().upper()
    try:
        raw = await ctx.nse.option_chain(sym)
        source = "nseindia.com (live)"
    except APIError as live_err:
        rec = ctx.chain_import(sym)
        if not rec:
            raise APIError(f"No live data for {sym} and nothing imported yet. Download the option chain CSV from "
                           "nseindia.com/option-chain and import it here.", status=404) from live_err
        raw = rec["payload"]
        source = f"Imported CSV ({rec.get('filename') or sym}, imported {rec.get('imported_at')})"
    try:
        result = analytics.option_chain_analysis(raw, sym, expiry or None)
    except ValueError as exc:
        raise APIError(f"{exc} Is {sym} in the F&O segment?", status=404) from exc
    return result | {"source": source, "spot_estimated": not bool(analytics.normalize_option_chain(raw)[1])}


# ---- Stock insights ----

async def _candles(ctx: Sources, symbol: str, months: int) -> list[dict[str, Any]]:
    """NSE serves at most 3 months per call; chain calls for longer periods."""
    candles: list[dict[str, Any]] = []
    end = "today"
    left = months
    while left > 0:
        chunk = await ctx.official.history(symbol, min(3, left), end)
        rows = (chunk or {}).get("data") or [] if isinstance(chunk, dict) else []
        candles = rows + candles
        end = (chunk or {}).get("next_end_date") if isinstance(chunk, dict) else None
        left -= 3
        if not end or not rows:
            break
    return candles


@tool("get_volume_profile", "Volume profile", "Research",
      "Volume profile for an NSE symbol from daily data: point of control, value area (70% of volume) and "
      "buy vs sell volume by price level. A daily-data stand-in for footprint charts.")
async def get_volume_profile(ctx: Sources, symbol: str, months: Literal[1, 3, 6, 12] = 3, bins: int = 24) -> Any:
    candles = await _candles(ctx, symbol, int(months))
    try:
        return {"symbol": symbol.upper(), "months": int(months), **analytics.volume_profile(candles, max(8, min(int(bins), 60)))}
    except ValueError as exc:
        raise APIError(str(exc), status=404) from exc


@tool("compare_stocks", "Compare stocks", "Research",
      "Compare total return and maximum drawdown of up to 10 NSE symbols over 1-24 months. "
      "Pass symbols comma-separated, e.g. 'TCS, INFY, WIPRO'.")
async def compare_stocks(ctx: Sources, symbols: str, months: Literal[1, 3, 6, 12, 24] = 6) -> Any:
    syms = [s.strip().upper() for s in symbols.replace(";", ",").split(",") if s.strip()][:10]
    if not syms:
        raise APIError("Give at least one symbol.", status=400)
    return await ctx.official.compare(syms, int(months))


@tool("get_corporate_actions", "Corporate actions", "Research", "Dividends, splits and bonuses with ex-dates for an NSE symbol (last 5 years).")
async def get_corporate_actions(ctx: Sources, symbol: str) -> Any:
    return await ctx.official.corporate_actions(symbol)


@tool("get_analyst_view", "Analyst view", "Research",
      "Analyst consensus for a stock: rating (Buy to Sell), how many analysts rate it each way, average/high/low "
      "target price, upside from the current price and how sentiment changed over 90 days.")
async def get_analyst_view(ctx: Sources, symbol: str, price: float | None = None) -> Any:
    raw = await ctx.indian.get("stock_target_price", {"stock_id": symbol})
    if price is None:
        try:
            price = num((await ctx.official.week52(symbol)).get("last_close"))
        except Exception:  # noqa: BLE001 - upside is optional
            price = None
    try:
        return {"symbol": symbol.upper(), "price": price, **analytics.analyst_view(raw, price)}
    except ValueError as exc:
        raise APIError(str(exc), status=404) from exc


@tool("get_stock_scorecard", "Stock scorecard", "Research",
      "One-glance health check for an NSE symbol combining trend (50/200-day averages), 1-year momentum, "
      "52-week position, volume vs average and analyst consensus. Each signal is explained; this is not advice.")
async def get_stock_scorecard(ctx: Sources, symbol: str, price: float | None = None) -> Any:
    sym = symbol.strip().upper()

    async def safe(coro):
        try:
            return await coro, None
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)

    (hist, e1), (target, e2), (w52, e3), (vol, e4) = await asyncio.gather(
        safe(ctx.indian.get("historical_data", {"stock_name": sym, "period": "1yr", "filter": "price"})),
        safe(ctx.indian.get("stock_target_price", {"stock_id": sym})),
        safe(ctx.official.week52(sym)),
        safe(ctx.official.volume_analysis(sym, 60)),
    )
    price = price if price is not None else num((w52 or {}).get("last_close")) if isinstance(w52, dict) else None
    analyst = None
    if target:
        try:
            analyst = analytics.analyst_view(target, price)
        except ValueError:
            analyst = None
    card = analytics.scorecard(price=price, history=hist, analyst=analyst,
                               week52=w52 if isinstance(w52, dict) else None, volume=vol if isinstance(vol, dict) else None)
    errors = {k: v for k, v in {"history": e1, "analysts": e2, "52_week": e3, "volume": e4}.items() if v}
    return {"symbol": sym, "price": price, **card, "analyst": analyst,
            "week52": w52 if isinstance(w52, dict) else None, "volume": vol if isinstance(vol, dict) else None, "errors": errors}
