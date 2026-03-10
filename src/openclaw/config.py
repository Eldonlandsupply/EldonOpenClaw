"""
Centralized config: secrets from .env / environment, non-secrets from config.yaml.
Fails loudly if misconfigured. Prints a redacted summary on boot.

config.yaml supports ${VAR} and ${VAR:default} substitution from environment.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── Environment variable expansion ────────────────────────────────────────

_ENV_TOKEN = re.compile(r"^\$\{([^}]+)\}$")


def _expand(value: Any) -> Any:
    """Recursively expand ${VAR} and ${VAR:default} tokens in YAML values."""
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    if isinstance(value, str):
        m = _ENV_TOKEN.match(value.strip())
        if m:
            inner = m.group(1)
            if ":" in inner:
                var, default = inner.split(":", 1)
                return os.environ.get(var.strip(), default)
            return os.environ.get(inner.strip(), "")
    return value


# ── Config section classes ─────────────────────────────────────────────────

class LLMConfig:
    def __init__(self, **data: Any) -> None:
        self.provider = str(data.get("provider", "none"))
        self.chat_model = str(data.get("chat_model", "gpt-4o-mini"))
        raw_embed = data.get("embedding_model")
        self.embedding_model = str(raw_embed) if raw_embed else None


class RuntimeConfig:
    def __init__(self, **data: Any) -> None:
        self.tick_seconds = int(data.get("tick_seconds", 10))
        self.log_level = str(data.get("log_level", "INFO")).upper()
        self.data_dir = str(data.get("data_dir", "./data"))
        raw_dry = data.get("dry_run", True)
        if isinstance(raw_dry, str):
            self.dry_run = raw_dry.lower() not in ("false", "0", "no")
        else:
            self.dry_run = bool(raw_dry)


class ConnectorCliConfig:
    def __init__(self, **data: Any) -> None:
        raw = data.get("enabled", True)
        self.enabled = raw if isinstance(raw, bool) else str(raw).lower() not in ("false", "0", "no")


class ConnectorTelegramConfig:
    def __init__(self, **data: Any) -> None:
        raw = data.get("enabled", False)
        self.enabled = raw if isinstance(raw, bool) else str(raw).lower() in ("true", "1", "yes")


class ConnectorsConfig:
    def __init__(self, **data: Any) -> None:
        cli_raw = data.get("cli", {})
        if isinstance(cli_raw, (bool, str)):
            cli_raw = {"enabled": cli_raw}
        self.cli = ConnectorCliConfig(**(cli_raw or {}))

        tg_raw = data.get("telegram", {})
        if isinstance(tg_raw, (bool, str)):
            tg_raw = {"enabled": tg_raw}
        self.telegram = ConnectorTelegramConfig(**(tg_raw or {}))


class ActionsConfig:
    def __init__(self, **data: Any) -> None:
        self.allowlist = list(data.get("allowlist", ["echo"]))
        raw = data.get("require_confirm", data.get("require_confirmation", False))
        if isinstance(raw, str):
            self.require_confirm = raw.lower() in ("true", "1", "yes")
        else:
            self.require_confirm = bool(raw)


class HealthConfig:
    def __init__(self, **data: Any) -> None:
        self.enabled = bool(data.get("enabled", True))
        self.host = str(data.get("host", "127.0.0.1"))
        self.port = int(data.get("port", 8080))


# ── Secrets from environment / .env ───────────────────────────────────────

def _find_env_file() -> str:
    """Resolve .env relative to the repo root, not the working directory."""
    candidates = [
        Path(".env"),
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path("/etc/openclaw/openclaw.env"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return ".env"  # fallback; pydantic-settings won't error if missing


class Secrets(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_allowed_chat_ids: Optional[str] = None
    gmail_user: Optional[str] = None
    gmail_app_password: Optional[str] = None
    notification_email: Optional[str] = None
    sqlite_path: str = "./data/openclaw.db"

    @property
    def allowed_chat_ids(self) -> list[int]:
        if not self.telegram_allowed_chat_ids:
            return []
        return [int(x.strip()) for x in self.telegram_allowed_chat_ids.split(",") if x.strip()]


# ── Valid sets ─────────────────────────────────────────────────────────────

_VALID_PROVIDERS: frozenset[str] = frozenset({"openai", "anthropic", "openrouter", "none"})
_VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})


# ── Merged app config ──────────────────────────────────────────────────────

class AppConfig:
    """Single object holding all config. Created once at startup."""

    def __init__(self, yaml_path: str = "config.yaml") -> None:
        self.secrets = Secrets()
        self._yaml_path = yaml_path
        self._load_yaml(yaml_path)
        self._validate()

    def _load_yaml(self, path: str) -> None:
        # Load .env first so ${VAR} expansion below sees the values
        load_dotenv(override=False)

        p = Path(path)
        if not p.exists():
            print(
                f"FATAL: config file not found: {path}\n"
                "       cp config.yaml.example config.yaml  # then edit it",
                file=sys.stderr,
            )
            sys.exit(1)

        with p.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        expanded = _expand(raw)

        self.llm = LLMConfig(**(expanded.get("llm") or {}))
        self.runtime = RuntimeConfig(**(expanded.get("runtime") or {}))
        self.connectors = ConnectorsConfig(**(expanded.get("connectors") or {}))
        self.actions = ActionsConfig(**(expanded.get("actions") or {}))
        self.health = HealthConfig(**(expanded.get("health") or {}))

    def _validate(self) -> None:
        if self.llm.provider not in _VALID_PROVIDERS:
            self._fatal(
                f"llm.provider must be one of {sorted(_VALID_PROVIDERS)}, "
                f"got: {self.llm.provider!r}"
            )
        if self.runtime.log_level not in _VALID_LOG_LEVELS:
            self._fatal(
                f"runtime.log_level must be one of {sorted(_VALID_LOG_LEVELS)}, "
                f"got: {self.runtime.log_level!r}"
            )
        if self.llm.provider == "openai" and not self.secrets.openai_api_key:
            self._fatal("llm.provider=openai but OPENAI_API_KEY is not set")
        if self.llm.provider == "openrouter" and not self.secrets.openrouter_api_key:
            self._fatal("llm.provider=openrouter but OPENROUTER_API_KEY is not set")
        if self.connectors.telegram.enabled and not self.secrets.telegram_bot_token:
            self._fatal("connectors.telegram.enabled=true but TELEGRAM_BOT_TOKEN is not set")
        Path(self.runtime.data_dir).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _fatal(msg: str) -> None:
        print(f"FATAL CONFIG ERROR: {msg}", file=sys.stderr)
        sys.exit(1)

    def summary(self) -> dict:
        return {
            "llm": {
                "provider": self.llm.provider,
                "chat_model": self.llm.chat_model,
                "embedding_model": self.llm.embedding_model,
            },
            "runtime": {
                "tick_seconds": self.runtime.tick_seconds,
                "log_level": self.runtime.log_level,
                "data_dir": self.runtime.data_dir,
                "dry_run": self.runtime.dry_run,
            },
            "connectors": {
                "cli": self.connectors.cli.enabled,
                "telegram": self.connectors.telegram.enabled,
            },
            "actions": {
                "allowlist": self.actions.allowlist,
                "require_confirm": self.actions.require_confirm,
            },
            "health": {
                "enabled": self.health.enabled,
                "host": self.health.host,
                "port": self.health.port,
            },
            "secrets": {
                "openai_api_key": "SET" if self.secrets.openai_api_key else "NOT SET",
                "openrouter_api_key": "SET" if self.secrets.openrouter_api_key else "NOT SET",
                "telegram_bot_token": "SET" if self.secrets.telegram_bot_token else "NOT SET",
                "gmail_user": self.secrets.gmail_user or "NOT SET",
                "notification_email": self.secrets.notification_email or "NOT SET",
                "sqlite_path": self.secrets.sqlite_path,
            },
        }


# ── Module-level singleton ─────────────────────────────────────────────────

_config: Optional[AppConfig] = None


def get_config(yaml_path: str = "config.yaml") -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig(yaml_path=yaml_path)
    return _config


def reset_config() -> None:
    """For use in tests only."""
    global _config
    _config = None
