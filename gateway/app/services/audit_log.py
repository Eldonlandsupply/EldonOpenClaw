"""
Structured audit log.
Every inbound request is recorded here.
No secrets logged.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..gateway.models import GatewayRequest

DATA_DIR = os.getenv("DATA_DIR", "./data")
_LOG_PATH = Path(DATA_DIR) / "audit.jsonl"


def _log_path() -> Path:
    p = Path(os.getenv("DATA_DIR", "./data")) / "audit.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def record(
    req: GatewayRequest,
    result_status: str,
    error_summary: Optional[str] = None,
    artifacts_created: Optional[list[str]] = None,
) -> None:
    entry: dict[str, Any] = {
        "request_id": req.request_id,
        "timestamp": req.timestamp.isoformat(),
        "sender": req.sender_display or req.sender_id,
        "channel": req.channel.value,
        "authenticated": req.authenticated,
        "auth_method": req.auth_method,
        "intent": req.intent.value,
        "risk": req.risk_level.value,
        "action": req.action_name,
        "result_status": result_status,
        "error_summary": error_summary,
        "artifacts_created": artifacts_created or [],
    }
    try:
        with _log_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # never crash the main flow due to logging


def recent(limit: int = 20) -> list[dict]:
    p = _log_path()
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    entries = []
    for line in reversed(lines):
        if len(entries) >= limit:
            break
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries
