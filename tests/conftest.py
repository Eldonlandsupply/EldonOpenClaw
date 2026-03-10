"""
Pytest configuration and shared fixtures.

Two sources read .env during tests and must both be blocked:

1. load_dotenv() inside AppConfig._load_yaml() — expands ${VAR} tokens.
   If allowed to run, it restores env vars monkeypatch deleted.

2. pydantic-settings Secrets class — env_file is evaluated at class
   definition time (module import), so patching _find_env_file() at test
   time is too late. Must patch Secrets.model_config directly to set
   env_file=None, preventing file reads during tests.

Fix: patch both at the session level.
Tests manage env vars explicitly via monkeypatch.setenv/delenv.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic_settings import SettingsConfigDict


@pytest.fixture(autouse=True)
def _isolate_env():
    """Block all .env file reads during tests.

    Patches:
    - openclaw.config.load_dotenv          — blocks os.environ expansion
    - openclaw.config.Secrets.model_config — removes env_file so
      pydantic-settings never reads the .env file on disk

    Without both patches a real .env file on the host (e.g. on a deployed Pi)
    injects values that monkeypatch has removed, breaking key-required tests.
    """
    import openclaw.config as _cfg
    no_file_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
    )
    with patch("openclaw.config.load_dotenv"), \
         patch.object(_cfg.Secrets, "model_config", no_file_config):
        yield
