"""
Core gateway pipeline.
Orchestrates: auth → dedupe → route → risk → confirm/execute → audit.
"""

from __future__ import annotations

from typing import Optional

from .auth import authenticate, is_duplicate
from .confirmations import get_store
from .models import (
    AttachmentMeta, Channel, GatewayRequest, Intent,
    RequestStatus, RiskLevel,
)
from .responses import format_error, format_rejection, format_response
from .risk import classify_risk
from .router import route
from ..services import audit_log
from ..services.command_registry import get_registry

# In-memory dedupe set (bounded by restart)
_seen_message_ids: set[str] = set()
_MAX_SEEN = 10_000


def _normalize_text(raw: str) -> str:
    return raw.strip()


async def process(req: GatewayRequest) -> tuple[str, GatewayRequest]:
    """
    Run the full pipeline for a GatewayRequest.
    Returns (reply_text, updated_req).
    """
    req.normalized_text = _normalize_text(req.raw_text)

    # 1. Dedupe
    if req.message_id:
        if is_duplicate(req, _seen_message_ids):
            return ("", req)  # silently drop duplicate
        if len(_seen_message_ids) < _MAX_SEEN:
            _seen_message_ids.add(req.message_id)

    # 2. Auth
    authenticate(req)
    if not req.authenticated:
        req.status = RequestStatus.REJECTED
        audit_log.record(req, "rejected_auth")
        return (format_rejection("Unauthorized sender"), req)

    req.status = RequestStatus.AUTHENTICATED

    # 3. Route intent
    route(req)

    # 4. Handle APPROVE flow before risk classification
    if req.intent == Intent.APPROVE:
        return await _handle_approve(req)

    # 5. Risk classification
    classify_risk(req)

    # 6. Registry check
    registry = get_registry()
    entry = registry.get(req.action_name)

    if entry is None and req.action_name not in ("unknown", ""):
        req.status = RequestStatus.FAILED
        reply = format_error(f"'{req.action_name}' is not a registered command. Type 'help'.")
        audit_log.record(req, "rejected_unknown_action")
        return (reply, req)

    # 7. Confirmation gate for HIGH risk
    if req.risk_level == RiskLevel.HIGH:
        return await _require_confirmation(req)

    # 8. Execute
    return await _execute(req)


async def _handle_approve(req: GatewayRequest) -> tuple[str, GatewayRequest]:
    token = req.action_args.get("token", "")
    store = get_store()
    pending = store.resolve(token, req.sender_id)
    if pending is None:
        req.status = RequestStatus.FAILED
        reply = format_error("Invalid, expired, or already-used confirmation token.")
        audit_log.record(req, "confirm_rejected")
        return (reply, req)

    # Restore original action from pending
    req.action_name = pending.action_name
    req.action_args = pending.action_args
    req.risk_level = RiskLevel.HIGH
    req.status = RequestStatus.EXECUTING

    registry = get_registry()
    result = await registry.dispatch(pending.action_name, action_name=pending.action_name, **pending.action_args)
    req.status = RequestStatus.COMPLETE
    reply = format_response(req, result)
    audit_log.record(req, "complete")
    return (reply, req)


async def _require_confirmation(req: GatewayRequest) -> tuple[str, GatewayRequest]:
    store = get_store()
    token = store.create(
        sender_id=req.sender_id,
        chat_id=req.chat_id,
        channel=req.channel.value,
        action_name=req.action_name,
        action_args=req.action_args,
        request_id=req.request_id,
    )
    req.status = RequestStatus.PENDING_CONFIRM
    req.requires_confirmation = True
    reply = format_response(
        req,
        result="CONFIRM REQUIRED",
        confirm_token=token,
        next_step=f"Reply exactly: APPROVE {token}",
    )
    audit_log.record(req, "pending_confirm")
    return (reply, req)


async def _execute(req: GatewayRequest) -> tuple[str, GatewayRequest]:
    req.status = RequestStatus.EXECUTING
    registry = get_registry()

    result = await registry.dispatch(
        req.action_name,
        action_name=req.action_name,
        description=req.action_args.get("description", req.normalized_text),
        channel=req.channel.value,
        **req.action_args,
    )

    req.status = RequestStatus.COMPLETE
    reply = format_response(req, result)
    audit_log.record(req, "complete")
    return (reply, req)
