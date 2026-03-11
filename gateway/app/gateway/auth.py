"""
Authentication: allowlist-based gating.
Unknown senders are rejected immediately.
"""

from __future__ import annotations

import os
from typing import Optional

from .models import Channel, GatewayRequest


def _parse_ids(raw: Optional[str]) -> set[str]:
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


def _allowed_telegram_chat_ids() -> set[str]:
    return _parse_ids(os.getenv("ALLOWED_TELEGRAM_CHAT_IDS", ""))


def _allowed_telegram_user_ids() -> set[str]:
    return _parse_ids(os.getenv("ALLOWED_TELEGRAM_USER_IDS", ""))


def _allowed_sms_numbers() -> set[str]:
    return _parse_ids(os.getenv("ALLOWED_SMS_NUMBERS", ""))


def authenticate(req: GatewayRequest) -> GatewayRequest:
    """
    Mutates req in place: sets authenticated=True/False and auth_method.
    Returns the same object for chaining.
    """
    if req.channel == Channel.TELEGRAM:
        chat_ids = _allowed_telegram_chat_ids()
        user_ids = _allowed_telegram_user_ids()
        if req.chat_id in chat_ids:
            req.authenticated = True
            req.auth_method = "telegram_chat_id"
        elif req.sender_id in user_ids:
            req.authenticated = True
            req.auth_method = "telegram_user_id"
        else:
            req.authenticated = False
            req.auth_method = "none"

    elif req.channel == Channel.SMS:
        allowed = _allowed_sms_numbers()
        if req.sender_id in allowed:
            req.authenticated = True
            req.auth_method = "sms_allowlist"
        else:
            req.authenticated = False
            req.auth_method = "none"

    return req


def is_duplicate(req: GatewayRequest, seen_ids: set[str]) -> bool:
    """Return True if this message_id has been processed before."""
    if req.message_id and req.message_id in seen_ids:
        return True
    return False
