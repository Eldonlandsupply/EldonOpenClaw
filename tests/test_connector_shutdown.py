"""
tests/test_connector_shutdown.py
Verifies that connector stop() properly cancels the background poll task.

Without this: stop() only sets _running=False and closes the session.
The orphaned poll task would continue until the next network timeout,
then crash with "session is closed" errors.

Tests added 2026-03-17 as regression coverage for the fix in:
  src/openclaw/connectors/telegram.py
  src/openclaw/connectors/gmail.py
  src/openclaw/connectors/outlook.py
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── TelegramConnector ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_telegram_stop_cancels_poll_task():
    """stop() must cancel the poll task so it does not outlive the session."""
    from src.openclaw.connectors.telegram import TelegramConnector

    with patch("src.openclaw.connectors.telegram.aiohttp.ClientSession") as MockSession:
        mock_session = AsyncMock()
        mock_session.closed = False
        MockSession.return_value = mock_session

        connector = TelegramConnector(token="fake", allowed_chat_ids=[])
        await connector.start()

        assert connector._poll_task is not None, "poll_task must be stored on start()"
        assert not connector._poll_task.done()

        await connector.stop()

        assert connector._poll_task is None, "poll_task must be cleared on stop()"
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_telegram_stop_idempotent():
    """Calling stop() twice must not raise."""
    from src.openclaw.connectors.telegram import TelegramConnector

    with patch("src.openclaw.connectors.telegram.aiohttp.ClientSession") as MockSession:
        mock_session = AsyncMock()
        mock_session.closed = False
        MockSession.return_value = mock_session

        connector = TelegramConnector(token="fake", allowed_chat_ids=[])
        await connector.start()
        await connector.stop()
        await connector.stop()  # must not raise


# ── OutlookConnector ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_outlook_stop_cancels_poll_task():
    """stop() must cancel the poll task so it does not outlive the session."""
    from src.openclaw.connectors.outlook import OutlookConnector

    with patch("src.openclaw.connectors.outlook.aiohttp.ClientSession") as MockSession:
        mock_session = AsyncMock()
        mock_session.closed = False
        MockSession.return_value = mock_session

        connector = OutlookConnector(
            tenant_id="t", client_id="c", client_secret="s", user="u@example.com"
        )
        await connector.start()

        assert connector._poll_task is not None
        assert not connector._poll_task.done()

        await connector.stop()

        assert connector._poll_task is None
        mock_session.close.assert_awaited_once()


# ── health reset_health() ─────────────────────────────────────────────────

def test_reset_health_clears_degraded_state():
    """reset_health() must clear _degraded so a reload cycle starts clean."""
    import src.openclaw.health as h

    # Simulate degraded state from a previous run
    h._degraded = True
    h._degraded_reason = "test reason"
    h._last_tick = "2026-01-01T00:00:00+00:00"
    h._connector_status = {"telegram": "degraded"}

    h.reset_health()

    assert h._degraded is False
    assert h._degraded_reason == ""
    assert h._last_tick is None
    assert h._connector_status == {}


def test_reset_health_does_not_reset_start_time():
    """Uptime (_start_time) is cumulative across reloads — must not be reset."""
    import src.openclaw.health as h

    original_start = h._start_time
    h.reset_health()
    assert h._start_time == original_start
