"""
Pytest configuration and shared fixtures.

Key concern: load_dotenv() is called inside AppConfig._load_yaml() to support
${VAR} expansion from .env files at runtime. During tests, env vars are managed
explicitly via monkeypatch. If load_dotenv() runs inside a test it will restore
vars that monkeypatch deleted, breaking test isolation.

Fix: patch load_dotenv to a no-op for the entire test session.
Tests that need specific env vars use monkeypatch.setenv() directly.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _no_load_dotenv():
    """Prevent load_dotenv() from polluting os.environ during tests.

    Without this, AppConfig._load_yaml() calls load_dotenv(override=False)
    which re-reads the local .env file and restores env vars that monkeypatch
    has deleted, causing spurious test failures.
    """
    with patch("openclaw.config.load_dotenv"):
        yield
