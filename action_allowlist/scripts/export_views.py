"""
export_views.py

Exports top_100_actions.json and action_checklist.json to CSV for
spreadsheet review.

Usage:
    python scripts/export_views.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

HERE = Path(__file__).parent.parent

EXPORTS = [
    (
        HERE / "top_100_actions.json",
        HERE / "top_100_actions.csv",
        [
            "rank", "action_id", "action_name", "action_category",
            "status", "execution_mode", "composite_score",
            "profit_impact_score", "value_score", "risk_score",
            "owner", "trigger_type", "estimated_hours_saved_per_month",
            "enabled",
        ],
    ),
    (
        HERE / "action_checklist.json",
        HERE / "action_checklist.csv",
        [
            "checklist_item_id", "action_id", "action_name",
            "task_type", "severity", "status", "assigned_to",
            "due_date", "blocker_type", "blocker_description",
        ],
    ),
]


def export(src: Path, dst: Path, fields: list[str]) -> None:
    if not src.exists():
        print(f"SKIP: {src} not found.")
        return
    data = json.loads(src.read_text())
    with dst.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)
    print(f"Exported {len(data)} rows → {dst}")


def main() -> None:
    for src, dst, fields in EXPORTS:
        export(src, dst, fields)


if __name__ == "__main__":
    main()
