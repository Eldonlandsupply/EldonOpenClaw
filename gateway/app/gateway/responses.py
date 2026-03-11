"""
Outbound response formatting.
Concise operational format for message channels.
"""

from __future__ import annotations

from .models import GatewayRequest, RiskLevel


def format_response(
    req: GatewayRequest,
    result: str,
    confirm_token: str | None = None,
    next_step: str | None = None,
) -> str:
    lines = [
        f"Authenticated: {'YES' if req.authenticated else 'NO'}",
        f"Intent: {req.intent.value}",
        f"Risk: {req.risk_level.value}",
        f"Action: {req.action_name}",
        f"Result: {result}",
    ]

    if confirm_token:
        lines.append(f"Reply exactly: APPROVE {confirm_token}")

    if next_step:
        lines.append(f"Next step: {next_step}")

    return "\n".join(lines)


def format_rejection(reason: str = "Unauthorized sender") -> str:
    return f"REJECTED: {reason}"


def format_error(msg: str) -> str:
    return f"ERROR: {msg}"


def format_help(channel: str) -> str:
    cmds = [
        "status         — system health and queue summary",
        "health         — quick health check",
        "queue status   — show pending tasks",
        "list agents    — show configured agents",
        "restart openclaw — (HIGH risk, requires APPROVE)",
        "git pull       — pull latest repo (MEDIUM)",
        "run morning brief — run morning brief workflow",
        "create agent <description> — generate agent spec",
        "schedule <task> — schedule a task",
        "help           — this message",
        "",
        "HIGH-risk commands require confirmation:",
        "  1. Send command",
        "  2. Receive: APPROVE <token>",
        "  3. Reply: APPROVE <token>",
    ]
    header = f"OpenClaw Gateway — Commands ({channel.upper()})"
    return header + "\n\n" + "\n".join(cmds)
