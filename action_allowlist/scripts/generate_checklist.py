"""generate_checklist.py — auto-generate checklist items for incomplete actions."""
from __future__ import annotations
import json, uuid
from datetime import datetime, timezone
from pathlib import Path

def needs_checklist(action: dict) -> list:
    items = []
    def item(task_type, desc, severity="medium"):
        return {
            "checklist_item_id": f"CHK-{uuid.uuid4().hex[:8].upper()}",
            "action_id": action["action_id"],
            "task_type": task_type,
            "task_description": desc,
            "severity": severity,
            "status": "open",
            "assigned_to": action.get("owner","unassigned"),
            "blocker_type": None,
            "blocker_description": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "due_date": None,
            "dependency_ids": [],
            "resolution_notes": None,
        }
    if not action.get("trigger_definition"):
        items.append(item("define_trigger", f"Define trigger condition for {action['action_name']}", "high"))
    if not action.get("owner"):
        items.append(item("assign_owner", f"Assign owner for {action['action_name']}", "high"))
    if not action.get("approver") and action.get("execution_mode") in ("auto_execute","approval_required"):
        items.append(item("assign_approver", f"Assign approver for {action['action_name']}", "high"))
    if not action.get("success_metric"):
        items.append(item("define_success_metric", f"Define success metric for {action['action_name']}", "medium"))
    if not action.get("profit_impact_score"):
        items.append(item("quantify_profit_impact", f"Quantify profit impact for {action['action_name']}", "medium"))
    if action.get("status") == "proposed" and not items:
        items.append(item("approve_action", f"Review and approve {action['action_name']}", "low"))
    return items

def main():
    root = Path(__file__).parent.parent
    actions = json.loads((root / "top_100_actions.json").read_text())
    all_items = []
    for a in actions:
        all_items.extend(needs_checklist(a))
    out = root / "action_checklist.json"
    out.write_text(json.dumps(all_items, indent=2))
    print(f"Generated {len(all_items)} checklist items -> {out}")

if __name__ == "__main__":
    main()
