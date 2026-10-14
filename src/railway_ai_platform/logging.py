"""Structured JSON logging with redaction for common sensitive fields."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

_STANDARD_FIELDS = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}
_SENSITIVE_FIELDS = {
    "authorization",
    "email",
    "jwt",
    "name",
    "password",
    "phone",
    "pnr",
    "secret",
    "token",
}


def _redact(value: Any, key: str = "") -> Any:
    if key.lower() in _SENSITIVE_FIELDS or key.lower().endswith(("_token", "_secret")):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(item_key): _redact(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list | tuple):
        return [_redact(item) for item in value]
    return value


class JSONFormatter(logging.Formatter):
    """Serialize a log record and its structured extras as one JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            {
                key: _redact(value, key)
                for key, value in record.__dict__.items()
                if key not in _STANDARD_FIELDS and not key.startswith("_")
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging to emit structured JSON to stderr."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    if not root_logger.handlers:
        root_logger.addHandler(logging.StreamHandler())
    for handler in root_logger.handlers:
        handler.setFormatter(JSONFormatter())
