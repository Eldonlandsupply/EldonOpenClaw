"""
Async HTTP health endpoints.

Endpoints:
  GET /health  — full status JSON (used by monitoring, curl checks)
  GET /ready   — 200 if ready to serve, 503 if not (systemd / load balancer probe)
  GET /ping    — always 200 "pong" (cheap liveness check)
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Optional

from aiohttp import web

from openclaw import __version__
from openclaw.logging import get_logger

logger = get_logger(__name__)

_start_time: float = time.monotonic()
_last_tick: Optional[str] = None
_degraded: bool = False
_max_stale_seconds: int = 60


def record_tick() -> None:
    global _last_tick
    _last_tick = datetime.now(timezone.utc).isoformat()


def mark_degraded(reason: str = "") -> None:
    global _degraded
    _degraded = True
    logger.warning("health marked degraded", extra={"reason": reason})


def _compute_status() -> tuple[str, int]:
    """Return (status_string, http_status_code)."""
    stale = False
    if _last_tick is not None:
        last = datetime.fromisoformat(_last_tick.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - last).total_seconds()
        if age > _max_stale_seconds:
            stale = True
    status = "degraded" if (_degraded or stale) else "ok"
    code = 200 if status == "ok" else 503
    return status, code


async def _handle_health(request: web.Request) -> web.Response:  # noqa: ARG001
    status, code = _compute_status()
    payload = {
        "status": status,
        "uptime_s": int(time.monotonic() - _start_time),
        "last_tick": _last_tick,
        "version": __version__,
    }
    return web.Response(
        text=json.dumps(payload),
        content_type="application/json",
        status=code,
    )


async def _handle_ready(request: web.Request) -> web.Response:  # noqa: ARG001
    """Readiness probe — 200 when the main loop has ticked at least once."""
    _, code = _compute_status()
    body = "ready" if code == 200 else "not ready"
    return web.Response(text=body, status=code)


async def _handle_ping(request: web.Request) -> web.Response:  # noqa: ARG001
    """Liveness probe — always 200 as long as the process is alive."""
    return web.Response(text="pong", status=200)


async def start_health_server(host: str, port: int) -> None:
    app = web.Application()
    app.router.add_get("/health", _handle_health)
    app.router.add_get("/ready", _handle_ready)
    app.router.add_get("/ping", _handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info(
        "health server started",
        extra={"host": host, "port": port, "endpoints": ["/health", "/ready", "/ping"]},
    )
