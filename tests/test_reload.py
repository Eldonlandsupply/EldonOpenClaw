"""
tests/test_reload.py
Tests for the SIGHUP reload loop in cli_entry / run().
Verifies that:
  - run() returns True on reload signal
  - run() returns False on shutdown signal
  - _init_events() resets events between cycles (no stale state)
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


def _make_minimal_cfg():
    """Return a minimal AppConfig mock that satisfies run()."""
    cfg = MagicMock()
    cfg.runtime.log_level = "INFO"
    cfg.runtime.dry_run = True
    cfg.runtime.tick_seconds = 60
    cfg.runtime.data_dir = "/tmp/openclaw_test_data"
    cfg.health.enabled = False
    cfg.connectors.cli.enabled = False
    cfg.connectors.telegram.enabled = False
    cfg.secrets.gmail_user = None
    cfg.secrets.gmail_app_password = None
    cfg.secrets.azure_tenant_id = None
    cfg.secrets.attio_api_key = None
    cfg.secrets.sqlite_path = "/tmp/openclaw_test.db"
    cfg.actions.allowlist = ["echo"]
    cfg.actions.require_confirm = False
    cfg.summary.return_value = {}
    return cfg


@pytest.mark.asyncio
async def test_init_events_resets_shutdown():
    """_init_events() must produce fresh, unset events each call."""
    from src.openclaw.main import _init_events, _shutdown, _reload
    # Manually set both events
    import src.openclaw.main as m
    m._shutdown = asyncio.Event()
    m._reload = asyncio.Event()
    m._shutdown.set()
    m._reload.set()
    # Now reset
    _init_events()
    # After reset, both should be clear
    assert not m._shutdown.is_set(), "_shutdown must be clear after _init_events()"
    assert not m._reload.is_set(), "_reload must be clear after _init_events()"


@pytest.mark.asyncio
async def test_run_returns_false_on_shutdown():
    """run() must return False when SIGTERM/SIGINT fires (not SIGHUP)."""
    import src.openclaw.main as m

    cfg = _make_minimal_cfg()
    memory_mock = AsyncMock()
    memory_mock.init = AsyncMock()
    memory_mock.close = AsyncMock()
    chat_mock = AsyncMock()
    chat_mock.close = AsyncMock()

    with patch("src.openclaw.main.get_config", return_value=cfg), \
         patch("src.openclaw.main.configure_logging"), \
         patch("src.openclaw.main.SQLiteMemory", return_value=memory_mock), \
         patch("src.openclaw.main.ChatClient", return_value=chat_mock), \
         patch("src.openclaw.main.ActionRegistry"):

        # Schedule shutdown signal after a short delay
        async def fire_shutdown():
            await asyncio.sleep(0.05)
            m._shutdown.set()

        asyncio.create_task(fire_shutdown())
        result = await m.run()

    assert result is False, "run() must return False on clean shutdown"


@pytest.mark.asyncio
async def test_run_returns_true_on_reload():
    """run() must return True when SIGHUP fires without SIGTERM."""
    import src.openclaw.main as m

    cfg = _make_minimal_cfg()
    memory_mock = AsyncMock()
    memory_mock.init = AsyncMock()
    memory_mock.close = AsyncMock()
    chat_mock = AsyncMock()
    chat_mock.close = AsyncMock()

    with patch("src.openclaw.main.get_config", return_value=cfg), \
         patch("src.openclaw.main.configure_logging"), \
         patch("src.openclaw.main.SQLiteMemory", return_value=memory_mock), \
         patch("src.openclaw.main.ChatClient", return_value=chat_mock), \
         patch("src.openclaw.main.ActionRegistry"):

        async def fire_reload():
            await asyncio.sleep(0.05)
            m._reload.set()

        asyncio.create_task(fire_reload())
        result = await m.run()

    assert result is True, "run() must return True on reload (SIGHUP)"
