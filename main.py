"""
main.py — thin shim for running OpenClaw from the repo root.

Prefer using the package entry point:
    python -m openclaw.main [config.yaml]

Or the installed console script:
    openclaw [config.yaml]
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is importable when running as `python main.py`
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from openclaw.main import cli_entry  # noqa: E402

if __name__ == "__main__":
    cli_entry()
