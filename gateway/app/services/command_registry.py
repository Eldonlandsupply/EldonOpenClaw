"""
Command registry: approved actions only.
Arbitrary shell is OFF by default (ENABLE_RAW_SHELL=false).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

from ..gateway.models import Channel, RiskLevel


@dataclass
class CommandEntry:
    action_name: str
    description: str
    risk_level: RiskLevel
    handler: Optional[Callable[..., Coroutine[Any, Any, str]]] = None
    allow_channels: list[Channel] = field(default_factory=lambda: [Channel.TELEGRAM, Channel.SMS])
    requires_confirmation: bool = False
    allow_args: bool = False


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, CommandEntry] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        from ..handlers.status_handler import handle_status
        from ..handlers.task_handler import handle_task
        from ..handlers.agent_handler import handle_create_agent
        from ..handlers.help_handler import handle_help

        entries = [
            CommandEntry("status", "System health and queue summary", RiskLevel.LOW, handle_status),
            CommandEntry("health_check", "Quick health check", RiskLevel.LOW, handle_status),
            CommandEntry("list_agents", "List configured agents", RiskLevel.LOW, handle_status),
            CommandEntry("queue_status", "Show task queue", RiskLevel.LOW, handle_status),
            CommandEntry("help", "Show available commands", RiskLevel.LOW, handle_help),
            CommandEntry(
                "restart_openclaw", "Restart OpenClaw service", RiskLevel.HIGH,
                handle_task, requires_confirmation=True,
            ),
            CommandEntry(
                "git_pull_repo", "Pull latest from repo", RiskLevel.MEDIUM,
                handle_task, allow_args=True,
            ),
            CommandEntry(
                "run_morning_brief", "Run morning brief workflow", RiskLevel.MEDIUM,
                handle_task,
            ),
            CommandEntry(
                "check_failed_jobs", "Report recent failed jobs", RiskLevel.LOW,
                handle_status,
            ),
            CommandEntry(
                "create_agent", "Generate agent spec", RiskLevel.MEDIUM,
                handle_create_agent, allow_args=True,
            ),
            CommandEntry(
                "ingest_attachment", "Process file attachment", RiskLevel.MEDIUM,
                handle_task, allow_args=True,
            ),
            CommandEntry(
                "process_attachment", "Process file attachment", RiskLevel.MEDIUM,
                handle_task, allow_args=True,
            ),
        ]
        for e in entries:
            self._commands[e.action_name] = e

    def get(self, action_name: str) -> Optional[CommandEntry]:
        # Normalize
        key = action_name.lower().strip().replace(" ", "_")
        return self._commands.get(key)

    def is_registered(self, action_name: str) -> bool:
        return self.get(action_name) is not None

    def list_names(self) -> list[str]:
        return sorted(self._commands.keys())

    async def dispatch(self, action_name: str, **kwargs: Any) -> str:
        # Block raw shell unless explicitly enabled
        enable_shell = os.getenv("ENABLE_RAW_SHELL", "false").lower() == "true"
        if not enable_shell and action_name in ("shell", "exec", "bash", "sh", "eval"):
            return "ERROR: Raw shell execution is disabled. Set ENABLE_RAW_SHELL=true to enable."

        entry = self.get(action_name)
        if entry is None:
            return f"ERROR: Action '{action_name}' is not in the command registry."

        if entry.handler is None:
            return f"OPEN_ITEM: Handler for '{action_name}' not yet implemented."

        try:
            return await entry.handler(**kwargs)
        except Exception as exc:
            return f"ERROR executing '{action_name}': {exc}"


# Module-level singleton
_registry = CommandRegistry()


def get_registry() -> CommandRegistry:
    return _registry
