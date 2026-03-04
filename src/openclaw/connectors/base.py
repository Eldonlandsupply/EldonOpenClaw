"""Abstract base for all connectors (CLI, Telegram, voice, …)."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import AsyncIterator


class Message:
    """Normalized inbound message from any connector."""

    def __init__(self, text: str, source: str, chat_id: str | None = None):
        self.text = text.strip()
        self.source = source        # connector name, e.g. "cli"
        self.chat_id = chat_id      # None for CLI

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
        # This is a protocol stub — subclasses must implement.
        return
        yield  # make it an async generator

    @abstractmethod
    async def send(self, chat_id: str | None, text: str) -> None:
        """Send a reply back through this connector."""

    async def stop(self) -> None:
        """Optional teardown."""
