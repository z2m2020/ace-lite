"""Local JSONL write-through cache memory provider."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .helpers import (
    _dedupe_records,
    _estimate_tokens,
    _normalize_metadata,
)
from .protocol import MemoryProvider
from .record import MemoryRecord, MemoryRecordCompact

logger = logging.getLogger(__name__)


class LocalCacheProvider:
    """JSONL write-through cache wrapper for deterministic local replay."""

    def __init__(
        self,
        upstream: MemoryProvider,
        *,
        cache_path: str | Path = "context-map/memory_cache.jsonl",
        ttl_seconds: int = 7 * 24 * 60 * 60,
        max_entries: int = 5000,
        channel_name: str = "local_cache",
    ) -> None:
        self._upstream = upstream
        self._cache_path = Path(cache_path)
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._max_entries = max(16, int(max_entries))
        self._channel_name = channel_name
        self._io_lock = threading.RLock()
        self.last_channel_used = channel_name
        self.fallback_reason: str | None = None
        self.last_container_tag_fallback: str | None = None
        self.strategy = getattr(upstream, "strategy", "semantic")
        self.last_cache_stats: dict[str, Any] = {
            "enabled": True,
            "hit_count": 0,
            "miss_count": 0,
            "evicted_count": 0,
        }

    def search_compact(
        self,
        query: str,
        *,
        limit: int | None = None,
        container_tag: str | None = None,
    ) -> list[MemoryRecordCompact]:
        self.fallback_reason = None
        self.last_container_tag_fallback = None
        resolved_limit = (
            max(1, int(limit)) if isinstance(limit, int) and limit > 0 else None
        )
        namespace_key = str(container_tag or "").strip()
        fingerprint_source = f"{namespace_key}\n{query}".encode()
        query_fingerprint = hashlib.sha256(fingerprint_source).hexdigest()
        now_ts = time.time()

        rows = self._load_rows()
        rows, evicted_count = self._prune_rows(rows, now_ts=now_ts)

        matches = [
            row
            for row in rows
            if str(row.get("query_fingerprint", "")).strip() == query_fingerprint
        ]
        matches.sort(
            key=lambda row: (
                -float(row.get("score") or 0.0),
                -float(row.get("updated_at_ts") or 0.0),
                str(row.get("handle") or ""),
            )
        )
        if resolved_limit is not None:
            matches = matches[:resolved_limit]

        if matches:
            self.last_channel_used = f"{self._channel_name}:hit"
            self.fallback_reason = None
            self.last_cache_stats = {
                "enabled": True,
                "hit_count": len(matches),
                "miss_count": 0,
                "evicted_count": evicted_count,
            }
            if evicted_count > 0:
                self._save_rows(rows)
            return [self._row_to_compact(row) for row in matches]

        if container_tag is None:
            upstream_rows = list(self._upstream.search_compact(query, limit=resolved_limit))
        else:
            upstream_rows = list(
                self._upstream.search_compact(
                    query,
                    limit=resolved_limit,
                    container_tag=container_tag,
                )
            )
        upstream_namespace_fallback = getattr(
            self._upstream,
            "last_container_tag_fallback",
            None,
        )
        if (
            isinstance(upstream_namespace_fallback, str)
            and upstream_namespace_fallback.strip()
        ):
            self.last_container_tag_fallback = upstream_namespace_fallback.strip()

        created_at_iso = datetime.now(timezone.utc).isoformat()
        new_rows: list[dict[str, Any]] = []
        for upstream_row in upstream_rows:
            handle = str(upstream_row.handle or "").strip()
            if not handle:
                continue
            new_rows.append(
                {
                    "handle": handle,
                    "query_fingerprint": query_fingerprint,
                    "preview": str(upstream_row.preview or ""),
                    "text": "",
                    "metadata": dict(upstream_row.metadata),
                    "score": float(upstream_row.score)
                    if isinstance(upstream_row.score, (int, float))
                    else None,
                    "source": str(
                        upstream_row.source
                        or getattr(self._upstream, "last_channel_used", "upstream")
                    ),
                    "created_at": created_at_iso,
                    "updated_at": created_at_iso,
                    "updated_at_ts": now_ts,
                    "expires_at_ts": now_ts + self._ttl_seconds,
                    "full_text_available": False,
                }
            )

        if new_rows:
            existing_index = {
                (
                    str(item.get("query_fingerprint") or ""),
                    str(item.get("handle") or ""),
                ): idx
                for idx, item in enumerate(rows)
                if isinstance(item, dict)
            }
            for new_row in new_rows:
                key = (
                    str(new_row.get("query_fingerprint") or ""),
                    str(new_row.get("handle") or ""),
                )
                target_idx = existing_index.get(key)
                if target_idx is None:
                    existing_index[key] = len(rows)
                    rows.append(new_row)
                else:
                    rows[target_idx] = new_row

        rows, extra_evicted = self._prune_rows(rows, now_ts=now_ts)
        self._save_rows(rows)

        self.last_channel_used = getattr(
            self._upstream, "last_channel_used", "upstream"
        )
        self.fallback_reason = getattr(self._upstream, "fallback_reason", None)
        self.last_cache_stats = {
            "enabled": True,
            "hit_count": 0,
            "miss_count": len(upstream_rows),
            "evicted_count": evicted_count + extra_evicted,
        }
        return upstream_rows

    def fetch(self, handles: Sequence[str]) -> list[MemoryRecord]:
        resolved_handles = [
            str(handle).strip() for handle in handles if str(handle).strip()
        ]
        if not resolved_handles:
            return []

        rows = self._load_rows()
        rows, evicted_count = self._prune_rows(rows, now_ts=time.time())
        if evicted_count > 0:
            self._save_rows(rows)

        latest_by_handle: dict[str, dict[str, Any]] = {}
        for cache_row in rows:
            handle = str(cache_row.get("handle") or "").strip()
            if not handle:
                continue
            previous = latest_by_handle.get(handle)
            if previous is None or float(cache_row.get("updated_at_ts") or 0.0) > float(
                previous.get("updated_at_ts") or 0.0
            ):
                latest_by_handle[handle] = cache_row

        found: list[MemoryRecord] = []
        missing: list[str] = []
        for handle in resolved_handles:
            candidate_row = latest_by_handle.get(handle)
            if candidate_row is None:
                missing.append(handle)
                continue

            has_full_text = bool(
                candidate_row.get("full_text_available")
                or str(candidate_row.get("text") or "").strip()
            )
            if not has_full_text:
                missing.append(handle)
                continue

            found.append(self._row_to_record(candidate_row))

        if not missing:
            self.last_channel_used = f"{self._channel_name}:fetch_hit"
            return _dedupe_records(found)

        try:
            upstream_records = list(self._upstream.fetch(missing))
        except Exception as exc:
            self.fallback_reason = f"upstream_fetch_error:{exc.__class__.__name__}"
            logger.warning(
                "memory.cache.fetch.upstream_failed",
                extra={
                    "missing_count": len(missing),
                    "error": exc.__class__.__name__,
                },
            )
            if found:
                self.last_channel_used = f"{self._channel_name}:fetch_partial"
                return _dedupe_records(found)
            raise
        now_ts = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        upstream_by_handle = {
            str(record.handle).strip(): record
            for record in upstream_records
            if isinstance(record.handle, str) and record.handle.strip()
        }
        if upstream_by_handle:
            touched = False
            remaining = set(upstream_by_handle)
            for idx, row in enumerate(rows):
                handle = str(row.get("handle") or "").strip()
                record = upstream_by_handle.get(handle)
                if record is None:
                    continue

                rows[idx] = {
                    **dict(row),
                    "text": str(record.text or ""),
                    "metadata": dict(record.metadata),
                    "score": float(record.score)
                    if isinstance(record.score, (int, float))
                    else row.get("score"),
                    "source": str(record.source or row.get("source") or "upstream"),
                    "updated_at": now_iso,
                    "updated_at_ts": now_ts,
                    "expires_at_ts": now_ts + self._ttl_seconds,
                    "full_text_available": True,
                }
                touched = True
                remaining.discard(handle)

            for handle in sorted(remaining):
                record = upstream_by_handle[handle]
                rows.append(
                    {
                        "handle": handle,
                        "query_fingerprint": "",
                        "preview": str(record.text or ""),
                        "text": str(record.text or ""),
                        "metadata": dict(record.metadata),
                        "score": float(record.score)
                        if isinstance(record.score, (int, float))
                        else None,
                        "source": str(record.source or "upstream"),
                        "created_at": now_iso,
                        "updated_at": now_iso,
                        "updated_at_ts": now_ts,
                        "expires_at_ts": now_ts + self._ttl_seconds,
                        "full_text_available": True,
                    }
                )
                touched = True

            if touched:
                rows, _ = self._prune_rows(rows, now_ts=now_ts)
                self._save_rows(rows)

        self.last_channel_used = getattr(
            self._upstream, "last_channel_used", "upstream"
        )

        merged = _dedupe_records([*found, *upstream_records])
        by_handle = {
            str(record.handle).strip(): record
            for record in merged
            if isinstance(record.handle, str) and record.handle.strip()
        }

        ordered: list[MemoryRecord] = []
        for handle in resolved_handles:
            record = by_handle.get(handle)
            if record is not None:
                ordered.append(record)
        return ordered

    def _load_rows(self) -> list[dict[str, Any]]:
        with self._io_lock:
            if not self._cache_path.exists() or not self._cache_path.is_file():
                return []

            rows: list[dict[str, Any]] = []
            try:
                with self._cache_path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        raw = line.strip()
                        if not raw:
                            continue
                        try:
                            payload = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(payload, dict):
                            rows.append(payload)
            except OSError:
                return []
            return rows

    def _save_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        with self._io_lock:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._cache_path.with_suffix(self._cache_path.suffix + ".tmp")
            with tmp_path.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True))
                    fh.write("\n")
            tmp_path.replace(self._cache_path)

    def _prune_rows(
        self,
        rows: Sequence[dict[str, Any]],
        *,
        now_ts: float,
    ) -> tuple[list[dict[str, Any]], int]:
        valid: list[dict[str, Any]] = []
        evicted = 0

        for row in rows:
            expires_at = row.get("expires_at_ts")
            if isinstance(expires_at, (int, float)) and float(expires_at) < now_ts:
                evicted += 1
                continue
            valid.append(dict(row))

        valid.sort(
            key=lambda row: (
                -float(row.get("updated_at_ts") or 0.0),
                -float(row.get("score") or 0.0),
                str(row.get("handle") or ""),
            )
        )

        if len(valid) > self._max_entries:
            overflow = len(valid) - self._max_entries
            evicted += overflow
            valid = valid[: self._max_entries]

        return valid, evicted

    @staticmethod
    def _row_to_compact(row: Mapping[str, Any]) -> MemoryRecordCompact:
        preview = str(row.get("preview") or row.get("text") or "")
        metadata = _normalize_metadata(row.get("metadata"))
        score = row.get("score")
        normalized_score = float(score) if isinstance(score, (int, float)) else None
        return MemoryRecordCompact(
            handle=str(row.get("handle") or ""),
            preview=preview,
            score=normalized_score,
            metadata=metadata,
            est_tokens=_estimate_tokens(preview),
            source=str(row.get("source") or "local_cache"),
        )

    @staticmethod
    def _row_to_record(row: Mapping[str, Any]) -> MemoryRecord:
        text = str(row.get("text") or row.get("preview") or "")
        metadata = _normalize_metadata(row.get("metadata"))
        score = row.get("score")
        normalized_score = float(score) if isinstance(score, (int, float)) else None
        return MemoryRecord(
            text=text,
            score=normalized_score,
            metadata=metadata,
            handle=str(row.get("handle") or ""),
            source=str(row.get("source") or "local_cache"),
        )
