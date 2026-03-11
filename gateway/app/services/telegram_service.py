"""
Telegram service.
Handles outbound Bot API calls and inbound webhook normalization.
Requires python-telegram-bot>=20.0 OR falls back to raw aiohttp.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import aiohttp

_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_BASE = f"https://api.telegram.org/bot{_BOT_TOKEN}"


async def send_message(chat_id: str | int, text: str, parse_mode: str = "HTML") -> bool:
    """
    Send a text message via Telegram Bot API.
    Returns True on success.
    """
    if not _BOT_TOKEN:
        return False
    # Telegram max message length
    text = text[:4096]
    url = f"{_BASE}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status == 200
    except Exception:
        return False


async def set_webhook(webhook_url: str, secret_token: str | None = None) -> dict:
    """Register the webhook URL with Telegram."""
    url = f"{_BASE}/setWebhook"
    payload: dict[str, Any] = {"url": webhook_url}
    if secret_token:
        payload["secret_token"] = secret_token
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json()


async def get_webhook_info() -> dict:
    url = f"{_BASE}/getWebhookInfo"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()


def normalize_update(update: dict) -> Optional[dict]:
    """
    Extract (sender_id, chat_id, message_id, text, attachments) from a Telegram Update dict.
    Returns None if update has no parseable message.
    """
    message = update.get("message") or update.get("edited_message")
    if not message:
        return None

    sender = message.get("from", {})
    chat = message.get("chat", {})
    text = message.get("text") or message.get("caption") or ""

    attachments = []
    for key in ("document", "photo", "audio", "video", "voice"):
        obj = message.get(key)
        if obj:
            if isinstance(obj, list):
                obj = obj[-1]  # largest photo
            attachments.append({
                "file_id": obj.get("file_id", ""),
                "file_name": obj.get("file_name"),
                "mime_type": obj.get("mime_type"),
                "size_bytes": obj.get("file_size"),
            })

    return {
        "sender_id": str(sender.get("id", "")),
        "sender_display": sender.get("username") or sender.get("first_name") or "",
        "chat_id": str(chat.get("id", "")),
        "message_id": str(message.get("message_id", "")),
        "text": text,
        "attachments": attachments,
    }
