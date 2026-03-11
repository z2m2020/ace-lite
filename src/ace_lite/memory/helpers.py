"""Shared helper utilities for memory providers."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from .record import MemoryRecord, MemoryRecordCompact


def _estimate_tokens(text: str) -> int:
    return max(1, len(str(text or "").split()))


def _normalize_metadata(metadata: Any) -> dict[str, Any]:
    if isinstance(metadata, Mapping):
        return dict(metadata)
    return {}


def _stable_handle(*, text: str, metadata: Mapping[str, Any]) -> str:
    for key in ("id", "handle", "memory_id", "uid"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    metadata_json = json.dumps(
        dict(metadata), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    fingerprint_source = f"{text}::{metadata_json}".encode()
    return f"sha256:{hashlib.sha256(fingerprint_source).hexdigest()}"


def _parse_iso_timestamp(value: Any) -> float:
    if not isinstance(value, str):
        return 0.0
    normalized = str(value).strip()
    if not normalized:
        return 0.0
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return float(datetime.fromisoformat(normalized).timestamp())
    except ValueError:
        return 0.0


def prune_memory_notes_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    now_ts: float | None = None,
    expiry_enabled: bool = True,
    ttl_days: int = 90,
    max_age_days: int = 365,
) -> tuple[list[dict[str, Any]], int]:
    normalized_rows: list[dict[str, Any]] = []
    if not isinstance(rows, Sequence):
        return normalized_rows, 0

    for item in rows:
        if isinstance(item, Mapping):
            normalized_rows.append(dict(item))
    if not normalized_rows:
        return [], 0

    if not expiry_enabled:
        return normalized_rows, 0

    resolved_now = float(now_ts) if isinstance(now_ts, (int, float)) else time.time()
    ttl_cutoff = resolved_now - max(1, int(ttl_days)) * 86400.0
    max_age_cutoff = resolved_now - max(1, int(max_age_days)) * 86400.0

    valid: list[dict[str, Any]] = []
    expired_count = 0
    for row in normalized_rows:
        last_seen_ts = _parse_iso_timestamp(
            row.get("last_used_at")
            or row.get("captured_at")
            or row.get("updated_at")
            or row.get("created_at")
        )
        created_ts = _parse_iso_timestamp(
            row.get("created_at")
            or row.get("captured_at")
            or row.get("updated_at")
            or row.get("last_used_at")
        )
        ttl_expired = last_seen_ts > 0.0 and last_seen_ts < ttl_cutoff
        max_age_expired = created_ts > 0.0 and created_ts < max_age_cutoff
        if ttl_expired or max_age_expired:
            expired_count += 1
            continue
        valid.append(row)

    return valid, expired_count


def _dedupe_compacts(
    rows: Sequence[MemoryRecordCompact], *, limit: int | None = None
) -> list[MemoryRecordCompact]:
    deduped: list[MemoryRecordCompact] = []
    seen: set[str] = set()
    resolved_limit = (
        max(1, int(limit)) if isinstance(limit, int) and limit > 0 else None
    )

    for row in rows:
        handle = str(row.handle or "").strip()
        if not handle or handle in seen:
            continue
        seen.add(handle)
        deduped.append(row)
        if resolved_limit is not None and len(deduped) >= resolved_limit:
            break

    return deduped


def _dedupe_records(records: Sequence[MemoryRecord]) -> list[MemoryRecord]:
    deduped: list[MemoryRecord] = []
    seen: set[str] = set()

    for record in records:
        metadata = _normalize_metadata(record.metadata)
        handle = str(record.handle or "").strip() or _stable_handle(
            text=str(record.text or ""), metadata=metadata
        )
        if handle in seen:
            continue
        seen.add(handle)
        deduped.append(
            MemoryRecord(
                text=str(record.text or ""),
                score=float(record.score)
                if isinstance(record.score, (int, float))
                else None,
                metadata=metadata,
                handle=handle,
                source=str(record.source or "memory"),
            )
        )

    return deduped
