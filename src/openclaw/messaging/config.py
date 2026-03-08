import os
from pydantic import BaseModel, model_validator
from typing import List, Optional

class MessagingConfig(BaseModel):
    enabled: bool = False
    provider: str = "log_only"
    allowed_recipients: List[str] = []
    rate_limit_per_hour: int = 10
    dedup_window_minutes: int = 15
    kill_switch: bool = False
    from_handle: Optional[str] = None

    @classmethod
    def from_env(cls) -> "MessagingConfig":
        return cls(
            enabled=os.getenv("IMESSAGE_ENABLED", "false").lower() == "true",
            provider=os.getenv("IMESSAGE_PROVIDER", "log_only"),
            allowed_recipients=os.getenv("IMESSAGE_ALLOWED_RECIPIENTS", "").split(","),
            rate_limit_per_hour=int(os.getenv("IMESSAGE_RATE_LIMIT_PER_HOUR", "10")),
            dedup_window_minutes=int(os.getenv("IMESSAGE_DEDUP_WINDOW_MINUTES", "15")),
            kill_switch=os.getenv("IMESSAGE_KILL_SWITCH", "false").lower() == "true",
            from_handle=os.getenv("IMESSAGE_FROM_HANDLE"),
        )

    @model_validator(mode="after")
    def check_imessage_requires_handle(self):
        if self.provider == "imessage" and not self.from_handle:
            raise ValueError("IMESSAGE_FROM_HANDLE must be set when provider=imessage")
        return self
