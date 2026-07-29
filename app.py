"""CLI entry point for the Tally Connector.

Usage:
    python app.py                                   # run continuously on the configured interval
    python app.py --full-sync                       # one full sync of all entities, then exit
    python app.py --incremental-sync                 # one incremental sync, then exit
    python app.py --resync-entity ledger              # resync a single entity, then exit
    python app.py --resync-entity sales_voucher \
        --resync-range 2024-01-01 2024-01-31          # resync a voucher entity within a date range
    python app.py --process-retries                  # drain the retry queue, then exit
    python app.py --health-check                     # check Tally/Frappe reachability, then exit
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from config.settings import get_settings
from services.health_check import run_health_check
from services.scheduler import run_forever
from sync.engine import SyncEngine
from utils.exceptions import TallyConnectorError
from utils.logging_setup import configure_logging, get_logger

logger = get_logger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TallyPrime <-> Frappe connector")
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--full-sync", action="store_true", help="Run one full sync of all entities and exit"
    )
    action.add_argument(
        "--incremental-sync", action="store_true", help="Run one incremental sync and exit"
    )
    action.add_argument("--resync-entity", metavar="NAME", help="Resync a single entity and exit")
    action.add_argument(
        "--process-retries", action="store_true", help="Drain the retry queue and exit"
    )
    action.add_argument(
        "--health-check", action="store_true", help="Check Tally/Frappe reachability and exit"
    )
    parser.add_argument(
        "--resync-range",
        nargs=2,
        metavar=("START", "END"),
        help="With --resync-entity: limit to this YYYY-MM-DD date range (voucher entities only)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    configure_logging(
        log_dir=settings.log_dir, log_level=settings.log_level, debug_mode=settings.debug_mode
    )

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.resync_range and not args.resync_entity:
        parser.error("--resync-range requires --resync-entity")

    if args.health_check:
        status = run_health_check(settings)
        logger.info("Tally reachable: %s (%s)", status.tally_ok, status.tally_error or "ok")
        logger.info("Frappe reachable: %s (%s)", status.frappe_ok, status.frappe_error or "ok")
        return 0 if status.all_ok else 1

    engine = SyncEngine(settings=settings)

    try:
        if args.full_sync:
            cycle_result = engine.run_full_sync()
            logger.info(
                "Full sync complete: %s entities, %s failures",
                len(cycle_result.results),
                cycle_result.total_failed,
            )
            return 0 if cycle_result.total_failed == 0 else 1

        if args.incremental_sync:
            cycle_result = engine.run_incremental_sync()
            logger.info(
                "Incremental sync complete: %s entities, %s failures",
                len(cycle_result.results),
                cycle_result.total_failed,
            )
            return 0 if cycle_result.total_failed == 0 else 1

        if args.resync_entity:
            if args.resync_range:
                start = date.fromisoformat(args.resync_range[0])
                end = date.fromisoformat(args.resync_range[1])
                entity_result = engine.resync_entity(
                    args.resync_entity, date_from=start, date_to=end
                )
            else:
                entity_result = engine.resync_entity(args.resync_entity)
            logger.info(
                "Resync '%s' complete: fetched=%s created=%s updated=%s unchanged=%s failed=%s",
                entity_result.entity_name,
                entity_result.fetched,
                entity_result.created,
                entity_result.updated,
                entity_result.unchanged,
                entity_result.failed,
            )
            return 0 if entity_result.failed == 0 else 1

        if args.process_retries:
            succeeded = engine.process_retry_queue()
            logger.info("Retry queue processed: %s succeeded", succeeded)
            return 0
    except (TallyConnectorError, KeyError) as exc:
        logger.error("Command failed: %s", exc)
        return 2

    # Default: run continuously on the configured interval.
    def cycle() -> None:
        health = run_health_check(settings)
        if not health.all_ok:
            logger.warning(
                "Skipping sync cycle: health check failed (tally_ok=%s frappe_ok=%s)",
                health.tally_ok,
                health.frappe_ok,
            )
            return
        engine.run_incremental_sync()
        engine.process_retry_queue()

    run_forever(settings.sync_interval_minutes, cycle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
