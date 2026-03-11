"""
generate_checklist.py

For every action in action_backlog.json or any action missing required fields,
generate structured checklist items in action_checklist.json.

Usage:
    python scripts/generate_checklist.py
"""

from __future__ import annotations

import json
from datetime import datetime, date, timezone, timedelta
from pathlib import Path

ACTIONS_FILE   = Path(__file__).parent.parent / "top_100_actions.json"
BACKLOG_FILE   = Path(__file__).parent.parent / "action_backlog.json"
CHECKLIST_FILE = Path(__file__).parent.parent / "action_checklist.json"
CANDIDATES_FILE = Path(__file__).parent.parent / "action_candidates.json"


REQUIRED_FIELDS = [
    ("owner",               "assign_owner",        "critical"),
    ("trigger_definition",  "define_trigger",      "critical"),
    ("success_metric",      "define_success_metric","high"),
    ("failure_metric",      "define_failure_metric","high"),
    ("approver",            "assign_approver",     "medium"),
    ("system_dependencies", "confirm_dependencies","medium"),
    ("required_inputs",     "confirm_inputs",      "medium"),
    ("estimated_hours_saved_per_month", "quantify_time_savings", "low"),
]


def checklist_id(action_id: str, task_type: str) -> str:
    return f"CL-{abs(hash(action_id + task_type)) % 100000:05d}"


def due_date_for_severity(severity: str) -> str:
    days = {"critical": 3, "high": 7, "medium": 14, "low": 30}
    d = date.today() + timedelta(days=days.get(severity, 14))
    return d.isoformat()


def generate_for_action(action: dict) -> list[dict]:
    items = []
    action_id = action.get("action_id", "UNKNOWN")
    action_name = action.get("action_name", "")

    for field, task_type, severity in REQUIRED_FIELDS:
        val = action.get(field)
        if not val or (isinstance(val, list) and len(val) == 0):
            items.append({
                "checklist_item_id": checklist_id(action_id, task_type),
                "action_id": action_id,
                "action_name": action_name,
                "task_type": task_type,
                "task_description": f"Action {action_id} is missing '{field}'. Define this before enabling.",
                "severity": severity,
                "status": "open",
                "assigned_to": "CEO" if severity == "critical" else "Operations",
                "blocker_type": "missing_definition",
                "blocker_description": f"Field '{field}' is null or empty",
                "evidence_needed": f"Confirmed value for '{field}'",
                "required_integration": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "due_date": due_date_for_severity(severity),
                "dependency_ids": [],
                "resolution_notes": "",
            })

    # Check for auto_execute with high risk
    if action.get("execution_mode") == "auto_execute" and action.get("risk_score", 0) >= 5:
        items.append({
            "checklist_item_id": checklist_id(action_id, "validate_execution_mode"),
            "action_id": action_id,
            "action_name": action_name,
            "task_type": "validate_execution_mode",
            "task_description": f"Action {action_id} is set to auto_execute but has risk_score={action.get('risk_score')}. CEO must review and confirm.",
            "severity": "critical",
            "status": "open",
            "assigned_to": "CEO",
            "blocker_type": "risk_review",
            "blocker_description": f"auto_execute mode with risk_score={action.get('risk_score')}",
            "evidence_needed": "CEO written confirmation",
            "required_integration": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "due_date": due_date_for_severity("critical"),
            "dependency_ids": [],
            "resolution_notes": "",
        })

    return items


def generate_for_candidate(candidate: dict) -> list[dict]:
    """Generate formalization checklist for a candidate action."""
    cid = candidate.get("candidate_id", "CAND-????")
    label = candidate.get("pattern_label", "unknown")
    return [
        {
            "checklist_item_id": checklist_id(cid, "formalize_candidate"),
            "action_id": cid,
            "action_name": f"[CANDIDATE] {label}",
            "task_type": "formalize_candidate",
            "task_description": f"Pattern '{label}' has been detected {candidate.get('detection_count', '?')} times. Evaluate for formalization as an approved action.",
            "severity": "medium",
            "status": "open",
            "assigned_to": "CEO",
            "blocker_type": "needs_definition",
            "blocker_description": "Candidate action lacks required fields for formal approval",
            "evidence_needed": "Completed action record with all required fields",
            "required_integration": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "due_date": due_date_for_severity("medium"),
            "dependency_ids": [],
            "resolution_notes": "",
        }
    ]


def main() -> None:
    all_items: list[dict] = []
    existing_ids: set[str] = set()

    if CHECKLIST_FILE.exists():
        existing = json.loads(CHECKLIST_FILE.read_text())
        # Keep only open items; resolved items stay but don't get regenerated
        for item in existing:
            existing_ids.add(item["checklist_item_id"])
            all_items.append(item)

    # Generate from actions with missing fields
    if ACTIONS_FILE.exists():
        actions = json.loads(ACTIONS_FILE.read_text())
        for action in actions:
            for item in generate_for_action(action):
                if item["checklist_item_id"] not in existing_ids:
                    all_items.append(item)
                    existing_ids.add(item["checklist_item_id"])

    # Generate from candidates
    if CANDIDATES_FILE.exists():
        candidates = json.loads(CANDIDATES_FILE.read_text())
        for cand in candidates:
            if cand.get("status") == "proposed":
                for item in generate_for_candidate(cand):
                    if item["checklist_item_id"] not in existing_ids:
                        all_items.append(item)
                        existing_ids.add(item["checklist_item_id"])

    CHECKLIST_FILE.write_text(json.dumps(all_items, indent=2))

    open_items = [i for i in all_items if i.get("status") == "open"]
    critical   = [i for i in open_items if i.get("severity") == "critical"]

    print(f"Checklist updated: {len(all_items)} total items, {len(open_items)} open.")
    if critical:
        print(f"CRITICAL: {len(critical)} critical items require immediate attention:")
        for item in critical:
            print(f"  [{item['checklist_item_id']}] [{item['action_id']}] {item['task_description'][:80]}")


if __name__ == "__main__":
    main()
