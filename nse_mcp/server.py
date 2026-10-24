"""MCP server (stdio + Streamable HTTP), REST API for the dashboard, and static file hosting."""

from __future__ import annotations

import functools
import inspect
import json
import logging
import typing
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.staticfiles import StaticFiles

from . import __version__, analytics, imports
from .api_errors import APIError
from .config import PROJECT_ROOT, Settings
from .sources import Sources, create_sources
from .tools import TOOLS, ToolSpec

logger = logging.getLogger("nse_mcp")

INSTRUCTIONS = (
    "Indian stock market data (NSE & BSE). Prices are in INR. "
    "Market overview: get_indices, get_market_breadth, get_trending_stocks, get_nse_most_active. "
    "One company: get_stock_data, get_stock_scorecard, get_analyst_view, get_volume_profile, get_historical_data. "
    "Institutions and derivatives: get_fii_dii, get_option_chain (NIFTY, BANKNIFTY or an F&O stock). "
    "Tools that take `symbol` expect an NSE symbol such as RELIANCE or TCS. Outputs describe data, not advice."
)


def _mcp_tool(spec: ToolSpec, source: Sources):
    """Wrap a ToolSpec as an MCP tool function with the same parameters, returning JSON text."""

    @functools.wraps(spec.fn)
    async def run(**kwargs: Any) -> str:
        try:
            data = await spec.fn(source, **kwargs)
        except APIError as exc:
            # ToolError reaches the model as a readable isError result.
            raise ToolError(str(exc)) from exc
        prefix = "[DEMO DATA - not live quotes]\n" if source.demo else ""
        return prefix + json.dumps(data, ensure_ascii=False, indent=1)

    sig = spec.signature.replace(return_annotation=str)
    run.__signature__ = sig  # type: ignore[attr-defined]
    run.__annotations__ = {p.name: p.annotation for p in sig.parameters.values()} | {"return": str}
    del run.__wrapped__  # stop inspect from following back to the original (which has `src`)
    return run


def build_mcp(settings: Settings, source: Sources | None = None) -> tuple[MCPServer, Sources]:
    source = source or create_sources(settings)
    mcp = MCPServer(
        name="nse-bse-market",
        title="NSE / BSE Market Data",
        instructions=INSTRUCTIONS,
        version=__version__,
        log_level=settings.log_level if settings.log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL") else "INFO",
    )
    for spec in TOOLS.values():
        mcp.tool(name=spec.name, title=spec.title, description=spec.description, structured_output=False)(
            _mcp_tool(spec, source)
        )
    return mcp, source


# ---------- REST API for the dashboard ----------

def _coerce_params(spec: ToolSpec, query: dict[str, str]) -> dict[str, Any]:
    """Validate query-string args against the tool signature. Raises ValueError with a readable message."""
    args: dict[str, Any] = {}
    for param in spec.signature.parameters.values():
        value = query.get(param.name)
        if value is None or value == "":
            if param.default is inspect.Parameter.empty:
                raise ValueError(f"Missing required parameter '{param.name}'.")
            continue
        args[param.name] = _convert(param.name, param.annotation, value.strip())
    return args


def _convert(name: str, annotation: Any, value: str) -> Any:
    if typing.get_origin(annotation) is typing.Literal:
        allowed = typing.get_args(annotation)
        for a in allowed:
            if str(a) == value:
                return a
        raise ValueError(f"'{name}' must be one of: {', '.join(map(str, allowed))}.")
    kinds = set(typing.get_args(annotation)) or {annotation}
    for kind in (int, float):
        if kind in kinds:
            try:
                return kind(value)
            except ValueError:
                raise ValueError(f"'{name}' must be a number.") from None
    return value


