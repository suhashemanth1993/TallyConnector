"""HTTP client for TallyPrime's local XML/HTTP Collection API."""

from __future__ import annotations

import requests

from config.settings import Settings, get_settings
from services.retry_engine import build_retry_decorator
from utils.exceptions import TallyConnectionError, TallyResponseError
from utils.logging_setup import get_logger

logger = get_logger(__name__)

_HEADERS = {"Content-Type": "text/xml"}


class TallyClient:
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self._retry = build_retry_decorator(
            (TallyConnectionError,),
            max_attempts=self._settings.retry_max_attempts,
            base_wait_seconds=self._settings.retry_backoff_base_seconds,
        )

    def send_request(self, xml_request: bytes) -> bytes:
        return self._retry(self._send_once)(xml_request)

    def _send_once(self, xml_request: bytes) -> bytes:
        try:
            response = requests.post(
                self._settings.tally_url,
                data=xml_request,
                headers=_HEADERS,
                timeout=self._settings.tally_timeout_seconds,
            )
        except requests.Timeout as exc:
            raise TallyConnectionError(
                f"Timed out connecting to Tally at {self._settings.tally_url}"
            ) from exc
        except requests.ConnectionError as exc:
            raise TallyConnectionError(
                f"Could not connect to Tally at {self._settings.tally_url}: {exc}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise TallyConnectionError(
                f"Invalid TALLY_URL ({self._settings.tally_url!r}): {exc}. "
                "Check TALLY_URL in .env — it must include a scheme, e.g. http://localhost:9000"
            ) from exc

        if response.status_code != 200:
            logger.error("Tally returned HTTP %s", response.status_code)
            raise TallyResponseError(f"Tally returned unexpected status {response.status_code}")

        body = response.content
        if b"<LINEERROR>" in body:
            error_text = _extract_line_error(body)
            raise TallyResponseError(f"Tally reported an error: {error_text}")

        return body


def _extract_line_error(body: bytes) -> str:
    start = body.find(b"<LINEERROR>")
    end = body.find(b"</LINEERROR>", start)
    if start == -1 or end == -1:
        return "unknown error"
    return body[start + len(b"<LINEERROR>") : end].decode("utf-8", errors="replace")
