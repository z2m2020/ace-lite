"""Dual-channel provider with fallback semantics."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from .helpers import _dedupe_compacts, _dedupe_records
from .protocol import MemoryProvider
from .record import MemoryRecord, MemoryRecordCompact

logger = logging.getLogger(__name__)


class DualChannelMemoryProvider:
    def __init__(
        self,
        primary: MemoryProvider,
        secondary: MemoryProvider | None = None,
        *,
        fallback_on_empty: bool = False,
        merge_on_fallback: bool = True,
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        self._fallback_on_empty = fallback_on_empty
        self._merge_on_fallback = merge_on_fallback
        self.last_channel_used = "none"
        self.fallback_reason: str | None = None
        self.last_container_tag_fallback: str | None = None
        self.strategy = "semantic"

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

        primary_rows: list[MemoryRecordCompact] = []
        try:
            if container_tag is None:
                primary_rows = list(self._primary.search_compact(query, limit=limit))
            else:
                primary_rows = list(
                    self._primary.search_compact(
                        query,
                        limit=limit,
                        container_tag=container_tag,
                    )
                )
            primary_namespace_fallback = getattr(
                self._primary,
                "last_container_tag_fallback",
                None,
            )
            if (
                isinstance(primary_namespace_fallback, str)
                and primary_namespace_fallback.strip()
            ):
                self.last_container_tag_fallback = primary_namespace_fallback.strip()
            self.last_channel_used = self._provider_channel_name(
                self._primary, default="primary"
            )
        except Exception as exc:
            self.fallback_reason = f"primary_error:{exc.__class__.__name__}"
            logger.info(
                "memory.dual_channel.fallback", extra={"reason": self.fallback_reason}
            )
            return self._search_secondary(
                query=query,
                primary_rows=[],
                limit=limit,
                container_tag=container_tag,
            )

        if primary_rows:
            return _dedupe_compacts(primary_rows, limit=limit)

        if self._fallback_on_empty:
            self.fallback_reason = "primary_empty"
            logger.info(
                "memory.dual_channel.fallback", extra={"reason": self.fallback_reason}
            )
            return self._search_secondary(
                query=query,
                primary_rows=[],
                limit=limit,
                container_tag=container_tag,
            )

        return []

    def fetch(self, handles: Sequence[str]) -> list[MemoryRecord]:
        resolved_handles = [
            str(handle).strip() for handle in handles if str(handle).strip()
        ]
        if not resolved_handles:
            return []

        primary_records: list[MemoryRecord] = []
        secondary_records: list[MemoryRecord] = []

        try:
            primary_records = list(self._primary.fetch(resolved_handles))
        except Exception as exc:
            if not self.fallback_reason:
                self.fallback_reason = f"primary_fetch_error:{exc.__class__.__name__}"

        primary_handles = {
            str(record.handle).strip()
            for record in primary_records
            if isinstance(record.handle, str) and record.handle.strip()
        }
        missing = [
            handle for handle in resolved_handles if handle not in primary_handles
        ]

        if missing and self._secondary is not None:
            try:
                secondary_records = list(self._secondary.fetch(missing))
                self.last_channel_used = self._provider_channel_name(
                    self._secondary, default="secondary"
                )
            except Exception as exc:
                if not self.fallback_reason:
                    self.fallback_reason = (
                        f"secondary_fetch_error:{exc.__class__.__name__}"
                    )

        merged = _dedupe_records([*primary_records, *secondary_records])
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

    def _search_secondary(
        self,
        *,
        query: str,
        primary_rows: list[MemoryRecordCompact],
        limit: int | None,
        container_tag: str | None,
    ) -> list[MemoryRecordCompact]:
        if self._secondary is None:
            return _dedupe_compacts(primary_rows, limit=limit)

        try:
            if container_tag is None:
                secondary_rows = list(self._secondary.search_compact(query, limit=limit))
            else:
                secondary_rows = list(
                    self._secondary.search_compact(
                        query,
                        limit=limit,
                        container_tag=container_tag,
                    )
                )
            secondary_namespace_fallback = getattr(
                self._secondary,
                "last_container_tag_fallback",
                None,
            )
            if (
                isinstance(secondary_namespace_fallback, str)
                and secondary_namespace_fallback.strip()
            ):
                self.last_container_tag_fallback = secondary_namespace_fallback.strip()
            self.last_channel_used = self._provider_channel_name(
                self._secondary, default="secondary"
            )
        except Exception as exc:
            if not self.fallback_reason:
                self.fallback_reason = f"secondary_error:{exc.__class__.__name__}"
            return _dedupe_compacts(primary_rows, limit=limit)

        if self._merge_on_fallback:
            return _dedupe_compacts([*primary_rows, *secondary_rows], limit=limit)
        return _dedupe_compacts(secondary_rows, limit=limit)

    @staticmethod
    def _provider_channel_name(provider: MemoryProvider, *, default: str) -> str:
        channel = getattr(provider, "last_channel_used", None)
        if isinstance(channel, str) and channel:
            return channel
        return default
