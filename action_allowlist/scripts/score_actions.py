"""score_actions.py — compute composite scores and rank all actions."""
from __future__ import annotations
import json
from pathlib import Path

WEIGHTS = {
    "profit_impact_score": 0.30,
    "time_saved_score":    0.20,
    "frequency_score":     0.15,
    "value_score":         0.15,
    "confidence_score":    0.10,
    "risk_inverted":       0.10,
}

def score(action: dict) -> float:
    base = (
        action.get("profit_impact_score", 5) * WEIGHTS["profit_impact_score"]
        + action.get("time_saved_score",   5) * WEIGHTS["time_saved_score"]
        + action.get("frequency_score",    5) * WEIGHTS["frequency_score"]
        + action.get("value_score",        5) * WEIGHTS["value_score"]
        + action.get("confidence_score",   5) * WEIGHTS["confidence_score"]
        + (10 - action.get("risk_score",   5)) * WEIGHTS["risk_inverted"]
    )
    if action.get("execution_mode") == "manual_only": base -= 2.0
    if not action.get("owner"):                       base -= 1.5
    if not action.get("trigger_definition"):          base -= 1.0
    return round(max(base, 0), 3)

def rank_actions(actions):
    for a in actions:
        a["composite_score"] = score(a)
    ranked = sorted(actions, key=lambda x: x["composite_score"], reverse=True)
    for i, a in enumerate(ranked, 1):
        a["rank"] = i
    return ranked

def main():
    root = Path(__file__).parent.parent
    src = root / "top_100_actions.json"
    actions = json.loads(src.read_text())
    ranked = rank_actions(actions)
    src.write_text(json.dumps(ranked, indent=2))
    print(f"Scored and ranked {len(ranked)} actions.")
    for a in ranked[:10]:
        print(f"  #{a['rank']:>3}  {a['composite_score']:.2f}  {a['action_name']}")

if __name__ == "__main__":
    main()
