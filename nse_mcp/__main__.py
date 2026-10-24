"""Command line entry point.

    python -m nse_mcp            # stdio MCP server (Claude Desktop, Claude Code)
    python -m nse_mcp http       # dashboard + MCP over HTTP at /mcp
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import Settings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="nse-mcp", description="NSE/BSE market data MCP server")
    parser.add_argument("mode", nargs="?", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", help="HTTP host (default from ISE_HTTP_HOST or 127.0.0.1)")
    parser.add_argument("--port", type=int, help="HTTP port (default from ISE_HTTP_PORT or 8000)")
    parser.add_argument("--demo", action="store_true", help="Use bundled sample data instead of IndianAPI")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    overrides = {k: v for k, v in {"host": args.host, "port": args.port}.items() if v}
    if args.demo:
        overrides["force_demo"] = True
    if overrides:
        from dataclasses import replace
        settings = replace(settings, **overrides)

    # stdout carries the MCP protocol in stdio mode, so logs always go to stderr.
    logging.basicConfig(stream=sys.stderr, level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from .server import build_http_app, build_mcp

    if args.mode == "stdio":
        mcp, _ = build_mcp(settings)
        mcp.run("stdio")
        return

    import uvicorn

    app = build_http_app(settings)
    base = f"http://{settings.host}:{settings.port}"
    print(f"\n  Dashboard  {base}/\n  MCP (HTTP) {base}/mcp\n  Mode       {'DEMO data' if settings.demo_mode else 'LIVE (IndianAPI)'}\n", file=sys.stderr)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
