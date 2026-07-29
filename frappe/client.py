"""Thin REST client for Frappe's standard `/api/resource/<DocType>` API.

No schema assumptions beyond Frappe's own REST conventions: token auth via
`Authorization: token <api_key>:<api_secret>`, JSON in/out.
"""

from __future__ import annotations

import json
from typing import Any

import requests

from config.settings import Settings, get_settings
from services.retry_engine import build_retry_decorator
from utils.exceptions import FrappeAPIError, FrappeAuthError
from utils.logging_setup import get_logger

logger = get_logger(__name__)


class _TransientFrappeError(Exception):
    """Internal marker for retryable Frappe failures (timeouts, connection errors, 5xx)."""


class FrappeClient:
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self._retry = build_retry_decorator(
            (_TransientFrappeError,),
            max_attempts=self._settings.retry_max_attempts,
            base_wait_seconds=self._settings.retry_backoff_base_seconds,
        )

    def _headers(self) -> dict[str, str]:
        token = f"{self._settings.frappe_api_key}:{self._settings.frappe_api_secret}"
        return {
            "Authorization": f"token {token}",
            "Content-Type": "application/json",
        }

    def _url(self, doctype: str, name: str | None = None) -> str:
        base = f"{self._settings.frappe_base_url}/api/resource/{doctype}"
        return f"{base}/{name}" if name else base

    def _request(self, method: str, url: str, **kwargs: Any) -> dict:
        try:
            return self._retry(self._request_once)(method, url, **kwargs)
        except _TransientFrappeError as exc:
            raise FrappeAPIError(f"Frappe request failed after retries: {exc}") from exc

    def _request_once(self, method: str, url: str, **kwargs: Any) -> dict:
        try:
            response = requests.request(
                method,
                url,
                headers=self._headers(),
                timeout=self._settings.frappe_timeout_seconds,
                **kwargs,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise _TransientFrappeError(str(exc)) from exc
        except requests.exceptions.RequestException as exc:
            raise FrappeAPIError(
                f"Invalid FRAPPE_BASE_URL ({self._settings.frappe_base_url!r}): {exc}. "
                "Check FRAPPE_BASE_URL in .env — it must include a scheme, "
                "e.g. https://your-instance.frappe.cloud"
            ) from exc

        if response.status_code in (401, 403):
            raise FrappeAuthError(f"Frappe rejected credentials (HTTP {response.status_code})")
        if response.status_code >= 500:
            raise _TransientFrappeError(f"Frappe returned HTTP {response.status_code}")
        if response.status_code >= 400:
            raise FrappeAPIError(
                f"Frappe returned HTTP {response.status_code}: {response.text[:500]}"
            )

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            # HTTP succeeded but the body isn't JSON — almost always a wrong
            # FRAPPE_BASE_URL (pointing at a login/landing page, not the API)
            # rather than a transient issue, so don't retry it forever.
            content_type = response.headers.get("Content-Type", "unknown")
            snippet = response.text[:200].replace("\n", " ")
            raise FrappeAPIError(
                f"Frappe response wasn't valid JSON (Content-Type: {content_type}): {snippet!r}. "
                f"Check FRAPPE_BASE_URL ({self._settings.frappe_base_url!r}) points at your "
                "actual Frappe site's API, not a login page or the wrong host."
            ) from exc

    def get(
        self, doctype: str, filters: dict[str, Any], fields: list[str] | None = None
    ) -> list[dict]:
        filter_list = [[field, "=", value] for field, value in filters.items()]
        params = {"filters": json.dumps(filter_list)}
        if fields:
            params["fields"] = json.dumps(fields)
        result = self._request("GET", self._url(doctype), params=params)
        return result.get("data", [])

    def create(self, doctype: str, payload: dict[str, Any]) -> dict:
        result = self._request("POST", self._url(doctype), json=payload)
        return result.get("data", {})

    def update(self, doctype: str, name: str, payload: dict[str, Any]) -> dict:
        result = self._request("PUT", self._url(doctype, name), json=payload)
        return result.get("data", {})
