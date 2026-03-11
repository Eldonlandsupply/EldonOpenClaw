"""
Agent creation handler.
Produces structured YAML agent specs stored under agents/.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


AGENTS_DIR = os.getenv("AGENTS_DIR", "./agents")


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:40]


def _infer_spec(description: str) -> dict:
    desc_lower = description.lower()

    trigger = "manual"
    if "schedule" in desc_lower or "daily" in desc_lower or "every" in desc_lower:
        trigger = "schedule"
    elif "inbox" in desc_lower or "email" in desc_lower:
        trigger = "email_ingest"
    elif "webhook" in desc_lower:
        trigger = "webhook"

    allowed_tools = ["memory_read", "memory_write", "echo"]
    if "email" in desc_lower or "inbox" in desc_lower:
        allowed_tools.append("email_read")
    if "crm" in desc_lower or "follow" in desc_lower:
        allowed_tools.append("crm_query")
    if "summary" in desc_lower or "brief" in desc_lower:
        allowed_tools.append("llm_summarize")

    return {
        "trigger": trigger,
        "allowed_tools": allowed_tools,
    }


async def handle_create_agent(description: str = "", **kwargs: Any) -> str:
    if not description:
        return "ERROR: Provide a description, e.g.: create agent that watches inbox"

    slug = _slugify(description)
    agent_id = f"agent-{slug}-{uuid.uuid4().hex[:6]}"
    inferred = _infer_spec(description)

    spec = {
        "schema_version": "1.0",
        "id": agent_id,
        "name": slug,
        "purpose": description,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "trigger": inferred["trigger"],
        "inputs": ["text"],
        "outputs": ["text", "event_log"],
        "allowed_tools": inferred["allowed_tools"],
        "permissions": ["memory_read", "memory_write"],
        "schedule": None,
        "escalation": {
            "on_failure": "log_and_notify",
            "max_retries": 3,
        },
        "failure_behavior": "log_error_and_halt",
        "status": "draft",
    }

    agents_dir = Path(AGENTS_DIR)
    agents_dir.mkdir(parents=True, exist_ok=True)
    out_path = agents_dir / f"{agent_id}.yaml"
    out_path.write_text(yaml.dump(spec, default_flow_style=False, sort_keys=False))

    return (
        f"Agent spec created: {out_path}\n"
        f"ID: {agent_id}\n"
        f"Trigger: {inferred['trigger']}\n"
        f"Tools: {', '.join(inferred['allowed_tools'])}\n"
        f"Edit {out_path} to refine before activating."
    )
