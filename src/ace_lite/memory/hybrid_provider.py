"""Hybrid memory provider using reciprocal-rank fusion."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ace_lite.concurrency import LanePool, build_memory_lane_pool

from .helpers import _dedupe_compacts, _dedupe_records, _estimate_tokens
from .protocol import MemoryProvider
from .record import MemoryRecord, MemoryRecordCompact


class HybridMemoryProvider:
    """Merge semantic and keyword channels via Reciprocal Rank Fusion."""

    def __init__(
        self,
        semantic: MemoryProvider,
        keyword: MemoryProvider,
        *,
        rrf_k: int = 60,
        limit: int = 20,
        lane_pool: LanePool | None = None,
        search_lane: str = "main",
        fetch_lane: str = "sub",
    ) -> None:
        self._semantic = semantic
        self._keyword = keyword
        self._rrf_k = max(1, int(rrf_k))
        self._limit = max(1, int(limit))
        self._lane_pool = lane_pool or build_memory_lane_pool()
        self._search_lane = str(search_lane or "main").strip() or "main"
        self._fetch_lane = str(fetch_lane or "sub").strip() or "sub"
        self.last_channel_used = "hybrid"
        self.fallback_reason: str | None = None
        self.last_container_tag_fallback: str | None = None
        self.strategy = "hybrid"
        self.last_hybrid_stats: dict[str, Any] = {
            "semantic_candidates": 0,
            "keyword_candidates": 0,
            "merged_candidates": 0,
            "rrf_k": self._rrf_k,
        }
        self._last_semantic_handles: set[str] = set()
        self._last_keyword_handles: set[str] = set()

    def search_compact(
        self,
        query: str,
        *,
        limit: int | None = None,
        container_tag: str | None = None,
    ) -> list[MemoryRecordCompact]:
        resolved_limit = self._limit
        if isinstance(limit, int) and limit > 0:
            resolved_limit = max(1, int(limit))

        self.last_channel_used = "hybrid"
        self.fallback_reason = None
        self.last_container_tag_fallback = None

        errors: list[str] = []

        def _search(
            provider: MemoryProvider, name: str
        ) -> tuple[str, list[MemoryRecordCompact]]:
            try:
                if container_tag is None:
                    rows = list(provider.search_compact(query, limit=resolved_limit))
                else:
                    rows = list(
                        provider.search_compact(
                            query,
                            limit=resolved_limit,
                            container_tag=container_tag,
                        )
                    )
                return name, rows
            except Exception as exc:  # pragma: no cover - defensive path
                errors.append(f"{name}:{exc.__class__.__name__}")
                return name, []

        semantic_future = self._lane_pool.submit(
            self._search_lane,
            _search,
            self._semantic,
            "semantic",
        )
        keyword_future = self._lane_pool.submit(
            self._search_lane,
            _search,
            self._keyword,
            "keyword",
        )
        semantic_name, semantic_rows = semantic_future.result()
        keyword_name, keyword_rows = keyword_future.result()
        for provider in (self._semantic, self._keyword):
            namespace_fallback = getattr(provider, "last_container_tag_fallback", None)
            if isinstance(namespace_fallback, str) and namespace_fallback.strip():
                self.last_container_tag_fallback = namespace_fallback.strip()
                break

        if errors and not semantic_rows and not keyword_rows:
            self.fallback_reason = "hybrid_error:" + ",".join(errors)

        semantic_rows = _dedupe_compacts(semantic_rows)
        keyword_rows = _dedupe_compacts(keyword_rows)

        self._last_semantic_handles = {
            row.handle for row in semantic_rows if row.handle
        }
        self._last_keyword_handles = {row.handle for row in keyword_rows if row.handle}

        merged_scores: dict[str, float] = {}
        merged_rows: dict[str, MemoryRecordCompact] = {}

        for rank, row in enumerate(semantic_rows, start=1):
            if not row.handle:
                continue
            merged_scores[row.handle] = merged_scores.get(row.handle, 0.0) + 1.0 / (
                self._rrf_k + rank
            )
            merged_rows.setdefault(row.handle, row)

        for rank, row in enumerate(keyword_rows, start=1):
            if not row.handle:
                continue
            merged_scores[row.handle] = merged_scores.get(row.handle, 0.0) + 1.0 / (
                self._rrf_k + rank
            )
            merged_rows.setdefault(row.handle, row)

        sorted_handles = sorted(
            merged_scores.keys(),
            key=lambda handle: (
                -float(merged_scores.get(handle, 0.0)),
                -float(
                    merged_rows.get(
                        handle, MemoryRecordCompact(handle="", preview="")
                    ).score
                    or 0.0
                ),
                handle,
            ),
        )

        merged: list[MemoryRecordCompact] = []
        for handle in sorted_handles[:resolved_limit]:
            merged_row = merged_rows.get(handle)
            if merged_row is None:
                continue
            metadata = dict(merged_row.metadata)
            metadata["rrf_score"] = round(float(merged_scores.get(handle, 0.0)), 6)
            merged.append(
                MemoryRecordCompact(
                    handle=handle,
                    preview=merged_row.preview,
                    score=round(float(merged_scores.get(handle, 0.0)), 6),
                    metadata=metadata,
                    est_tokens=max(
                        1,
                        int(
                            merged_row.est_tokens
                            or _estimate_tokens(merged_row.preview)
                        ),
                    ),
                    source="hybrid",
                )
            )

        self.last_hybrid_stats = {
            "semantic_candidates": len(semantic_rows),
            "keyword_candidates": len(keyword_rows),
            "merged_candidates": len(merged),
            "rrf_k": self._rrf_k,
            "semantic_channel": semantic_name,
            "keyword_channel": keyword_name,
        }
        return merged

    def fetch(self, handles: Sequence[str]) -> list[MemoryRecord]:
        resolved_handles = [
            str(handle).strip() for handle in handles if str(handle).strip()
        ]
        if not resolved_handles:
            return []

        semantic_future = self._lane_pool.submit(
            self._fetch_lane,
            self._safe_fetch,
            self._semantic,
            resolved_handles,
        )
        keyword_future = self._lane_pool.submit(
            self._fetch_lane,
            self._safe_fetch,
            self._keyword,
            resolved_handles,
        )
        semantic_records, semantic_error = semantic_future.result()
        keyword_records, keyword_error = keyword_future.result()

        if semantic_error and keyword_error:
            self.fallback_reason = (
                f"hybrid_fetch_error:{semantic_error},{keyword_error}"
            )

        merged = _dedupe_records([*semantic_records, *keyword_records])
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

    @staticmethod
    def _safe_fetch(
        provider: MemoryProvider,
        handles: Sequence[str],
    ) -> tuple[list[MemoryRecord], str | None]:
        try:
            return list(provider.fetch(handles)), None
        except Exception as exc:  # pragma: no cover - defensive path
            return [], exc.__class__.__name__
