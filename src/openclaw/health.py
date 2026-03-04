"""
Minimal async HTTP health endpoint.
Returns JSON: {"status": "ok"|"degraded", "uptime_s": N, "last_tick": "...", "version": "..."}
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Optional

from aiohttp import web

from openclaw import __version__
from openclaw.logging import get_logger

logger = get_logger(__name__)

# Shared mutable state updated by the main loop
_start_time: float = time.monotonic()
_last_tick: Optional[str] = None
_degraded: bool = False
_max_stale_seconds: int = 60  # health goes degraded if loop hasn't ticked in this long


def record_tick() -> None:
    global _last_tick
    _last_tick = datetime.now(timezone.utc).isoformat()


def mark_degraded(reason: str = "") -> None:
    global _degraded
    _degraded = True
    logger.warning("health marked degraded", extra={"reason": reason})


async def _handle_health(request: web.Request) -> web.Response:  # noqa: ARG001
    uptime = int(time.monotonic() - _start_time)

    # Auto-degrade if main loop has stalled
    stale = False
    if _last_tick is not None:
        from datetime import datetime as _dt
        last = _dt.fromisoformat(_last_tick.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - last).total_seconds()
        if age > _max_stale_seconds:
            stale = True

    status = "degraded" if (_degraded or stale) else "ok"
    payload = {
        "status": status,
        "uptime_s": uptime,
        "last_tick": _last_tick,
        "version": __version__,
    }
    return web.Response(
        text=json.dumps(payload),
        content_type="application/json",
        status=200 if status == "ok" else 503,
    )


async def start_health_server(host: str, port: int) -> None:
    app = web.Application()
    app.router.add_get("/health", _handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("health server started", extra={"host": host, "port": port})
