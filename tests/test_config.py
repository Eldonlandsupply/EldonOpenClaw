"""
tests/test_config.py
Tests for the canonical runtime config system (src/openclaw/config.AppConfig).

This is the single authoritative config test suite. The previous version
tested src/config/schema.py (Settings), a separate system that is now
deprecated. These tests cover the config the live process actually uses.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openclaw.config import AppConfig, reset_config


def write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(content))
    return p


@pytest.fixture(autouse=True)
def clear_config():
    reset_config()
    yield
    reset_config()


# ── Happy path ─────────────────────────────────────────────────────────────

def test_minimal_valid_config(tmp_path):
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: gpt-test
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.llm.chat_model == "gpt-test"
    assert cfg.llm.provider == "none"
    assert cfg.runtime.dry_run is True
    assert cfg.connectors.cli.enabled is True
    assert cfg.connectors.telegram.enabled is False


def test_env_var_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_MODEL", "gpt-expanded")
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: ${TEST_MODEL:fallback}
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.llm.chat_model == "gpt-expanded"


def test_env_var_default_used_when_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("TEST_MODEL", raising=False)
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: ${TEST_MODEL:fallback-model}
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.llm.chat_model == "fallback-model"


def test_dry_run_false(tmp_path):
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: gpt-test
        runtime:
          dry_run: false
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.runtime.dry_run is False


def test_dry_run_defaults_true(tmp_path):
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: gpt-test
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.runtime.dry_run is True


def test_health_defaults(tmp_path):
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: gpt-test
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.health.enabled is True
    assert cfg.health.port == 8080


def test_connector_bool_shorthand(tmp_path):
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: gpt-test
        connectors:
          cli: true
          telegram: false
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.connectors.cli.enabled is True
    assert cfg.connectors.telegram.enabled is False


def test_connector_telegram_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: gpt-test
        connectors:
          telegram: true
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.connectors.telegram.enabled is True


def test_summary_redacts_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret-key")
    p = write_yaml(tmp_path, """
        llm:
          provider: openrouter
          chat_model: test-model
    """)
    cfg = AppConfig(yaml_path=str(p))
    summary = cfg.summary()
    assert summary["secrets"]["openrouter_api_key"] == "SET"
    assert "sk-secret-key" not in str(summary)


def test_actions_require_confirm_both_spellings(tmp_path):
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: gpt-test
        actions:
          require_confirmation: true
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.actions.require_confirm is True

    reset_config()
    sub = tmp_path / "b"
    sub.mkdir()
    p2 = write_yaml(sub, """
        llm:
          provider: none
          chat_model: gpt-test
        actions:
          require_confirm: false
    """)
    cfg2 = AppConfig(yaml_path=str(p2))
    assert cfg2.actions.require_confirm is False


# ── Fail-fast ──────────────────────────────────────────────────────────────

def test_missing_config_file_exits():
    with pytest.raises(SystemExit):
        AppConfig(yaml_path="/nonexistent/config.yaml")


def test_invalid_provider_exits(tmp_path):
    p = write_yaml(tmp_path, """
        llm:
          provider: fakeprovider
          chat_model: gpt-test
    """)
    with pytest.raises(SystemExit):
        AppConfig(yaml_path=str(p))


def test_invalid_log_level_exits(tmp_path):
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: gpt-test
        runtime:
          log_level: verbose
    """)
    with pytest.raises(SystemExit):
        AppConfig(yaml_path=str(p))


def test_openrouter_without_key_exits(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    p = write_yaml(tmp_path, """
        llm:
          provider: openrouter
          chat_model: openai/gpt-4o-mini
    """)
    with pytest.raises(SystemExit):
        AppConfig(yaml_path=str(p))


def test_telegram_enabled_without_token_exits(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: gpt-test
        connectors:
          telegram: true
    """)
    with pytest.raises(SystemExit):
        AppConfig(yaml_path=str(p))
