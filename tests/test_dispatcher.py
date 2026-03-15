"""
Tests for the Dispatcher class in main.py.
Verifies routing, memory built-ins, /reset, and LLM fallback.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_dispatcher():
    """Build a Dispatcher with mocked dependencies."""
    from src.openclaw.main import Dispatcher
    registry    = MagicMock()
    memory      = MagicMock()
    chat_client = MagicMock()

    # Default: nothing is allowed
    registry.is_allowed.return_value = False

    memory.get        = AsyncMock(return_value=None)
    memory.list_keys  = AsyncMock(return_value=[])
    memory.set        = AsyncMock()
    memory.log_event  = AsyncMock()

    chat_client.chat  = AsyncMock(return_value="LLM reply")
    chat_client.reset = MagicMock()

    return Dispatcher(registry, memory, chat_client), registry, memory, chat_client


@pytest.mark.asyncio
async def test_reset_command_clears_history():
    d, _, _, chat = make_dispatcher()
    reply = await d.handle("cli", None, "/reset")
    assert "cleared" in reply.lower()
    chat.reset.assert_called_once()


@pytest.mark.asyncio
async def test_memory_read_allowed():
    d, registry, memory, _ = make_dispatcher()
    registry.is_allowed.side_effect = lambda name: name == "memory_read"
    memory.get = AsyncMock(return_value="stored_val")
    reply = await d.handle("cli", None, "memory_read mykey")
    assert reply == "stored_val"


@pytest.mark.asyncio
async def test_memory_read_no_key_lists_all():
    d, registry, memory, _ = make_dispatcher()
    registry.is_allowed.side_effect = lambda name: name == "memory_read"
    memory.list_keys = AsyncMock(return_value=["k1", "k2"])
    reply = await d.handle("cli", None, "memory_read")
    assert "k1" in reply and "k2" in reply


@pytest.mark.asyncio
async def test_memory_write_allowed():
    d, registry, memory, _ = make_dispatcher()
    registry.is_allowed.side_effect = lambda name: name == "memory_write"
    reply = await d.handle("cli", None, "memory_write foo=bar")
    memory.set.assert_awaited_once_with("foo", "bar")
    assert "stored" in reply.lower()


@pytest.mark.asyncio
async def test_memory_write_bad_syntax():
    d, registry, memory, _ = make_dispatcher()
    registry.is_allowed.side_effect = lambda name: name == "memory_write"
    reply = await d.handle("cli", None, "memory_write noequalssign")
    assert "ERROR" in reply


@pytest.mark.asyncio
async def test_action_dispatched():
    from src.openclaw.actions.base import ActionResult
    d, registry, _, _ = make_dispatcher()
    registry.is_allowed.side_effect = lambda name: name == "echo"
    registry.dispatch = AsyncMock(return_value=ActionResult(success=True, output="echoed"))
    reply = await d.handle("cli", None, "echo hello")
    assert reply == "echoed"


@pytest.mark.asyncio
async def test_action_failed():
    from src.openclaw.actions.base import ActionResult
    d, registry, _, _ = make_dispatcher()
    registry.is_allowed.side_effect = lambda name: name == "echo"
    registry.dispatch = AsyncMock(return_value=ActionResult(success=False, error="oops"))
    reply = await d.handle("cli", None, "echo hello")
    assert "ERROR: oops" == reply


@pytest.mark.asyncio
async def test_llm_fallback():
    d, registry, _, chat = make_dispatcher()
    registry.is_allowed.return_value = False
    reply = await d.handle("cli", None, "what is the weather?")
    assert reply == "LLM reply"
    chat.chat.assert_awaited_once_with("what is the weather?")
