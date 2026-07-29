"""Durable local state: last-sync timestamps, the retry queue, and the
Tally-GUID -> Frappe-name dedup cache.

SQLite (stdlib `sqlite3`, WAL mode) rather than JSON: retry-queue writes
happen per-record and must be atomic across a mid-write crash, and dedup
lookups need an indexed point query (entity + guid), not a linear scan of a
JSON blob.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_state (
    entity_name TEXT PRIMARY KEY,
    last_synced_at TEXT,
    last_alter_id INTEGER,
    status TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS retry_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_name TEXT NOT NULL,
    record_guid TEXT NOT NULL,
    operation TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT NOT NULL,
    last_error TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(entity_name, record_guid, operation)
);

CREATE TABLE IF NOT EXISTS sync_cache (
    entity_name TEXT NOT NULL,
    tally_guid TEXT NOT NULL,
    frappe_name TEXT NOT NULL,
    frappe_doctype TEXT NOT NULL,
    content_hash TEXT,
    last_pushed_at TEXT,
    PRIMARY KEY (entity_name, tally_guid)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    def __init__(self, db_path: str = ".state/sync_state.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        cursor = self._conn.cursor()
        try:
            yield cursor
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # -- sync_state -----------------------------------------------------

    def get_last_sync(self, entity_name: str) -> sqlite3.Row | None:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM sync_state WHERE entity_name = ?", (entity_name,))
            return cur.fetchone()

    def update_last_sync(
        self, entity_name: str, *, last_alter_id: int | None, status: str = "ok"
    ) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO sync_state
                    (entity_name, last_synced_at, last_alter_id, status, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(entity_name) DO UPDATE SET
                    last_synced_at=excluded.last_synced_at,
                    last_alter_id=excluded.last_alter_id,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (entity_name, _now(), last_alter_id, status, _now()),
            )

    # -- retry_queue ------------------------------------------------------

    def enqueue_retry(
        self,
        *,
        entity_name: str,
        record_guid: str,
        operation: str,
        payload_json: str,
        next_attempt_at: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO retry_queue
                    (entity_name, record_guid, operation, payload_json, attempt_count,
                     next_attempt_at, last_error, created_at)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                ON CONFLICT(entity_name, record_guid, operation) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    attempt_count=retry_queue.attempt_count + 1,
                    next_attempt_at=excluded.next_attempt_at,
                    last_error=excluded.last_error
                """,
                (
                    entity_name,
                    record_guid,
                    operation,
                    payload_json,
                    next_attempt_at or _now(),
                    error,
                    _now(),
                ),
            )

    def dequeue_due_retries(self, now: str | None = None, limit: int = 100) -> list[sqlite3.Row]:
        now = now or _now()
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM retry_queue WHERE next_attempt_at <= ? ORDER BY id LIMIT ?",
                (now, limit),
            )
            return cur.fetchall()

    def mark_retry_success(self, retry_id: int) -> None:
        with self._cursor() as cur:
            cur.execute("DELETE FROM retry_queue WHERE id = ?", (retry_id,))

    def mark_retry_failed(self, retry_id: int, error: str, next_attempt_at: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE retry_queue
                SET attempt_count = attempt_count + 1, last_error = ?, next_attempt_at = ?
                WHERE id = ?
                """,
                (error, next_attempt_at, retry_id),
            )

    # -- sync_cache (dedup) -----------------------------------------------

    def get_cached_frappe_name(self, entity_name: str, tally_guid: str) -> str | None:
        with self._cursor() as cur:
            cur.execute(
                "SELECT frappe_name FROM sync_cache WHERE entity_name = ? AND tally_guid = ?",
                (entity_name, tally_guid),
            )
            row = cur.fetchone()
            return row["frappe_name"] if row else None

    def get_cache_entry(self, entity_name: str, tally_guid: str) -> sqlite3.Row | None:
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM sync_cache WHERE entity_name = ? AND tally_guid = ?",
                (entity_name, tally_guid),
            )
            return cur.fetchone()

    def upsert_cache(
        self,
        *,
        entity_name: str,
        tally_guid: str,
        frappe_name: str,
        frappe_doctype: str,
        content_hash: str,
    ) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO sync_cache
                    (entity_name, tally_guid, frappe_name, frappe_doctype,
                     content_hash, last_pushed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_name, tally_guid) DO UPDATE SET
                    frappe_name=excluded.frappe_name,
                    frappe_doctype=excluded.frappe_doctype,
                    content_hash=excluded.content_hash,
                    last_pushed_at=excluded.last_pushed_at
                """,
                (entity_name, tally_guid, frappe_name, frappe_doctype, content_hash, _now()),
            )
