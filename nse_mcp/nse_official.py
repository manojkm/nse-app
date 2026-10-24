"""Client for NSE's official MCP servers (https://www.nseindia.com/nse-mcp).

- Bhavcopy: 5 years of end-of-day data, market breadth, volume analysis, corporate actions.
- CM Market Live: live quotes and movers, 1-3 minutes delayed.

No API key is needed. NSE states the data is for informational, non-commercial use.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from . import sample_data
from .api_errors import APIError

logger = logging.getLogger("nse_mcp.nse_official")

SERVERS = {
    "bhavcopy": "https://mcp.nseindia.in/bhavcopy/cm/mcp",
    "live": "https://mcp.nseindia.in/cmmkt/mcp",
}


def _parse(result: Any) -> Any:
    """NSE tools return JSON (or a bare number) as text content."""
    texts = [c.text for c in (result.content or []) if getattr(c, "type", "") == "text"]
    text = "\n".join(texts).strip()
    if result.is_error:
        raise APIError(text or "NSE MCP tool failed.")
    try:
        data = json.loads(text)
    except ValueError:
        return text
    if isinstance(data, dict) and data.get("error") and len(data) <= 3:
        raise APIError(f"NSE: {data['error']}", status=404)
    return data


class NSEOfficial:
    demo = False

    def __init__(self, cache_ttl: float = 300, timeout: float = 30):
        self._cache_ttl = cache_ttl
        self._timeout = timeout
        self._cache: dict[str, tuple[float, Any]] = {}

    async def call(self, server: str, tool: str, args: dict[str, Any] | None = None, ttl: float | None = None) -> Any:
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client

        args = args or {}
        key = f"{server}:{tool}:{json.dumps(args, sort_keys=True)}"
        hit = self._cache.get(key)
        ttl = self._cache_ttl if ttl is None else ttl
        if hit and time.monotonic() - hit[0] < ttl:
            return hit[1]
        try:
            # NSE's edge rejects the session DELETE, so don't send it on close.
            transport = streamable_http_client(SERVERS[server], terminate_on_close=False)
            async with Client(transport, read_timeout_seconds=self._timeout) as client:
                result = await client.call_tool(tool, args)
        except APIError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.info("NSE MCP %s/%s failed: %r", server, tool, exc)
            raise APIError("Could not reach NSE's official data service (mcp.nseindia.in). Try again shortly.", status=502) from exc
        data = _parse(result)
        self._cache[key] = (time.monotonic(), data)
        return data

    # Thin, typed helpers -------------------------------------------------

    async def history(self, symbol: str, months: int = 3, end_date: str = "today") -> Any:
        return await self.call("bhavcopy", "get_stock_history", {"symbol": symbol.upper(), "months": months, "endDate": end_date})

    async def breadth(self, date: str = "") -> Any:
        return await self.call("bhavcopy", "get_market_breadth", {"date": date})

    async def volume_analysis(self, symbol: str, days: int = 60) -> Any:
        return await self.call("bhavcopy", "get_volume_analysis", {"symbol": symbol.upper(), "days": days})

    async def week52(self, symbol: str) -> Any:
        return await self.call("bhavcopy", "get_52_week_high_low", {"symbol": symbol.upper()})

    async def compare(self, symbols: list[str], months: int = 6) -> Any:
        return await self.call("bhavcopy", "compare_stocks", {"symbols": [s.upper() for s in symbols], "months": months})

    async def corporate_actions(self, symbol: str) -> Any:
        return await self.call("bhavcopy", "get_corporate_actions", {"symbol": symbol.upper(), "fromDate": "", "toDate": ""}, ttl=86400)

    async def lookup(self, query: str) -> Any:
        return await self.call("bhavcopy", "search_symbols", {"query": query}, ttl=86400)

    async def aclose(self) -> None:
        return None


class NSEOfficialDemo:
    demo = True

    async def history(self, symbol: str, months: int = 3, end_date: str = "today") -> Any:
        return sample_data.nse_history(symbol, months)

    async def breadth(self, date: str = "") -> Any:
        return sample_data.breadth()

    async def volume_analysis(self, symbol: str, days: int = 60) -> Any:
        return sample_data.volume_analysis(symbol)

    async def week52(self, symbol: str) -> Any:
        return sample_data.nse_week52(symbol)

    async def compare(self, symbols: list[str], months: int = 6) -> Any:
        return sample_data.compare(symbols, months)

    async def corporate_actions(self, symbol: str) -> Any:
        return sample_data.corporate_actions(symbol)

    async def lookup(self, query: str) -> Any:
        return sample_data.lookup(query)

    async def aclose(self) -> None:
        return None
