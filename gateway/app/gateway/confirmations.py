"""
Confirmation flow.
HIGH-risk commands generate a short token; execution waits for APPROVE <token>.
"""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional


_TTL_SECONDS = 120  # tokens expire in 2 minutes


@dataclass
class PendingConfirmation:
    token: str
    sender_id: str
    chat_id: str
    channel: str
    action_name: str
    action_args: dict
    request_id: str
    expires_at: datetime
    used: bool = False


class ConfirmationStore:
    """In-memory store. Pi-friendly; swap for SQLite if needed."""

    def __init__(self) -> None:
        self._store: dict[str, PendingConfirmation] = {}

    def _generate_token(self, prefix: str = "") -> str:
        alphabet = string.ascii_lowercase + string.digits
        suffix = "".join(secrets.choice(alphabet) for _ in range(6))
        slug = (prefix.replace("_", "-")[:16] + "-" + suffix) if prefix else suffix
        return slug

    def create(
        self,
        *,
        sender_id: str,
        chat_id: str,
        channel: str,
        action_name: str,
        action_args: dict,
        request_id: str,
    ) -> str:
        token = self._generate_token(action_name)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=_TTL_SECONDS)
        self._store[token] = PendingConfirmation(
            token=token,
            sender_id=sender_id,
            chat_id=chat_id,
            channel=channel,
            action_name=action_name,
            action_args=action_args,
            request_id=request_id,
            expires_at=expires_at,
        )
        return token

    def resolve(self, token: str, sender_id: str) -> Optional[PendingConfirmation]:
        """
        Returns the PendingConfirmation if valid, marks it used.
        Returns None if not found, expired, already used, or sender mismatch.
        """
        pending = self._store.get(token)
        if pending is None:
            return None
        if pending.used:
            return None
        if pending.sender_id != sender_id:
            return None
        if datetime.now(timezone.utc) > pending.expires_at:
            return None
        pending.used = True
        return pending

    def purge_expired(self) -> int:
        """Remove expired entries. Call periodically."""
        now = datetime.now(timezone.utc)
        expired = [t for t, p in self._store.items() if now > p.expires_at]
        for t in expired:
            del self._store[t]
        return len(expired)


# Module-level singleton
_store = ConfirmationStore()


def get_store() -> ConfirmationStore:
    return _store
