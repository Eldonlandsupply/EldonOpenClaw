"""
Notifier — sends templated messages through a configured provider.

Usage:
    notifier = Notifier.from_config(config)
    notifier.send("critical_alert", message="disk full")
    notifier.send_raw("Custom message", recipient="user@example.com")
"""
from __future__ import annotations

import logging

from openclaw.messaging.config import MessagingConfig
from openclaw.messaging.policy import MessagePolicy
from openclaw.messaging.providers import build_provider
from openclaw.messaging.templates import render

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, config: MessagingConfig) -> None:
        self.config = config
        self.policy = MessagePolicy(config)
        self.provider = build_provider(config)

    @classmethod
    def from_config(cls, config: MessagingConfig | None = None) -> "Notifier":
        if config is None:
            config = MessagingConfig.from_env()
        return cls(config)

    def _resolve_recipient(self, recipient: str | None) -> str | None:
        if recipient:
            return recipient
        return self.config.allowed_recipients[0] if self.config.allowed_recipients else None

    def send(self, template_name: str, recipient: str | None = None, **kwargs: object) -> bool:
        """Render a named template and send it."""
        body = render(template_name, **kwargs)
        return self.send_raw(body, recipient=recipient)

    def send_raw(self, body: str, recipient: str | None = None) -> bool:
        """Send a raw message string without template rendering."""
        target = self._resolve_recipient(recipient)
        if not target:
            logger.warning("Notifier.send_raw: no recipient specified and allowlist is empty")
            return False

        allowed, reason = self.policy.allow(target, body)
        if not allowed:
            logger.info("Notifier blocked: %s | body=%s", reason, body[:80])
            return False

        success = self.provider.send(target, body)
        if success:
            self.policy.record_send(target, body)
            logger.info("Notifier sent to %s", target)
        return success
