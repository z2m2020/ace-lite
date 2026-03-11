"""Memory provider protocols."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from .record import MemoryRecord, MemoryRecordCompact


class OpenMemoryClient(Protocol):
    def search(
        self,
        *,
        query: str,
        user_id: str | None = None,
        app: str | None = None,
        container_tag: str | None = None,
        limit: int = 5,
    ) -> Any: ...


class MemoryProvider(Protocol):
    def search_compact(
        self,
        query: str,
        *,
        limit: int | None = None,
        container_tag: str | None = None,
    ) -> list[MemoryRecordCompact]: ...

    def fetch(self, handles: Sequence[str]) -> list[MemoryRecord]: ...
