"""Models hydrated from the StateStore (sync/state_store.py)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class SyncState(BaseModel):
    entity_name: str
    last_synced_at: datetime | None = None
    last_alter_id: int | None = None
    status: Literal["ok", "error"] = "ok"


class RetryQueueItem(BaseModel):
    id: int | None = None
    entity_name: str
    record_guid: str
    operation: Literal["create", "update"]
    payload: dict[str, Any]
    attempt_count: int = 0
    next_attempt_at: datetime
    last_error: str | None = None
    created_at: datetime
