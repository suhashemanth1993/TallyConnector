"""Typed exceptions used across the connector, so callers can catch narrowly
instead of bare `except Exception`."""

from __future__ import annotations


class TallyConnectorError(Exception):
    """Base class for all errors raised by this package."""


class TallyConnectionError(TallyConnectorError):
    """Tally could not be reached (connection refused, DNS, timeout)."""


class TallyResponseError(TallyConnectorError):
    """Tally responded, but with a non-success HTTP status or an error body."""


class TallyXMLParseError(TallyConnectorError):
    """Tally's response body could not be parsed as the expected XML shape."""


class FrappeAuthError(TallyConnectorError):
    """Frappe rejected the request due to invalid/expired credentials (401/403)."""


class FrappeAPIError(TallyConnectorError):
    """Frappe responded with an unexpected error status or body."""


class SyncConflictError(TallyConnectorError):
    """A record changed on both sides in a way the current conflict policy can't resolve."""


class TallyDataError(TallyConnectorError):
    """A record is structurally unusable (e.g. missing its natural key).

    Distinct from transient errors: retrying will not fix this, so callers
    should log and skip rather than queue it for retry.
    """
