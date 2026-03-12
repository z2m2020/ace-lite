"""Stable prompt segment structures and canonical ordering helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

SEGMENT_ORDERING = "canonical_v1"
SEGMENT_HASH_ALGORITHM = "sha256"


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _normalize_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_metadata(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_metadata(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


@dataclass(frozen=True, slots=True)
class PromptSegment:
    """Canonical segment unit for the prompt rendering boundary."""

    segment_id: str
    kind: str
    heading: str
    body: str
    priority: int = 0
    path: str = ""
    qualified_name: str = ""
    lineno: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    segment_hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "segment_id", _normalize_text(self.segment_id))
        object.__setattr__(self, "kind", _normalize_text(self.kind))
        object.__setattr__(self, "heading", _normalize_text(self.heading))
        object.__setattr__(self, "body", _normalize_text(self.body))
        object.__setattr__(self, "path", _normalize_text(self.path))
        object.__setattr__(
            self,
            "qualified_name",
            _normalize_text(self.qualified_name),
        )
        object.__setattr__(self, "lineno", _normalize_int(self.lineno))
        object.__setattr__(self, "priority", _normalize_int(self.priority))
        object.__setattr__(
            self,
            "metadata",
            _normalize_metadata(self.metadata) if isinstance(self.metadata, Mapping) else {},
        )
        object.__setattr__(self, "segment_hash", compute_segment_hash(self))


def segment_payload(segment: PromptSegment) -> dict[str, Any]:
    return {
        "segment_id": segment.segment_id,
        "kind": segment.kind,
        "heading": segment.heading,
        "body": segment.body,
        "priority": int(segment.priority),
        "path": segment.path,
        "qualified_name": segment.qualified_name,
        "lineno": int(segment.lineno),
        "metadata": _normalize_metadata(segment.metadata),
    }


def compute_segment_hash(segment: PromptSegment) -> str:
    payload = json.dumps(
        segment_payload(segment),
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def coerce_prompt_segment(value: PromptSegment | Mapping[str, Any]) -> PromptSegment:
    if isinstance(value, PromptSegment):
        return value
    return PromptSegment(
        segment_id=str(value.get("segment_id") or value.get("id") or ""),
        kind=str(value.get("kind") or ""),
        heading=str(value.get("heading") or value.get("title") or ""),
        body=str(value.get("body") or value.get("content") or ""),
        priority=value.get("priority", 0),
        path=str(value.get("path") or ""),
        qualified_name=str(value.get("qualified_name") or ""),
        lineno=value.get("lineno", 0),
        metadata=dict(value.get("metadata") or {})
        if isinstance(value.get("metadata"), Mapping)
        else {},
    )


def segment_sort_key(segment: PromptSegment) -> tuple[Any, ...]:
    return (
        -int(segment.priority),
        segment.kind,
        segment.path,
        int(segment.lineno),
        segment.qualified_name,
        segment.segment_id,
        segment.heading,
        segment.segment_hash,
    )


def canonicalize_segments(
    values: Iterable[PromptSegment | Mapping[str, Any]],
) -> list[PromptSegment]:
    segments = [coerce_prompt_segment(item) for item in values]
    return sorted(segments, key=segment_sort_key)


__all__ = [
    "PromptSegment",
    "SEGMENT_HASH_ALGORITHM",
    "SEGMENT_ORDERING",
    "canonicalize_segments",
    "coerce_prompt_segment",
    "compute_segment_hash",
    "segment_payload",
    "segment_sort_key",
]
