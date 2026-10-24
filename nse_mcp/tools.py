"""The market-data tools, defined once and shared by the MCP server and the REST API."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

from .api import MarketData

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
    fn: Callable[..., Awaitable[Any]]  # first arg is the MarketData source

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
async def get_trending_stocks(src: MarketData) -> Any:
    return await src.get("trending")


@tool("get_nse_most_active", "NSE most active", "Market", "Most actively traded NSE stocks, ranked by volume.")
async def get_nse_most_active(src: MarketData) -> Any:
    return await src.get("NSE_most_active")


@tool("get_bse_most_active", "BSE most active", "Market", "Most actively traded BSE stocks, ranked by volume.")
async def get_bse_most_active(src: MarketData) -> Any:
    return await src.get("BSE_most_active")


@tool("get_52_week_high_low", "52-week highs & lows", "Market",
      "Stocks at or near their 52-week high or low on BSE and NSE. May be empty while the market is closed.")
async def get_52_week_high_low(src: MarketData) -> Any:
    return await src.get("fetch_52_week_high_low_data")


@tool("get_price_shockers", "Price shockers", "Market", "Stocks with sharp price moves in a short period.")
async def get_price_shockers(src: MarketData) -> Any:
    return await src.get("price_shockers")


@tool("get_commodities", "Commodity futures", "Market",
      "Live commodity futures (gold, silver, crude oil, etc.): price, change, volume and open interest.")
async def get_commodities(src: MarketData) -> Any:
    return await src.get("commodities")


# ---- Company research ----

@tool("get_stock_data", "Company details", "Research",
      "Full details for one company by name or symbol (e.g. 'Reliance', 'TCS'): NSE/BSE price, % change, "
      "52-week range, profile, financials, analyst view, shareholding and recent news.")
async def get_stock_data(src: MarketData, name: str) -> Any:
    return await src.get("stock", {"name": name})


@tool("search_industry", "Search by industry", "Research",
      "Find listed companies in an industry or sector (e.g. 'software', 'banks').")
async def search_industry(src: MarketData, query: str) -> Any:
    return await src.get("industry_search", {"query": query})


@tool("get_historical_data", "Price history", "Research",
      "Historical price (with 50/200-day moving averages), volume or valuation ratios for a stock.")
async def get_historical_data(src: MarketData, stock_name: str, period: Period = "1yr", filter: HistoryFilter = "price") -> Any:
    return await src.get("historical_data", {"stock_name": stock_name, "period": period, "filter": filter})


@tool("get_historical_stats", "Financial statements", "Research",
      "Quarterly/annual results, balance sheet, cash flow, ratios or shareholding pattern for a stock.")
async def get_historical_stats(src: MarketData, stock_name: str, stats: Stats) -> Any:
    return await src.get("historical_stats", {"stock_name": stock_name, "stats": stats})


@tool("get_analyst_recommendations", "Analyst targets", "Research",
      "Analyst target prices and buy/hold/sell recommendation breakdown for a stock "
      "(1 = Buy, 2 = Outperform, 3 = Hold, 4 = Underperform, 5 = Sell).")
async def get_analyst_recommendations(src: MarketData, stock_id: str) -> Any:
    return await src.get("stock_target_price", {"stock_id": stock_id})


@tool("get_stock_forecasts", "Forecasts", "Research",
      "Analyst forecasts or actuals for one measure (EPS, revenue, ROE, ...) of a stock.")
async def get_stock_forecasts(
    src: MarketData,
    stock_id: str,
    measure_code: MeasureCode = "EPS",
    period_type: PeriodType = "Annual",
    data_type: DataType = "Estimates",
    age: DataAge = "Current",
) -> Any:
    return await src.get("stock_forecasts", {
        "stock_id": stock_id, "measure_code": measure_code, "period_type": period_type,
        "data_type": data_type, "age": age,
    })


# ---- Funds ----

@tool("get_mutual_funds", "Mutual funds", "Funds",
      "Latest mutual fund NAVs and 1M-5Y returns, grouped by category (Equity, Debt, Hybrid...).")
async def get_mutual_funds(src: MarketData) -> Any:
    return await src.get("mutual_funds")


@tool("search_mutual_funds", "Search mutual funds", "Funds", "Search mutual fund schemes by name.")
async def search_mutual_funds(src: MarketData, query: str) -> Any:
    return await src.get("mutual_fund_search", {"query": query})
