"""
Async HTTP health endpoints.

Endpoints:
  GET /health  — full status JSON
  GET /ready   — 200 if ready, 503 if not
  GET /ping    — always 200 "pong"
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

_start_time:        float             = time.monotonic()
_last_tick:         Optional[str]     = None
_degraded:          bool              = False
_degraded_reason:   str               = ""
_max_stale_seconds: int               = 60
_connector_status:  dict[str, str]    = {}   # name → "ok" | "degraded"


def record_tick() -> None:
    global _last_tick
    _last_tick = datetime.now(timezone.utc).isoformat()


def mark_degraded(reason: str = "") -> None:
    global _degraded, _degraded_reason
    _degraded        = True
    _degraded_reason = reason
    logger.warning("health marked degraded", extra={"reason": reason})


def record_connector_ok(name: str) -> None:
    _connector_status[name] = "ok"


def record_connector_degraded(name: str) -> None:
    _connector_status[name] = "degraded"


def _compute_status() -> tuple[str, int]:
    stale = False
    if _last_tick is not None:
        last = datetime.fromisoformat(_last_tick.replace("Z", "+00:00"))
        age  = (datetime.now(timezone.utc) - last).total_seconds()
        if age > _max_stale_seconds:
            stale = True
    any_connector_degraded = any(v == "degraded" for v in _connector_status.values())
    ok = not (_degraded or stale or any_connector_degraded)
    return ("ok" if ok else "degraded"), (200 if ok else 503)


async def _handle_health(request: web.Request) -> web.Response:
    status, code = _compute_status()
    payload = {
        "status":     status,
        "uptime_s":   int(time.monotonic() - _start_time),
        "last_tick":  _last_tick,
        "version":    __version__,
        "connectors": _connector_status,
        "reason":     _degraded_reason if status != "ok" else "",
    }
    return web.Response(
        text=json.dumps(payload),
        content_type="application/json",
        status=code,
    )


async def _handle_ready(request: web.Request) -> web.Response:
    _, code = _compute_status()
    return web.Response(text=("ready" if code == 200 else "not ready"), status=code)


async def _handle_ping(request: web.Request) -> web.Response:
    return web.Response(text="pong", status=200)


async def start_health_server(host: str, port: int) -> None:
    app = web.Application()
    app.router.add_get("/health", _handle_health)
    app.router.add_get("/ready",  _handle_ready)
    app.router.add_get("/ping",   _handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("health server started",
                extra={"host": host, "port": port,
                       "endpoints": ["/health", "/ready", "/ping"]})
