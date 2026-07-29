from __future__ import annotations

from sync.engine import CycleResult, SyncEngine


def run_incremental_sync(engine: SyncEngine | None = None) -> CycleResult:
    engine = engine or SyncEngine()
    return engine.run_incremental_sync()
