"""
tests/test_runtime_config.py
Tests for the runtime config system (src/openclaw/config.py).
No network. No real API keys.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openclaw.config import AppConfig, reset_config, _expand


# ── _expand unit tests ────────────────────────────────────────────────────

def test_expand_default_when_var_missing(monkeypatch):
    monkeypatch.delenv("MISSING_VAR", raising=False)
    assert _expand("${MISSING_VAR:fallback}") == "fallback"


def test_expand_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("MY_VAR", "real_value")
    assert _expand("${MY_VAR:fallback}") == "real_value"


def test_expand_no_default_missing_returns_empty(monkeypatch):
    monkeypatch.delenv("EMPTY_VAR", raising=False)
    assert _expand("${EMPTY_VAR}") == ""


def test_expand_non_token_passthrough():
    assert _expand("plain string") == "plain string"
    assert _expand(42) == 42
    assert _expand(True) is True


def test_expand_recursive_dict(monkeypatch):
    monkeypatch.setenv("KEY_A", "hello")
    result = _expand({"a": "${KEY_A:default}", "b": "literal"})
    assert result == {"a": "hello", "b": "literal"}


def test_expand_recursive_list(monkeypatch):
    monkeypatch.setenv("ITEM", "x")
    result = _expand(["${ITEM:y}", "static"])
    assert result == ["x", "static"]


# ── AppConfig happy path ──────────────────────────────────────────────────

def write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(content))
    return p


@pytest.fixture(autouse=True)
def clear_config():
    reset_config()
    yield
    reset_config()


def test_minimal_config_none_provider(tmp_path):
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: test-model
        runtime:
          dry_run: false
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.llm.provider == "none"
    assert cfg.llm.chat_model == "test-model"
    assert cfg.runtime.dry_run is False


def test_openrouter_provider_requires_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    p = write_yaml(tmp_path, """
        llm:
          provider: openrouter
          chat_model: openai/gpt-4o-mini
    """)
    with pytest.raises(SystemExit):
        AppConfig(yaml_path=str(p))


def test_openrouter_provider_with_key(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    p = write_yaml(tmp_path, """
        llm:
          provider: openrouter
          chat_model: openai/gpt-4o-mini
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.llm.provider == "openrouter"
    assert cfg.secrets.openrouter_api_key == "sk-or-test"


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


def test_dry_run_string_false(tmp_path):
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


def test_connector_cli_enabled_default(tmp_path):
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: gpt-test
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.connectors.cli.enabled is True
    assert cfg.connectors.telegram.enabled is False


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


def test_health_defaults(tmp_path):
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: gpt-test
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.health.enabled is True
    assert cfg.health.port == 8080


def test_env_var_expansion_in_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_MODEL", "my-model")
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: ${TEST_MODEL:fallback}
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.llm.chat_model == "my-model"


def test_env_var_default_used_when_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("TEST_MODEL", raising=False)
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: ${TEST_MODEL:fallback-model}
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.llm.chat_model == "fallback-model"


def test_missing_config_file_exits():
    with pytest.raises(SystemExit):
        AppConfig(yaml_path="/nonexistent/path/config.yaml")


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
    # Old spelling: require_confirmation
    p = write_yaml(tmp_path, """
        llm:
          provider: none
          chat_model: gpt-test
        actions:
          require_confirmation: true
    """)
    cfg = AppConfig(yaml_path=str(p))
    assert cfg.actions.require_confirm is True

    # New spelling: require_confirm
    reset_config()
    subdir = tmp_path / "b"
    subdir.mkdir(exist_ok=True)
    p2 = write_yaml(subdir, """
        llm:
          provider: none
          chat_model: gpt-test
        actions:
          require_confirm: false
    """)
    cfg2 = AppConfig(yaml_path=str(p2))
    assert cfg2.actions.require_confirm is False
