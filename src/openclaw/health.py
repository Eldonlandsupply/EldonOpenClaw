"""
Async HTTP health endpoints.

Endpoints:
  GET /health  — full status JSON
  GET /ready   — 200 if ready, 503 if not
  GET /ping    — always 200 "pong"

Fix (2026-03-17):
  - Added reset_health() so SIGHUP reload cycles start with clean state.
    Without this, _degraded / _connector_status from a previous run carry
    over and produce false-degraded readings after reload.
  - start_health_server() is now idempotent: a second call is a no-op so
    reload does not attempt to bind the same port twice (which would throw
    OSError and crash the reload cycle).
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
_server_started:    bool              = False  # FIXED: guard against double-bind


def reset_health() -> None:
    """Reset mutable health state for a fresh reload cycle.

    Call this at the start of each run() cycle so SIGHUP reloads do not
    carry degraded flags or stale connector status from the previous cycle.
    Does NOT reset _start_time (uptime is cumulative across reloads).
    """
    global _last_tick, _degraded, _degraded_reason, _connector_status
    _last_tick        = None
    _degraded         = False
    _degraded_reason  = ""
    _connector_status = {}


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
    """Start the health server. Idempotent — second call is a no-op.

    On SIGHUP reload, run() calls this again. Without the guard the second
    bind attempt throws OSError (address already in use) and crashes the
    reload cycle. The existing server continues serving across reloads.
    """
    global _server_started
    if _server_started:
        logger.info("health server already running — skipping rebind",
                    extra={"host": host, "port": port})
        return
    app = web.Application()
    app.router.add_get("/health", _handle_health)
    app.router.add_get("/ready",  _handle_ready)
    app.router.add_get("/ping",   _handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    _server_started = True
    logger.info("health server started",
                extra={"host": host, "port": port,
                       "endpoints": ["/health", "/ready", "/ping"]})
