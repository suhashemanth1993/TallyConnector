from __future__ import annotations

import json
import sqlite3

from sync.state_store import StateStore


def test_last_sync_roundtrip(tmp_path):
    store = StateStore(str(tmp_path / "state.db"))
    assert store.get_last_sync("ledger") is None

    store.update_last_sync("ledger", last_alter_id=42)
    row = store.get_last_sync("ledger")
    assert row["last_alter_id"] == 42
    assert row["status"] == "ok"

    store.update_last_sync("ledger", last_alter_id=99)
    row = store.get_last_sync("ledger")
    assert row["last_alter_id"] == 99


def test_retry_queue_lifecycle(tmp_path):
    store = StateStore(str(tmp_path / "state.db"))
    store.enqueue_retry(
        entity_name="ledger",
        record_guid="g-1",
        operation="create",
        payload_json=json.dumps({"name": "Cash"}),
    )
    due = store.dequeue_due_retries()
    assert len(due) == 1
    assert due[0]["entity_name"] == "ledger"

    store.mark_retry_success(due[0]["id"])
    assert store.dequeue_due_retries() == []


def test_retry_queue_failure_reschedules_not_deletes(tmp_path):
    store = StateStore(str(tmp_path / "state.db"))
    store.enqueue_retry(
        entity_name="ledger", record_guid="g-1", operation="create", payload_json="{}"
    )
    due = store.dequeue_due_retries()
    retry_id = due[0]["id"]

    far_future = "9999-01-01T00:00:00+00:00"
    store.mark_retry_failed(retry_id, "boom", far_future)

    assert store.dequeue_due_retries() == []
    with_far_future = store._conn.execute("SELECT * FROM retry_queue WHERE id = ?", (retry_id,))
    row = with_far_future.fetchone()
    assert row["attempt_count"] == 1
    assert row["last_error"] == "boom"


def test_sync_cache_roundtrip(tmp_path):
    store = StateStore(str(tmp_path / "state.db"))
    assert store.get_cached_frappe_name("ledger", "g-1", "https://dev.example.com") is None

    store.upsert_cache(
        entity_name="ledger",
        tally_guid="g-1",
        frappe_base_url="https://dev.example.com",
        frappe_name="LEDG-0001",
        frappe_doctype="Tally Ledger",
        content_hash="abc123",
    )
    assert store.get_cached_frappe_name("ledger", "g-1", "https://dev.example.com") == "LEDG-0001"

    entry = store.get_cache_entry("ledger", "g-1", "https://dev.example.com")
    assert entry["content_hash"] == "abc123"


def test_sync_cache_is_scoped_per_frappe_target(tmp_path):
    """Regression test: the same Tally GUID synced to two different Frappe
    sites (e.g. dev then prod) must not be treated as already existing on
    the second site just because it's cached from the first."""
    store = StateStore(str(tmp_path / "state.db"))
    store.upsert_cache(
        entity_name="ledger",
        tally_guid="g-1",
        frappe_base_url="https://dev.example.com",
        frappe_name="LEDG-0001",
        frappe_doctype="Tally Ledger",
        content_hash="abc123",
    )

    assert store.get_cached_frappe_name("ledger", "g-1", "https://dev.example.com") == "LEDG-0001"
    assert store.get_cached_frappe_name("ledger", "g-1", "https://prod.example.com") is None


def test_sync_cache_migrates_old_schema_by_dropping_stale_cache(tmp_path):
    """A pre-existing state DB from before frappe_base_url scoping must not
    crash on open, and must not silently keep serving unscoped (unsafe)
    cache rows — see test_sync_cache_is_scoped_per_frappe_target."""
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE sync_cache (
            entity_name TEXT NOT NULL,
            tally_guid TEXT NOT NULL,
            frappe_name TEXT NOT NULL,
            frappe_doctype TEXT NOT NULL,
            content_hash TEXT,
            last_pushed_at TEXT,
            PRIMARY KEY (entity_name, tally_guid)
        )
        """)
    conn.execute(
        "INSERT INTO sync_cache VALUES ('ledger', 'g-1', 'LEDG-OLD', 'Tally Ledger', 'x', 'now')"
    )
    conn.commit()
    conn.close()

    store = StateStore(str(db_path))
    # Old unscoped row must be gone, not silently reused for any target.
    assert store.get_cached_frappe_name("ledger", "g-1", "https://dev.example.com") is None
