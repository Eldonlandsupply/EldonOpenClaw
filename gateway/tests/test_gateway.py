"""
Gateway tests.
All offline — no network, no Telegram, no Twilio.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.gateway.models import Channel, GatewayRequest, Intent, RiskLevel
from app.gateway.auth import authenticate
from app.gateway.risk import classify_risk
from app.gateway.router import route
from app.gateway.confirmations import ConfirmationStore
from app.gateway.responses import format_response, format_rejection


# ── Helpers ───────────────────────────────────────────────────────────────

def _tg_req(text: str, sender_id: str = "111", chat_id: str = "999") -> GatewayRequest:
    return GatewayRequest(
        channel=Channel.TELEGRAM,
        sender_id=sender_id,
        chat_id=chat_id,
        message_id=f"msg-{text[:8]}",
        raw_text=text,
        normalized_text=text,
    )


def _sms_req(text: str, sender_id: str = "+15550001234") -> GatewayRequest:
    return GatewayRequest(
        channel=Channel.SMS,
        sender_id=sender_id,
        chat_id=sender_id,
        raw_text=text,
        normalized_text=text,
    )


# ── Auth tests ────────────────────────────────────────────────────────────

def test_authorized_telegram_sender_accepted(monkeypatch):
    monkeypatch.setenv("ALLOWED_TELEGRAM_CHAT_IDS", "999")
    req = _tg_req("status", chat_id="999")
    authenticate(req)
    assert req.authenticated is True
    assert req.auth_method == "telegram_chat_id"


def test_unauthorized_telegram_sender_rejected(monkeypatch):
    monkeypatch.setenv("ALLOWED_TELEGRAM_CHAT_IDS", "123")
    req = _tg_req("status", chat_id="999")
    authenticate(req)
    assert req.authenticated is False


def test_authorized_sms_sender_accepted(monkeypatch):
    monkeypatch.setenv("ALLOWED_SMS_NUMBERS", "+15550001234")
    req = _sms_req("status", sender_id="+15550001234")
    authenticate(req)
    assert req.authenticated is True
    assert req.auth_method == "sms_allowlist"


def test_unauthorized_sms_sender_rejected(monkeypatch):
    monkeypatch.setenv("ALLOWED_SMS_NUMBERS", "+19999999999")
    req = _sms_req("status", sender_id="+15550001234")
    authenticate(req)
    assert req.authenticated is False


def test_telegram_user_id_allowlist(monkeypatch):
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_IDS", "777")
    monkeypatch.setenv("ALLOWED_TELEGRAM_CHAT_IDS", "")
    req = _tg_req("status", sender_id="777", chat_id="999")
    authenticate(req)
    assert req.authenticated is True
    assert req.auth_method == "telegram_user_id"


# ── Risk tests ────────────────────────────────────────────────────────────

def test_status_is_low_risk():
    req = _tg_req("status")
    req.action_name = "status"
    classify_risk(req)
    assert req.risk_level == RiskLevel.LOW


def test_restart_is_high_risk():
    req = _tg_req("restart openclaw")
    req.action_name = "restart_openclaw"
    classify_risk(req)
    assert req.risk_level == RiskLevel.HIGH
    assert req.requires_confirmation is True


def test_git_pull_is_medium_risk():
    req = _tg_req("git pull")
    req.action_name = "git_pull_repo"
    classify_risk(req)
    assert req.risk_level == RiskLevel.MEDIUM


def test_delete_is_high_risk():
    req = _tg_req("delete all files")
    req.action_name = "delete"
    classify_risk(req)
    assert req.risk_level == RiskLevel.HIGH


def test_raw_shell_blocked_by_default(monkeypatch):
    monkeypatch.setenv("ENABLE_RAW_SHELL", "false")
    req = _tg_req("$ ls -la")
    req.action_name = "shell"
    classify_risk(req)
    assert req.risk_level == RiskLevel.HIGH


# ── Confirmation tests ────────────────────────────────────────────────────

def test_confirmation_token_round_trip():
    store = ConfirmationStore()
    token = store.create(
        sender_id="111",
        chat_id="999",
        channel="telegram",
        action_name="restart_openclaw",
        action_args={},
        request_id="req-1",
    )
    assert token
    pending = store.resolve(token, "111")
    assert pending is not None
    assert pending.action_name == "restart_openclaw"


def test_confirmation_wrong_sender_rejected():
    store = ConfirmationStore()
    token = store.create(
        sender_id="111",
        chat_id="999",
        channel="telegram",
        action_name="restart_openclaw",
        action_args={},
        request_id="req-2",
    )
    pending = store.resolve(token, "WRONG_SENDER")
    assert pending is None


def test_confirmation_token_used_once():
    store = ConfirmationStore()
    token = store.create(
        sender_id="111",
        chat_id="999",
        channel="telegram",
        action_name="restart_openclaw",
        action_args={},
        request_id="req-3",
    )
    assert store.resolve(token, "111") is not None
    assert store.resolve(token, "111") is None  # already used


def test_expired_token_rejected():
    from datetime import datetime, timedelta, timezone
    store = ConfirmationStore()
    token = store.create(
        sender_id="111",
        chat_id="999",
        channel="telegram",
        action_name="restart_openclaw",
        action_args={},
        request_id="req-4",
    )
    # manually expire it
    store._store[token].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    pending = store.resolve(token, "111")
    assert pending is None


# ── Router tests ──────────────────────────────────────────────────────────

def test_route_status():
    req = _tg_req("status")
    route(req)
    assert req.intent == Intent.STATUS


def test_route_help():
    req = _tg_req("help")
    route(req)
    assert req.intent == Intent.HELP


def test_route_create_agent():
    req = _tg_req("create agent that watches my inbox")
    req.normalized_text = req.raw_text
    route(req)
    assert req.intent == Intent.CREATE_AGENT


def test_route_approve():
    req = _tg_req("APPROVE restart-openclaw-abc123")
    req.normalized_text = req.raw_text
    route(req)
    assert req.intent == Intent.APPROVE
    assert req.action_args["token"] == "restart-openclaw-abc123"


def test_route_execute_task():
    req = _tg_req("run morning brief")
    req.normalized_text = req.raw_text
    route(req)
    assert req.intent == Intent.EXECUTE_TASK


# ── Registry tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_registry_blocks_unknown_action():
    from app.services.command_registry import CommandRegistry
    reg = CommandRegistry()
    result = await reg.dispatch("definitely_not_registered")
    assert "not in the command registry" in result


@pytest.mark.asyncio
async def test_registry_blocks_raw_shell(monkeypatch):
    monkeypatch.setenv("ENABLE_RAW_SHELL", "false")
    from app.services.command_registry import CommandRegistry
    reg = CommandRegistry()
    result = await reg.dispatch("shell")
    assert "disabled" in result.lower()


@pytest.mark.asyncio
async def test_help_handler_returns_content():
    from app.handlers.help_handler import handle_help
    result = await handle_help(channel="telegram")
    assert "status" in result.lower()
    assert "APPROVE" in result
