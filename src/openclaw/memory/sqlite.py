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

# Keep at most this many event_log rows; trim runs automatically after inserts
_EVENT_LOG_MAX_ROWS = 10_000
_EVENT_LOG_TRIM_TO = 8_000


class SQLiteMemory:
    def __init__(self, db_path: str = "./data/openclaw.db") -> None:
        self._path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._event_count = 0  # approximate, avoids COUNT(*) on every insert

    async def init(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._sync_init)
        logger.info("SQLite memory initialized", extra={"path": self._path})

    def _sync_init(self) -> None:
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")  # safe with WAL, faster than FULL
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source TEXT,
                action TEXT,
                content TEXT
            )
            """
        )
        # Index for fast recent-events queries and trim operations
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_event_log_id ON event_log(id DESC)"
        )
        self._conn.commit()

        # Seed approximate count to avoid COUNT(*) at startup
        row = self._conn.execute("SELECT COUNT(*) FROM event_log").fetchone()
        self._event_count = row[0] if row else 0

    # ── KV store ──────────────────────────────────────────────────────────

    async def set(self, key: str, value: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await asyncio.to_thread(self._sync_set, key, value, now)

    def _sync_set(self, key: str, value: str, now: str) -> None:
        assert self._conn
        self._conn.execute(
            "INSERT OR REPLACE INTO kv (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now),
        )
        self._conn.commit()

    async def get(self, key: str) -> Optional[str]:
        return await asyncio.to_thread(self._sync_get, key)

    def _sync_get(self, key: str) -> Optional[str]:
        assert self._conn
        row = self._conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._sync_delete, key)

    def _sync_delete(self, key: str) -> None:
        assert self._conn
        self._conn.execute("DELETE FROM kv WHERE key = ?", (key,))
        self._conn.commit()

    # ── Event log ─────────────────────────────────────────────────────────

    async def log_event(self, source: str, action: str, content: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await asyncio.to_thread(self._sync_log, now, source, action, content)

    def _sync_log(self, now: str, source: str, action: str, content: str) -> None:
        assert self._conn
        self._conn.execute(
            "INSERT INTO event_log (timestamp, source, action, content) VALUES (?, ?, ?, ?)",
            (now, source, action, content),
        )
        self._conn.commit()

        self._event_count += 1
        if self._event_count > _EVENT_LOG_MAX_ROWS:
            self._sync_trim()

    def _sync_trim(self) -> None:
        """Delete oldest rows, keeping only the most recent _EVENT_LOG_TRIM_TO."""
        assert self._conn
        self._conn.execute(
            """
            DELETE FROM event_log WHERE id NOT IN (
                SELECT id FROM event_log ORDER BY id DESC LIMIT ?
            )
            """,
            (_EVENT_LOG_TRIM_TO,),
        )
        self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        self._conn.commit()
        self._event_count = _EVENT_LOG_TRIM_TO
        logger.info(
            "event_log trimmed",
            extra={"kept": _EVENT_LOG_TRIM_TO},
        )

    async def recent_events(self, limit: int = 20) -> list[dict]:
        return await asyncio.to_thread(self._sync_recent, limit)

    def _sync_recent(self, limit: int) -> list[dict]:
        assert self._conn
        rows = self._conn.execute(
            "SELECT timestamp, source, action, content FROM event_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"timestamp": r[0], "source": r[1], "action": r[2], "content": r[3]}
            for r in rows
        ]

    async def close(self) -> None:
        if self._conn:
            await asyncio.to_thread(self._conn.close)
