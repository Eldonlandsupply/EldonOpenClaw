"""
scripts/doctor.py — OpenClaw config sanity check.

Uses the canonical runtime config (src/openclaw/config.AppConfig),
which is the same system the live process uses. A passing doctor
means the live config is valid — not just a separate schema.

Usage:
  python scripts/doctor.py [config.yaml]
"""
from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
_repo_src  = _repo_root / "src"
if str(_repo_src) not in sys.path:
    sys.path.insert(0, str(_repo_src))

from openclaw.config import AppConfig  # noqa: E402


def main() -> None:
    yaml_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    # AppConfig calls sys.exit(1) on fatal misconfiguration — that IS the
    # fail-fast behaviour the CI golden-path test expects.
    cfg = AppConfig(yaml_path=yaml_path)
    print("OK config loaded")
    print(f"provider={cfg.llm.provider}")
    print(f"chat_model={cfg.llm.chat_model}")
    print(f"embedding_model={cfg.llm.embedding_model or '(none)'}")
    print(f"dry_run={cfg.runtime.dry_run}")
    print(f"connector_cli={cfg.connectors.cli.enabled}")
    print(f"connector_telegram={cfg.connectors.telegram.enabled}")
    print(f"health_port={cfg.health.port}")
    print(f"sqlite_path={cfg.secrets.sqlite_path}")
    print(f"attio_api_key={'SET' if cfg.secrets.attio_api_key else 'NOT SET'}")
    print(f"openrouter_api_key={'SET' if cfg.secrets.openrouter_api_key else 'NOT SET'}")


if __name__ == "__main__":
    main()
