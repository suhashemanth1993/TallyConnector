"""Manual / selective resync: a single entity, optionally scoped to a date range."""

from __future__ import annotations

from datetime import date

from sync.engine import EntitySyncResult, SyncEngine


def resync_entity(entity_name: str, engine: SyncEngine | None = None) -> EntitySyncResult:
    engine = engine or SyncEngine()
    return engine.resync_entity(entity_name)


def resync_date_range(
    entity_name: str, start: date, end: date, engine: SyncEngine | None = None
) -> EntitySyncResult:
    engine = engine or SyncEngine()
    return engine.resync_entity(entity_name, date_from=start, date_to=end)
