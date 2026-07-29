from __future__ import annotations

from app import main
from config.settings import get_settings
from tests.conftest import load_fixture


def _configure_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TALLY_URL", "http://localhost:9000")
    monkeypatch.setenv("FRAPPE_BASE_URL", "https://example.frappe.cloud")
    monkeypatch.setenv("FRAPPE_API_KEY", "key")
    monkeypatch.setenv("FRAPPE_API_SECRET", "secret")
    monkeypatch.setenv("STATE_DB_PATH", str(tmp_path / "state.db"))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("RETRY_MAX_ATTEMPTS", "1")
    get_settings.cache_clear()


def test_cli_resync_entity_success(tmp_path, requests_mock, monkeypatch):
    _configure_env(monkeypatch, tmp_path)

    def tally_cb(request, context):
        body = request.body if isinstance(request.body, bytes) else request.body.encode()
        if b"ledger Collection" in body:
            return load_fixture("ledger_collection_response.xml")
        return b"<ENVELOPE></ENVELOPE>"

    requests_mock.post("http://localhost:9000", content=tally_cb)
    requests_mock.get("https://example.frappe.cloud/api/resource/Tally Ledger", json={"data": []})
    requests_mock.post(
        "https://example.frappe.cloud/api/resource/Tally Ledger",
        json={"data": {"name": "LEDG-0001"}},
    )

    exit_code = main(["--resync-entity", "ledger"])
    assert exit_code == 0


def test_cli_resync_unknown_entity_returns_error(tmp_path, requests_mock, monkeypatch):
    _configure_env(monkeypatch, tmp_path)
    exit_code = main(["--resync-entity", "not_a_real_entity"])
    assert exit_code == 2


def test_cli_health_check_reports_failure(tmp_path, requests_mock, monkeypatch):
    _configure_env(monkeypatch, tmp_path)
    import requests as requests_lib

    requests_mock.get("http://localhost:9000", exc=requests_lib.ConnectionError)
    requests_mock.get("https://example.frappe.cloud/api/method/ping", json={"message": "pong"})

    exit_code = main(["--health-check"])
    assert exit_code == 1


def test_cli_resync_range_without_entity_errors(tmp_path, monkeypatch, capsys):
    _configure_env(monkeypatch, tmp_path)
    try:
        main(["--resync-range", "2024-01-01", "2024-01-31"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")
