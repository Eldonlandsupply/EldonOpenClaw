"""
MessagingConfig — controls the notification subsystem.
Secrets (gmail_user, app_password) are injected from AppConfig.secrets,
not read directly from env here, to keep secret handling centralized.
"""
from __future__ import annotations

import os
from typing import List, Optional

from pydantic import BaseModel, model_validator


class MessagingConfig(BaseModel):
    enabled: bool = False
    # provider: log_only | gmail | imessage
    provider: str = "log_only"
    allowed_recipients: List[str] = []
    rate_limit_per_hour: int = 10
    dedup_window_minutes: int = 15
    kill_switch: bool = False

    # iMessage
    from_handle: Optional[str] = None

    # Gmail — populated by the runtime from AppConfig.secrets
    gmail_user: Optional[str] = None
    gmail_app_password: Optional[str] = None

    @classmethod
    def from_env(cls) -> "MessagingConfig":
        """
        Build from environment variables.
        Supports both MESSAGING_* and legacy IMESSAGE_* prefixes.
        """
        provider = (
            os.getenv("MESSAGING_PROVIDER")
            or os.getenv("IMESSAGE_PROVIDER", "log_only")
        )
        enabled_raw = (
            os.getenv("MESSAGING_ENABLED")
            or os.getenv("IMESSAGE_ENABLED", "false")
        )
        recipients_raw = (
            os.getenv("MESSAGING_ALLOWED_RECIPIENTS")
            or os.getenv("IMESSAGE_ALLOWED_RECIPIENTS", "")
        )
        return cls(
            enabled=enabled_raw.lower() == "true",
            provider=provider,
            allowed_recipients=[r for r in recipients_raw.split(",") if r.strip()],
            rate_limit_per_hour=int(
                os.getenv("MESSAGING_RATE_LIMIT_PER_HOUR")
                or os.getenv("IMESSAGE_RATE_LIMIT_PER_HOUR", "10")
            ),
            dedup_window_minutes=int(
                os.getenv("MESSAGING_DEDUP_WINDOW_MINUTES")
                or os.getenv("IMESSAGE_DEDUP_WINDOW_MINUTES", "15")
            ),
            kill_switch=(
                os.getenv("MESSAGING_KILL_SWITCH", "false").lower() == "true"
            ),
            from_handle=os.getenv("IMESSAGE_FROM_HANDLE"),
            gmail_user=os.getenv("GMAIL_USER"),
            gmail_app_password=os.getenv("GMAIL_APP_PASSWORD"),
        )

    @model_validator(mode="after")
    def check_provider_requirements(self) -> "MessagingConfig":
        if self.provider == "imessage" and not self.from_handle:
            raise ValueError("IMESSAGE_FROM_HANDLE must be set when provider=imessage")
        return self
