"""All data sources the tools can use, bundled so each tool gets one object."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import sample_data
from .analytics import merge_history
from .api import DemoData, MarketData, create_source
from .config import PROJECT_ROOT, Settings
from .nse_official import NSEOfficial, NSEOfficialDemo
from .nse_site import NSESite, NSESiteDemo

logger = logging.getLogger("nse_mcp.sources")


@dataclass
class Sources:
    indian: MarketData                # IndianAPI (needs ISE_API_KEY)
    nse: NSESite | NSESiteDemo        # nseindia.com website data (FII/DII, option chain)
    official: NSEOfficial | NSEOfficialDemo  # NSE's official MCP servers
    history_file: Path | None = None  # where daily FII/DII figures are kept
    _fii_history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def demo(self) -> bool:
        return bool(self.indian.demo)

    def fii_history(self) -> list[dict[str, Any]]:
        if self.history_file is None:
            return self._fii_history
        try:
            return json.loads(self.history_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def save_fii_day(self, day: dict[str, Any]) -> list[dict[str, Any]]:
        history = merge_history(self.fii_history(), day)
        if self.history_file is None:
            self._fii_history = history
            return history
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            self.history_file.write_text(json.dumps(history, indent=1), encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not save FII/DII history: %s", exc)
        return history

    async def aclose(self) -> None:
        for s in (self.indian, self.nse, self.official):
            await s.aclose()


def demo_sources() -> Sources:
    return Sources(DemoData(), NSESiteDemo(), NSEOfficialDemo(), None, sample_data.fii_dii_history())


def create_sources(settings: Settings) -> Sources:
    if settings.demo_mode:
        return Sources(create_source(settings), NSESiteDemo(), NSEOfficialDemo(), None, sample_data.fii_dii_history())
    return Sources(
        create_source(settings),
        NSESite(cache_ttl=settings.cache_ttl),
        NSEOfficial(cache_ttl=max(settings.cache_ttl, 300)),
        PROJECT_ROOT / "data" / "fii_dii_history.json",
    )
