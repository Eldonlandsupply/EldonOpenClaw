"""
validate_actions.py

Validates all actions in top_100_actions.json against action_schema.json.
Fails loudly with detailed error output.

Usage:
    python scripts/validate_actions.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install jsonschema --break-system-packages")
    sys.exit(1)

ACTIONS_FILE = Path(__file__).parent.parent / "top_100_actions.json"
SCHEMA_FILE  = Path(__file__).parent.parent / "action_schema.json"


def main() -> None:
    if not ACTIONS_FILE.exists():
        print(f"ERROR: {ACTIONS_FILE} not found.")
        sys.exit(1)
    if not SCHEMA_FILE.exists():
        print(f"ERROR: {SCHEMA_FILE} not found.")
        sys.exit(1)

    schema  = json.loads(SCHEMA_FILE.read_text())
    actions = json.loads(ACTIONS_FILE.read_text())

    errors = 0
    for action in actions:
        try:
            jsonschema.validate(instance=action, schema=schema)
        except jsonschema.ValidationError as e:
            print(f"FAIL [{action.get('action_id', '???')}] {action.get('action_name', '???')}")
            print(f"     {e.message}")
            errors += 1

    if errors == 0:
        print(f"OK: All {len(actions)} actions pass schema validation.")
    else:
        print(f"\nFAILED: {errors} validation errors found.")
        sys.exit(1)


if __name__ == "__main__":
    main()
