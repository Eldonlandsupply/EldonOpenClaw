"""
CLI connector — reads lines from stdin, emits Message objects.
Supports require_confirm gating with a y/n prompt before dispatch.
"""

from __future__ import annotations

import asyncio
import sys
from typing import AsyncIterator

from openclaw.connectors.base import BaseConnector, Message
from openclaw.logging import get_logger

logger = get_logger(__name__)


class CLIConnector(BaseConnector):
    name = "cli"

    def __init__(self, require_confirm: bool = False) -> None:
        self._require_confirm = require_confirm
        self._queue: asyncio.Queue[Message] = asyncio.Queue()
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        self._running = True
        self._loop = asyncio.get_running_loop()
        self._loop.run_in_executor(None, self._read_stdin)
        logger.info("CLI connector started — type commands and press Enter")

    def _read_stdin(self) -> None:
        """Blocking stdin reader, runs in a thread pool executor."""
        assert self._loop is not None
        try:
            while self._running:
                line = sys.stdin.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                if self._require_confirm:
                    print(f"[openclaw] execute: {line!r}  [y/N] ", end="", flush=True)
                    answer = sys.stdin.readline().strip().lower()
                    if answer not in ("y", "yes"):
                        print("[openclaw] cancelled.")
                        continue
                self._loop.call_soon_threadsafe(
                    self._queue.put_nowait, Message(text=line, source="cli")
                )
        except (EOFError, OSError):
            pass

    async def messages(self) -> AsyncIterator[Message]:
        while True:
            msg = await self._queue.get()
            yield msg

    async def send(self, chat_id: str | None, text: str) -> None:  # noqa: ARG002
        print(f"[openclaw] {text}")

    async def stop(self) -> None:
        self._running = False
