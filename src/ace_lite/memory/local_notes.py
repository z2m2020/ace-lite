"""Local notes provider layered on top of an upstream provider."""

from __future__ import annotations

import json
import threading
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ace_lite.text_tokens import code_token_set

from .helpers import (
    _dedupe_compacts,
    _dedupe_records,
    _estimate_tokens,
    _parse_iso_timestamp,
    _stable_handle,
    prune_memory_notes_rows,
)
from .protocol import MemoryProvider
from .record import MemoryRecord, MemoryRecordCompact

_CAPTURE_NOTES_LOCK = threading.Lock()


def _code_tokens(text: str) -> set[str]:
    """Code-aware tokenization for local notes lexical search.

    Examples:
    - getUserById -> {get, user, by, id, getuserbyid}
    - internal/app/api -> {internal, app, api}
    """
    return code_token_set(text, min_len=2, max_tokens=64)


def _overlap_ratio(*, query_tokens: set[str], field_tokens: set[str]) -> float:
    if not query_tokens or not field_tokens:
        return 0.0
    hits = len(query_tokens.intersection(field_tokens))
    if hits <= 0:
        return 0.0
    return float(hits) / float(max(1, len(query_tokens)))


def append_capture_note(
    *,
    notes_path: Path,
    query: str,
    repo: str,
    namespace: str | None,
    matched_keywords: Sequence[str],
    expiry_enabled: bool,
    ttl_days: int,
    max_age_days: int,
) -> tuple[int, int]:
    """Append a capture note to a JSONL file, pruning expired rows first."""
    captured_items = 0
    notes_pruned_expired_count = 0

    with _CAPTURE_NOTES_LOCK:
        notes_path.parent.mkdir(parents=True, exist_ok=True)

        existing_rows: list[dict[str, Any]] = []
        if notes_path.exists() and notes_path.is_file():
            with notes_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    raw = line.strip()
                    if not raw:
                        continue
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict):
                        existing_rows.append(payload)

        valid_rows, notes_pruned_expired_count = prune_memory_notes_rows(
            existing_rows,
            expiry_enabled=bool(expiry_enabled),
            ttl_days=max(1, int(ttl_days)),
            max_age_days=max(1, int(max_age_days)),
        )
        note = {
            "query": str(query or ""),
            "repo": str(repo or ""),
            "namespace": str(namespace or "").strip() or None,
            "matched_keywords": [
                str(keyword)
                for keyword in matched_keywords
                if isinstance(keyword, str) and keyword.strip()
            ],
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        valid_rows.append(note)
        with notes_path.open("w", encoding="utf-8") as fh:
            for row in valid_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        captured_items += 1

    return captured_items, notes_pruned_expired_count


class LocalNotesProvider:
    """Read local JSONL notes and merge them into memory search results."""

    def __init__(
        self,
        upstream: MemoryProvider,
        *,
        notes_path: str | Path = "context-map/memory_notes.jsonl",
        default_limit: int = 5,
        mode: str = "supplement",
        expiry_enabled: bool = True,
        ttl_days: int = 90,
        max_age_days: int = 365,
    ) -> None:
        self._upstream = upstream
        self._notes_path = Path(notes_path)
        self._notes_lock = threading.Lock()
        self._default_limit = max(1, int(default_limit))
        normalized_mode = str(mode or "supplement").strip().lower() or "supplement"
        if normalized_mode not in {"supplement", "prefer_local", "local_only"}:
            normalized_mode = "supplement"
        self._mode = normalized_mode
        self._expiry_enabled = bool(expiry_enabled)
        self._ttl_days = max(1, int(ttl_days))
        self._max_age_days = max(1, int(max_age_days))
        self.last_channel_used = "local_notes"
        self.fallback_reason: str | None = None
        self.last_container_tag_fallback: str | None = None
        self.strategy = getattr(upstream, "strategy", "semantic")
        self.last_notes_stats: dict[str, Any] = {
            "enabled": True,
            "mode": self._mode,
            "notes_path": str(self._notes_path),
            "expiry_enabled": self._expiry_enabled,
            "ttl_days": self._ttl_days,
            "max_age_days": self._max_age_days,
            "loaded_count": 0,
            "matched_count": 0,
            "selected_count": 0,
            "namespace_filtered_count": 0,
            "expired_count": 0,
            "cache_hit": False,
            "upstream_selected_count": 0,
            "local_share": 0.0,
        }
        self._last_local_records: dict[str, MemoryRecord] = {}
        self._notes_cache_rows: list[dict[str, Any]] = []
        self._notes_cache_expired_count = 0
        self._notes_cache_fingerprint: tuple[int, int] | None = None

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
            max(1, int(limit)) if isinstance(limit, int) and limit > 0 else self._default_limit
        )

        local_rows, local_records, note_stats = self._search_local_notes(
            query=query,
            container_tag=container_tag,
            limit=max(resolved_limit, self._default_limit),
        )
        self._last_local_records = local_records

        upstream_rows: list[MemoryRecordCompact] = []
        if self._mode != "local_only":
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
            self.fallback_reason = getattr(self._upstream, "fallback_reason", None)
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

        if self._mode == "local_only":
            merged = _dedupe_compacts(local_rows, limit=resolved_limit)
        elif self._mode == "prefer_local":
            merged = _dedupe_compacts([*local_rows, *upstream_rows], limit=resolved_limit)
        else:
            merged = _dedupe_compacts([*upstream_rows, *local_rows], limit=resolved_limit)

        upstream_channel = str(
            getattr(self._upstream, "last_channel_used", "upstream") or "upstream"
        )
        if merged and note_stats["selected_count"] > 0 and upstream_rows:
            self.last_channel_used = f"{upstream_channel}+local_notes"
        elif note_stats["selected_count"] > 0:
            self.last_channel_used = "local_notes"
        else:
            self.last_channel_used = upstream_channel

        self.last_notes_stats = {
            **note_stats,
            "enabled": True,
            "mode": self._mode,
            "notes_path": str(self._notes_path),
            "expiry_enabled": self._expiry_enabled,
            "ttl_days": self._ttl_days,
            "max_age_days": self._max_age_days,
            "selected_count": max(
                0,
                sum(1 for row in merged if str(row.source or "") == "local_notes"),
            ),
        }
        local_selected_count = int(self.last_notes_stats["selected_count"] or 0)
        upstream_selected_count = max(0, len(merged) - local_selected_count)
        self.last_notes_stats["upstream_selected_count"] = upstream_selected_count
        self.last_notes_stats["local_share"] = (
            float(local_selected_count) / float(len(merged)) if merged else 0.0
        )
        return merged

    def fetch(self, handles: Sequence[str]) -> list[MemoryRecord]:
        resolved_handles = [
            str(handle).strip() for handle in handles if str(handle).strip()
        ]
        if not resolved_handles:
            return []

        local_records: list[MemoryRecord] = []
        missing: list[str] = []
        for handle in resolved_handles:
            record = self._last_local_records.get(handle)
            if record is None:
                missing.append(handle)
                continue
            local_records.append(record)

        upstream_records: list[MemoryRecord] = []
        if missing and self._mode != "local_only":
            upstream_records = list(self._upstream.fetch(missing))

        if local_records and upstream_records:
            self.last_channel_used = "local_notes+upstream"
        elif local_records:
            self.last_channel_used = "local_notes"
        else:
            self.last_channel_used = str(
                getattr(self._upstream, "last_channel_used", "upstream") or "upstream"
            )

        merged = _dedupe_records([*local_records, *upstream_records])
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

    def _search_local_notes(
        self,
        *,
        query: str,
        container_tag: str | None,
        limit: int,
    ) -> tuple[list[MemoryRecordCompact], dict[str, MemoryRecord], dict[str, Any]]:
        rows, expired_count, cache_hit = self._load_notes_rows()
        query_tokens = _code_tokens(str(query or ""))
        query_phrase = str(query or "").strip().lower()

        matched: list[tuple[float, float, str, MemoryRecordCompact, MemoryRecord]] = []
        namespace_filtered = 0

        for row in rows:
            namespace = str(row.get("namespace") or "").strip() or None
            if container_tag and namespace != container_tag:
                namespace_filtered += 1
                continue

            text = str(row.get("text") or row.get("query") or "").strip()
            if not text:
                continue
            note_query_text = str(row.get("query") or "").strip()
            keyword_text = " ".join(
                str(value) for value in row.get("matched_keywords", []) if str(value).strip()
            ).strip()

            text_tokens = _code_tokens(text)
            query_field_tokens = _code_tokens(note_query_text)
            keyword_tokens = _code_tokens(keyword_text)

            # Weighted overlap across fields:
            # - note text: primary signal
            # - matched_keywords: often high-signal "why it was captured"
            # - captured query: secondary signal (may be noisy)
            score = 0.0
            score += 1.0 * _overlap_ratio(query_tokens=query_tokens, field_tokens=text_tokens)
            score += 1.2 * _overlap_ratio(query_tokens=query_tokens, field_tokens=keyword_tokens)
            score += 0.8 * _overlap_ratio(query_tokens=query_tokens, field_tokens=query_field_tokens)

            if score <= 0.0:
                continue

            search_blob = " ".join([text, note_query_text, keyword_text]).strip().lower()
            if query_phrase and search_blob and query_phrase in search_blob:
                score += 0.5

            # Cap score for stability.
            if score > 2.0:
                score = 2.0

            metadata: dict[str, Any] = {
                key: row[key]
                for key in ("namespace", "repo", "captured_at", "created_at", "source", "tags")
                if key in row
            }
            handle = _stable_handle(text=text, metadata=metadata)
            compact = MemoryRecordCompact(
                handle=handle,
                preview=text,
                score=round(float(score), 6),
                metadata=metadata,
                est_tokens=_estimate_tokens(text),
                source="local_notes",
            )
            record = MemoryRecord(
                text=text,
                score=round(float(score), 6),
                metadata=metadata,
                handle=handle,
                source="local_notes",
            )
            timestamp = _parse_iso_timestamp(
                row.get("captured_at") or row.get("created_at") or row.get("updated_at")
            )
            matched.append((float(score), timestamp, handle, compact, record))

        matched.sort(key=lambda item: (-item[0], -item[1], item[2]))
        selected = matched[: max(1, int(limit))]
        compacts = [item[3] for item in selected]
        records = {item[2]: item[4] for item in selected}
        stats = {
            "loaded_count": len(rows),
            "matched_count": len(matched),
            "selected_count": len(selected),
            "namespace_filtered_count": namespace_filtered,
            "expired_count": expired_count,
            "cache_hit": cache_hit,
        }
        return compacts, records, stats

    @staticmethod
    def _build_notes_fingerprint(stat_result: Any) -> tuple[int, int]:
        mtime_ns = getattr(stat_result, "st_mtime_ns", None)
        if not isinstance(mtime_ns, int):
            mtime_seconds = float(getattr(stat_result, "st_mtime", 0.0) or 0.0)
            mtime_ns = int(mtime_seconds * 1_000_000_000)
        size = int(getattr(stat_result, "st_size", 0) or 0)
        return max(0, int(mtime_ns)), max(0, size)

    def _load_notes_rows(self) -> tuple[list[dict[str, Any]], int, bool]:
        with self._notes_lock:
            if not self._notes_path.exists() or not self._notes_path.is_file():
                self._notes_cache_rows = []
                self._notes_cache_expired_count = 0
                self._notes_cache_fingerprint = None
                return [], 0, False

            try:
                stat_result = self._notes_path.stat()
            except OSError:
                return [], 0, False

            fingerprint = self._build_notes_fingerprint(stat_result)
            if self._notes_cache_fingerprint == fingerprint:
                return (
                    [dict(row) for row in self._notes_cache_rows],
                    int(self._notes_cache_expired_count),
                    True,
                )

            rows: list[dict[str, Any]] = []
            try:
                with self._notes_path.open("r", encoding="utf-8") as fh:
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
                return [], 0, False

            valid_rows, expired_count = prune_memory_notes_rows(
                rows,
                expiry_enabled=self._expiry_enabled,
                ttl_days=self._ttl_days,
                max_age_days=self._max_age_days,
            )
            if expired_count > 0:
                try:
                    self._notes_path.parent.mkdir(parents=True, exist_ok=True)
                    with self._notes_path.open("w", encoding="utf-8") as fh:
                        for row in valid_rows:
                            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    fingerprint = self._build_notes_fingerprint(self._notes_path.stat())
                except OSError:
                    pass

            self._notes_cache_rows = [dict(row) for row in valid_rows]
            self._notes_cache_expired_count = int(expired_count)
            self._notes_cache_fingerprint = fingerprint
            return [dict(row) for row in valid_rows], int(expired_count), False
