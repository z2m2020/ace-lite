"""OpenMemory-backed provider implementation."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from .helpers import (
    _dedupe_compacts,
    _dedupe_records,
    _estimate_tokens,
    _normalize_metadata,
    _stable_handle,
)
from .protocol import OpenMemoryClient
from .record import MemoryRecord, MemoryRecordCompact

logger = logging.getLogger(__name__)


class OpenMemoryMemoryProvider:
    def __init__(
        self,
        client: OpenMemoryClient,
        *,
        user_id: str | None = None,
        app: str | None = None,
        container_tag: str | None = None,
        limit: int = 5,
        channel_name: str = "client",
    ) -> None:
        self._client = client
        self._user_id = user_id
        self._app = app
        self._container_tag = container_tag
        self._limit = max(1, int(limit))
        self._channel_name = channel_name
        self._last_records: dict[str, MemoryRecord] = {}
        self.last_channel_used = channel_name
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
        logger.debug(
            "memory.provider.search_compact.start",
            extra={"channel": self._channel_name},
        )
        self.last_channel_used = self._channel_name
        self.fallback_reason = None
        self.last_container_tag_fallback = None

        resolved_limit = self._limit
        if isinstance(limit, int) and limit > 0:
            resolved_limit = max(1, int(limit))

        effective_container_tag = (
            container_tag if container_tag is not None else self._container_tag
        )
        raw_payload = self._call_search(
            query=query,
            limit=resolved_limit,
            container_tag=effective_container_tag,
        )
        client_namespace_fallback = getattr(
            self._client,
            "last_container_tag_fallback",
            None,
        )
        if (
            isinstance(client_namespace_fallback, str)
            and client_namespace_fallback.strip()
        ):
            self.last_container_tag_fallback = client_namespace_fallback.strip()
        rows = self._normalize_rows(raw_payload)

        compact_rows: list[MemoryRecordCompact] = []
        records: dict[str, MemoryRecord] = {}
        for row in rows:
            text = row.get("memory") or row.get("text") or row.get("content")
            if not isinstance(text, str) or not text.strip():
                continue

            score = row.get("score")
            normalized_score = float(score) if isinstance(score, (int, float)) else None
            metadata = _normalize_metadata(row.get("metadata"))
            handle = _stable_handle(text=text, metadata=metadata)

            record = MemoryRecord(
                text=text,
                score=normalized_score,
                metadata=metadata,
                handle=handle,
                source=self._channel_name,
            )
            records[handle] = record
            compact_rows.append(
                MemoryRecordCompact(
                    handle=handle,
                    preview=text,
                    score=normalized_score,
                    metadata=metadata,
                    est_tokens=_estimate_tokens(text),
                    source=self._channel_name,
                )
            )

        self._last_records = records
        deduped = _dedupe_compacts(compact_rows, limit=resolved_limit)
        logger.debug(
            "memory.provider.search_compact.end",
            extra={"channel": self._channel_name, "records": len(deduped)},
        )
        return deduped

    def fetch(self, handles: Sequence[str]) -> list[MemoryRecord]:
        self.last_channel_used = self._channel_name
        resolved_handles = [
            str(handle).strip() for handle in handles if str(handle).strip()
        ]
        if not resolved_handles:
            return []

        records: list[MemoryRecord] = []
        seen: set[str] = set()
        for handle in resolved_handles:
            if handle in seen:
                continue
            seen.add(handle)
            record = self._last_records.get(handle)
            if record is None:
                continue
            records.append(record)
        return _dedupe_records(records)

    def _call_search(
        self, *, query: str, limit: int, container_tag: str | None
    ) -> Any:
        try:
            return self._client.search(
                query=query,
                user_id=self._user_id,
                app=self._app,
                container_tag=container_tag,
                limit=limit,
            )
        except TypeError:
            self.last_container_tag_fallback = "provider_unsupported_container_tag"
            try:
                return self._client.search(
                    query=query,
                    user_id=self._user_id,
                    app=self._app,
                    limit=limit,
                )
            except TypeError:
                return self._client.search(query=query)

    @staticmethod
    def _normalize_rows(payload: Any) -> list[Mapping[str, Any]]:
        maybe_rows = payload.get("results", []) if isinstance(payload, Mapping) else payload

        if not isinstance(maybe_rows, Sequence) or isinstance(
            maybe_rows, (str, bytes, bytearray)
        ):
            return []

        rows: list[Mapping[str, Any]] = []
        for item in maybe_rows:
            if isinstance(item, Mapping):
                rows.append(item)
        return rows
