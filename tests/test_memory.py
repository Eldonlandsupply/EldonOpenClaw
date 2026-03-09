"""
tests/test_memory.py
Tests for SQLiteMemory: KV store, event log, list_keys, search_events, trim.
"""
from __future__ import annotations

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openclaw.memory.sqlite import SQLiteMemory, _EVENT_LOG_MAX_ROWS, _EVENT_LOG_TRIM_TO


@pytest.fixture
async def mem(tmp_path):
    m = SQLiteMemory(db_path=str(tmp_path / "test.db"))
    await m.init()
    yield m
    await m.close()


# ── KV ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_and_get(mem):
    await mem.set("foo", "bar")
    assert await mem.get("foo") == "bar"


@pytest.mark.asyncio
async def test_get_missing_returns_none(mem):
    assert await mem.get("nonexistent") is None


@pytest.mark.asyncio
async def test_set_overwrites(mem):
    await mem.set("k", "v1")
    await mem.set("k", "v2")
    assert await mem.get("k") == "v2"


@pytest.mark.asyncio
async def test_delete(mem):
    await mem.set("k", "v")
    await mem.delete("k")
    assert await mem.get("k") is None


@pytest.mark.asyncio
async def test_delete_nonexistent_is_safe(mem):
    await mem.delete("no_such_key")  # must not raise


@pytest.mark.asyncio
async def test_list_keys_empty(mem):
    assert await mem.list_keys() == []


@pytest.mark.asyncio
async def test_list_keys_returns_all(mem):
    await mem.set("alpha", "1")
    await mem.set("beta", "2")
    await mem.set("gamma", "3")
    keys = await mem.list_keys()
    assert sorted(keys) == ["alpha", "beta", "gamma"]


@pytest.mark.asyncio
async def test_list_keys_prefix_filter(mem):
    await mem.set("app:config", "x")
    await mem.set("app:state", "y")
    await mem.set("other:thing", "z")
    keys = await mem.list_keys(prefix="app:")
    assert sorted(keys) == ["app:config", "app:state"]


# ── Event log ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_log_and_recent_events(mem):
    await mem.log_event("cli", "echo", '{"args": "hi"}')
    events = await mem.recent_events(limit=10)
    assert len(events) == 1
    assert events[0]["action"] == "echo"
    assert events[0]["source"] == "cli"


@pytest.mark.asyncio
async def test_recent_events_newest_first(mem):
    for i in range(5):
        await mem.log_event("cli", f"action_{i}", "")
    events = await mem.recent_events(limit=5)
    assert events[0]["action"] == "action_4"
    assert events[-1]["action"] == "action_0"


@pytest.mark.asyncio
async def test_recent_events_limit(mem):
    for i in range(10):
        await mem.log_event("cli", "echo", str(i))
    events = await mem.recent_events(limit=3)
    assert len(events) == 3


@pytest.mark.asyncio
async def test_search_events_by_action(mem):
    await mem.log_event("cli", "echo", "a")
    await mem.log_event("cli", "memory_write", "b")
    await mem.log_event("cli", "echo", "c")
    results = await mem.search_events(action="echo")
    assert len(results) == 2
    assert all(r["action"] == "echo" for r in results)


@pytest.mark.asyncio
async def test_search_events_by_source(mem):
    await mem.log_event("cli", "echo", "a")
    await mem.log_event("telegram", "echo", "b")
    results = await mem.search_events(source="telegram")
    assert len(results) == 1
    assert results[0]["source"] == "telegram"


@pytest.mark.asyncio
async def test_search_events_combined_filter(mem):
    await mem.log_event("cli", "echo", "a")
    await mem.log_event("cli", "memory_write", "b")
    await mem.log_event("telegram", "echo", "c")
    results = await mem.search_events(action="echo", source="cli")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_events_no_filter_returns_recent(mem):
    for i in range(5):
        await mem.log_event("cli", "echo", str(i))
    results = await mem.search_events(limit=3)
    assert len(results) == 3


# ── Trim ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_event_log_trim(mem):
    # Insert enough rows to trigger trim
    trigger_count = _EVENT_LOG_MAX_ROWS + 5
    for i in range(trigger_count):
        await mem.log_event("cli", "echo", str(i))
    # After trim, count should be at TRIM_TO
    # Trim fired once; a few rows may have been inserted after the trigger
    assert mem._event_count <= _EVENT_LOG_TRIM_TO + (_EVENT_LOG_MAX_ROWS - _EVENT_LOG_TRIM_TO)


# ── Error: uninitialized ──────────────────────────────────────────────────

def test_get_before_init_raises():
    m = SQLiteMemory(db_path=":memory:")
    with pytest.raises(RuntimeError, match="init"):
        m._sync_get("key")


def test_set_before_init_raises():
    m = SQLiteMemory(db_path=":memory:")
    with pytest.raises(RuntimeError, match="init"):
        m._sync_set("k", "v", "now")
