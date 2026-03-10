"""Abstract base for all actions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ActionResult:
    success: bool
    output: Any = None
    error: str | None = None


class BaseAction(ABC):
    """
    An action is a unit of work the agent can perform.
    Registered by name in the ActionRegistry.
    """

    name: str  # must be unique, matches allowlist entry

    @abstractmethod
    async def run(self, args: str, dry_run: bool = False) -> ActionResult:
        """Execute the action. Must be safe to call with dry_run=True."""
