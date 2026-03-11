"""Memory record models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MemoryRecord:
    text: str
    score: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    handle: str = ""
    source: str = "memory"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text": self.text,
            "metadata": dict(self.metadata),
            "source": self.source,
        }
        if self.score is not None:
            payload["score"] = self.score
        if self.handle:
            payload["handle"] = self.handle
        return payload


@dataclass(slots=True)
class MemoryRecordCompact:
    handle: str
    preview: str
    score: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    est_tokens: int = 1
    source: str = "memory"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "handle": self.handle,
            "preview": self.preview,
            "metadata": dict(self.metadata),
            "est_tokens": max(1, int(self.est_tokens or 1)),
            "source": self.source,
        }
        if self.score is not None:
            payload["score"] = self.score
        return payload
