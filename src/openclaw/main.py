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

Security:
  - Cross-connector deduplication (content hash, 60s window)
  - Per-connector health monitoring — alerts admin via Telegram if a connector
    fails consecutively for more than MAX_CONNECTOR_FAILURES ticks
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import signal
import sys
import time
from collections import defaultdict
from typing import Optional

from openclaw import __version__
from openclaw.actions.registry import ActionRegistry
from openclaw.chat.client import ChatClient
from openclaw.config import get_config, reset_config
from openclaw.connectors.cli import CLIConnector
from openclaw.health import mark_degraded, record_tick, start_health_server
from openclaw.logging import configure_logging, get_logger
from openclaw.memory.sqlite import SQLiteMemory

logger = get_logger(__name__)
_shutdown = asyncio.Event()
_reload   = asyncio.Event()

# ── Deduplication ─────────────────────────────────────────────────────────

_DEDUP_WINDOW_S = 60   # seconds; discard messages seen within this window


class MessageDeduplicator:
    """Cross-connector, time-windowed message deduplication."""

    def __init__(self, window_s: int = _DEDUP_WINDOW_S) -> None:
        self._window = window_s
        self._seen: dict[str, float] = {}   # hash → timestamp

    def _key(self, connector: str, text: str) -> str:
        # Include source connector so the same text on different connectors
        # is NOT deduplicated (it could be intentional).
        # Within the same connector, identical text within the window IS deduped.
        raw = f"{connector}:{text}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def is_duplicate(self, connector: str, text: str) -> bool:
        now = time.monotonic()
        key = self._key(connector, text)
        # Expire old entries
        self._seen = {k: v for k, v in self._seen.items() if now - v < self._window}
        if key in self._seen:
            return True
        self._seen[key] = now
        return False


# ── Connector health monitor ───────────────────────────────────────────────

MAX_CONNECTOR_FAILURES = 5   # consecutive poll errors before alert


class ConnectorHealth:
    def __init__(self) -> None:
        self._failures: dict[str, int] = defaultdict(int)
        self._alerted:  set[str]       = set()

    def record_ok(self, name: str) -> None:
        self._failures[name] = 0
        self._alerted.discard(name)

    def record_failure(self, name: str) -> bool:
        """Returns True if this failure crosses the alert threshold."""
        self._failures[name] += 1
        if self._failures[name] >= MAX_CONNECTOR_FAILURES and name not in self._alerted:
            self._alerted.add(name)
            return True
        return False


# ── Signal handling ───────────────────────────────────────────────────────

def _handle_signal(sig: signal.Signals) -> None:
    logger.info("signal received", extra={"signal": sig.name})
    if sig == signal.SIGHUP:
        _reload.set()
    else:
        _shutdown.set()


# ── Tick loop ─────────────────────────────────────────────────────────────

async def _tick_loop(interval: int) -> None:
    while not _shutdown.is_set():
        record_tick()
        logger.info("tick")
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


# ── Message dispatch ──────────────────────────────────────────────────────

class Dispatcher:
    """
    Stateless message router. Encapsulates all routing logic so that
    _message_loop stays clean and this class can be unit-tested independently.
    """

    def __init__(
        self,
        registry: ActionRegistry,
        memory: SQLiteMemory,
        chat_client: ChatClient,
    ) -> None:
        self._registry    = registry
        self._memory      = memory
        self._chat_client = chat_client

    async def handle(self, connector_name: str, chat_id: Optional[str], text: str) -> str:
        """Route a message and return the reply string."""
        parts       = text.split(None, 1)
        action_name = parts[0].lower()
        args        = parts[1] if len(parts) > 1 else ""

        # ── built-in: memory_read ──────────────────────────────────────
        if action_name == "memory_read" and self._registry.is_allowed("memory_read"):
            key = args.strip()
            if key:
                value = await self._memory.get(key)
                reply = value if value is not None else f"(no value stored for key: {key!r})"
            else:
                keys  = await self._memory.list_keys()
                reply = "Stored keys: " + ", ".join(keys) if keys else "(no keys stored)"
            await self._memory.log_event(connector_name, "memory_read",
                                          json.dumps({"key": key}))
            return reply

        # ── built-in: memory_write ─────────────────────────────────────
        if action_name == "memory_write" and self._registry.is_allowed("memory_write"):
            if "=" in args:
                key, _, val = args.partition("=")
                await self._memory.set(key.strip(), val.strip())
                reply = f"stored: {key.strip()!r}"
            else:
                reply = "ERROR: memory_write requires key=value syntax"
            await self._memory.log_event(connector_name, "memory_write",
                                          json.dumps({"args": args}))
            return reply

        # ── built-in: /reset ────────────────────────────────────────────
        if text.strip().lower() in ("/reset", "reset"):
            self._chat_client.reset()
            return "Conversation history cleared."

        # ── registered actions ──────────────────────────────────────────
        if self._registry.is_allowed(action_name):
            result = await self._registry.dispatch(action_name, args)
            await self._memory.log_event(
                connector_name, action_name,
                json.dumps({"args": args, "success": result.success,
                            "output": str(result.output)[:200]}),
            )
            return str(result.output) if result.success else f"ERROR: {result.error}"

        # ── LLM chat fallback ───────────────────────────────────────────
        reply = await self._chat_client.chat(text)
        await self._memory.log_event(
            connector_name, "chat",
            json.dumps({"input": text[:200], "reply": reply[:200]}),
        )
        return reply


