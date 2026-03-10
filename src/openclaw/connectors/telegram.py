"""
Telegram connector — polls getUpdates, emits Message objects, sends replies.
No external library required; uses aiohttp (already a dep via health server).
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import aiohttp

from openclaw.connectors.base import BaseConnector, Message
from openclaw.logging import get_logger

logger = get_logger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramConnector(BaseConnector):
    name = "telegram"

    def __init__(
        self,
        token: str,
        allowed_chat_ids: list[int],
        poll_timeout: int = 30,
    ) -> None:
        self._token = token
        self._allowed = set(allowed_chat_ids)
        self._poll_timeout = poll_timeout
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._offset = 0
        self._session: aiohttp.ClientSession | None = None

    def _url(self, method: str) -> str:
        return _API.format(token=self._token, method=method)

    async def start(self) -> None:
        self._session = aiohttp.ClientSession()
        self._running = True
        asyncio.create_task(self._poll_loop())
        logger.info("Telegram connector started", extra={"allowed_chat_ids": list(self._allowed)})

    async def _poll_loop(self) -> None:
        assert self._session is not None
        while self._running:
            try:
                async with self._session.get(
                    self._url("getUpdates"),
                    params={"offset": self._offset, "timeout": self._poll_timeout},
                    timeout=aiohttp.ClientTimeout(total=self._poll_timeout + 10),
                ) as resp:
                    data = await resp.json()
                if not data.get("ok"):
                    logger.warning("Telegram getUpdates error", extra={"data": data})
                    await asyncio.sleep(5)
                    continue
                for update in data.get("result", []):
                    self._offset = update["update_id"] + 1
                    msg = update.get("message") or update.get("edited_message")
                    if not msg:
                        continue
                    chat_id = msg["chat"]["id"]
                    if self._allowed and chat_id not in self._allowed:
                        logger.warning("Telegram message from unknown chat_id", extra={"chat_id": chat_id})
                        continue
                    text = msg.get("text", "").strip()
                    if not text:
                        continue
                    await self._queue.put(Message(text=text, source="telegram", chat_id=str(chat_id)))
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Telegram poll error", extra={"error": str(exc)})
                await asyncio.sleep(5)

    async def messages(self) -> AsyncIterator[Message]:
        while True:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield item
            except asyncio.TimeoutError:
                if not self._running:
                    return

    async def send(self, chat_id: str | None, text: str) -> None:
        if not chat_id or not self._session:
            return
        try:
            async with self._session.post(
                self._url("sendMessage"),
                json={"chat_id": int(chat_id), "text": text},
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("Telegram sendMessage failed", extra={"status": resp.status, "body": body})
        except Exception as exc:
            logger.warning("Telegram send error", extra={"error": str(exc)})

    async def stop(self) -> None:
        self._running = False
        if self._session:
            await self._session.close()
