"""
Action registry with allowlist gating.

Every action must be registered AND appear in config actions.allowlist
before it can execute. In dry_run mode, actions log intent but do nothing.
"""

from __future__ import annotations

from typing import Optional

from openclaw.actions.base import ActionResult, BaseAction
from openclaw.logging import get_logger

logger = get_logger(__name__)

# ── Built-in actions ───────────────────────────────────────────────────────

class EchoAction(BaseAction):
    name = "echo"

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        if dry_run:
            logger.info(
                "DRY RUN action",
                extra={"action": self.name, "args": args, "result": "skipped"},
            )
            return ActionResult(success=True, output=f"[dry_run] echo: {args}")
        logger.info("action run", extra={"action": self.name, "args": args})
        return ActionResult(success=True, output=args)


class MemoryWriteAction(BaseAction):
    name = "memory_write"

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        if dry_run:
            logger.info(
                "DRY RUN action",
                extra={"action": self.name, "args": args, "result": "skipped"},
            )
            return ActionResult(success=True, output=f"[dry_run] memory_write: {args}")
        # Actual write delegated to memory layer via main loop.
        # Registry just validates; main.py calls memory directly.
        return ActionResult(success=True, output=f"memory_write queued: {args}")


class MemoryReadAction(BaseAction):
    name = "memory_read"

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        if dry_run:
            return ActionResult(success=True, output=f"[dry_run] memory_read: {args}")
        return ActionResult(success=True, output=f"memory_read queued: {args}")


# ── Registry ───────────────────────────────────────────────────────────────

class ActionRegistry:
    def __init__(self, allowlist: list[str], dry_run: bool = True):
        self._allowlist: set[str] = set(allowlist)
        self._dry_run = dry_run
        self._actions: dict[str, BaseAction] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        for action in [EchoAction(), MemoryWriteAction(), MemoryReadAction()]:
            self._actions[action.name] = action

    def register(self, action: BaseAction) -> None:
        """Register a custom action at runtime."""
        self._actions[action.name] = action
        logger.info("action registered", extra={"action": action.name})

    def is_allowed(self, name: str) -> bool:
        return name in self._allowlist

    async def dispatch(self, name: str, args: str = "") -> ActionResult:
        """
        Gate-checked dispatch.
        Returns ActionResult(success=False) if blocked.
        """
        if not self.is_allowed(name):
            logger.warning(
                "action blocked by allowlist",
                extra={"action": name, "result": "blocked"},
            )
            return ActionResult(success=False, error=f"action '{name}' not in allowlist")

        action = self._actions.get(name)
        if action is None:
            logger.warning(
                "action unknown",
                extra={"action": name, "result": "unknown"},
            )
            return ActionResult(success=False, error=f"action '{name}' not registered")

        try:
            result = await action.run(args=args, dry_run=self._dry_run)
            logger.info(
                "action dispatched",
                extra={
                    "action": name,
                    "dry_run": self._dry_run,
                    "result": "ok" if result.success else "error",
                },
            )
            return result
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "action raised exception",
                extra={"action": name, "error": str(exc)},
                exc_info=True,
            )
            return ActionResult(success=False, error=str(exc))
