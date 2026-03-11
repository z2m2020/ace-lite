"""Null memory provider."""

from __future__ import annotations

from collections.abc import Sequence

from .record import MemoryRecord, MemoryRecordCompact


class NullMemoryProvider:
    last_channel_used = "none"
    fallback_reason: str | None = None
    last_container_tag_fallback: str | None = None
    strategy = "semantic"

    def search_compact(
        self,
        query: str,
        *,
        limit: int | None = None,
        container_tag: str | None = None,
    ) -> list[MemoryRecordCompact]:
        self.last_channel_used = "none"
        self.fallback_reason = None
        self.last_container_tag_fallback = None
        return []

    def fetch(self, handles: Sequence[str]) -> list[MemoryRecord]:
        self.last_channel_used = "none"
        return []
