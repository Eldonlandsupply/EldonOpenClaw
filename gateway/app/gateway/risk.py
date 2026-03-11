"""
Risk engine: deterministic classification of commands.
"""

from __future__ import annotations

from .models import GatewayRequest, Intent, RiskLevel

# ── Keyword maps ──────────────────────────────────────────────────────────

_LOW = {
    "status", "health", "health_check", "healthcheck",
    "queue", "queue_status", "list_agents", "agents",
    "help", "hi", "hello", "ping",
}

_MEDIUM = {
    "run", "execute", "task", "workflow",
    "create_agent", "create agent", "make agent", "build agent",
    "schedule", "git_pull", "pull", "process", "ingest",
    "morning_brief", "brief",
}

_HIGH = {
    "restart", "reboot", "stop", "kill",
    "install", "pip", "apt", "brew",
    "delete", "remove", "rm",
    "shell", "exec", "eval", "bash", "sh",
    "config", "reconfigure", "update_config",
    "send_email", "email", "sms_send",
}


def classify_risk(req: GatewayRequest) -> GatewayRequest:
    """
    Sets req.risk_level based on action_name and intent.
    """
    action = (req.action_name or req.normalized_text or "").lower().strip()

    # Explicit high-risk check first
    for kw in _HIGH:
        if kw in action:
            req.risk_level = RiskLevel.HIGH
            req.requires_confirmation = True
            return req

    # Shell disabled check: any unknown action without whitelist = HIGH
    import os
    enable_shell = os.getenv("ENABLE_RAW_SHELL", "false").lower() == "true"
    if not enable_shell and action.startswith("$") or action.startswith("!"):
        req.risk_level = RiskLevel.HIGH
        req.requires_confirmation = True
        return req

    for kw in _MEDIUM:
        if kw in action:
            req.risk_level = RiskLevel.MEDIUM
            return req

    for kw in _LOW:
        if kw in action:
            req.risk_level = RiskLevel.LOW
            return req

    # Intent-based fallback
    if req.intent == Intent.STATUS:
        req.risk_level = RiskLevel.LOW
    elif req.intent in (Intent.EXECUTE_TASK, Intent.SCHEDULE_TASK):
        req.risk_level = RiskLevel.MEDIUM
    elif req.intent == Intent.CREATE_AGENT:
        req.risk_level = RiskLevel.MEDIUM
    else:
        req.risk_level = RiskLevel.LOW

    return req
