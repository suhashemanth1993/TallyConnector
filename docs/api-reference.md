# API / Module Reference

## Configuration (`config/settings.py`)

`get_settings() -> Settings` — cached pydantic-settings instance loaded
from `.env`. See `docs/user-guide.md` for the full variable list.

## Entity registry (`models/registry.py`)

- `REGISTRY: dict[str, EntitySpec]` — all 23 entities, keyed by name
  (`"company"`, `"ledger"`, `"sales_voucher"`, ...).
- `get_entity(name) -> EntitySpec`
- `list_masters() / list_vouchers() -> list[EntitySpec]`
- `resolve_sync_order() -> list[EntitySpec]` — dependency-respecting order.

## Tally layer (`tally/`)

- `xml_builder.build_collection_request(spec, *, since_alter_id=None, date_from=None, date_to=None, company=None) -> bytes`
- `xml_parser.parse_collection_response(xml_bytes, spec) -> list[dict]` —
  raises `utils.exceptions.TallyXMLParseError` on malformed XML.
- `mapper.to_model(raw_dict, spec) -> TallyMaster | TallyVoucher`
- `client.TallyClient(settings=None).send_request(xml_bytes) -> bytes` —
  raises `TallyConnectionError` / `TallyResponseError`.

## Frappe layer (`frappe/`)

- `mapping.load_mapping(path) -> dict[str, MappingEntry]`;
  `MappingEntry.apply(model_dict) -> dict` renames fields per `field_map`.
- `client.FrappeClient(settings=None)` — `.get(doctype, filters, fields=None)`,
  `.create(doctype, payload)`, `.update(doctype, name, payload)`. Raises
  `FrappeAuthError` (401/403) or `FrappeAPIError` (other failures).
- `dedup.find_existing(store, client, mapping_entry, natural_key_field, natural_key_value) -> str | None`
  — `natural_key_field` is the model attribute used as identity for this entity (`EntitySpec.natural_key_field`, usually `"guid"`; `"name"` for Company, which doesn't reliably expose a GUID).

## State (`sync/state_store.py`)

`StateStore(db_path)` — SQLite-backed:
- `get_last_sync(entity_name)`, `update_last_sync(entity_name, last_alter_id=, status=)`
- `enqueue_retry(...)`, `dequeue_due_retries(now=, limit=)`,
  `mark_retry_success(id)`, `mark_retry_failed(id, error, next_attempt_at)`
- `get_cached_frappe_name(entity_name, guid)`, `get_cache_entry(...)`,
  `upsert_cache(...)`

## Sync engine (`sync/engine.py`)

`SyncEngine(settings=None, tally_client=None, frappe_client=None, state_store=None, mapping=None)`
- `.run_full_sync() -> CycleResult`
- `.run_incremental_sync() -> CycleResult`
- `.resync_entity(name, date_from=None, date_to=None) -> EntitySyncResult`
- `.process_retry_queue(limit=100) -> int` (count of retries that succeeded)

`EntitySyncResult(entity_name, fetched, created, updated, unchanged, failed)`,
`CycleResult(results: list[EntitySyncResult])` with `.total_failed`.

## Services (`services/`)

- `retry_engine.build_retry_decorator(exceptions, max_attempts=, base_wait_seconds=)`
- `health_check.run_health_check(settings=None) -> HealthStatus`
- `scheduler.run_forever(interval_minutes, job)` /
  `register_interval_job(interval_minutes, job)`

## CLI (`app.py`)

`main(argv=None) -> int` — see `docs/user-guide.md#running` for flags.
