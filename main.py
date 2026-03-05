"""
main.py — EldonOpenClaw entry point
"""
from __future__ import annotations

import asyncio
import logging
import sys

from src.config import load_settings


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )


async def main() -> None:
    settings = load_settings()

    _setup_logging(settings.app.log_level)
    log = logging.getLogger("openclaw")

    log.info("OpenClaw starting — env=%s", settings.app.env)
    log.info("LLM: chat_model=%s embed_model=%s",
             settings.llm.chat_model,
             settings.llm.embedding_model or "(none)")
    log.info("Connectors: cli=%s telegram=%s voice=%s",
             settings.connectors.cli,
             settings.connectors.telegram,
             settings.connectors.voice)
    log.info("Memory: enabled=%s", settings.memory.enabled)
    log.info("Actions: require_confirmation=%s", settings.actions.require_confirmation)

    # OPEN_ITEM: connector dispatch lives here once connectors are implemented
    log.warning("No connectors implemented yet — OPEN_ITEM: src/connectors/")


if __name__ == "__main__":
    asyncio.run(main())
