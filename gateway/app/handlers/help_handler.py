from __future__ import annotations
from typing import Any
from ..gateway.responses import format_help


async def handle_help(channel: str = "telegram", **kwargs: Any) -> str:
    return format_help(channel)
