"""nseindia.com website data: FII/DII flows and option chains.

NSE has no official public API for these, and its site uses bot protection to
block automated access. This client makes plain, honestly identified requests and
does NOT try to get around that protection. If NSE declines the request (the usual
outcome), the tools return a clear "unavailable" message instead of data.

For reliable option-chain data, use a broker API you have an account with
(see README: "Getting FII/DII and option-chain data").
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from . import sample_data
from .api_errors import APIError

logger = logging.getLogger("nse_mcp.nse_site")

BASE = "https://www.nseindia.com"

UNAVAILABLE_MSG = (
    "NSE's website declined the request: it blocks automated access to this data, and this app "
    "doesn't try to get around that. See the README section 'Getting FII/DII and option-chain data' "
    "for official alternatives."
)


class NSESite:
    demo = False

    def __init__(self, cache_ttl: float = 60, timeout: float = 15):
        self._cache_ttl = cache_ttl
        self._http = httpx.AsyncClient(
            base_url=BASE, timeout=timeout,
            headers={"User-Agent": "nse-mcp/1.0 (personal dashboard)", "Accept": "application/json"},
        )
        self._cache: dict[str, tuple[float, Any]] = {}

    async def get(self, path: str, ttl: float | None = None) -> Any:
        ttl = self._cache_ttl if ttl is None else ttl
        hit = self._cache.get(path)
        if hit and time.monotonic() - hit[0] < ttl:
            return hit[1]
        try:
            r = await self._http.get(path)
        except httpx.HTTPError as exc:
            raise APIError(f"Could not reach nseindia.com ({exc.__class__.__name__}).", status=502) from exc
        if r.status_code != 200:
            logger.info("NSE %s -> HTTP %s", path, r.status_code)
            raise APIError(UNAVAILABLE_MSG, status=502)
        try:
            data = r.json()
        except ValueError as exc:
            raise APIError(UNAVAILABLE_MSG, status=502) from exc
        if data in (None, {}, []):
            raise APIError(UNAVAILABLE_MSG, status=502)
        self._cache[path] = (time.monotonic(), data)
        return data

    async def fii_dii(self) -> Any:
        return await self.get("/api/fiidiiTradeReact", ttl=900)

    async def option_chain(self, symbol: str) -> Any:
        symbol = symbol.strip().upper()
        return await self.get(f"/api/NextApi/apiClient/GetQuoteApi?functionName=getSymbolDerivativesData&symbol={symbol}")

    async def expiries(self, symbol: str) -> list[str]:
        data = await self.get(
            f"/api/NextApi/apiClient/GetQuoteApi?functionName=getOptionChainDropdown&symbol={symbol.strip().upper()}", ttl=3600
        )
        return list(data.get("expiryDates") or []) if isinstance(data, dict) else []

    async def aclose(self) -> None:
        await self._http.aclose()


class NSESiteDemo:
    demo = True

    async def fii_dii(self) -> Any:
        return sample_data.fii_dii()

    async def option_chain(self, symbol: str) -> Any:
        return sample_data.option_chain(symbol)

    async def expiries(self, symbol: str) -> list[str]:
        return sample_data.option_expiries()

    async def aclose(self) -> None:
        return None
