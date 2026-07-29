from __future__ import annotations

from config.settings import Settings
from frappe.client import FrappeClient
from frappe.dedup import find_existing
from frappe.mapping import load_mapping
from sync.state_store import StateStore


def _settings(**overrides):
    base = dict(
        frappe_base_url="https://example.frappe.cloud",
        frappe_api_key="key123",
        frappe_api_secret="secret456",
    )
    base.update(overrides)
    return Settings(**base)


def test_find_existing_uses_cache_before_network(tmp_path, requests_mock):
    store = StateStore(str(tmp_path / "state.db"))
    store.upsert_cache(
        entity_name="ledger",
        tally_guid="g-1",
        frappe_base_url="https://example.frappe.cloud",
        frappe_name="LEDG-0001",
        frappe_doctype="Tally Ledger",
        content_hash="x",
    )
    client = FrappeClient(settings=_settings())
    mapping = load_mapping("frappe/mapping.yaml")

    result = find_existing(store, client, mapping["ledger"], "guid", "g-1")
    assert result == "LEDG-0001"
    assert requests_mock.call_count == 0


def test_find_existing_falls_back_to_frappe_and_populates_cache(tmp_path, requests_mock):
    requests_mock.get(
        "https://example.frappe.cloud/api/resource/Tally Ledger",
        json={"data": [{"name": "LEDG-0009"}]},
    )
    store = StateStore(str(tmp_path / "state.db"))
    client = FrappeClient(settings=_settings())
    mapping = load_mapping("frappe/mapping.yaml")

    result = find_existing(store, client, mapping["ledger"], "guid", "g-9")
    assert result == "LEDG-0009"
    assert (
        store.get_cached_frappe_name("ledger", "g-9", "https://example.frappe.cloud") == "LEDG-0009"
    )


def test_find_existing_returns_none_when_not_found(tmp_path, requests_mock):
    requests_mock.get("https://example.frappe.cloud/api/resource/Tally Ledger", json={"data": []})
    store = StateStore(str(tmp_path / "state.db"))
    client = FrappeClient(settings=_settings())
    mapping = load_mapping("frappe/mapping.yaml")

    assert find_existing(store, client, mapping["ledger"], "guid", "g-missing") is None


def test_find_existing_does_not_cross_contaminate_between_frappe_targets(tmp_path, requests_mock):
    """Regression test for the real bug: switching FRAPPE_BASE_URL (e.g. dev
    -> prod) with the same state DB must not report records as already
    existing on the new target just because they're cached from the old one."""
    store = StateStore(str(tmp_path / "state.db"))
    mapping = load_mapping("frappe/mapping.yaml")

    dev_client = FrappeClient(settings=_settings(frappe_base_url="https://dev.example.com"))
    store.upsert_cache(
        entity_name="ledger",
        tally_guid="g-1",
        frappe_base_url="https://dev.example.com",
        frappe_name="LEDG-0001",
        frappe_doctype="Tally Ledger",
        content_hash="x",
    )
    assert find_existing(store, dev_client, mapping["ledger"], "guid", "g-1") == "LEDG-0001"

    requests_mock.get("https://prod.example.com/api/resource/Tally Ledger", json={"data": []})
    prod_client = FrappeClient(settings=_settings(frappe_base_url="https://prod.example.com"))
    assert find_existing(store, prod_client, mapping["ledger"], "guid", "g-1") is None


def test_find_existing_dedupes_on_name_for_company_style_entities(tmp_path, requests_mock):
    requests_mock.get(
        "https://example.frappe.cloud/api/resource/Tally Company",
        json={"data": [{"name": "COMP-0001"}]},
    )
    store = StateStore(str(tmp_path / "state.db"))
    client = FrappeClient(settings=_settings())
    mapping = load_mapping("frappe/mapping.yaml")

    result = find_existing(store, client, mapping["company"], "name", "Acme Traders")
    assert result == "COMP-0001"
    request = requests_mock.request_history[0]
    assert "title" in request.qs["filters"][0]
