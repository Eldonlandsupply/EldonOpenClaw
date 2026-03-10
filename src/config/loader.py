from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .schema import Settings


def _expand_env_token(token: str) -> str:
    """
    Supports:
      ${VAR}
      ${VAR:default}
    """
    inner = token[2:-1]  # strip ${ and }
    if ":" in inner:
        var, default = inner.split(":", 1)
        return os.getenv(var, default)
    return os.getenv(inner, "")


def _walk_expand(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _walk_expand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_expand(v) for v in obj]
    if isinstance(obj, str):
        s = obj.strip()
        if s.startswith("${") and s.endswith("}"):
            return _expand_env_token(s)
        return obj
    return obj


def load_settings(config_path: str = "config.yaml") -> Settings:
    p = Path(config_path)
    if not p.exists():
        raise RuntimeError(
            f"Config file not found: {config_path}. "
            f"Create it or copy from a template. Expected at: {p.resolve()}"
        )

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    expanded = _walk_expand(raw)

    try:
        return Settings.model_validate(expanded)
    except Exception as e:
        raise RuntimeError(f"Config validation failed: {e}") from e
