
from __future__ import annotations
import asyncio
import re
import time
from typing import AsyncIterator
import aiohttp
from openclaw.connectors.base import BaseConnector, Message
from openclaw.logging import get_logger

logger = get_logger(__name__)
_GRAPH = "https://graph.microsoft.com/v1.0"

class OutlookConnector(BaseConnector):
    name = "outlook"

    def __init__(self, tenant_id, client_id, client_secret, user, poll_interval=30):
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._user = user
        self._poll_interval = poll_interval
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._token = None
        self._token_expiry = 0.0
        self._session = None

    async def start(self):
        self._session = aiohttp.ClientSession()
        self._running = True
        asyncio.create_task(self._poll_loop())
        logger.info("Outlook connector started", extra={"user": self._user})

    async def _get_token(self):
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        url = f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token"
        async with self._session.post(url, data={
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }) as resp:
            data = await resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"Token error: {data}")
        self._token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        return self._token

    async def _poll_loop(self):
        while self._running:
            try:
                token = await self._get_token()
                headers = {"Authorization": f"Bearer {token}"}
                url = f"{_GRAPH}/users/{self._user}/mailFolders/Inbox/messages"
                params = {"$filter": "isRead eq false", "$top": "10", "$orderby": "receivedDateTime asc"}
                async with self._session.get(url, headers=headers, params=params) as resp:
                    data = await resp.json()
                for msg in data.get("value", []):
                    msg_id = msg["id"]
                    sender = msg.get("from", {}).get("emailAddress", {}).get("address", "")
                    subject = msg.get("subject", "")
                    body = re.sub(r"<[^>]+>", "", msg.get("body", {}).get("content", "")).strip()
                    text = f"[Outlook from {sender}] Subject: {subject}\n{body[:500]}"
                    await self._queue.put(Message(text=text, source="outlook", chat_id=sender))
                    patch_url = f"{_GRAPH}/users/{self._user}/messages/{msg_id}"
                    await self._session.patch(patch_url, headers=headers, json={"isRead": True})
            except Exception as exc:
                logger.warning("Outlook poll error", extra={"error": str(exc)})
            await asyncio.sleep(self._poll_interval)

    async def messages(self) -> AsyncIterator[Message]:
        while True:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield item
            except asyncio.TimeoutError:
                if not self._running:
                    return

    async def send(self, chat_id, text):
        if not chat_id or not self._session:
            return
        try:
            token = await self._get_token()
            headers = {"Authorization": f"Bearer {token}"}
            url = f"{_GRAPH}/users/{self._user}/sendMail"
            payload = {"message": {"subject": "OpenClaw Reply",
                "body": {"contentType": "Text", "content": text},
                "toRecipients": [{"emailAddress": {"address": chat_id}}]}}
            async with self._session.post(url, headers=headers, json=payload) as resp:
                if resp.status not in (200, 202):
                    logger.warning("Outlook send failed", extra={"status": resp.status})
                else:
                    logger.info("Outlook sent", extra={"to": chat_id})
        except Exception as exc:
            logger.warning("Outlook send error", extra={"error": str(exc)})

    async def stop(self):
        self._running = False
        if self._session:
            await self._session.close()
