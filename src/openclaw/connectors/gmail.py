"""
Gmail connector — polls IMAP for unread messages, sends replies via SMTP SSL.
Uses only stdlib: imaplib, smtplib, email.
"""
from __future__ import annotations

import asyncio
import email as email_lib
import imaplib
import smtplib
import time
from email.mime.text import MIMEText
from typing import AsyncIterator

from openclaw.connectors.base import BaseConnector, Message
from openclaw.logging import get_logger

logger = get_logger(__name__)


class GmailConnector(BaseConnector):
    name = "gmail"

    def __init__(
        self,
        user: str,
        app_password: str,
        poll_interval: int = 30,
    ) -> None:
        self._user = user
        self._password = app_password
        self._poll_interval = poll_interval
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        self._running = True
        self._loop = asyncio.get_running_loop()
        asyncio.create_task(self._poll_loop())
        logger.info("Gmail connector started", extra={"user": self._user})

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._loop.run_in_executor(None, self._fetch_unread)
            except Exception as exc:
                logger.warning("Gmail poll error", extra={"error": str(exc)})
            await asyncio.sleep(self._poll_interval)

    def _fetch_unread(self) -> None:
        with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
            imap.login(self._user, self._password)
            imap.select("INBOX")
            _, data = imap.search(None, "UNSEEN")
            for num in data[0].split():
                _, msg_data = imap.fetch(num, "(RFC822)")
                raw = msg_data[0][1]
                msg = email_lib.message_from_bytes(raw)
                subject = msg.get("Subject", "")
                sender = msg.get("From", "")
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="replace")
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="replace")
                text = f"[Email from {sender}] Subject: {subject}\n{body.strip()}"
                if self._loop and not self._loop.is_closed():
                    self._loop.call_soon_threadsafe(
                        self._queue.put_nowait,
                        Message(text=text, source="gmail", chat_id=sender),
                    )
                imap.store(num, "+FLAGS", "\\Seen")

    async def messages(self) -> AsyncIterator[Message]:
        while True:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield item
            except asyncio.TimeoutError:
                if not self._running:
                    return

    async def send(self, chat_id: str | None, text: str) -> None:
        to = chat_id or self._user
        # Extract plain email from "Name <email>" format
        if "<" in to and ">" in to:
            to = to.split("<")[1].rstrip(">")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._send_smtp, to, text)

    def _send_smtp(self, to: str, text: str) -> None:
        msg = MIMEText(text)
        msg["Subject"] = "OpenClaw Reply"
        msg["From"] = self._user
        msg["To"] = to
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(self._user, self._password)
            smtp.sendmail(self._user, [to], msg.as_string())
        logger.info("Gmail sent", extra={"to": to})

    async def stop(self) -> None:
        self._running = False
