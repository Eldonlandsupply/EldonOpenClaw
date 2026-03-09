"""
scripts/doctor.py — Validate runtime config without starting the full agent.

Run from repo root:
    python scripts/doctor.py [config.yaml]

Exit 0 = config is valid. Exit 1 = misconfiguration found.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make src/ importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openclaw.config import AppConfig, reset_config  # noqa: E402


def main() -> None:
    yaml_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"

    reset_config()  # ensure fresh load even if called multiple times
    try:
        cfg = AppConfig(yaml_path=yaml_path)
    except SystemExit:
        # AppConfig calls sys.exit(1) on fatal errors — already printed message
        sys.exit(1)
    except Exception as exc:
        print(f"\n✗ Config FAILED: {exc}\n", file=sys.stderr)
        sys.exit(1)

    print("✓ Config loaded successfully\n")
    summary = cfg.summary()
    print(json.dumps(summary, indent=2))

    print("\n--- Quick checks ---")
    print(f"  dry_run       = {cfg.runtime.dry_run}"
          + (" ← WARN: agent will not execute actions" if cfg.runtime.dry_run else " ✓"))
    print(f"  provider      = {cfg.llm.provider}")
    print(f"  chat_model    = {cfg.llm.chat_model}")
    print(f"  health        = {cfg.health.host}:{cfg.health.port}")
    print(f"  sqlite_path   = {cfg.secrets.sqlite_path}")

    openrouter_set = bool(cfg.secrets.openrouter_api_key)
    openai_set = bool(cfg.secrets.openai_api_key)
    print(f"  OPENROUTER_API_KEY = {'SET ✓' if openrouter_set else 'NOT SET'}")
    print(f"  OPENAI_API_KEY     = {'SET ✓' if openai_set else 'NOT SET'}")
    print(f"  GMAIL_USER         = {cfg.secrets.gmail_user or 'NOT SET'}")
    print(f"  NOTIFICATION_EMAIL = {cfg.secrets.notification_email or 'NOT SET'}")

    print("\n✓ doctor done — no fatal errors found")


if __name__ == "__main__":
    main()