# ── Message loop ──────────────────────────────────────────────────────────

async def _message_loop(
    connector,
    dispatcher: Dispatcher,
    dedup: MessageDeduplicator,
    health: ConnectorHealth,
    admin_connector=None,
) -> None:
    """Read messages from a connector, deduplicate, and dispatch."""
    async for msg in connector.messages():
        if _shutdown.is_set():
            break

        if not msg.text:
            continue

        # Cross-connector deduplication
        if dedup.is_duplicate(connector.name, msg.text):
            logger.info(
                "duplicate message suppressed",
                extra={"connector": connector.name, "text": msg.text[:80]},
            )
            continue

        logger.info(
            "message received",
            extra={"connector": connector.name, "text": msg.text[:200]},
        )

        try:
            reply = await dispatcher.handle(connector.name, msg.chat_id, msg.text)
            await connector.send(msg.chat_id, reply)
            health.record_ok(connector.name)
        except Exception as exc:
            logger.error(
                "connector dispatch error",
                extra={"connector": connector.name, "error": str(exc)},
                exc_info=True,
            )
            threshold_crossed = health.record_failure(connector.name)
            if threshold_crossed and admin_connector:
                try:
                    await admin_connector.send(
                        None,
                        f"[OpenClaw ALERT] Connector '{connector.name}' has failed "
                        f"{MAX_CONNECTOR_FAILURES} consecutive times. Last error: {exc}",
                    )
                except Exception:
                    pass
            mark_degraded(f"connector {connector.name} dispatch error: {exc}")


# ── Main ──────────────────────────────────────────────────────────────────

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
        logger.info(
            "Attio integration active",
            extra={"actions": ["attio_search", "attio_note", "attio_task",
                               "attio_tasks", "attio_upsert"]},
        )
    else:
        logger.info("Attio integration disabled — set ATTIO_API_KEY to enable")

    # ── Chat client ───────────────────────────────────────────────────────
    chat_client = ChatClient(cfg)

    # ── Health server ─────────────────────────────────────────────────────
    if cfg.health.enabled:
        await start_health_server(cfg.health.host, cfg.health.port)

    # ── Shared infrastructure ─────────────────────────────────────────────
    dedup      = MessageDeduplicator()
    con_health = ConnectorHealth()
    dispatcher = Dispatcher(registry, memory, chat_client)

    # ── Connectors ────────────────────────────────────────────────────────
    tasks:      list[asyncio.Task] = []
    connectors: list = []
    admin_tg = None   # Telegram connector used for admin alerts

    tasks.append(asyncio.create_task(_tick_loop(cfg.runtime.tick_seconds)))

    if cfg.connectors.cli.enabled:
        cli = CLIConnector(require_confirm=cfg.actions.require_confirm)
        await cli.start()
        connectors.append(cli)
        tasks.append(asyncio.create_task(
            _message_loop(cli, dispatcher, dedup, con_health)))
        logger.info(
            "CLI connector active",
            extra={"allowed_actions": registry.list_allowed(),
                   "llm_provider": cfg.llm.provider,
                   "chat_model": cfg.llm.chat_model},
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
        admin_tg = tg   # use Telegram for admin alerts
        tasks.append(asyncio.create_task(
            _message_loop(tg, dispatcher, dedup, con_health, admin_connector=tg)))
        logger.info("Telegram connector active", extra={"allowed_chat_ids": allowed})

    if cfg.secrets.gmail_user and cfg.secrets.gmail_app_password:
        from openclaw.connectors.gmail import GmailConnector
        gm = GmailConnector(
            user=cfg.secrets.gmail_user,
            app_password=cfg.secrets.gmail_app_password,
        )
        await gm.start()
        connectors.append(gm)
        tasks.append(asyncio.create_task(
            _message_loop(gm, dispatcher, dedup, con_health, admin_connector=admin_tg)))
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
        tasks.append(asyncio.create_task(
            _message_loop(ol, dispatcher, dedup, con_health, admin_connector=admin_tg)))
        logger.info("Outlook connector active",
                    extra={"user": cfg.secrets.outlook_user})

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
    await chat_client.close()
    await memory.close()
    logger.info("openclaw stopped cleanly")

    if not _shutdown.is_set():
        reset_config()
        await run(yaml_path)


def cli_entry() -> None:
    yaml_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    asyncio.run(run(yaml_path=yaml_path))


if __name__ == "__main__":
    cli_entry()
