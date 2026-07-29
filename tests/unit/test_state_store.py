from __future__ import annotations

import json

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
    assert store.get_cached_frappe_name("ledger", "g-1") is None

    store.upsert_cache(
        entity_name="ledger",
        tally_guid="g-1",
        frappe_name="LEDG-0001",
        frappe_doctype="Tally Ledger",
        content_hash="abc123",
    )
    assert store.get_cached_frappe_name("ledger", "g-1") == "LEDG-0001"

    entry = store.get_cache_entry("ledger", "g-1")
    assert entry["content_hash"] == "abc123"
