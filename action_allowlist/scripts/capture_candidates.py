"""capture_candidates.py — append a new candidate action to the backlog."""
from __future__ import annotations
import json, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

def capture(name: str, description: str, category: str = "admin_elimination", source: str = "manual"):
    root = Path(__file__).parent.parent
    backlog_file = root / "action_backlog.json"
    backlog = json.loads(backlog_file.read_text()) if backlog_file.exists() else []
    candidate = {
        "candidate_id": f"CAND-{uuid.uuid4().hex[:8].upper()}",
        "action_name": name,
        "action_description": description,
        "suggested_category": category,
        "source": source,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": "backlog",
        "notes": "",
    }
    backlog.append(candidate)
    backlog_file.write_text(json.dumps(backlog, indent=2))
    print(f"Captured candidate: {candidate['candidate_id']} — {name}")
    return candidate

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: capture_candidates.py 'Action Name' 'Description' [category]")
        sys.exit(1)
    name = sys.argv[1]
    desc = sys.argv[2]
    cat  = sys.argv[3] if len(sys.argv) > 3 else "admin_elimination"
    capture(name, desc, cat)
