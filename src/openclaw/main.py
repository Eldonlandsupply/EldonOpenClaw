"""
OpenClaw main async loop.

Boot sequence:
  1. Load config (fatal on misconfiguration)
  2. Configure structured logging
  3. Init memory
  4. Start health server
  5. Start connectors
  6. Run main tick loop + message dispatch loop
"""

from __future__ import annotations

import asyncio
import json
import signal
import sys
from typing import Optional

from openclaw import __version__
from openclaw.actions.registry import ActionRegistry
from openclaw.config import get_config
from openclaw.connectors.cli import CLIConnector
from openclaw.health import record_tick, start_health_server
from openclaw.logging import configure_logging, get_logger
from openclaw.memory.sqlite import SQLiteMemory

logger = get_logger(__name__)
_shutdown = asyncio.Event()


def _handle_signal(sig: signal.Signals) -> None:
    logger.info("shutdown signal received", extra={"signal": sig.name})
    _shutdown.set()


async def _tick_loop(interval: int) -> None:
    """Heartbeat: runs every tick_seconds, updates health state."""
    while not _shutdown.is_set():
        record_tick()
        logger.info("tick")
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


async def _message_loop(
    connector: CLIConnector,
    registry: ActionRegistry,
    memory: SQLiteMemory,
) -> None:
    """Read messages from a connector, parse and dispatch actions."""
    async for msg in connector.messages():
        if _shutdown.is_set():
            break

        logger.info(
            "message received",
            extra={"connector": connector.name, "text": msg.text},
        )

        # Simple dispatch: first word = action name, rest = args
        parts = msg.text.split(None, 1)
        action_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        result = await registry.dispatch(action_name, args)

        # Persist to event log
        await memory.log_event(
            source=connector.name,
            action=action_name,
            content=json.dumps({"args": args, "success": result.success, "output": str(result.output)}),
        )

        reply = result.output if result.success else f"ERROR: {result.error}"
        await connector.send(msg.chat_id, str(reply))


async def run(yaml_path: str = "config.yaml") -> None:
    cfg = get_config(yaml_path)
    configure_logging(cfg.runtime.log_level)

    logger.info(
        "openclaw starting",
        extra={"version": __version__, "config": cfg.summary()},
    )

    if cfg.runtime.dry_run:
        logger.warning(
            "DRY RUN MODE ACTIVE — actions will be logged but not executed. "
            "Set runtime.dry_run: false in config.yaml when ready."
        )

    # ── Memory ───────────────────────────────────────────────────────────
    memory = SQLiteMemory(db_path=cfg.secrets.sqlite_path)
    await memory.init()

    # ── Action registry ───────────────────────────────────────────────────
    registry = ActionRegistry(
        allowlist=cfg.actions.allowlist,
        dry_run=cfg.runtime.dry_run,
    )

    # ── Health server ─────────────────────────────────────────────────────
    if cfg.health.enabled:
        await start_health_server(cfg.health.host, cfg.health.port)

    # ── Connectors ────────────────────────────────────────────────────────
    tasks: list[asyncio.Task] = []

    tasks.append(asyncio.create_task(_tick_loop(cfg.runtime.tick_seconds)))

    if cfg.connectors.cli.enabled:
        cli = CLIConnector(require_confirm=cfg.actions.require_confirm)
        await cli.start()
        tasks.append(asyncio.create_task(_message_loop(cli, registry, memory)))
        logger.info("CLI connector active")

    # OPEN_ITEM: Telegram connector — enabled behind feature flag
    if cfg.connectors.telegram.enabled:
        logger.warning(
            "OPEN_ITEM: Telegram connector is enabled in config but not yet implemented. "
            "Install 'openclaw[telegram]' and wire TelegramConnector to activate."
        )

    logger.info("openclaw running — Ctrl+C to stop")

    # ── Shutdown wiring ───────────────────────────────────────────────────
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal, sig)

    await _shutdown.wait()

    logger.info("shutting down")
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await memory.close()
    logger.info("openclaw stopped cleanly")


def cli_entry() -> None:
    """Entry point for `openclaw` console script."""
    yaml_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    asyncio.run(run(yaml_path=yaml_path))


if __name__ == "__main__":
    cli_entry()
