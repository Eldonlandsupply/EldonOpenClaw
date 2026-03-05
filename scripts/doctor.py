"""
scripts/doctor.py — Validate config without starting the full runtime.
Run: python scripts/doctor.py

Expected output on success:
  ✓ Config loaded successfully
  chat_model    = <your-model>
  embed_model   = <your-model or (none)>
  memory        = false
  connectors    = cli=True telegram=False voice=False
  action_confirm= True
"""
import sys
from pathlib import Path

# Make project root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings  # noqa: E402


def main() -> None:
    try:
        s = load_settings()
    except Exception as exc:
        print(f"\n✗ Config FAILED:\n\n{exc}\n", file=sys.stderr)
        sys.exit(1)

    print("✓ Config loaded successfully")
    print(f"  env           = {s.app.env}")
    print(f"  log_level     = {s.app.log_level}")
    print(f"  chat_model    = {s.llm.chat_model}")
    print(f"  embed_model   = {s.llm.embedding_model or '(none)'}")
    print(f"  base_url      = {s.llm.base_url or '(default)'}")
    print(f"  memory        = {s.memory.enabled}")
    print(f"  connectors    = cli={s.connectors.cli} "
          f"telegram={s.connectors.telegram} voice={s.connectors.voice}")
    print(f"  action_confirm= {s.actions.require_confirmation}")


if __name__ == "__main__":
    main()
