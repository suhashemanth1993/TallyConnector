# User Guide

## Configuration

All configuration is via `.env` (copy from `.env.example`). Key settings:

| Variable | Meaning |
|---|---|
| `TALLY_URL` | Tally's HTTP gateway, e.g. `http://localhost:9000` |
| `TALLY_COMPANY` | Optional: restrict requests to one open Tally company |
| `FRAPPE_BASE_URL` | Your Frappe site, e.g. `https://acme.frappe.cloud` |
| `FRAPPE_API_KEY` / `FRAPPE_API_SECRET` | Frappe API credentials |
| `SYNC_INTERVAL_MINUTES` | How often the background loop runs a sync cycle |
| `RETRY_MAX_ATTEMPTS` / `RETRY_BACKOFF_BASE_SECONDS` | Retry policy for transient HTTP failures |
| `LOG_LEVEL` / `DEBUG_MODE` | Logging verbosity |
| `FRAPPE_MAPPING_FILE` | Path to the Tally-to-Frappe field mapping (default `frappe/mapping.yaml`) |

## Verifying a new install

Before trusting `pytest` output or a real sync, run the standalone sanity
check — it isolates *why* something is broken (wrong Python version, a
missing compiled wheel, bad `.env`, Tally/Frappe unreachable) far faster
than reading a pytest traceback:

```bash
python verify_setup.py
```

It checks, in order: Python version, that every module imports cleanly,
that the Pydantic models actually build (the thing most likely to break on
an older Python like 3.8), the entity registry, the Frappe field mapping,
your `.env` values, a local SQLite read/write, and live Tally/Frappe
reachability. `PASS` rows are fine, `WARN` rows are usually just
unconfigured Frappe credentials (fine until you're ready to push data),
and any `FAIL` row is something to fix before going further — exit code is
non-zero only on `FAIL`.

## Running

```bash
python app.py --health-check          # verify connectivity, don't sync
python app.py --full-sync             # sync every entity from scratch, once
python app.py --incremental-sync      # sync only what changed since last run, once
python app.py --resync-entity ledger  # resync just one entity
python app.py --resync-entity sales_voucher --resync-range 2024-01-01 2024-01-31
python app.py --process-retries       # retry previously-failed pushes now
python app.py                         # run forever: health check + incremental sync + retry drain, every SYNC_INTERVAL_MINUTES
```

Entity names for `--resync-entity` are the registry keys in
`models/registry.py`, e.g. `company`, `group`, `ledger`, `stock_item`,
`sales_voucher`, `purchase_voucher`, `payment_voucher`, etc.

## What "sync" means here

Each cycle, for every entity (masters first, then vouchers, in dependency
order): the connector asks Tally for records (all of them on a full sync,
only those with a higher `ALTERID` than last time on an incremental sync),
maps each one to a Frappe DocType via `frappe/mapping.yaml`, checks whether
it already exists in Frappe (by its Tally GUID), and creates or updates it.
Records whose mapped content hasn't changed since the last successful push
are skipped. Records that fail to push are queued and retried with
exponential backoff rather than being dropped.

## Logs

Rotating logs are written to `logs/` (`app.log`, `error.log`). Secrets
(API keys, tokens, passwords) are redacted before anything is written.

## Customizing the Frappe mapping

`frappe/mapping.yaml` ships with placeholder DocType names (`Tally Ledger`,
`Tally Sales Voucher`, ...). Edit `frappe_doctype` and `field_map` entries
to match your real Frappe schema — no code changes needed.
