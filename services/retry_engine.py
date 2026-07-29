"""A single config-driven retry policy shared by TallyClient and FrappeClient.

Built as a factory (not a module-level decorator) so it reads
max_attempts/backoff from Settings at client-construction time rather than
at import time, letting `.env` changes take effect without code changes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

T = TypeVar("T")


def build_retry_decorator(
    exceptions: tuple[type[Exception], ...],
    *,
    max_attempts: int,
    base_wait_seconds: float,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    return retry(
        retry=retry_if_exception_type(exceptions),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=base_wait_seconds, min=base_wait_seconds, max=60),
        reraise=True,
    )
