import logging
from .config import MessagingConfig
from .policy import MessagePolicy
from .providers import build_provider
from .templates import render

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self, config: MessagingConfig):
        self.config = config
        self.policy = MessagePolicy(config)
        self.provider = build_provider(config)

    @classmethod
    def from_config(cls, config: MessagingConfig | None = None) -> "Notifier":
        if config is None:
            config = MessagingConfig.from_env()
        return cls(config)

    def send(self, template_name: str, recipient: str | None = None, **kwargs) -> bool:
        body = render(template_name, **kwargs)
        target = recipient or (self.config.allowed_recipients[0] if self.config.allowed_recipients else None)
        if not target:
            logger.warning("No recipient specified and allowlist is empty")
            return False
        allowed, reason = self.policy.allow(target, body)
        if not allowed:
            logger.info(f"[Notifier] Blocked ({reason}): {body}")
            return False
        success = self.provider.send(target, body)
        if success:
            self.policy.record_send(target, body)
            logger.info(f"[Notifier] Sent to {target}: {body}")
        return success
