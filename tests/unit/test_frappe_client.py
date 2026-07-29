from __future__ import annotations

import pytest

from config.settings import Settings
from frappe.client import FrappeClient
from utils.exceptions import FrappeAPIError, FrappeAuthError


def _settings(**overrides):
    base = dict(
        frappe_base_url="https://example.frappe.cloud",
        frappe_api_key="key123",
        frappe_api_secret="secret456",
        retry_max_attempts=2,
        retry_backoff_base_seconds=0.01,
    )
    base.update(overrides)
    return Settings(**base)


def test_get_returns_data_list(requests_mock):
    requests_mock.get(
        "https://example.frappe.cloud/api/resource/Tally Ledger",
        json={"data": [{"name": "LEDG-0001"}]},
    )
    client = FrappeClient(settings=_settings())
    result = client.get("Tally Ledger", {"tally_guid": "g-1"})
    assert result == [{"name": "LEDG-0001"}]


def test_create_posts_and_returns_data(requests_mock):
    requests_mock.post(
        "https://example.frappe.cloud/api/resource/Tally Ledger",
        json={"data": {"name": "LEDG-0002"}},
        status_code=200,
    )
    client = FrappeClient(settings=_settings())
    result = client.create("Tally Ledger", {"title": "Cash"})
    assert result == {"name": "LEDG-0002"}


def test_auth_failure_raises_frappe_auth_error(requests_mock):
    requests_mock.get(
        "https://example.frappe.cloud/api/resource/Tally Ledger", status_code=401, json={}
    )
    client = FrappeClient(settings=_settings())
    with pytest.raises(FrappeAuthError):
        client.get("Tally Ledger", {"tally_guid": "g-1"})


def test_client_error_raises_frappe_api_error(requests_mock):
    requests_mock.get(
        "https://example.frappe.cloud/api/resource/Tally Ledger",
        status_code=400,
        text="bad filter",
    )
    client = FrappeClient(settings=_settings())
    with pytest.raises(FrappeAPIError):
        client.get("Tally Ledger", {"tally_guid": "g-1"})


def test_get_raises_typed_error_on_malformed_base_url():
    client = FrappeClient(settings=_settings(frappe_base_url="example.frappe.cloud"))
    with pytest.raises(FrappeAPIError, match="FRAPPE_BASE_URL"):
        client.get("Tally Ledger", {"tally_guid": "g-1"})


def test_non_json_response_raises_typed_error_not_raw_traceback(requests_mock):
    """Reproduces a real failure: FRAPPE_BASE_URL pointing at something that
    returns HTTP 200 with an HTML page (e.g. a login page) instead of JSON."""
    requests_mock.get(
        "https://example.frappe.cloud/api/resource/Tally Ledger",
        status_code=200,
        headers={"Content-Type": "text/html"},
        text="<html><body>Please log in</body></html>",
    )
    client = FrappeClient(settings=_settings())
    with pytest.raises(FrappeAPIError, match="FRAPPE_BASE_URL"):
        client.get("Tally Ledger", {"tally_guid": "g-1"})


def test_server_error_is_retried_then_raises_frappe_api_error(requests_mock):
    requests_mock.get(
        "https://example.frappe.cloud/api/resource/Tally Ledger", status_code=500, text="oops"
    )
    client = FrappeClient(settings=_settings())
    with pytest.raises(FrappeAPIError):
        client.get("Tally Ledger", {"tally_guid": "g-1"})
    assert requests_mock.call_count == 2
