from __future__ import annotations

import pytest
import requests

from config.settings import Settings
from tally.client import TallyClient
from utils.exceptions import TallyConnectionError, TallyResponseError


def _settings(**overrides):
    base = dict(
        tally_url="http://localhost:9000",
        retry_max_attempts=3,
        retry_backoff_base_seconds=0.01,
    )
    base.update(overrides)
    return Settings(**base)


def test_send_request_returns_body_on_success(requests_mock):
    requests_mock.post("http://localhost:9000", content=b"<ENVELOPE>ok</ENVELOPE>")
    client = TallyClient(settings=_settings())
    assert client.send_request(b"<ENVELOPE/>") == b"<ENVELOPE>ok</ENVELOPE>"


def test_send_request_retries_then_succeeds_on_connection_error(requests_mock):
    requests_mock.post(
        "http://localhost:9000",
        [
            {"exc": requests.ConnectionError},
            {"content": b"<ENVELOPE>ok</ENVELOPE>"},
        ],
    )
    client = TallyClient(settings=_settings())
    assert client.send_request(b"<ENVELOPE/>") == b"<ENVELOPE>ok</ENVELOPE>"


def test_send_request_raises_after_exhausting_retries(requests_mock):
    requests_mock.post("http://localhost:9000", exc=requests.ConnectionError)
    client = TallyClient(settings=_settings(retry_max_attempts=2))
    with pytest.raises(TallyConnectionError):
        client.send_request(b"<ENVELOPE/>")
    assert requests_mock.call_count == 2


def test_send_request_raises_on_non_200(requests_mock):
    requests_mock.post("http://localhost:9000", status_code=500, content=b"boom")
    client = TallyClient(settings=_settings())
    with pytest.raises(TallyResponseError):
        client.send_request(b"<ENVELOPE/>")


def test_send_request_raises_typed_error_on_malformed_url():
    client = TallyClient(settings=_settings(tally_url="localhost:9000", retry_max_attempts=1))
    with pytest.raises(TallyConnectionError, match="TALLY_URL"):
        client.send_request(b"<ENVELOPE/>")


def test_send_request_raises_on_line_error_body(requests_mock):
    requests_mock.post(
        "http://localhost:9000",
        content=b"<ENVELOPE><LINEERROR>Company not found</LINEERROR></ENVELOPE>",
    )
    client = TallyClient(settings=_settings())
    with pytest.raises(TallyResponseError, match="Company not found"):
        client.send_request(b"<ENVELOPE/>")
