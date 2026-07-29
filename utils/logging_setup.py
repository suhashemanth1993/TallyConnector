"""Rotating file + console logging, with a filter that scrubs secrets from
every record before it's formatted or written anywhere."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 5

_REDACTED = "***REDACTED***"
_SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|api[_-]?secret|authorization|password|token)"
    r"(['\"]?\s*[:=]\s*['\"]?)([^'\"\s,}&]+)",
    re.IGNORECASE,
)


def redact(text: str) -> str:
    """Scrub common secret-bearing key/value patterns out of a log message."""
    return _SECRET_KEY_PATTERN.sub(rf"\1\2{_REDACTED}", text)


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            record.args = tuple(redact(arg) if isinstance(arg, str) else arg for arg in record.args)
        return True


def configure_logging(
    *, log_dir: str = "logs", log_level: str = "INFO", debug_mode: bool = False
) -> None:
    """Configure the root logger with rotating file + console handlers.

    Safe to call more than once (e.g. in tests); handlers are replaced, not stacked.
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if debug_mode else getattr(logging, log_level.upper(), logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    redaction_filter = RedactionFilter()

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.addFilter(redaction_filter)
    root.addHandler(console)

    app_file = RotatingFileHandler(
        Path(log_dir) / "app.log", maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT
    )
    app_file.setFormatter(fmt)
    app_file.addFilter(redaction_filter)
    root.addHandler(app_file)

    error_file = RotatingFileHandler(
        Path(log_dir) / "error.log", maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT
    )
    error_file.setLevel(logging.ERROR)
    error_file.setFormatter(fmt)
    error_file.addFilter(redaction_filter)
    root.addHandler(error_file)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
