from __future__ import annotations

from sync.engine import SyncEngine


def process_retry_queue(engine: SyncEngine | None = None, limit: int = 100) -> int:
    engine = engine or SyncEngine()
    return engine.process_retry_queue(limit=limit)
