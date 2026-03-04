"""
Tests for action gating: allowlist enforcement + dry_run behavior.
Zero network calls.
"""

from __future__ import annotations

import pytest

from openclaw.actions.registry import ActionRegistry


@pytest.fixture
def registry_live():
    return ActionRegistry(allowlist=["echo", "memory_write", "memory_read"], dry_run=False)


@pytest.fixture
def registry_dry():
    return ActionRegistry(allowlist=["echo", "memory_write", "memory_read"], dry_run=True)


# ── Allowlist ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_allowed_action_succeeds(registry_live):
    result = await registry_live.dispatch("echo", "hello world")
    assert result.success is True
    assert "hello world" in str(result.output)


@pytest.mark.asyncio
async def test_blocked_action_fails(registry_live):
    result = await registry_live.dispatch("rm_rf", "/")
    assert result.success is False
    assert "allowlist" in result.error.lower()


@pytest.mark.asyncio
async def test_unknown_action_fails(registry_live):
    # Action is in allowlist but not registered
    r = ActionRegistry(allowlist=["ghost_action"], dry_run=False)
    result = await r.dispatch("ghost_action")
    assert result.success is False
    assert "not registered" in result.error


@pytest.mark.asyncio
async def test_empty_allowlist_blocks_everything(registry_live):
    r = ActionRegistry(allowlist=[], dry_run=False)
    result = await r.dispatch("echo", "test")
    assert result.success is False


# ── Dry run ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dry_run_returns_success_but_marks_dry(registry_dry):
    result = await registry_dry.dispatch("echo", "test")
    assert result.success is True
    assert "dry_run" in str(result.output).lower()


@pytest.mark.asyncio
async def test_dry_run_does_not_block(registry_dry):
    result = await registry_dry.dispatch("memory_write", "key=val")
    assert result.success is True


# ── is_allowed helper ─────────────────────────────────────────────────────

def test_is_allowed(registry_live):
    assert registry_live.is_allowed("echo") is True
    assert registry_live.is_allowed("sudo_rm") is False
