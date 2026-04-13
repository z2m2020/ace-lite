"""Timestamp parsing helpers shared by memory components."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


def parse_memory_timestamp(value: Any) -> float | None:
    """Parse a timestamp value to Unix epoch seconds (UTC).

    Supports:
    - int/float epoch seconds
    - ISO-8601 string (naive treated as UTC for deterministic behavior)
    """
    if isinstance(value, (int, float)):
        candidate = float(value)
        if math.isfinite(candidate):
            return candidate
        return None

    if not isinstance(value, str):
        return None

    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).timestamp()


def extract_memory_record_timestamp(metadata: dict[str, Any]) -> float | None:
    """Extract an epoch timestamp from memory record metadata."""
    for key in (
        "updated_at_ts",
        "created_at_ts",
        "timestamp",
        "updated_at",
        "created_at",
        "captured_at",
        "last_used_at",
    ):
        ts = parse_memory_timestamp(metadata.get(key))
        if ts is None:
            continue
        if ts <= 0.0:
            continue
        return float(ts)
    return None


__all__ = ["extract_memory_record_timestamp", "parse_memory_timestamp"]

