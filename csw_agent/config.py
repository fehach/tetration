"""Runtime configuration loaded from CLI args, env vars, and defaults."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CREDENTIALS = Path.home() / ".csw" / "bancoppel.json"
LEGACY_CREDENTIALS_CANDIDATES = (
    Path.home() / ".csw" / "credentials.json",
    Path("credentials.json"),
    Path.home() / "Downloads" / "cxtaas_api_credentials.json",
)


@dataclass(slots=True)
class Settings:
    """Centralized configuration. Field defaults can be overridden by env or CLI."""

    api_endpoint: str = "https://bancoppel.tetrationcloud.com/"
    credentials_file: Path = DEFAULT_CREDENTIALS
    verify_tls: bool = True
    claudegate_url: str = "http://localhost:9999"
    claudegate_api_key: str = "sk-ant-dummy-key"
    claude_model: str = "github-copilot/claude-sonnet-4.6"
    safe_mode: bool = True
    max_history_turns: int = 10
    max_tokens_code: int = 8000
    max_tokens_csv: int = 6000
    syntax_retry_limit: int = 2
    workspace_cache_ttl_seconds: int = 300
    request_timeout_seconds: int = 60
    log_level: str = "INFO"
    extras: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> Settings:
        """Build a Settings instance from environment variables."""
        kwargs: dict[str, object] = {}
        if v := os.environ.get("CSW_ENDPOINT"):
            kwargs["api_endpoint"] = v
        if v := os.environ.get("CSW_CREDENTIALS"):
            kwargs["credentials_file"] = Path(v).expanduser()
        if v := os.environ.get("CSW_VERIFY_TLS"):
            kwargs["verify_tls"] = v.lower() not in ("0", "false", "no")
        if v := os.environ.get("CLAUDEGATE_URL"):
            kwargs["claudegate_url"] = v
        if v := os.environ.get("CLAUDEGATE_API_KEY"):
            kwargs["claudegate_api_key"] = v
        if v := os.environ.get("CLAUDE_MODEL"):
            kwargs["claude_model"] = v
        if v := os.environ.get("CSW_SAFE_MODE"):
            kwargs["safe_mode"] = v.lower() not in ("0", "false", "no")
        if v := os.environ.get("CSW_LOG_LEVEL"):
            kwargs["log_level"] = v.upper()
        if v := os.environ.get("CSW_REQUEST_TIMEOUT"):
            try:
                kwargs["request_timeout_seconds"] = int(v)
            except ValueError:
                logger.warning("Invalid CSW_REQUEST_TIMEOUT=%r; using default.", v)
        return cls(**kwargs)  # type: ignore[arg-type]

    def resolve_credentials(self) -> Path:
        """Return the credentials path, falling back to legacy locations if needed."""
        if self.credentials_file.exists():
            return self.credentials_file
        for legacy in LEGACY_CREDENTIALS_CANDIDATES:
            if legacy.exists():
                logger.warning(
                    "Using legacy credentials path %s; recommended location is %s",
                    legacy,
                    DEFAULT_CREDENTIALS,
                )
                return legacy
        raise FileNotFoundError(
            f"Credentials file not found at {self.credentials_file}. "
            "Place it at ~/.csw/credentials.json (chmod 600) or set CSW_CREDENTIALS."
        )
