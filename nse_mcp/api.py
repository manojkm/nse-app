"""Data sources: the live IndianAPI client and an offline demo source."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Protocol

import httpx

from . import sample_data
from .api_errors import APIError
from .config import Settings

logger = logging.getLogger("nse_mcp.api")


class MarketData(Protocol):
    demo: bool

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any: ...

    async def aclose(self) -> None: ...


class IndianAPIClient:
    """Thin async client for https://stock.indianapi.in with a small TTL cache."""

    demo = False

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://stock.indianapi.in",
        timeout: float = 30,
        cache_ttl: float = 60,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=timeout,
            headers={"X-Api-Key": api_key, "Accept": "application/json", "User-Agent": "nse-mcp/1.0"},
            transport=transport,
        )
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        key = endpoint + "?" + json.dumps(params, sort_keys=True)
        now = time.monotonic()
        hit = self._cache.get(key)
        if hit and now - hit[0] < self._cache_ttl:
            return hit[1]

        try:
            response = await self._http.get(endpoint.lstrip("/"), params=params)
        except httpx.TimeoutException as exc:
            raise APIError("IndianAPI did not respond in time. Try again shortly.") from exc
        except httpx.HTTPError as exc:
            raise APIError(f"Could not reach IndianAPI: {exc.__class__.__name__}") from exc

        if response.status_code >= 400:
            raise APIError(_error_message(response), status=response.status_code)

        try:
            data = response.json()
        except ValueError as exc:
            raise APIError("IndianAPI returned a response that is not JSON.") from exc

        if self._cache_ttl > 0:
            self._cache[key] = (now, data)
        return data

    async def aclose(self) -> None:
        await self._http.aclose()


def _error_message(response: httpx.Response) -> str:
    detail = ""
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = str(body.get("error") or body.get("message") or body.get("detail") or "")
    except ValueError:
        pass
    status = response.status_code
    if status in (401, 403):
        return "IndianAPI rejected the API key. Check ISE_API_KEY and your subscription."
    if status == 404:
        return detail or "No data found for that request."
    if status == 429:
        return "IndianAPI rate limit reached. Wait a moment or check your plan quota."
    return detail or f"IndianAPI request failed with HTTP {status}."


class DemoData:
    """Serves bundled sample data so the server and dashboard work without a key."""

    demo = True

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        return sample_data.respond(endpoint.strip("/"), params or {})

    async def aclose(self) -> None:
        return None


def create_source(settings: Settings) -> MarketData:
    if settings.demo_mode:
        logger.warning("Running in DEMO mode with sample data. Set ISE_API_KEY for live data.")
        return DemoData()
    return IndianAPIClient(
        api_key=settings.api_key or "",
        base_url=settings.base_url,
        timeout=settings.timeout,
        cache_ttl=settings.cache_ttl,
    )
