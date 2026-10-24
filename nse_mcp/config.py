"""Settings, read from environment variables and an optional .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(*paths: Path) -> None:
    """Load KEY=VALUE lines into os.environ without overriding real env vars."""
    for path in paths:
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    base_url: str
    timeout: float
    cache_ttl: float
    host: str
    port: int
    log_level: str
    force_demo: bool

    @property
    def demo_mode(self) -> bool:
        """Demo mode serves bundled sample data instead of calling IndianAPI."""
        return self.force_demo or not self.api_key

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(Path.cwd() / ".env", PROJECT_ROOT / ".env")
        env = os.environ.get
        return cls(
            api_key=(env("ISE_API_KEY") or "").strip() or None,
            base_url=(env("ISE_API_BASE_URL") or "https://stock.indianapi.in").rstrip("/"),
            timeout=float(env("ISE_REQUEST_TIMEOUT") or 30),
            cache_ttl=float(env("ISE_CACHE_TTL") or 60),
            host=env("ISE_HTTP_HOST") or "127.0.0.1",
            port=int(env("ISE_HTTP_PORT") or 8000),
            log_level=(env("ISE_LOG_LEVEL") or "INFO").upper(),
            force_demo=_truthy(env("ISE_DEMO_MODE")),
        )
