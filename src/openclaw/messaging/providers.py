"""
Messaging providers. Each implements BaseProvider.send(recipient, body) -> bool.

Available providers:
  log_only   — logs the message, no actual send (default/safe)
  gmail      — sends via Gmail SMTP using app password
  imessage   — stub, wired to MCP send_imessage (not yet implemented)
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from abc import ABC, abstractmethod
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    @abstractmethod
    def send(self, recipient: str, body: str) -> bool: ...


class LogOnlyProvider(BaseProvider):
    def send(self, recipient: str, body: str) -> bool:
        logger.info("[LogOnly] Would send to %s: %s", recipient, body)
        return True


class GmailProvider(BaseProvider):
    """Send via Gmail SMTP using an app password (not account password)."""

    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 465

    def __init__(self, gmail_user: str, app_password: str) -> None:
        self._user = gmail_user
        self._password = app_password

    def send(self, recipient: str, body: str) -> bool:
        try:
            msg = EmailMessage()
            msg["From"] = self._user
            msg["To"] = recipient
            msg["Subject"] = "[OpenClaw]"
            msg.set_content(body)

            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.SMTP_HOST, self.SMTP_PORT, context=context) as smtp:
                smtp.login(self._user, self._password)
                smtp.send_message(msg)

            logger.info("[Gmail] Sent to %s", recipient)
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error("[Gmail] Authentication failed — check GMAIL_APP_PASSWORD")
            return False
        except smtplib.SMTPException as exc:
            logger.error("[Gmail] SMTP error: %s", exc)
            return False
        except OSError as exc:
            logger.error("[Gmail] Network error: %s", exc)
            return False


class ClaudeIMessageProvider(BaseProvider):
    def __init__(self, from_handle: str) -> None:
        self.from_handle = from_handle

    def send(self, recipient: str, body: str) -> bool:
        # TODO: wire to actual MCP send_imessage tool call
        logger.info("[iMessage] STUB — would send to %s from %s: %s",
                    recipient, self.from_handle, body)
        return True


def build_provider(config) -> BaseProvider:
    if config.provider == "gmail":
        if not config.gmail_user or not config.gmail_app_password:
            logger.error(
                "[Gmail] GMAIL_USER and GMAIL_APP_PASSWORD must be set. "
                "Falling back to LogOnlyProvider."
            )
            return LogOnlyProvider()
        return GmailProvider(
            gmail_user=config.gmail_user,
            app_password=config.gmail_app_password,
        )
    if config.provider == "imessage":
        return ClaudeIMessageProvider(from_handle=config.from_handle)
    return LogOnlyProvider()
