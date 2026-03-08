"""
Centralized config: secrets from .env, non-secrets from config.yaml.
Fails loudly if misconfigured. Prints a redacted summary on boot.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── Env-var expansion ──────────────────────────────────────────────────────
# Supports ${VAR} and ${VAR:default} tokens in config.yaml values.

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _expand_value(value: str) -> str:
    def replace(match: re.Match) -> str:
        inner = match.group(1)
        if ":" in inner:
            var, default = inner.split(":", 1)
            return os.getenv(var.strip(), default)
        return os.getenv(inner.strip(), "")
    return _ENV_VAR_RE.sub(replace, value)


def _walk_expand(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _walk_expand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_expand(v) for v in obj]
    if isinstance(obj, str):
        return _expand_value(obj)
    return obj


def _coerce_bools(obj: Any) -> Any:
    """YAML env expansion produces strings; convert 'true'/'false' to bool."""
    if isinstance(obj, dict):
        return {k: _coerce_bools(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_bools(v) for v in obj]
    if isinstance(obj, str):
        if obj.lower() == "true":
            return True
        if obj.lower() == "false":
            return False
    return obj


# ── Pydantic models for each YAML section ──────────────────────────────────

class LLMConfig:
    provider: str = "none"
    chat_model: str = "gpt-4o-mini"
    embedding_model: Optional[str] = None

    def __init__(self, **data):
        for k, v in data.items():
            setattr(self, k, v)


class RuntimeConfig:
    tick_seconds: int = 10
    log_level: str = "INFO"
    data_dir: str = "./data"
    dry_run: bool = True

    def __init__(self, **data):
        for k, v in data.items():
            setattr(self, k, v)


class ConnectorCliConfig:
    enabled: bool = True

    def __init__(self, **data):
        for k, v in data.items():
            setattr(self, k, v)


class ConnectorTelegramConfig:
    enabled: bool = False

    def __init__(self, **data):
        for k, v in data.items():
            setattr(self, k, v)


class ConnectorsConfig:
    cli: ConnectorCliConfig = ConnectorCliConfig()
    telegram: ConnectorTelegramConfig = ConnectorTelegramConfig()

    def __init__(self, **data):
        if "cli" in data:
            self.cli = ConnectorCliConfig(**(data["cli"] or {}))
        if "telegram" in data:
            self.telegram = ConnectorTelegramConfig(**(data["telegram"] or {}))


class ActionsConfig:
    allowlist: list[str] = ["echo"]
    require_confirm: bool = False

    def __init__(self, **data):
        for k, v in data.items():
            setattr(self, k, v)


class HealthConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8080

    def __init__(self, **data):
        for k, v in data.items():
            setattr(self, k, v)


# ── Secrets from .env ──────────────────────────────────────────────────────

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
    telegram_bot_token: Optional[str] = None
    telegram_allowed_chat_ids: Optional[str] = None  # raw comma-separated string
    sqlite_path: str = "./data/openclaw.db"

    @property
    def allowed_chat_ids(self) -> list[int]:
        if not self.telegram_allowed_chat_ids:
            return []
        return [int(x.strip()) for x in self.telegram_allowed_chat_ids.split(",") if x.strip()]


# ── Merged app config ──────────────────────────────────────────────────────

class AppConfig:
    """Single object holding all config. Created once at startup."""

    def __init__(self, yaml_path: str = "config.yaml"):
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
                f"       cp config.yaml.example config.yaml  # then edit it",
                file=sys.stderr,
            )
            sys.exit(1)

        with p.open() as f:
            raw = yaml.safe_load(f) or {}

        # Expand ${VAR} / ${VAR:default} tokens, then coerce string bools
        raw = _coerce_bools(_walk_expand(raw))

        self.llm = LLMConfig(**(raw.get("llm") or {}))
        self.runtime = RuntimeConfig(**(raw.get("runtime") or {}))
        self.connectors = ConnectorsConfig(**(raw.get("connectors") or {}))
        self.actions = ActionsConfig(**(raw.get("actions") or {}))
        self.health = HealthConfig(**(raw.get("health") or {}))

    def _validate(self) -> None:
        valid_providers = {"openai", "anthropic", "none"}
        if self.llm.provider not in valid_providers:
            self._fatal(f"llm.provider must be one of {valid_providers}, got: {self.llm.provider!r}")

        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if self.runtime.log_level.upper() not in valid_levels:
            self._fatal(f"runtime.log_level must be one of {valid_levels}")

        if self.llm.provider == "openai" and not self.secrets.openai_api_key:
            self._fatal("llm.provider=openai but OPENAI_API_KEY is not set in .env")

        if self.connectors.telegram.enabled and not self.secrets.telegram_bot_token:
            self._fatal("connectors.telegram.enabled=true but TELEGRAM_BOT_TOKEN is not set in .env")

        Path(self.runtime.data_dir).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _fatal(msg: str) -> None:
        print(f"FATAL CONFIG ERROR: {msg}", file=sys.stderr)
        sys.exit(1)

    def summary(self) -> dict:
        """Redacted summary safe to log at startup."""
        return {
            "llm": {"provider": self.llm.provider, "chat_model": self.llm.chat_model},
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
                "telegram_bot_token": "SET" if self.secrets.telegram_bot_token else "NOT SET",
                "sqlite_path": self.secrets.sqlite_path,
            },
        }


# ── Module-level singleton ─────────────────────────────────────────────────
# Callers: from openclaw.config import get_config
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
