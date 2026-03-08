import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseProvider(ABC):
    @abstractmethod
    def send(self, recipient: str, body: str) -> bool:
        ...

class LogOnlyProvider(BaseProvider):
    def send(self, recipient: str, body: str) -> bool:
        logger.info(f"[LogOnly] Would send to {recipient}: {body}")
        return True

class ClaudeIMessageProvider(BaseProvider):
    def __init__(self, from_handle: str):
        self.from_handle = from_handle

    def send(self, recipient: str, body: str) -> bool:
        try:
            logger.info(f"[iMessage] Sending to {recipient} from {self.from_handle}: {body}")
            # TODO: wire to actual MCP send_imessage tool call
            return True
        except Exception as e:
            logger.error(f"[iMessage] Send failed: {e}")
            return False

def build_provider(config) -> BaseProvider:
    if config.provider == "imessage":
        return ClaudeIMessageProvider(from_handle=config.from_handle)
    return LogOnlyProvider()
