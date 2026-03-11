"""
score_actions.py

Computes composite scores for all actions in top_100_actions.json.
Outputs updated scores in place.

Usage:
    python scripts/score_actions.py
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

ACTIONS_FILE = Path(__file__).parent.parent / "top_100_actions.json"
BACKLOG_FILE = Path(__file__).parent.parent / "action_backlog.json"

WEIGHTS = {
    "profit_impact_score": 2.5,
    "value_score": 2.0,
    "frequency_score": 1.5,
    "time_saved_score": 1.5,
    "confidence_score": 1.0,
    "risk_score": -2.0,
}
WEIGHT_SUM = sum(abs(v) for v in WEIGHTS.values())  # normalizer


def compute_composite(action: dict) -> float:
    raw = sum(
        action.get(field, 5) * weight
        for field, weight in WEIGHTS.items()
    )
    return round(raw / WEIGHT_SUM, 3)


DISQUALIFIERS = [
    lambda a: a.get("status") not in ("approved", "enabled"),
    lambda a: not a.get("owner"),
    lambda a: not a.get("trigger_definition"),
    lambda a: (a.get("execution_mode") == "auto_execute" and a.get("risk_score", 0) >= 7),
    lambda a: a.get("confidence_score", 10) <= 3,
]


def is_disqualified(action: dict) -> tuple[bool, str]:
    reasons = []
    if action.get("status") not in ("approved", "enabled"):
        reasons.append(f"status={action.get('status')} not in [approved, enabled]")
    if not action.get("owner"):
        reasons.append("missing owner")
    if not action.get("trigger_definition"):
        reasons.append("missing trigger_definition")
    if action.get("execution_mode") == "auto_execute" and action.get("risk_score", 0) >= 7:
        reasons.append("auto_execute with risk_score >= 7")
    if action.get("confidence_score", 10) <= 3:
        reasons.append("confidence_score <= 3")
    return (bool(reasons), "; ".join(reasons))


def main() -> None:
    if not ACTIONS_FILE.exists():
        print(f"ERROR: {ACTIONS_FILE} not found.")
        return

    actions = json.loads(ACTIONS_FILE.read_text())
    qualified = []
    disqualified = []

    for action in actions:
        score = compute_composite(action)
        action["composite_score"] = score
        dq, reason = is_disqualified(action)
        if dq:
            action["disqualification_reason"] = reason
            disqualified.append(action)
        else:
            qualified.append(action)

    # Sort qualified by composite_score desc, then by tiebreakers
    qualified.sort(
        key=lambda a: (
            -a["composite_score"],
            -a.get("profit_impact_score", 0),
            -a.get("frequency_score", 0),
            a.get("risk_score", 0),
        )
    )

    # Assign rank
    for i, action in enumerate(qualified, start=1):
        action["rank"] = i

    # Write back
    all_actions = qualified + disqualified
    ACTIONS_FILE.write_text(json.dumps(all_actions, indent=2))

    print(f"Scored {len(qualified)} qualified actions.")
    if disqualified:
        print(f"WARNING: {len(disqualified)} actions disqualified:")
        for a in disqualified:
            print(f"  [{a['action_id']}] {a['action_name']}: {a['disqualification_reason']}")

    # Update backlog with disqualified
    if disqualified:
        backlog = []
        if BACKLOG_FILE.exists():
            backlog = json.loads(BACKLOG_FILE.read_text())
        backlog_ids = {b["action_id"] for b in backlog}
        for a in disqualified:
            if a["action_id"] not in backlog_ids:
                backlog.append({
                    "action_id": a["action_id"],
                    "action_name": a["action_name"],
                    "disqualification_reason": a.get("disqualification_reason", ""),
                    "added_at": datetime.now(timezone.utc).isoformat(),
                })
        BACKLOG_FILE.write_text(json.dumps(backlog, indent=2))
        print(f"Backlog updated: {len(backlog)} total entries.")


if __name__ == "__main__":
    main()
