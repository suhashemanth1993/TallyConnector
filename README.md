# Tally Connector

A Windows-deployable connector that synchronizes company, ledger, stock,
and voucher data between **TallyPrime** (local HTTP/XML API on port 9000)
and a cloud-hosted **Frappe ERP** (REST API), on a schedule or on demand.

```
                        +----------------------+
                        |   Frappe Cloud ERP   |
                        |      REST APIs       |
                        +----------▲-----------+
                                   |
                           HTTPS / JSON
                                   |
+--------------------------------------------------------------+
|                 Tally Connector (Windows)                    |
|----------------------------------------------------------------|
| app.py (CLI)          sync/engine.py (Sync Engine)            |
| tally/client.py        tally/xml_builder.py / xml_parser.py    |
| frappe/client.py       frappe/mapping.py / dedup.py            |
| sync/state_store.py    services/retry_engine.py                |
| services/scheduler.py  services/health_check.py                |
| config/settings.py     utils/logging_setup.py                  |
+--------------------------------------------------------------+
                 |
          HTTP/XML (Port 9000)
                 |
        +-------------------+
        |   TallyPrime      |
        +-------------------+
```

## What it does

- Pulls 14 Tally master types (Companies, Groups, Ledgers, Stock Items, ...)
  and 9 voucher types (Sales, Purchase, Payment, ...) via Tally's XML
  Collection API.
- Maps each record to a Frappe DocType via an editable YAML mapping file
  and pushes it via Frappe's REST API, deduplicating on a stable GUID.
- Tracks per-entity sync state (SQLite) so incremental syncs only fetch
  what changed (`ALTERID`-based) since the last run.
- Queues failed pushes for retry with backoff instead of dropping them.
- Runs on a schedule, or on demand for a full/incremental/single-entity
  resync.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env        # fill in TALLY_URL, FRAPPE_BASE_URL, FRAPPE_API_KEY/SECRET
# Edit frappe/mapping.yaml once your real Frappe DocTypes exist —
# it ships with placeholder DocType names ("Tally Ledger", etc).

python app.py --health-check       # confirm Tally + Frappe are reachable
python app.py --full-sync          # one-time full sync
python app.py                      # run continuously on SYNC_INTERVAL_MINUTES
```

## Documentation

- [Installation Guide](docs/installation.md)
- [User Guide](docs/user-guide.md)
- [Developer Guide](docs/developer-guide.md)
- [API / Module Reference](docs/api-reference.md)
- [Troubleshooting Guide](docs/troubleshooting.md)

## Status

This is a working foundation: config, logging, the generic XML
builder/parser covering all 23 Tally entity types, retry engine, SQLite
state store, Frappe REST client with dedup, sync engine (full /
incremental / selective / retry-queue draining), CLI, and a full test
suite (unit + integration, all against fixtures/mocks — no live Tally
instance was available while building this).

Not yet done / needs a live environment to finish:
- Validation against a real TallyPrime company (see the note on
  `gst_master`/`state` object-type names in `models/registry.py`).
- Producing the actual `.exe` (build assets are ready — see
  [Installation Guide](docs/installation.md#windows-executable)).
- Installer UX, auto-start, config wizard, digital signing.
