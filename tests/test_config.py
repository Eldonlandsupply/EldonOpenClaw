"""
Tests for config loading. No network calls, no real LLM keys required.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from openclaw.config import AppConfig, reset_config


@pytest.fixture(autouse=True)
def clear_singleton():
    reset_config()
    yield
    reset_config()


def write_yaml(tmp_path: Path, content: str) -> str:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(content))
    return str(p)


def write_env(tmp_path: Path, content: str = "") -> None:
    p = tmp_path / ".env"
    p.write_text(content)


# ── Happy path ────────────────────────────────────────────────────────────

def test_minimal_config_loads(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_env(tmp_path)
    yaml = write_yaml(
        tmp_path,
        """
        llm:
          provider: "none"
        runtime:
          tick_seconds: 5
          log_level: "DEBUG"
          data_dir: "./data"
          dry_run: true
        connectors:
          cli:
            enabled: true
          telegram:
            enabled: false
        actions:
          allowlist: ["echo"]
          require_confirm: false
        health:
          enabled: false
          host: "127.0.0.1"
          port: 8080
        """,
    )
    cfg = AppConfig(yaml_path=yaml)
    assert cfg.llm.provider == "none"
    assert cfg.runtime.tick_seconds == 5
    assert cfg.runtime.dry_run is True
    assert cfg.connectors.cli.enabled is True
    assert cfg.connectors.telegram.enabled is False
    assert "echo" in cfg.actions.allowlist
    assert cfg.health.enabled is False


def test_summary_redacts_secrets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_env(tmp_path, "OPENAI_API_KEY=sk-super-secret")
    yaml = write_yaml(
        tmp_path,
        """
        llm:
          provider: "none"
        runtime:
          tick_seconds: 10
          log_level: "INFO"
          data_dir: "./data"
          dry_run: true
        connectors:
          cli:
            enabled: true
          telegram:
            enabled: false
        actions:
          allowlist: ["echo"]
          require_confirm: false
        health:
          enabled: false
          host: "127.0.0.1"
          port: 8080
        """,
    )
    cfg = AppConfig(yaml_path=yaml)
    summary = cfg.summary()
    assert summary["secrets"]["openai_api_key"] == "SET"
    assert "sk-super-secret" not in str(summary)


def test_missing_yaml_exits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        AppConfig(yaml_path=str(tmp_path / "nonexistent.yaml"))


def test_invalid_provider_exits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_env(tmp_path)
    yaml = write_yaml(
        tmp_path,
        """
        llm:
          provider: "banana"
        runtime:
          tick_seconds: 10
          log_level: "INFO"
          data_dir: "./data"
          dry_run: true
        connectors:
          cli:
            enabled: true
          telegram:
            enabled: false
        actions:
          allowlist: ["echo"]
          require_confirm: false
        health:
          enabled: false
          host: "127.0.0.1"
          port: 8080
        """,
    )
    with pytest.raises(SystemExit):
        AppConfig(yaml_path=yaml)


def test_openai_provider_requires_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_env(tmp_path, "OPENAI_API_KEY=")  # empty
    yaml = write_yaml(
        tmp_path,
        """
        llm:
          provider: "openai"
        runtime:
          tick_seconds: 10
          log_level: "INFO"
          data_dir: "./data"
          dry_run: true
        connectors:
          cli:
            enabled: true
          telegram:
            enabled: false
        actions:
          allowlist: ["echo"]
          require_confirm: false
        health:
          enabled: false
          host: "127.0.0.1"
          port: 8080
        """,
    )
    with pytest.raises(SystemExit):
        AppConfig(yaml_path=yaml)