def _tool_info(spec: ToolSpec) -> dict[str, Any]:
    params = []
    for p in spec.signature.parameters.values():
        info: dict[str, Any] = {"name": p.name, "required": p.default is inspect.Parameter.empty}
        if p.default is not inspect.Parameter.empty:
            info["default"] = p.default
        if typing.get_origin(p.annotation) is typing.Literal:
            info["enum"] = list(typing.get_args(p.annotation))
        params.append(info)
    return {"name": spec.name, "title": spec.title, "group": spec.group, "description": spec.description, "params": params}


def build_http_app(settings: Settings, source: Sources | None = None) -> Starlette:
    mcp, source = build_mcp(settings, source)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> Response:
        return JSONResponse({"status": "ok", "version": __version__, "demo": source.demo})

    @mcp.custom_route("/api/tools", methods=["GET"])
    async def list_tools(_: Request) -> Response:
        return JSONResponse({"demo": source.demo, "tools": [_tool_info(s) for s in TOOLS.values()]})

    @mcp.custom_route("/api/tools/{name}", methods=["GET"])
    async def call_tool(request: Request) -> Response:
        spec = TOOLS.get(request.path_params["name"])
        if spec is None:
            return JSONResponse({"error": "Unknown tool."}, status_code=404)
        try:
            args = _coerce_params(spec, dict(request.query_params))
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        try:
            data = await spec.fn(source, **args)
        except APIError as exc:
            status = exc.status if exc.status in (400, 401, 403, 404, 429) else 502
            return JSONResponse({"error": str(exc)}, status_code=status)
        except Exception:  # noqa: BLE001 - never leak internals to the browser
            logger.exception("Tool %s failed", spec.name)
            return JSONResponse({"error": "Unexpected server error."}, status_code=500)
        return JSONResponse({"demo": source.demo, "data": data}, headers={"Cache-Control": "no-store"})

    async def read_csv(request: Request) -> str:
        body = await request.body()
        if len(body) > imports.MAX_BYTES:
            raise imports.ImportProblem("File is too large (max 3 MB).")
        for enc in ("utf-8-sig", "cp1252"):
            try:
                return body.decode(enc)
            except UnicodeDecodeError:
                continue
        raise imports.ImportProblem("Couldn't read the file as text. Is it a CSV?")

    @mcp.custom_route("/api/import/option-chain", methods=["POST"])
    async def import_option_chain(request: Request) -> Response:
        q = request.query_params
        try:
            spot = float(q["spot"]) if q.get("spot") else None
        except ValueError:
            return JSONResponse({"error": "Spot must be a number."}, status_code=400)
        try:
            parsed = imports.parse_option_chain_csv(await read_csv(request), filename=q.get("filename", ""),
                                                    symbol=q.get("symbol", ""), expiry=q.get("expiry", ""), spot=spot)
            symbol = parsed["symbol"] or q.get("symbol", "").upper()
            if not symbol:
                raise imports.ImportProblem("Couldn't tell which symbol this is from the file name. Enter it and try again.")
            payload = {"data": parsed["data"]}
            result = analytics.option_chain_analysis(payload, symbol)
        except (imports.ImportProblem, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        source.save_chain_import(symbol, {"payload": payload, "filename": q.get("filename", ""), "expiry": parsed["expiry"]})
        result |= {"source": f"Imported CSV ({q.get('filename') or symbol})", "spot_estimated": parsed["spot"] is None}
        return JSONResponse({"demo": source.demo, "data": result})

    @mcp.custom_route("/api/import/fii-dii", methods=["POST"])
    async def import_fii_dii(request: Request) -> Response:
        try:
            days = imports.parse_fii_dii_csv(await read_csv(request))
        except imports.ImportProblem as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        history = source.fii_history()
        for day in days:
            history = source.save_fii_day(day)
        latest = analytics.fii_dii_summary(analytics.day_from_history(
            next(h for h in history if h["date"] == days[-1]["date"])))
        return JSONResponse({"demo": source.demo, "data": {**latest, "history": history, "imported_days": len(days),
                                                           "source": "Imported CSV"}})

    app = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, host=settings.host)
    web_dir = PROJECT_ROOT / "web"
    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app
