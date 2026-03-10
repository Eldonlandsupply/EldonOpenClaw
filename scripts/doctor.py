from __future__ import annotations

import sys
from pathlib import Path

# Allow running from repo root: python scripts/doctor.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.loader import load_settings


def main() -> None:
    s = load_settings()
    print("OK config loaded")
    print(f"chat_model={s.llm.chat_model}")
    print(f"embedding_model={s.llm.embedding_model or '(none)'}")
    print(f"memory_enabled={s.memory.enabled}")
    print(f"vector_store={s.memory.vector_store}")
    print(f"vector_store_path={s.memory.vector_store_path}")


if __name__ == "__main__":
    main()
