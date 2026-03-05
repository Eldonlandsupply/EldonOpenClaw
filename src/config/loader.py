"""
src/config/loader.py
Loads config.yaml, expands ${VAR:default} placeholders from environment,
validates via Pydantic schema, and enforces cross-field gates.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from .schema import Settings

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _expand_value(value: str) -> str:
    """Expand ${VAR} or ${VAR:default} in a single string."""
    def replace(match: re.Match) -> str:
        inner = match.group(1)
        if ":" in inner:
            var, default = inner.split(":", 1)
            return os.getenv(var.strip(), default)
        return os.getenv(inner.strip(), "")

    return _ENV_VAR_RE.sub(replace, value)


def _walk_expand(obj: Any) -> Any:
    """Recursively expand env-var placeholders in a parsed YAML structure."""
    if isinstance(obj, dict):
        return {k: _walk_expand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_expand(v) for v in obj]
    if isinstance(obj, str):
        return _expand_value(obj)
    return obj


def _coerce_bools(obj: Any) -> Any:
    """YAML parses 'true'/'false' strings (from env expansion) as strings; fix that."""
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


def load_settings(config_path: str = "config.yaml") -> Settings:
    """
    Load, expand, validate, and return Settings.
    Raises RuntimeError with actionable message on any misconfiguration.
    """
    p = Path(config_path)
    if not p.exists():
        raise RuntimeError(
            f"Config file not found: {p.resolve()}\n"
            "Fix: copy .env.example → .env, then ensure config.yaml exists."
        )

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    expanded = _walk_expand(raw)
    coerced = _coerce_bools(expanded)

    try:
        settings = Settings.model_validate(coerced)
    except Exception as exc:
        raise RuntimeError(
            f"Configuration validation failed:\n{exc}\n\n"
            "Check your .env file against .env.example."
        ) from exc

    return settings
