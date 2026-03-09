"""
SQLite-backed memory store. Thread-safe via asyncio.to_thread.
Schema: key-value store + append-only event log with index and auto-trim.
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from openclaw.logging import get_logger

logger = get_logger(__name__)

_EVENT_LOG_MAX_ROWS = 10_000
_EVENT_LOG_TRIM_TO = 8_000


def _require_init(conn: Optional[sqlite3.Connection]) -> sqlite3.Connection:
    if conn is None:
        raise RuntimeError(
            "SQLiteMemory.init() has not been called. "
            "Await memory.init() before using the memory store."
        )
    return conn


class SQLiteMemory:
    def __init__(self, db_path: str = "./data/openclaw.db") -> None:
        self._path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._event_count = 0

    async def init(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._sync_init)
        logger.info("SQLite memory initialized", extra={"path": self._path})

    def _sync_init(self) -> None:
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kv (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source    TEXT,
                action    TEXT,
                content   TEXT
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_event_log_id ON event_log(id DESC)"
        )
        # Index for filtering events by action name (used by search_events)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_event_log_action ON event_log(action)"
        )
        self._conn.commit()
        row = self._conn.execute("SELECT COUNT(*) FROM event_log").fetchone()
        self._event_count = row[0] if row else 0

    # ── KV store ──────────────────────────────────────────────────────────

    async def set(self, key: str, value: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await asyncio.to_thread(self._sync_set, key, value, now)

    def _sync_set(self, key: str, value: str, now: str) -> None:
        conn = _require_init(self._conn)
        conn.execute(
            "INSERT OR REPLACE INTO kv (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now),
        )
        conn.commit()

    async def get(self, key: str) -> Optional[str]:
        return await asyncio.to_thread(self._sync_get, key)

    def _sync_get(self, key: str) -> Optional[str]:
        conn = _require_init(self._conn)
        row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._sync_delete, key)

    def _sync_delete(self, key: str) -> None:
        conn = _require_init(self._conn)
        conn.execute("DELETE FROM kv WHERE key = ?", (key,))
        conn.commit()

    async def list_keys(self, prefix: str = "") -> list[str]:
        """Return all KV keys, optionally filtered by prefix."""
        return await asyncio.to_thread(self._sync_list_keys, prefix)

    def _sync_list_keys(self, prefix: str) -> list[str]:
        conn = _require_init(self._conn)
        if prefix:
            rows = conn.execute(
                "SELECT key FROM kv WHERE key LIKE ? ORDER BY key",
                (prefix + "%",),
            ).fetchall()
        else:
            rows = conn.execute("SELECT key FROM kv ORDER BY key").fetchall()
        return [r[0] for r in rows]

    # ── Event log ─────────────────────────────────────────────────────────

    async def log_event(self, source: str, action: str, content: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await asyncio.to_thread(self._sync_log, now, source, action, content)

    def _sync_log(self, now: str, source: str, action: str, content: str) -> None:
        conn = _require_init(self._conn)
        conn.execute(
            "INSERT INTO event_log (timestamp, source, action, content) VALUES (?, ?, ?, ?)",
            (now, source, action, content),
        )
        conn.commit()
        self._event_count += 1
        if self._event_count > _EVENT_LOG_MAX_ROWS:
            self._sync_trim(conn)

    def _sync_trim(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "DELETE FROM event_log WHERE id NOT IN "
            "(SELECT id FROM event_log ORDER BY id DESC LIMIT ?)",
            (_EVENT_LOG_TRIM_TO,),
        )
        conn.commit()
        # Checkpoint outside any transaction
        conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        self._event_count = _EVENT_LOG_TRIM_TO
        logger.info("event_log trimmed", extra={"kept": _EVENT_LOG_TRIM_TO})

    async def recent_events(self, limit: int = 20) -> list[dict]:
        """Return the most recent N events, newest first."""
        return await asyncio.to_thread(self._sync_recent, limit)

    def _sync_recent(self, limit: int) -> list[dict]:
        conn = _require_init(self._conn)
        rows = conn.execute(
            "SELECT timestamp, source, action, content "
            "FROM event_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"timestamp": r[0], "source": r[1], "action": r[2], "content": r[3]}
            for r in rows
        ]

    async def search_events(
        self,
        action: str | None = None,
        source: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Filter event log by action name and/or source connector."""
        return await asyncio.to_thread(self._sync_search, action, source, limit)

    def _sync_search(
        self,
        action: str | None,
        source: str | None,
        limit: int,
    ) -> list[dict]:
        conn = _require_init(self._conn)
        clauses: list[str] = []
        params: list[object] = []
        if action:
            clauses.append("action = ?")
            params.append(action)
        if source:
            clauses.append("source = ?")
            params.append(source)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        rows = conn.execute(
            f"SELECT timestamp, source, action, content "
            f"FROM event_log {where} ORDER BY id DESC LIMIT ?",
            params,
        ).fetchall()
        return [
            {"timestamp": r[0], "source": r[1], "action": r[2], "content": r[3]}
            for r in rows
        ]

    async def close(self) -> None:
        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None
