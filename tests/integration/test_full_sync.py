from __future__ import annotations

import json

from config.settings import Settings
from sync.engine import SyncEngine
from tests.conftest import load_fixture


def _settings(tmp_path, **overrides):
    base = dict(
        tally_url="http://localhost:9000",
        frappe_base_url="https://example.frappe.cloud",
        frappe_api_key="key",
        frappe_api_secret="secret",
        state_db_path=str(tmp_path / "state.db"),
        frappe_mapping_file="frappe/mapping.yaml",
        retry_max_attempts=2,
        retry_backoff_base_seconds=0.01,
    )
    base.update(overrides)
    return Settings(**base)


def _tally_callback_for(*fixtures_by_fragment):
    """fixtures_by_fragment: list of (collection_name_fragment, fixture_filename)."""

    def callback(request, _context):
        body = request.body if isinstance(request.body, bytes) else request.body.encode()
        for fragment, fixture_name in fixtures_by_fragment:
            if fragment.encode() in body:
                return load_fixture(fixture_name)
        return b"<ENVELOPE></ENVELOPE>"

    return callback


def test_resync_ledger_creates_records_in_frappe(tmp_path, requests_mock):
    requests_mock.post(
        "http://localhost:9000",
        content=_tally_callback_for(("ledger Collection", "ledger_collection_response.xml")),
    )
    requests_mock.get("https://example.frappe.cloud/api/resource/Tally Ledger", json={"data": []})
    created_names = iter(["LEDG-0001", "LEDG-0002", "LEDG-0003"])
    requests_mock.post(
        "https://example.frappe.cloud/api/resource/Tally Ledger",
        json=lambda request, context: {"data": {"name": next(created_names)}},
    )

    engine = SyncEngine(settings=_settings(tmp_path))
    result = engine.resync_entity("ledger")

    assert result.fetched == 3
    assert result.created == 3
    assert result.failed == 0


def test_resync_sales_voucher_pushes_nested_entries(tmp_path, requests_mock):
    requests_mock.post(
        "http://localhost:9000",
        content=_tally_callback_for(
            ("sales_voucher Collection", "sales_voucher_collection_response.xml")
        ),
    )
    requests_mock.get(
        "https://example.frappe.cloud/api/resource/Tally Sales Voucher", json={"data": []}
    )

    captured_payloads = []

    def create_cb(request, context):
        payload = json.loads(request.body)
        captured_payloads.append(payload)
        return {"data": {"name": f"SV-{len(captured_payloads)}"}}

    requests_mock.post(
        "https://example.frappe.cloud/api/resource/Tally Sales Voucher", json=create_cb
    )

    engine = SyncEngine(settings=_settings(tmp_path))
    result = engine.resync_entity("sales_voucher")

    assert result.fetched == 2
    assert result.created == 2
    assert len(captured_payloads[0]["items"]) == 1
    assert captured_payloads[0]["items"][0]["stock_item_name"] == "Widget A"
    assert len(captured_payloads[0]["ledger_entries"]) == 2


def test_second_run_is_a_noop_when_unchanged(tmp_path, requests_mock):
    requests_mock.post(
        "http://localhost:9000",
        content=_tally_callback_for(("ledger Collection", "ledger_collection_response.xml")),
    )

    call_count = {"get": 0, "post": 0}

    def get_cb(request, context):
        call_count["get"] += 1
        return {"data": []}

    def create_cb(request, context):
        call_count["post"] += 1
        return {"data": {"name": f"LEDG-{call_count['post']:04d}"}}

    requests_mock.get("https://example.frappe.cloud/api/resource/Tally Ledger", json=get_cb)
    requests_mock.post("https://example.frappe.cloud/api/resource/Tally Ledger", json=create_cb)

    settings = _settings(tmp_path)
    engine = SyncEngine(settings=settings)

    first = engine.resync_entity("ledger")
    assert first.created == 3

    # Re-register GET so cache lookups short-circuit before any GET is needed;
    # dedup should already be served by the local cache, not a second network call.
    second = engine.resync_entity("ledger")
    assert second.created == 0
    assert second.unchanged == 3
    assert call_count["post"] == 3  # no new creates on the second run


def test_resync_company_without_guid_dedupes_on_name(tmp_path, requests_mock):
    """Mirrors real TallyPrime: Company rows carry no GUID. The engine must
    fall back to EntitySpec.natural_key_field ('name' for company) rather
    than crashing on a missing 'guid'."""
    requests_mock.post(
        "http://localhost:9000",
        content=_tally_callback_for(
            ("company Collection", "company_collection_response_no_guid.xml")
        ),
    )
    requests_mock.get("https://example.frappe.cloud/api/resource/Tally Company", json={"data": []})
    captured = []

    def create_cb(request, context):
        payload = json.loads(request.body)
        captured.append(payload)
        return {"data": {"name": "COMP-0001"}}

    requests_mock.post("https://example.frappe.cloud/api/resource/Tally Company", json=create_cb)

    engine = SyncEngine(settings=_settings(tmp_path))
    result = engine.resync_entity("company")

    assert result.fetched == 1
    assert result.created == 1
    assert result.failed == 0
    assert "tally_guid" not in captured[0]
    assert captured[0]["title"] == "Acme Traders Pvt Ltd"


def test_record_missing_natural_key_is_skipped_without_retry_loop(tmp_path, requests_mock):
    """A record so broken it's missing even its natural key (e.g. Name)
    must be logged and skipped, not endlessly retried — retrying a
    structurally invalid record can never succeed."""
    broken_xml = b"<ENVELOPE><LEDGER><PARENT>Sundry Debtors</PARENT></LEDGER></ENVELOPE>"
    requests_mock.post("http://localhost:9000", content=broken_xml)
    requests_mock.get("https://example.frappe.cloud/api/resource/Tally Ledger", json={"data": []})

    engine = SyncEngine(settings=_settings(tmp_path))
    result = engine.resync_entity("ledger")

    assert result.fetched == 1
    assert result.failed == 1
    assert result.created == 0
    # nothing should have been queued for retry — it would never succeed
    assert engine.process_retry_queue() == 0


def test_failed_push_is_queued_and_retry_processor_recovers(tmp_path, requests_mock):
    requests_mock.post(
        "http://localhost:9000",
        content=_tally_callback_for(("ledger Collection", "ledger_collection_response.xml")),
    )
    requests_mock.get("https://example.frappe.cloud/api/resource/Tally Ledger", json={"data": []})
    requests_mock.post(
        "https://example.frappe.cloud/api/resource/Tally Ledger", status_code=500, text="down"
    )

    settings = _settings(tmp_path, retry_max_attempts=1)
    engine = SyncEngine(settings=settings)
    result = engine.resync_entity("ledger")

    assert result.created == 0
    assert result.failed == 3

    requests_mock.post(
        "https://example.frappe.cloud/api/resource/Tally Ledger",
        json={"data": {"name": "LEDG-RECOVERED"}},
    )
    succeeded = engine.process_retry_queue()
    assert succeeded == 3
