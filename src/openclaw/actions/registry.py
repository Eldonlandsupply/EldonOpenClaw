"""
Action registry with allowlist gating.

Every action must be registered AND appear in config actions.allowlist
before it can execute. In dry_run mode, actions log intent but do nothing.

Built-in actions: echo, memory_write, memory_read, help
"""

from __future__ import annotations

from openclaw.actions.base import ActionResult, BaseAction
from openclaw.logging import get_logger

logger = get_logger(__name__)


# ── Built-in actions ───────────────────────────────────────────────────────

class EchoAction(BaseAction):
    name = "echo"

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        if dry_run:
            logger.info("DRY RUN action", extra={"action": self.name, "args": args})
            return ActionResult(success=True, output=f"[dry_run] echo: {args}")
        logger.info("action run", extra={"action": self.name, "args": args})
        return ActionResult(success=True, output=args)


class MemoryWriteAction(BaseAction):
    name = "memory_write"

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        if dry_run:
            logger.info("DRY RUN action", extra={"action": self.name, "args": args})
            return ActionResult(success=True, output=f"[dry_run] memory_write: {args}")
        # Actual write handled in main._message_loop — registry just validates gate
        return ActionResult(success=True, output=f"memory_write queued: {args}")


class MemoryReadAction(BaseAction):
    name = "memory_read"

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        if dry_run:
            return ActionResult(success=True, output=f"[dry_run] memory_read: {args}")
        # Actual read handled in main._message_loop
        return ActionResult(success=True, output=f"memory_read queued: {args}")


class HelpAction(BaseAction):
    """List all registered and allowed actions."""
    name = "help"

    def __init__(self, registry: "ActionRegistry") -> None:
        self._registry = registry

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:  # noqa: ARG002
        registered = sorted(self._registry._actions.keys())
        allowed = sorted(self._registry._allowlist)
        lines = [
            "Available actions (registered & allowed):",
            *[
                f"  {name}" + (" [registered]" if name in self._registry._actions else " [not registered]")
                for name in allowed
            ],
        ]
        if not allowed:
            lines = ["No actions are currently allowed. Check actions.allowlist in config.yaml."]
        return ActionResult(success=True, output="\n".join(lines))


# ── Registry ───────────────────────────────────────────────────────────────

class ActionRegistry:
    def __init__(self, allowlist: list[str], dry_run: bool = True) -> None:
        self._allowlist: set[str] = set(allowlist)
        self._dry_run = dry_run
        self._actions: dict[str, BaseAction] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        for action in [EchoAction(), MemoryWriteAction(), MemoryReadAction()]:
            self._actions[action.name] = action
        # help is always registered and always allowed regardless of allowlist
        help_action = HelpAction(registry=self)
        self._actions[help_action.name] = help_action
        self._allowlist.add("help")

    def register(self, action: BaseAction) -> None:
        """Register a custom action at runtime."""
        self._actions[action.name] = action
        logger.info("action registered", extra={"action": action.name})

    def is_allowed(self, name: str) -> bool:
        return name in self._allowlist

    def list_registered(self) -> list[str]:
        """Return sorted list of all registered action names."""
        return sorted(self._actions.keys())

    def list_allowed(self) -> list[str]:
        """Return sorted list of all allowlisted action names."""
        return sorted(self._allowlist)

    async def dispatch(self, name: str, args: str = "") -> ActionResult:
        """Gate-checked dispatch. Returns ActionResult(success=False) if blocked."""
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
