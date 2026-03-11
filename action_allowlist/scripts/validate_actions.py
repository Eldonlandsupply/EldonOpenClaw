"""validate_actions.py — validate actions against schema."""
from __future__ import annotations
import json, sys
from pathlib import Path

REQUIRED = ["action_id","action_name","action_category","execution_mode","status","trigger_type","owner","risk_score","enabled"]
VALID_CATEGORIES = {"ceo_leverage","revenue_acceleration","admin_elimination","execution_control"}
VALID_MODES = {"auto_execute","draft_then_review","recommend_only","approval_required","manual_only"}
VALID_STATUSES = {"proposed","under_review","approved","enabled","paused","deprecated","rejected","archived"}

def validate(action: dict) -> list:
    errors = []
    for f in REQUIRED:
        if f not in action:
            errors.append(f"Missing required field: {f}")
    if action.get("action_category") not in VALID_CATEGORIES:
        errors.append(f"Invalid category: {action.get('action_category')}")
    if action.get("execution_mode") not in VALID_MODES:
        errors.append(f"Invalid execution_mode: {action.get('execution_mode')}")
    if action.get("status") not in VALID_STATUSES:
        errors.append(f"Invalid status: {action.get('status')}")
    if action.get("risk_score", 0) >= 8 and action.get("execution_mode") == "auto_execute":
        errors.append("High-risk action cannot be auto_execute")
    return errors

def main():
    root = Path(__file__).parent.parent
    actions = json.loads((root / "top_100_actions.json").read_text())
    total_errors = 0
    for a in actions:
        errs = validate(a)
        if errs:
            print(f"FAIL {a.get('action_id','?')} {a.get('action_name','?')}")
            for e in errs:
                print(f"     {e}")
            total_errors += len(errs)
    if total_errors == 0:
        print(f"OK — all {len(actions)} actions valid")
    else:
        print(f"\n{total_errors} validation errors across {len(actions)} actions")
        sys.exit(1)

if __name__ == "__main__":
    main()
