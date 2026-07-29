from __future__ import annotations

from config.settings import Settings
from services.health_check import run_health_check


def _settings(**overrides):
    base = dict(
        tally_url="http://localhost:9000",
        frappe_base_url="https://example.frappe.cloud",
        frappe_api_key="key",
        frappe_api_secret="secret",
    )
    base.update(overrides)
    return Settings(**base)


def test_health_check_all_ok(requests_mock):
    requests_mock.get("http://localhost:9000", content=b"ok")
    requests_mock.get("https://example.frappe.cloud/api/method/ping", json={"message": "pong"})
    status = run_health_check(_settings())
    assert status.all_ok


def test_health_check_tally_down(requests_mock):
    import requests as requests_lib

    requests_mock.get("http://localhost:9000", exc=requests_lib.ConnectionError)
    requests_mock.get("https://example.frappe.cloud/api/method/ping", json={"message": "pong"})
    status = run_health_check(_settings())
    assert not status.tally_ok
    assert status.frappe_ok
    assert not status.all_ok


def test_health_check_frappe_auth_failure(requests_mock):
    requests_mock.get("http://localhost:9000", content=b"ok")
    requests_mock.get("https://example.frappe.cloud/api/method/ping", status_code=403, json={})
    status = run_health_check(_settings())
    assert status.tally_ok
    assert not status.frappe_ok


def test_health_check_frappe_not_configured(requests_mock):
    requests_mock.get("http://localhost:9000", content=b"ok")
    status = run_health_check(_settings(frappe_base_url=""))
    assert not status.frappe_ok
    assert "not configured" in status.frappe_error
