import json
from dataclasses import replace

import httpx
import pytest
from mcp import Client
from starlette.testclient import TestClient

from nse_mcp.api import DemoData, IndianAPIClient
from nse_mcp.api_errors import APIError
from nse_mcp.config import Settings
from nse_mcp.server import build_http_app, build_mcp
from nse_mcp.tools import TOOLS

DEMO = replace(Settings.from_env(), force_demo=True, host="127.0.0.1")

EXPECTED_TOOLS = {
    "get_stock_data", "search_industry", "search_mutual_funds", "get_trending_stocks", "get_52_week_high_low",
    "get_nse_most_active", "get_bse_most_active", "get_mutual_funds", "get_price_shockers", "get_commodities",
    "get_analyst_recommendations", "get_stock_forecasts", "get_historical_data", "get_historical_stats",
}


def test_registry_has_all_reference_tools():
    assert set(TOOLS) == EXPECTED_TOOLS


async def test_mcp_lists_and_calls_tools():
    mcp, _ = build_mcp(DEMO, DemoData())
    async with Client(mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        assert set(tools) == EXPECTED_TOOLS
        schema = tools["get_historical_data"].input_schema
        assert schema["required"] == ["stock_name"]
        assert "src" not in schema["properties"]
        assert "1yr" in schema["properties"]["period"]["enum"]

        result = await client.call_tool("get_stock_data", {"name": "Reliance"})
        assert not result.is_error
        text = result.content[0].text
        assert text.startswith("[DEMO DATA")
        assert json.loads(text.split("\n", 1)[1])["tickerId"] == "RELIANCE"


async def test_mcp_reports_upstream_errors_as_tool_errors():
    mcp, _ = build_mcp(DEMO, DemoData())
    async with Client(mcp) as client:
        result = await client.call_tool("get_stock_data", {"name": "nonexistent-co"})
        assert result.is_error
        assert "No demo stock" in result.content[0].text


@pytest.mark.parametrize("name", sorted(EXPECTED_TOOLS))
async def test_every_tool_returns_demo_data(name):
    spec = TOOLS[name]
    sample_args = {"name": "TCS", "query": "bank", "stock_id": "TCS", "stock_name": "TCS", "stats": "quarter_results"}
    if name == "search_mutual_funds":
        sample_args["query"] = "bluechip"
    args = {p: sample_args[p] for p in spec.signature.parameters if p in sample_args}
    data = await spec.fn(DemoData(), **args)
    assert data


def test_rest_api():
    with TestClient(build_http_app(DEMO, DemoData())) as http:
        assert http.get("/health").json()["demo"] is True
        assert len(http.get("/api/tools").json()["tools"]) == 14

        body = http.get("/api/tools/get_trending_stocks").json()
        assert body["demo"] is True
        assert len(body["data"]["trending_stocks"]["top_gainers"]) == 3

        assert http.get("/api/tools/get_stock_data").status_code == 400  # missing name
        assert http.get("/api/tools/get_historical_data?stock_name=TCS&period=2d").status_code == 400
        assert http.get("/api/tools/get_stock_data?name=nope").status_code == 404
        assert http.get("/api/tools/does_not_exist").status_code == 404

        page = http.get("/")
        assert page.status_code == 200 and "<html" in page.text.lower()


def test_mcp_over_http():
    with TestClient(build_http_app(DEMO, DemoData()), base_url="http://127.0.0.1:8000") as http:
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}
        r = http.post("/mcp", json=init, headers=headers)
        assert r.status_code == 200, r.text
        r = http.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                      headers=headers | {"MCP-Protocol-Version": "2025-06-18"})
        assert r.status_code == 200, r.text
        assert "get_trending_stocks" in r.text


def test_mcp_http_rejects_foreign_host_header():
    with TestClient(build_http_app(DEMO, DemoData()), base_url="http://evil.example") as http:
        r = http.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                      headers={"Accept": "application/json, text/event-stream"})
        assert r.status_code == 421


# ---- live client, against a mocked IndianAPI ----

def _client(handler, **kw):
    return IndianAPIClient("test-key", base_url="https://stock.indianapi.in/", transport=httpx.MockTransport(handler), **kw)


async def test_live_client_builds_url_and_sends_key():
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    api = _client(handler)
    assert await api.get("/stock", {"name": "Tata Motors", "empty": ""}) == {"ok": True}
    req = seen[0]
    assert str(req.url) == "https://stock.indianapi.in/stock?name=Tata+Motors"
    assert req.headers["x-api-key"] == "test-key"
    await api.aclose()


async def test_live_client_caches_identical_calls():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=[calls])

    api = _client(handler, cache_ttl=60)
    assert await api.get("trending") == [1]
    assert await api.get("trending") == [1]
    assert calls == 1


@pytest.mark.parametrize("status,needle", [(401, "API key"), (429, "rate limit"), (404, "not found here"), (500, "HTTP 500")])
async def test_live_client_error_messages(status, needle):
    body = {"error": "not found here"} if status == 404 else {}
    api = _client(lambda r: httpx.Response(status, json=body))
    with pytest.raises(APIError) as exc:
        await api.get("stock", {"name": "x"})
    assert needle in str(exc.value)
    assert exc.value.status == status


async def test_stdio_mode_end_to_end(tmp_path):
    """Launch `python -m nse_mcp` as a subprocess, exactly like Claude Desktop does."""
    import os
    import sys

    from mcp import StdioServerParameters

    from nse_mcp.config import PROJECT_ROOT

    params = StdioServerParameters(
        command=sys.executable, args=["-m", "nse_mcp", "--demo"], cwd=str(PROJECT_ROOT),
        env={**os.environ, "ISE_API_KEY": ""},
    )
    async with Client(params) as client:
        tools = (await client.list_tools()).tools
        assert len(tools) == 14
        result = await client.call_tool("get_nse_most_active", {})
        assert not result.is_error
        assert "RELIANCE.NS" in result.content[0].text
