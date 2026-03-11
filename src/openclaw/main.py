"""
OpenClaw main async loop.

Boot sequence:
  1. Load config (fatal on misconfiguration)
  2. Configure structured logging
  3. Init memory
  4. Start health server
  5. Init chat client
  6. Start connectors
  7. Run main tick loop + message dispatch loop

Signals:
  SIGINT / SIGTERM  — graceful shutdown
  SIGHUP            — reload config (restarts loop with fresh config)
"""

from __future__ import annotations

import asyncio
import json
import signal
import sys

from openclaw import __version__
from openclaw.actions.registry import ActionRegistry
from openclaw.chat.client import ChatClient
from openclaw.config import get_config, reset_config
from openclaw.connectors.cli import CLIConnector
from openclaw.health import record_tick, start_health_server
from openclaw.logging import configure_logging, get_logger
from openclaw.memory.sqlite import SQLiteMemory

logger = get_logger(__name__)
_shutdown = asyncio.Event()
_reload = asyncio.Event()


def _handle_signal(sig: signal.Signals) -> None:
    logger.info("signal received", extra={"signal": sig.name})
    if sig == signal.SIGHUP:
        _reload.set()
    else:
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
    chat_client: ChatClient,
) -> None:
    """Read messages from a connector, dispatch actions or send to LLM."""
    async for msg in connector.messages():
        if _shutdown.is_set():
            break

        if not msg.text:
            continue

        logger.info(
            "message received",
            extra={"connector": connector.name, "text": msg.text},
        )

        parts = msg.text.split(None, 1)
        action_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # ── built-in: memory_read ─────────────────────────────────────────
        if action_name == "memory_read" and registry.is_allowed("memory_read"):
            key = args.strip()
            if key:
                value = await memory.get(key)
                reply = value if value is not None else f"(no value stored for key: {key!r})"
            else:
                keys = await memory.list_keys()
                reply = "Stored keys: " + ", ".join(keys) if keys else "(no keys stored)"
            await connector.send(msg.chat_id, reply)
            await memory.log_event(
                source=connector.name,
                action=action_name,
                content=json.dumps({"key": args.strip()}),
            )
            continue

        # ── built-in: memory_write ────────────────────────────────────────
        if action_name == "memory_write" and registry.is_allowed("memory_write"):
            if "=" in args:
                key, _, val = args.partition("=")
                await memory.set(key.strip(), val.strip())
                reply = f"stored: {key.strip()!r}"
            else:
                reply = "ERROR: memory_write requires key=value syntax"
            await connector.send(msg.chat_id, reply)
            await memory.log_event(
                source=connector.name,
                action=action_name,
                content=json.dumps({"args": args}),
            )
            continue

        # ── built-in: /reset — clear chat history ─────────────────────────
        if msg.text.strip().lower() in ("/reset", "reset"):
            chat_client.reset()
            await connector.send(msg.chat_id, "Conversation history cleared.")
            continue

        # ── registered actions (allowlisted) ─────────────────────────────
        if registry.is_allowed(action_name):
            result = await registry.dispatch(action_name, args)
            await memory.log_event(
                source=connector.name,
                action=action_name,
                content=json.dumps({
                    "args": args,
                    "success": result.success,
                    "output": str(result.output),
                }),
            )
            reply = result.output if result.success else f"ERROR: {result.error}"
            await connector.send(msg.chat_id, str(reply))
            continue

        # ── LLM chat fallback ─────────────────────────────────────────────
        reply = await chat_client.chat(msg.text)
        await memory.log_event(
            source=connector.name,
            action="chat",
            content=json.dumps({"input": msg.text, "reply": reply[:200]}),
        )
        await connector.send(msg.chat_id, reply)


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

    # ── Memory ────────────────────────────────────────────────────────────
    memory = SQLiteMemory(db_path=cfg.secrets.sqlite_path)
    await memory.init()

    # ── Action registry ───────────────────────────────────────────────────
    registry = ActionRegistry(
        allowlist=cfg.actions.allowlist,
        dry_run=cfg.runtime.dry_run,
    )

    # ── Attio integration ─────────────────────────────────────────────────
    if cfg.secrets.attio_api_key:
        from openclaw.integrations.attio.actions import build_attio_actions
        for attio_action in build_attio_actions(cfg.secrets.attio_api_key):
            registry.register(attio_action)
        logger.info("Attio integration active — actions: attio_search, attio_note, attio_task, attio_tasks, attio_upsert")
    else:
        logger.info("Attio integration disabled — set ATTIO_API_KEY to enable")

    # ── Chat client ───────────────────────────────────────────────────────
    chat_client = ChatClient(cfg)

    # ── Health server ─────────────────────────────────────────────────────
    if cfg.health.enabled:
        await start_health_server(cfg.health.host, cfg.health.port)

    # ── Connectors ────────────────────────────────────────────────────────
    tasks: list[asyncio.Task] = []
    connectors: list[CLIConnector] = []

    tasks.append(asyncio.create_task(_tick_loop(cfg.runtime.tick_seconds)))

    if cfg.connectors.cli.enabled:
        cli = CLIConnector(require_confirm=cfg.actions.require_confirm)
        await cli.start()
        connectors.append(cli)
        tasks.append(asyncio.create_task(_message_loop(cli, registry, memory, chat_client)))
        logger.info(
            "CLI connector active",
            extra={
                "allowed_actions": registry.list_allowed(),
                "llm_provider": cfg.llm.provider,
                "chat_model": cfg.llm.chat_model,
            },
        )

    if cfg.connectors.telegram.enabled:
        from openclaw.connectors.telegram import TelegramConnector
        allowed = cfg.secrets.allowed_chat_ids
        tg = TelegramConnector(
            token=cfg.secrets.telegram_bot_token,
            allowed_chat_ids=allowed,
        )
        await tg.start()
        connectors.append(tg)
        tasks.append(asyncio.create_task(_message_loop(tg, registry, memory, chat_client)))
        logger.info("Telegram connector active", extra={"allowed_chat_ids": allowed})

    if cfg.secrets.gmail_user and cfg.secrets.gmail_app_password:
        from openclaw.connectors.gmail import GmailConnector
        gm = GmailConnector(
            user=cfg.secrets.gmail_user,
            app_password=cfg.secrets.gmail_app_password,
        )
        await gm.start()
        connectors.append(gm)
        tasks.append(asyncio.create_task(_message_loop(gm, registry, memory, chat_client)))
        logger.info("Gmail connector active", extra={"user": cfg.secrets.gmail_user})

    if (cfg.secrets.azure_tenant_id and cfg.secrets.azure_client_id
            and cfg.secrets.azure_client_secret and cfg.secrets.outlook_user):
        from openclaw.connectors.outlook import OutlookConnector
        ol = OutlookConnector(
            tenant_id=cfg.secrets.azure_tenant_id,
            client_id=cfg.secrets.azure_client_id,
            client_secret=cfg.secrets.azure_client_secret,
            user=cfg.secrets.outlook_user,
        )
        await ol.start()
        connectors.append(ol)
        tasks.append(asyncio.create_task(_message_loop(ol, registry, memory, chat_client)))
        logger.info("Outlook connector active", extra={"user": cfg.secrets.outlook_user})

    logger.info("openclaw running — Ctrl+C to stop | type /reset to clear history")

    # ── Signal handling ───────────────────────────────────────────────────
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(sig, _handle_signal, sig)

    done, _ = await asyncio.wait(
        [
            asyncio.create_task(_shutdown.wait()),
            asyncio.create_task(_reload.wait()),
        ],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if _reload.is_set() and not _shutdown.is_set():
        logger.info("SIGHUP received — reloading config")
        _reload.clear()

    logger.info("shutting down")
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    for c in connectors:
        await c.stop()
    await memory.close()
    logger.info("openclaw stopped cleanly")

    if not _shutdown.is_set():
        reset_config()
        await run(yaml_path)


def cli_entry() -> None:
    """Entry point for `openclaw` console script."""
    yaml_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    asyncio.run(run(yaml_path=yaml_path))


if __name__ == "__main__":
    cli_entry()
