"""Pre-flight checks: is Tally reachable? Is Frappe reachable and authenticated?"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from config.settings import Settings, get_settings
from utils.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class HealthStatus:
    tally_ok: bool
    frappe_ok: bool
    tally_error: str | None = None
    frappe_error: str | None = None

    @property
    def all_ok(self) -> bool:
        return self.tally_ok and self.frappe_ok


def check_tally(settings: Settings | None = None) -> tuple[bool, str | None]:
    settings = settings or get_settings()
    try:
        requests.get(settings.tally_url, timeout=settings.tally_timeout_seconds)
        return True, None
    except requests.RequestException as exc:
        return False, str(exc)


def check_frappe(settings: Settings | None = None) -> tuple[bool, str | None]:
    settings = settings or get_settings()
    if not settings.frappe_base_url:
        return False, "FRAPPE_BASE_URL is not configured"
    try:
        response = requests.get(
            f"{settings.frappe_base_url}/api/method/ping",
            headers={
                "Authorization": f"token {settings.frappe_api_key}:{settings.frappe_api_secret}"
            },
            timeout=settings.frappe_timeout_seconds,
        )
        if response.status_code in (401, 403):
            return False, f"Frappe rejected credentials (HTTP {response.status_code})"
        return True, None
    except requests.RequestException as exc:
        return False, str(exc)


def run_health_check(settings: Settings | None = None) -> HealthStatus:
    settings = settings or get_settings()
    tally_ok, tally_error = check_tally(settings)
    frappe_ok, frappe_error = check_frappe(settings)
    status = HealthStatus(
        tally_ok=tally_ok, frappe_ok=frappe_ok, tally_error=tally_error, frappe_error=frappe_error
    )
    if not status.all_ok:
        logger.warning("Health check failed: tally_ok=%s frappe_ok=%s", tally_ok, frappe_ok)
    return status
