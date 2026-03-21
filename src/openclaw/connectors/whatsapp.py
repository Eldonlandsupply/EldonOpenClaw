"""
WhatsApp connector — bridges to the local whatsmeow HTTP bridge.

The whatsmeow bridge runs on localhost:8181 and exposes:
  GET  /messages  -> drain queued inbound messages
  POST /send      -> send a message {to, text}
  GET  /status    -> {connected, logged_in}
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

import aiohttp

from openclaw.connectors.base import BaseConnector, Message
from openclaw.logging import get_logger

logger = get_logger(__name__)

DEFAULT_BRIDGE_URL = "http://127.0.0.1:8181"


class WhatsAppConnector(BaseConnector):
    name = "whatsapp"

    def __init__(
        self,
        allowed_numbers: list[str],
        bridge_url: str = DEFAULT_BRIDGE_URL,
        poll_interval: int = 5,
    ) -> None:
        self._allowed = set(allowed_numbers)
        self._bridge_url = bridge_url.rstrip("/")
        self._poll_interval = poll_interval
        self._queue: asyncio.Queue | None = None
        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self._queue = asyncio.Queue()
        self._session = aiohttp.ClientSession()
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("WhatsApp connector started", extra={
            "bridge": self._bridge_url,
            "allowed_numbers": list(self._allowed),
        })

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                async with self._session.get(
                    f"{self._bridge_url}/messages", timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        msgs = await resp.json() or []
                        for m in msgs:
                            sender = m.get("from", "")
                            text = m.get("text", "").strip()
                            if not text:
                                continue
                            number = sender.split("@")[0]
                            if self._allowed and number not in self._allowed:
                                logger.info("WhatsApp message from unlisted number ignored",
                                            extra={"from": number})
                                continue
                            await self._queue.put(
                                Message(text=text, source="whatsapp", chat_id=sender)
                            )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("WhatsApp poll error", extra={"error": str(exc)})
            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break

    async def messages(self) -> AsyncIterator[Message]:
        while True:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield item
            except asyncio.TimeoutError:
                if not self._running:
                    return

    async def send(self, chat_id: str | None, text: str) -> None:
        if not chat_id:
            logger.warning("WhatsApp send called with no chat_id")
            return
        jid = chat_id if "@" in chat_id else f"{chat_id}@s.whatsapp.net"
        try:
            async with self._session.post(
                f"{self._bridge_url}/send",
                json={"to": jid, "text": text},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    logger.info("WhatsApp sent", extra={"to": jid})
                else:
                    body = await resp.text()
                    logger.error("WhatsApp send failed", extra={"status": resp.status, "body": body})
        except Exception as exc:
            logger.error("WhatsApp send error", extra={"error": str(exc)})

    async def stop(self) -> None:
        self._running = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self._session:
            await self._session.close()
        self._poll_task = None
        self._session = None
