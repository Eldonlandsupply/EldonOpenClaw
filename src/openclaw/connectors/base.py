"""Abstract base for all connectors (CLI, Telegram, voice, …)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class Message:
    """Normalized inbound message from any connector."""
    text: str
    source: str
    chat_id: str | None = field(default=None)

    def __post_init__(self) -> None:
        self.text = self.text.strip()

    def __repr__(self) -> str:
        return f"Message(source={self.source!r}, text={self.text!r})"


class BaseConnector(ABC):
    """
    A connector produces Messages and optionally sends replies.
    Each connector runs as a long-lived asyncio task.
    """

    name: str = "base"

    @abstractmethod
    async def start(self) -> None:
        """Called once at startup. Perform setup here."""

    @abstractmethod
    async def messages(self) -> AsyncIterator[Message]:
        """Yield inbound messages as they arrive."""
        return
        yield  # make it an async generator

    @abstractmethod
    async def send(self, chat_id: str | None, text: str) -> None:
        """Send a reply back through this connector."""

    async def stop(self) -> None:
        """Optional teardown."""
