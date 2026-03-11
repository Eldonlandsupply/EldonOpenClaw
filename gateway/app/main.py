"""
OpenClaw Gateway — main ASGI app.
Endpoints:
  GET  /health
  POST /webhooks/telegram
  POST /webhooks/sms
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Any

from aiohttp import web

from .gateway.models import AttachmentMeta, Channel, GatewayRequest
from .gateway.pipeline import process
from .services import telegram_service, sms_service

logger = logging.getLogger("gateway")

_TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
_ENABLE_TELEGRAM = os.getenv("ENABLE_TELEGRAM", "true").lower() == "true"
_ENABLE_SMS = os.getenv("ENABLE_SMS", "false").lower() == "true"


# ── Health ────────────────────────────────────────────────────────────────

async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "openclaw-gateway"})


# ── Telegram webhook ──────────────────────────────────────────────────────

def _verify_telegram_secret(request: web.Request, body: bytes) -> bool:
    if not _TELEGRAM_WEBHOOK_SECRET:
        return True  # not configured = skip verification (warn in logs)
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    return hmac.compare_digest(header, _TELEGRAM_WEBHOOK_SECRET)


async def telegram_webhook(request: web.Request) -> web.Response:
    if not _ENABLE_TELEGRAM:
        return web.json_response({"error": "Telegram disabled"}, status=403)

    body = await request.read()

    if not _verify_telegram_secret(request, body):
        logger.warning("Telegram webhook: secret mismatch")
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        update = json.loads(body)
    except json.JSONDecodeError:
        return web.json_response({"error": "Bad JSON"}, status=400)

    normalized = telegram_service.normalize_update(update)
    if not normalized:
        return web.json_response({"ok": True})  # not a message update

    req = GatewayRequest(
        channel=Channel.TELEGRAM,
        sender_id=normalized["sender_id"],
        sender_display=normalized["sender_display"],
        chat_id=normalized["chat_id"],
        message_id=normalized["message_id"],
        raw_text=normalized["text"],
        attachments=[AttachmentMeta(**a) for a in normalized["attachments"]],
    )

    reply, updated_req = await process(req)
    if reply:
        await telegram_service.send_message(req.chat_id, reply)

    return web.json_response({"ok": True})


# ── SMS webhook (Twilio) ──────────────────────────────────────────────────

async def sms_webhook(request: web.Request) -> web.Response:
    if not _ENABLE_SMS:
        return web.Response(
            text=sms_service.twilio_twiml_response("SMS gateway is disabled."),
            content_type="text/xml",
        )

    form_data = await request.post()
    normalized = sms_service.parse_inbound(dict(form_data))
    if not normalized:
        return web.Response(
            text=sms_service.twilio_twiml_response("Could not parse request."),
            content_type="text/xml",
        )

    req = GatewayRequest(
        channel=Channel.SMS,
        sender_id=normalized["sender_id"],
        sender_display=normalized["sender_display"],
        chat_id=normalized["chat_id"],
        message_id=normalized["message_id"],
        raw_text=normalized["text"],
    )

    reply, _ = await process(req)
    if not reply:
        reply = "OK"

    return web.Response(
        text=sms_service.twilio_twiml_response(reply),
        content_type="text/xml",
    )


# ── App factory ───────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_post("/webhooks/telegram", telegram_webhook)
    app.router.add_post("/webhooks/sms", sms_webhook)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    port = int(os.getenv("GATEWAY_PORT", "8443"))
    web.run_app(create_app(), port=port)
