"""Runtime settings, read from environment variables (and an optional .env).

Secrets (the external AI key) stay in this process. `public_view()` is the only
thing ever sent to the browser, and it never contains the key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TRUE = {"1", "true", "yes", "on"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env loader: KEY=VALUE lines; existing env vars win."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    db_path: Path
    static_dir: Path
    external_enabled: bool
    external_provider: str
    anthropic_api_key: str | None
    external_model: str
    external_effort: str
    external_timeout_s: float

    @property
    def external_ready(self) -> bool:
        return self.external_enabled and self.external_provider == "anthropic" and bool(self.anthropic_api_key)

    def public_view(self) -> dict:
        return {
            "default_mode": "external" if self.external_ready else "local",
            "external_enabled": self.external_enabled,
            "external_configured": self.external_ready,
            "external_provider": self.external_provider if self.external_enabled else None,
            "external_model": self.external_model if self.external_ready else None,
        }


def load_settings() -> Settings:
    load_dotenv()
    effort = os.environ.get("ANALYST_EFFORT", "medium").lower()
    return Settings(
        host=os.environ.get("APP_HOST", "127.0.0.1"),
        port=int(os.environ.get("APP_PORT", "8000")),
        db_path=Path(os.environ.get("APP_DB_PATH", ROOT / "var" / "app.db")),
        static_dir=Path(os.environ.get("APP_STATIC_DIR", ROOT / "frontend" / "dist")),
        external_enabled=os.environ.get("ANALYST_EXTERNAL_ENABLED", "false").lower() in TRUE,
        external_provider=os.environ.get("ANALYST_PROVIDER", "anthropic").lower(),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        external_model=os.environ.get("ANALYST_MODEL", "claude-opus-5-5"),
        external_effort=effort if effort in EFFORTS else "medium",
        external_timeout_s=float(os.environ.get("ANALYST_TIMEOUT_S", "60")),
    )
