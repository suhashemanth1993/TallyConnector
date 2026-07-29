"""Runs a sync callback on a fixed interval using the `schedule` library."""

from __future__ import annotations

import time
from collections.abc import Callable

import schedule

from utils.logging_setup import get_logger

logger = get_logger(__name__)


def register_interval_job(interval_minutes: int, job: Callable[[], None]) -> schedule.Job:
    return schedule.every(interval_minutes).minutes.do(job)


def run_forever(
    interval_minutes: int, job: Callable[[], None], *, poll_seconds: float = 1.0
) -> None:
    """Run `job` immediately, then every `interval_minutes` thereafter, until
    interrupted (Ctrl+C / SIGTERM)."""
    logger.info("Scheduler starting: running every %s minute(s)", interval_minutes)
    job()
    register_interval_job(interval_minutes, job)
    try:
        while True:
            schedule.run_pending()
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")
