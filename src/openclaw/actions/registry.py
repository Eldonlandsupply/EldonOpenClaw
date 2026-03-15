"""
Action registry with allowlist gating, risk-score enforcement, and
startup-time validation that warns on unimplemented allowlist entries.

Every action must be:
  1. Registered (via register()) — has a handler
  2. In the allowlist (config actions.allowlist) — approved for use

Risk enforcement (from action_allowlist JSON):
  - risk_score > 3 and execution_mode == "auto_execute"  → hard blocked
  - execution_mode == "approval_required"                → blocked (must go
    through the explicit approval flow, not direct dispatch)
  - execution_mode == "draft_then_review"                → allowed but flagged
    in the result output so the caller knows to present for review

Built-in actions: echo, memory_write, memory_read, help
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from openclaw.actions.base import ActionResult, BaseAction

logger = logging.getLogger(__name__)

# Path to the allowlist JSON catalogue (relative to repo root)
_ALLOWLIST_JSON = Path(__file__).resolve().parents[4] / "action_allowlist" / "top_100_actions.json"

# execution_mode values that require out-of-band approval
_APPROVAL_MODES = {"approval_required"}
# execution_mode values that should be flagged as needing review before send
_REVIEW_MODES   = {"draft_then_review"}
# Risk score above which auto-execution is hard-blocked
_MAX_AUTO_RISK  = 3


def _load_allowlist_meta() -> dict[str, dict]:
    """
    Load action metadata from the catalogue JSON.
    Returns a dict keyed by action_name (lowercased, spaces → underscores).
    Gracefully returns {} if file not found.
    """
    if not _ALLOWLIST_JSON.exists():
        return {}
    try:
        raw = json.loads(_ALLOWLIST_JSON.read_text(encoding="utf-8"))
        return {
            entry["action_name"].lower().replace(" ", "_"): entry
            for entry in raw
            if "action_name" in entry
        }
    except Exception as exc:
        logger.warning("Could not load action allowlist JSON: %s", exc)
        return {}


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
        return ActionResult(success=True, output=f"memory_write queued: {args}")


class MemoryReadAction(BaseAction):
    name = "memory_read"

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        if dry_run:
            return ActionResult(success=True, output=f"[dry_run] memory_read: {args}")
        return ActionResult(success=True, output=f"memory_read queued: {args}")


class HelpAction(BaseAction):
    """List all registered and allowed actions with their status."""
    name = "help"

    def __init__(self, registry: "ActionRegistry") -> None:
        self._registry = registry

    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        allowed   = sorted(self._registry._allowlist)
        meta      = self._registry._meta
        lines     = ["Available actions:"]
        for name in allowed:
            reg_status  = "[registered]" if name in self._registry._actions else "[NOT REGISTERED]"
            risk        = ""
            mode        = ""
            if name in meta:
                m    = meta[name]
                risk = f"risk={m.get('risk_score', '?')}"
                mode = f"mode={m.get('execution_mode', '?')}"
            lines.append(f"  {name}  {reg_status}  {risk}  {mode}".rstrip())
        if not allowed:
            lines = ["No actions are currently allowed. Check actions.allowlist in config.yaml."]
        return ActionResult(success=True, output="\n".join(lines))


# ── Registry ───────────────────────────────────────────────────────────────

class ActionRegistry:
    def __init__(self, allowlist: list[str], dry_run: bool = True) -> None:
        self._allowlist: set[str]        = set(allowlist)
        self._dry_run:   bool            = dry_run
        self._actions:   dict[str, BaseAction] = {}
        self._meta:      dict[str, dict] = _load_allowlist_meta()

        self._register_builtins()
        self._warn_unimplemented()

    # ── Setup ──────────────────────────────────────────────────────────────

    def _register_builtins(self) -> None:
        for action in [EchoAction(), MemoryWriteAction(), MemoryReadAction()]:
            self._actions[action.name] = action
        help_action = HelpAction(registry=self)
        self._actions[help_action.name] = help_action
        self._allowlist.add("help")

    def _warn_unimplemented(self) -> None:
        """Warn at startup for every allowlisted action with no registered handler."""
        missing = [
            name for name in sorted(self._allowlist)
            if name not in self._actions
        ]
        if missing:
            logger.warning(
                "Allowlisted actions have no registered handler and will fail at dispatch: %s",
                ", ".join(sorted(missing)),
                extra={"unimplemented": missing, "count": len(missing)},
            )

    # ── Registration ───────────────────────────────────────────────────────

    def register(self, action: BaseAction) -> None:
        """Register a custom action at runtime."""
        self._actions[action.name] = action
        logger.info("action registered", extra={"action": action.name})

    # ── Queries ────────────────────────────────────────────────────────────

    def is_allowed(self, name: str) -> bool:
        return name in self._allowlist

    def list_registered(self) -> list[str]:
        return sorted(self._actions.keys())

    def list_allowed(self) -> list[str]:
        return sorted(self._allowlist)

    # ── Dispatch ───────────────────────────────────────────────────────────

    async def dispatch(self, name: str, args: str = "") -> ActionResult:
        """Gate-checked dispatch with risk enforcement."""

        # Gate 1: allowlist
        if not self.is_allowed(name):
            logger.warning("action blocked — not in allowlist", extra={"action": name})
            return ActionResult(success=False, error=f"action '{name}' not in allowlist")

        # Gate 2: risk / execution_mode from catalogue
        meta = self._meta.get(name, {})
        execution_mode = meta.get("execution_mode", "")
        risk_score     = float(meta.get("risk_score", 0))

        if execution_mode in _APPROVAL_MODES:
            logger.warning(
                "action blocked — requires out-of-band approval",
                extra={"action": name, "execution_mode": execution_mode},
            )
            return ActionResult(
                success=False,
                error=(
                    f"action '{name}' has execution_mode='{execution_mode}'. "
                    "Submit through the approval workflow before dispatching."
                ),
            )

        if execution_mode == "auto_execute" and risk_score > _MAX_AUTO_RISK:
            logger.warning(
                "action blocked — risk score too high for auto-execution",
                extra={"action": name, "risk_score": risk_score},
            )
            return ActionResult(
                success=False,
                error=(
                    f"action '{name}' has risk_score={risk_score} which exceeds "
                    f"the auto-execute threshold ({_MAX_AUTO_RISK}). "
                    "Obtain explicit CEO approval and set execution_mode accordingly."
                ),
            )

        # Gate 3: registered handler
        action = self._actions.get(name)
        if action is None:
            logger.warning("action unknown — not registered", extra={"action": name})
            return ActionResult(success=False, error=f"action '{name}' not registered")

        # Execute
        try:
            result = await action.run(args=args, dry_run=self._dry_run)

            # Annotate draft-then-review results
            if result.success and execution_mode in _REVIEW_MODES and not self._dry_run:
                result = ActionResult(
                    success=True,
                    output=(
                        f"[DRAFT — review before sending]\n"
                        f"{result.output}"
                    ),
                    error=result.error,
                )

            logger.info(
                "action dispatched",
                extra={
                    "action": name,
                    "dry_run": self._dry_run,
                    "execution_mode": execution_mode or "unspecified",
                    "risk_score": risk_score,
                    "result": "ok" if result.success else "error",
                },
            )
            return result
        except Exception as exc:
            logger.error(
                "action raised exception",
                extra={"action": name, "error": str(exc)},
                exc_info=True,
            )
            return ActionResult(success=False, error=str(exc))
