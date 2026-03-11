"""export_views.py — export actions to CSV for spreadsheet review."""
from __future__ import annotations
import csv, json
from pathlib import Path

def export_csv(actions, out_path):
    if not actions:
        return
    keys = ["rank","action_id","action_name","action_category","execution_mode","status",
            "composite_score","profit_impact_score","time_saved_score","risk_score","owner","enabled"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(actions)
    print(f"Exported {len(actions)} rows -> {out_path}")

def main():
    root = Path(__file__).parent.parent
    actions = json.loads((root / "top_100_actions.json").read_text())
    export_csv(actions, root / "top_100_actions.csv")

    checklist = json.loads((root / "action_checklist.json").read_text()) if (root / "action_checklist.json").exists() else []
    if checklist:
        keys = ["checklist_item_id","action_id","task_type","task_description","severity","status","assigned_to"]
        with open(root / "action_checklist.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(checklist)
        print(f"Exported {len(checklist)} checklist rows -> action_checklist.csv")

if __name__ == "__main__":
    main()
