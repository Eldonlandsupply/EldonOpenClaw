"""
Intent router: deterministic, rule-based.
No LLM needed for safety classification.
"""

from __future__ import annotations

import re

from .models import GatewayRequest, Intent

# ── Keyword patterns ──────────────────────────────────────────────────────

_APPROVE_RE = re.compile(r"^approve\s+(\S+)$", re.IGNORECASE)

_STATUS_WORDS = {"status", "health", "healthcheck", "health_check", "ping", "uptime"}
_TASK_WORDS = {"run", "execute", "task", "workflow", "morning_brief", "brief", "git_pull", "pull", "check_failed"}
_AGENT_WORDS = {"create agent", "make agent", "build agent", "new agent", "create_agent"}
_SCHEDULE_WORDS = {"schedule", "cron", "at ", "every "}
_ATTACH_WORDS = {"attach", "attachment", "file", "upload", "note", "ingest"}
_HELP_WORDS = {"help", "commands", "what can", "hi", "hello"}


def route(req: GatewayRequest) -> GatewayRequest:
    """
    Classify req.intent and extract req.action_name / req.action_args.
    Mutates and returns req.
    """
    text = req.normalized_text.lower().strip()

    # APPROVE flow — must check first
    m = _APPROVE_RE.match(text)
    if m:
        req.intent = Intent.APPROVE
        req.action_name = "approve"
        req.action_args = {"token": m.group(1)}
        return req

    # STATUS
    if any(w in text for w in _STATUS_WORDS):
        req.intent = Intent.STATUS
        req.action_name = "status"
        return req

    # HELP
    if any(w in text for w in _HELP_WORDS):
        req.intent = Intent.HELP
        req.action_name = "help"
        return req

    # CREATE AGENT
    if any(w in text for w in _AGENT_WORDS):
        req.intent = Intent.CREATE_AGENT
        req.action_name = "create_agent"
        # pass the full text as description
        req.action_args = {"description": req.normalized_text}
        return req

    # SCHEDULE
    if any(w in text for w in _SCHEDULE_WORDS):
        req.intent = Intent.SCHEDULE_TASK
        req.action_name = "schedule_task"
        req.action_args = {"description": req.normalized_text}
        return req

    # INGEST ATTACHMENT
    if req.attachments or any(w in text for w in _ATTACH_WORDS):
        req.intent = Intent.INGEST_ATTACHMENT
        req.action_name = "ingest_attachment"
        return req

    # EXECUTE TASK
    if any(w in text for w in _TASK_WORDS):
        req.intent = Intent.EXECUTE_TASK
        # First word after verbs = action name
        parts = text.split()
        req.action_name = parts[0] if parts else "unknown"
        req.action_args = {"args": req.normalized_text}
        return req

    req.intent = Intent.UNKNOWN
    req.action_name = "unknown"
    return req
