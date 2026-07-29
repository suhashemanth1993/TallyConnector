# Developer Guide

## Architecture

The connector is schema-driven: one `EntitySpec` (see `models/entity_spec.py`)
describes each of the 23 Tally entities (14 masters + 9 vouchers), and one
generic XML builder, XML parser, Pydantic model pair, and sync engine
operate over all of them. Adding a 24th entity means adding one entry to
`models/registry.py` — not writing a new module.

```
config/settings.py          Settings (pydantic-settings, loads .env)
models/entity_spec.py       EntitySpec dataclass — the registry's schema
models/registry.py          REGISTRY: 23 EntitySpec entries + resolve_sync_order()
models/base.py masters.py vouchers.py sync_state.py   Pydantic models
tally/xml_builder.py        EntitySpec -> Tally Collection request XML
tally/xml_parser.py         Tally response XML -> list[dict]
tally/mapper.py             dict -> TallyMaster | TallyVoucher
tally/client.py             HTTP to Tally, retry-wrapped, typed exceptions
frappe/mapping.yaml/.py     Tally entity -> Frappe DocType + field_map
frappe/client.py            HTTP to Frappe REST API, retry-wrapped
frappe/dedup.py             GUID-based existence check (cache-first)
sync/state_store.py         SQLite: last-sync state, retry queue, dedup cache
sync/engine.py              SyncEngine — orchestrates one entity/cycle
sync/full_sync.py incremental_sync.py selective.py retry_processor.py   thin entry points
services/retry_engine.py    tenacity-based retry decorator factory
services/health_check.py    Tally/Frappe reachability checks
services/scheduler.py       `schedule`-based interval loop
utils/logging_setup.py      rotating logs + secret redaction
utils/exceptions.py         typed exception hierarchy
app.py                      argparse CLI wiring all of the above
```

## Adding a new Tally entity

1. Add an `EntitySpec` to `models/registry.py` (a `_master(...)` or
   `_voucher(...)` call) — give it `fetch_fields` matching the Tally field
   names you want, and `depends_on` if it references other masters.
2. Add a matching entry to `frappe/mapping.yaml` with the target
   `frappe_doctype` and a `field_map`.
3. Nothing else changes — the builder, parser, and sync engine pick it up
   automatically. Add a fixture + a couple of parser assertions in
   `tests/unit/test_xml_parser.py` if the entity has unusual fields.

## Running tests

```bash
pip install -r requirements.txt pytest requests-mock
pytest                 # all unit + integration tests, no live Tally/Frappe needed
pytest tests/unit       # fast, pure-function tests
pytest tests/integration  # mocked-network sync-cycle tests
```

Tests never hit a real Tally or Frappe instance — Tally responses come from
XML fixtures in `tests/fixtures/`, and both Tally and Frappe HTTP calls are
intercepted with `requests_mock`.

## Linting / type-checking

```bash
ruff check .
black --check .
mypy .
```

## Known gaps to close with real Tally access

`models/registry.py` has a note on `gst_master` and `state`: their
`tally_object_type` values (`GSTClassification`, `State`) are best-effort
guesses made without a live TallyPrime instance to confirm the exact TDL
object names against. Verify and adjust before relying on those two.

`ledger.LedgerContact` is similarly unverified — confirmed against real
Tally data that it doesn't error, but haven't yet confirmed it's the right
field name for a ledger's actual contact person (it may be blank in the
test data rather than wrong). `ledger.PartyGSTIN` *was* wrong (`GSTIN`
originally) and has been fixed and confirmed against real data — Tally
distinguishes a Company's own `GSTRegistrationNumber` from a Ledger/party's
`PartyGSTIN`.
