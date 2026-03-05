"""
tests/test_config.py
Tests for config loader and schema validation.
No network. No real API keys.
"""
from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

# Ensure project root is on path when running pytest from repo root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.loader import load_settings
from src.config.schema import Settings


# ── Helpers ────────────────────────────────────────────────────────────────

def write_config(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(content))
    return p


# ── Happy path ─────────────────────────────────────────────────────────────

def test_minimal_valid_config(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_CHAT_MODEL", "gpt-test")
    cfg = write_config(tmp_path, """
        llm:
          chat_model: ${OPENCLAW_CHAT_MODEL}
    """)
    s = load_settings(str(cfg))
    assert s.llm.chat_model == "gpt-test"
    assert s.llm.embedding_model is None
    assert s.memory.enabled is False
    assert s.connectors.cli is True


def test_memory_enabled_with_embed_model(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_CHAT_MODEL", "gpt-test")
    monkeypatch.setenv("OPENCLAW_EMBED_MODEL", "text-embedding-3-small")
    cfg = write_config(tmp_path, """
        llm:
          chat_model: ${OPENCLAW_CHAT_MODEL}
          embedding_model: ${OPENCLAW_EMBED_MODEL}
        memory:
          enabled: true
    """)
    s = load_settings(str(cfg))
    assert s.memory.enabled is True
    assert s.llm.embedding_model == "text-embedding-3-small"


def test_base_url_empty_becomes_none(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_CHAT_MODEL", "gpt-test")
    cfg = write_config(tmp_path, """
        llm:
          chat_model: ${OPENCLAW_CHAT_MODEL}
          base_url: ${OPENAI_BASE_URL:}
    """)
    s = load_settings(str(cfg))
    assert s.llm.base_url is None


def test_base_url_set(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_CHAT_MODEL", "gpt-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    cfg = write_config(tmp_path, """
        llm:
          chat_model: ${OPENCLAW_CHAT_MODEL}
          base_url: ${OPENAI_BASE_URL:}
    """)
    s = load_settings(str(cfg))
    assert s.llm.base_url == "http://localhost:11434/v1"


# ── Fail-fast: missing chat_model ──────────────────────────────────────────

def test_missing_chat_model_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENCLAW_CHAT_MODEL", raising=False)
    cfg = write_config(tmp_path, """
        llm:
          chat_model: ${OPENCLAW_CHAT_MODEL}
    """)
    with pytest.raises(RuntimeError, match="validation failed"):
        load_settings(str(cfg))


def test_placeholder_chat_model_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_CHAT_MODEL", "YOUR_CHAT_MODEL")
    cfg = write_config(tmp_path, """
        llm:
          chat_model: ${OPENCLAW_CHAT_MODEL}
    """)
    with pytest.raises(RuntimeError, match="placeholder"):
        load_settings(str(cfg))


# ── Fail-fast: memory enabled without embed model ──────────────────────────

def test_memory_enabled_without_embed_model_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_CHAT_MODEL", "gpt-test")
    monkeypatch.delenv("OPENCLAW_EMBED_MODEL", raising=False)
    cfg = write_config(tmp_path, """
        llm:
          chat_model: ${OPENCLAW_CHAT_MODEL}
          embedding_model: ${OPENCLAW_EMBED_MODEL:}
        memory:
          enabled: true
    """)
    with pytest.raises(RuntimeError, match="embedding_model"):
        load_settings(str(cfg))


# ── Fail-fast: bad log level ───────────────────────────────────────────────

def test_invalid_log_level_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_CHAT_MODEL", "gpt-test")
    cfg = write_config(tmp_path, """
        app:
          log_level: verbose
        llm:
          chat_model: ${OPENCLAW_CHAT_MODEL}
    """)
    with pytest.raises(RuntimeError, match="validation failed"):
        load_settings(str(cfg))


# ── Fail-fast: missing config file ────────────────────────────────────────

def test_missing_config_file_raises():
    with pytest.raises(RuntimeError, match="not found"):
        load_settings("/nonexistent/config.yaml")


# ── Connector flags parse correctly ───────────────────────────────────────

def test_connectors_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_CHAT_MODEL", "gpt-test")
    monkeypatch.setenv("OPENCLAW_CONNECTOR_TELEGRAM", "true")
    cfg = write_config(tmp_path, """
        llm:
          chat_model: ${OPENCLAW_CHAT_MODEL}
        connectors:
          cli: ${OPENCLAW_CONNECTOR_CLI:true}
          telegram: ${OPENCLAW_CONNECTOR_TELEGRAM:false}
          voice: ${OPENCLAW_CONNECTOR_VOICE:false}
    """)
    s = load_settings(str(cfg))
    assert s.connectors.telegram is True
    assert s.connectors.voice is False
