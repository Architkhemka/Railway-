"""Append-only, hash-chained JSONL audit events for model services."""

import fcntl
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_GENESIS_HASH = "0" * 64


def record_audit_event(service: str, event: str, details: dict[str, Any]) -> None:
    """Persist a hash-chained event without recording passenger identifiers."""
    path = Path(os.environ.get("AUDIT_LOG_PATH", "data/audit/events.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as audit_file:
        fcntl.flock(audit_file.fileno(), fcntl.LOCK_EX)
        try:
            audit_file.seek(0, os.SEEK_END)
            previous_hash = _GENESIS_HASH
            if audit_file.tell():
                audit_file.seek(0, os.SEEK_END)
                audit_file.seek(max(0, audit_file.tell() - 8192))
                lines = audit_file.readlines()
                if lines:
                    previous = json.loads(lines[-1])
                    previous_hash = str(previous["event_hash"])
            payload = {
                "timestamp": datetime.now(UTC).isoformat(),
                "service": service,
                "event": event,
                "details": details,
                "previous_hash": previous_hash,
            }
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            payload["event_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            audit_file.seek(0, os.SEEK_END)
            audit_file.write(json.dumps(payload, sort_keys=True) + "\n")
            audit_file.flush()
            os.fsync(audit_file.fileno())
        finally:
            fcntl.flock(audit_file.fileno(), fcntl.LOCK_UN)
