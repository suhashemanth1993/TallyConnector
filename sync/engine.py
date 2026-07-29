"""Orchestrates one sync cycle: Tally -> parse -> map -> dedup -> Frappe.

A failure on one record is caught, logged, and queued for retry — it never
aborts the whole cycle, so one bad voucher doesn't block 10,000 good ones.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from pydantic import ValidationError

from config.settings import Settings, get_settings
from frappe.client import FrappeClient
from frappe.dedup import find_existing
from frappe.mapping import MappingEntry, get_mapping
from models.entity_spec import EntitySpec
from models.registry import resolve_sync_order
from sync.state_store import StateStore
from tally.client import TallyClient
from tally.mapper import to_model
from tally.xml_builder import build_collection_request
from tally.xml_parser import parse_collection_response
from utils.exceptions import TallyConnectorError, TallyDataError
from utils.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class EntitySyncResult:
    entity_name: str
    fetched: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0


@dataclass
class CycleResult:
    results: list[EntitySyncResult] = field(default_factory=list)

    @property
    def total_failed(self) -> int:
        return sum(r.failed for r in self.results)


def _content_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class SyncEngine:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        tally_client: TallyClient | None = None,
        frappe_client: FrappeClient | None = None,
        state_store: StateStore | None = None,
        mapping: dict[str, MappingEntry] | None = None,
    ):
        self._settings = settings or get_settings()
        self._tally = tally_client or TallyClient(self._settings)
        self._frappe = frappe_client or FrappeClient(self._settings)
        self._store = state_store or StateStore(self._settings.state_db_path)
        self._mapping = mapping or get_mapping(self._settings.frappe_mapping_file)

    def run_full_sync(self) -> CycleResult:
        return self._run_cycle(incremental=False)

    def run_incremental_sync(self) -> CycleResult:
        return self._run_cycle(incremental=True)

    def resync_entity(
        self, entity_name: str, *, date_from: date | None = None, date_to: date | None = None
    ) -> EntitySyncResult:
        from models.registry import get_entity

        spec = get_entity(entity_name)
        return self._sync_entity(spec, since_alter_id=None, date_from=date_from, date_to=date_to)

    def process_retry_queue(self, limit: int = 100) -> int:
        """Re-attempt due items from the retry queue. Returns count succeeded."""
        from models.registry import get_entity

        due = self._store.dequeue_due_retries(limit=limit)
        succeeded = 0
        for item in due:
            spec = get_entity(item["entity_name"])
            mapping_entry = self._mapping.get(spec.name)
            if mapping_entry is None:
                self._store.mark_retry_success(item["id"])
                continue
            try:
                raw_record = json.loads(item["payload_json"])
                model = to_model(raw_record, spec)
                result = EntitySyncResult(entity_name=spec.name)
                self._push_record(spec, mapping_entry, model, result)
                self._store.mark_retry_success(item["id"])
                succeeded += 1
            except (ValidationError, TallyDataError) as exc:
                # Permanently invalid — retrying on a backoff will never
                # succeed, so drop it instead of rescheduling forever.
                logger.error(
                    "Dropping permanently-invalid retry item %s/%s: %s",
                    spec.name,
                    item["record_guid"],
                    exc,
                )
                self._store.mark_retry_success(item["id"])
            except Exception as exc:  # noqa: BLE001 - keep draining the rest of the queue
                backoff_seconds = min(
                    self._settings.retry_backoff_base_seconds * (2 ** item["attempt_count"]), 3600
                )
                next_attempt = (
                    datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
                ).isoformat()
                logger.warning(
                    "Retry failed again for %s/%s: %s", spec.name, item["record_guid"], exc
                )
                self._store.mark_retry_failed(item["id"], str(exc), next_attempt)
        return succeeded

    def _run_cycle(self, *, incremental: bool) -> CycleResult:
        cycle = CycleResult()
        for spec in resolve_sync_order():
            since_alter_id = None
            if incremental:
                last = self._store.get_last_sync(spec.name)
                since_alter_id = last["last_alter_id"] if last else None
            result = self._sync_entity(spec, since_alter_id=since_alter_id)
            cycle.results.append(result)
        return cycle

    def _sync_entity(
        self,
        spec: EntitySpec,
        *,
        since_alter_id: int | None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> EntitySyncResult:
        result = EntitySyncResult(entity_name=spec.name)
        mapping_entry = self._mapping.get(spec.name)
        if mapping_entry is None:
            logger.warning("No Frappe mapping for entity '%s'; skipping push", spec.name)

        xml_request = build_collection_request(
            spec,
            since_alter_id=since_alter_id,
            date_from=date_from,
            date_to=date_to,
            company=self._settings.tally_company or None,
        )

        try:
            response = self._tally.send_request(xml_request)
            records = parse_collection_response(response, spec)
        except TallyConnectorError as exc:
            logger.error("Failed to fetch '%s' from Tally: %s", spec.name, exc)
            self._store.update_last_sync(spec.name, last_alter_id=since_alter_id, status="error")
            return result

        result.fetched = len(records)
        max_alter_id = since_alter_id

        for record in records:
            try:
                model = to_model(record, spec)
            except ValidationError as exc:
                # Structurally invalid record (e.g. missing natural key) —
                # retrying it will hit the exact same error every time, so
                # log clearly (raw fields included, for self-service
                # debugging) and move on instead of queuing a pointless retry.
                logger.error(
                    "Skipping unparseable '%s' record (won't retry): %s | raw fields: %s",
                    spec.name,
                    exc,
                    record,
                )
                result.failed += 1
                continue

            alter_id = getattr(model, "alter_id", None)
            if alter_id is not None:
                max_alter_id = max(max_alter_id or 0, alter_id)

            if mapping_entry is None:
                continue

            try:
                self._push_record(spec, mapping_entry, model, result)
            except TallyDataError as exc:
                logger.error("Skipping '%s' record (won't retry): %s", spec.name, exc)
                result.failed += 1
            except Exception as exc:  # noqa: BLE001 - one bad record must not abort the cycle
                logger.exception(
                    "Failed to push a '%s' record, queued for retry: %s", spec.name, exc
                )
                result.failed += 1
                key = record.get(spec.natural_key_field, record.get("guid", "unknown"))
                self._store.enqueue_retry(
                    entity_name=spec.name,
                    record_guid=key,
                    operation="create",
                    payload_json=json.dumps(record, default=str),
                    error=str(exc),
                )

        self._store.update_last_sync(spec.name, last_alter_id=max_alter_id, status="ok")
        logger.info(
            "Synced '%s': fetched=%s created=%s updated=%s unchanged=%s failed=%s",
            spec.name,
            result.fetched,
            result.created,
            result.updated,
            result.unchanged,
            result.failed,
        )
        return result

    def _push_record(
        self, spec: EntitySpec, mapping_entry: MappingEntry, model, result: EntitySyncResult
    ) -> None:
        natural_key = getattr(model, spec.natural_key_field, None)
        if not natural_key:
            raise TallyDataError(
                f"'{spec.name}' record has no usable '{spec.natural_key_field}' value to "
                f"dedupe on: {model.model_dump(mode='json')}"
            )

        payload = mapping_entry.apply(model.model_dump(mode="json"))
        content_hash = _content_hash(payload)

        existing_name = find_existing(
            self._store, self._frappe, mapping_entry, spec.natural_key_field, natural_key
        )
        cache_entry = self._store.get_cache_entry(spec.name, natural_key, self._frappe.base_url)

        if existing_name and cache_entry and cache_entry["content_hash"] == content_hash:
            result.unchanged += 1
            return

        if existing_name:
            self._frappe.update(mapping_entry.frappe_doctype, existing_name, payload)
            result.updated += 1
            frappe_name = existing_name
        else:
            created = self._frappe.create(mapping_entry.frappe_doctype, payload)
            frappe_name = created.get("name", natural_key)
            result.created += 1

        self._store.upsert_cache(
            entity_name=spec.name,
            tally_guid=natural_key,
            frappe_base_url=self._frappe.base_url,
            frappe_name=frappe_name,
            frappe_doctype=mapping_entry.frappe_doctype,
            content_hash=content_hash,
        )
