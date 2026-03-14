from __future__ import annotations

from src.config.loader import load_settings


def main() -> None:
    s = load_settings()
    print("OK config loaded")
    print(f"provider={s.llm.provider}")
    print(f"chat_model={s.llm.chat_model}")
    print(f"embedding_model={s.llm.embedding_model or '(none)'}")
    print(f"memory_enabled={s.memory.enabled}")
    print(f"vector_store={s.memory.vector_store}")
    print(f"vector_store_path={s.memory.vector_store_path}")
    print(f"connectors: cli={s.connectors.cli} telegram={s.connectors.telegram} voice={s.connectors.voice}")


if __name__ == "__main__":
    main()
