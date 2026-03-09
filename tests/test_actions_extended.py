"""
tests/test_actions_extended.py
Extended action tests: HelpAction, list_registered, list_allowed, custom register.
"""
from __future__ import annotations

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openclaw.actions.registry import ActionRegistry, HelpAction
from openclaw.actions.base import ActionResult, BaseAction


class UppercaseAction(BaseAction):
    name = "uppercase"

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        if dry_run:
            return ActionResult(success=True, output=f"[dry_run] uppercase: {args}")
        return ActionResult(success=True, output=args.upper())


@pytest.fixture
def registry():
    return ActionRegistry(allowlist=["echo", "memory_write", "memory_read"], dry_run=False)


def test_help_always_registered(registry):
    assert "help" in registry.list_registered()


def test_help_always_allowed(registry):
    assert "help" in registry.list_allowed()


@pytest.mark.asyncio
async def test_help_returns_allowed_actions(registry):
    result = await registry.dispatch("help")
    assert result.success
    assert "echo" in result.output
    assert "memory_write" in result.output


@pytest.mark.asyncio
async def test_help_empty_allowlist():
    r = ActionRegistry(allowlist=[], dry_run=False)
    result = await r.dispatch("help")
    assert result.success
    # help itself is still allowed
    assert "help" in result.output


def test_list_registered_includes_builtins(registry):
    registered = registry.list_registered()
    assert "echo" in registered
    assert "memory_write" in registered
    assert "memory_read" in registered
    assert "help" in registered


def test_list_allowed_returns_sorted(registry):
    allowed = registry.list_allowed()
    assert allowed == sorted(allowed)


def test_register_custom_action(registry):
    registry.register(UppercaseAction())
    assert "uppercase" in registry.list_registered()


@pytest.mark.asyncio
async def test_custom_action_blocked_if_not_in_allowlist(registry):
    registry.register(UppercaseAction())
    result = await registry.dispatch("uppercase", "hello")
    assert result.success is False
    assert "allowlist" in result.error


@pytest.mark.asyncio
async def test_custom_action_runs_when_allowed():
    r = ActionRegistry(allowlist=["uppercase"], dry_run=False)
    r.register(UppercaseAction())
    result = await r.dispatch("uppercase", "hello world")
    assert result.success
    assert result.output == "HELLO WORLD"


@pytest.mark.asyncio
async def test_custom_action_dry_run():
    r = ActionRegistry(allowlist=["uppercase"], dry_run=True)
    r.register(UppercaseAction())
    result = await r.dispatch("uppercase", "hello")
    assert result.success
    assert "dry_run" in result.output.lower()


@pytest.mark.asyncio
async def test_action_exception_returns_failure():
    class BrokenAction(BaseAction):
        name = "broken"
        async def run(self, args: str, dry_run: bool = False) -> ActionResult:
            raise ValueError("kaboom")

    r = ActionRegistry(allowlist=["broken"], dry_run=False)
    r.register(BrokenAction())
    result = await r.dispatch("broken")
    assert result.success is False
    assert "kaboom" in result.error
