from __future__ import annotations

from collections.abc import Sequence

from ace_lite.memory.record import MemoryRecord, MemoryRecordCompact
from ace_lite.memory_long_term.store import LongTermMemoryStore


class LongTermMemoryProvider:
    def __init__(
        self,
        store: LongTermMemoryStore,
        *,
        limit: int = 5,
        container_tag: str | None = None,
        as_of: str | None = None,
        channel_name: str = "long_term",
        neighborhood_hops: int = 1,
        neighborhood_limit: int = 6,
        prefer_abstract_memory: bool = True,
        neighborhood_detail_only: bool = True,
    ) -> None:
        self._store = store
        self._limit = max(1, int(limit))
        self._container_tag = str(container_tag).strip() if container_tag is not None else None
        self._as_of = str(as_of).strip() if as_of is not None else None
        self._channel_name = str(channel_name or "long_term").strip() or "long_term"
        self._neighborhood_hops = max(0, min(2, int(neighborhood_hops or 0)))
        self._neighborhood_limit = max(1, int(neighborhood_limit or 6))
        self._prefer_abstract_memory = bool(prefer_abstract_memory)
        self._neighborhood_detail_only = bool(neighborhood_detail_only)
        self.last_channel_used = self._channel_name
        self.fallback_reason: str | None = None
        self.last_container_tag_fallback: str | None = None
        self.strategy = "keyword"

    def search_compact(
        self,
        query: str,
        *,
        limit: int | None = None,
        container_tag: str | None = None,
    ) -> list[MemoryRecordCompact]:
        resolved_limit = max(1, int(limit)) if isinstance(limit, int) and limit > 0 else self._limit
        effective_container_tag = (
            str(container_tag).strip()
            if container_tag is not None
            else self._container_tag
        )
        rows = self._store.search(
            query=query,
            limit=resolved_limit,
            container_tag=effective_container_tag,
            as_of=self._as_of,
            prefer_abstract=self._prefer_abstract_memory,
        )
        self.last_channel_used = self._channel_name
        return [
            MemoryRecordCompact(
                handle=row.handle,
                preview=row.preview,
                score=row.confidence if row.entry_kind == "fact" else None,
                metadata=row.to_record_metadata(),
                est_tokens=max(1, len(row.preview.split())),
                source=self._channel_name,
            )
            for row in rows
        ]

    def fetch(self, handles: Sequence[str]) -> list[MemoryRecord]:
        rows = self._store.fetch(handles=handles, as_of=self._as_of)
        self.last_channel_used = self._channel_name
        out: list[MemoryRecord] = []
        for row in rows:
            metadata = dict(row.to_record_metadata())
            text = row.text
            abstraction_level = str(metadata.get("abstraction_level") or "").strip().lower()
            allow_neighborhood = (
                row.entry_kind == "fact"
                and self._neighborhood_hops > 0
                and (
                    not self._neighborhood_detail_only
                    or abstraction_level in {"", "detail"}
                )
            )
            if allow_neighborhood:
                payload = row.payload if isinstance(row.payload, dict) else {}
                neighborhood = self._store.expand_triple_neighborhood(
                    seeds=[
                        str(payload.get("subject") or ""),
                        str(payload.get("object") or ""),
                    ],
                    repo=row.repo,
                    namespace=row.namespace,
                    user_id=row.user_id,
                    profile_key=row.profile_key,
                    as_of=row.as_of or self._as_of,
                    max_hops=self._neighborhood_hops,
                    limit=self._neighborhood_limit,
                )
                neighborhood = [
                    triple for triple in neighborhood if triple.fact_handle != row.handle
                ]
                metadata["neighborhood"] = {
                    "hops": self._neighborhood_hops,
                    "limit": self._neighborhood_limit,
                    "triple_count": len(neighborhood),
                    "triples": [triple.to_payload() for triple in neighborhood],
                }
                if neighborhood:
                    lines = [
                        f"- {triple.subject} {triple.predicate} {triple.object_value}"
                        for triple in neighborhood[: self._neighborhood_limit]
                    ]
                    text = f"{text}\n\n[graph-neighborhood]\n" + "\n".join(lines)

            out.append(
                MemoryRecord(
                    text=text,
                    score=row.confidence if row.entry_kind == "fact" else None,
                    metadata=metadata,
                    handle=row.handle,
                    source=self._channel_name,
                )
            )
        return out


__all__ = ["LongTermMemoryProvider"]
