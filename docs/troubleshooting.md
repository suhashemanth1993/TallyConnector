# Troubleshooting Guide

## `python app.py --health-check` reports Tally unreachable

- Confirm TallyPrime is running and its HTTP gateway is enabled (F1 >
  Settings > Connectivity) on the port in `TALLY_URL` (default 9000).
- If the connector runs on a different machine than Tally, check the
  gateway is bound to more than `localhost` and that a firewall isn't
  blocking the port.
- `TallyConnectionError` in the logs means the connector couldn't even
  open a connection — this is a network/firewall issue, not an auth one
  (Tally's local gateway has no authentication).

## `python app.py --health-check` reports Frappe unreachable / 401

- Double-check `FRAPPE_BASE_URL` has no trailing slash and uses `https://`.
- `FrappeAuthError` / HTTP 401-403 means the API key/secret pair is wrong,
  disabled, or lacks permission on the target DocTypes — regenerate the
  key pair in Frappe (User > API Access).

## Switched `FRAPPE_BASE_URL` (e.g. dev -> prod) and records show as "unchanged" but aren't there

- Fixed as of the dedup-cache-scoping change in `sync/state_store.py` — the
  local `STATE_DB_PATH` cache is now scoped per `FRAPPE_BASE_URL`, so
  switching targets no longer causes records already pushed to one Frappe
  site to be wrongly reported as already existing on another. If you're on
  an older build: delete/rename the SQLite file at `STATE_DB_PATH` before
  switching targets, or run `--full-sync` again after switching (the first
  post-fix run rebuilds the cache from scratch, which is expected and safe
  — it just costs one extra GET check per record).

## Records aren't appearing in Frappe

- Check `frappe/mapping.yaml` — if an entity has no mapping entry, the
  connector logs a warning and fetches it from Tally but never pushes it.
- Check `logs/error.log` for `FrappeAPIError` (e.g. a required field on the
  target DocType wasn't populated by `field_map`).
- A record that failed to push is queued for retry, not lost — run
  `python app.py --process-retries` to see it retried immediately, or check
  the `retry_queue` table in the SQLite file at `STATE_DB_PATH`.

## "N validation errors for TallyMaster / TallyVoucher" in the logs

- Means Tally sent a row missing a field the model requires (`name` is
  always required; `guid` is optional — see below). Run
  `python dump_xml.py <entity>` and compare the raw tag names to what
  `models/registry.py`'s `fetch_fields` expects for that entity; Tally's
  exact field names can vary by version/edition and weren't all verified
  against a live instance while this was built.
- These are logged as `Skipping unparseable '<entity>' record (won't
  retry)` with the raw parsed fields included in the same log line —
  that's deliberate: a record that fails validation will fail identically
  on every retry, so it's dropped rather than queued, and the log line
  alone should tell you which field is missing without needing
  `dump_xml.py` at all.

## "Company" (or another entity) records aren't getting a GUID

- Expected for `company`: it's a container object in Tally, not a true
  master, and often doesn't expose a `GUID`. `TallyMaster.guid` is
  optional for exactly this reason. Identity for dedup purposes is
  controlled per-entity by `EntitySpec.natural_key_field` in
  `models/registry.py` — `company` uses `"name"` instead of the default
  `"guid"`. If another entity turns out to have the same issue, add
  `natural_key_field="name"` (or whatever field is actually reliable) to
  its `_master(...)` / `_voucher(...)` registry entry.

## A sync seems to skip records that changed in Tally

- Incremental sync filters on Tally's `ALTERID`. If you edited a record
  directly through some path that doesn't bump `ALTERID` (unusual), it
  won't be picked up until a full sync (`--full-sync`) or a selective
  resync (`--resync-entity <name>`) is run.

## Malformed / unparseable Tally responses

- `TallyXMLParseError` in the logs usually means Tally returned an error
  page or truncated response rather than valid XML (e.g. wrong `TYPE` name
  for a custom TDL object). Check `models/registry.py`'s note about
  `gst_master` / `state` — those two object-type names were not verified
  against a live Tally instance and may need adjusting.

## Windows executable won't build

- PyInstaller must run on Windows; it cannot cross-compile from macOS or
  Linux. Build on a Windows machine (`build.ps1`) or via the
  `build-windows.yml` GitHub Actions workflow.

## Secrets showing up in logs

- They shouldn't: `utils/logging_setup.py` redacts common secret-bearing
  key/value patterns (`api_key`, `api_secret`, `authorization`, `token`,
  `password`) before any log line is written. If you find an exception,
  please treat it as a bug — the redaction filter should be extended to
  cover the new field name.
