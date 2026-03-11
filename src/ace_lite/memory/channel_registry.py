"""Channel registry for protocolized memory provider construction."""

from __future__ import annotations

from collections.abc import Callable

from .protocol import MemoryProvider

MemoryChannelFactory = Callable[[], MemoryProvider]


class MemoryChannelRegistry:
    """Register and resolve memory channels with alias support."""

    def __init__(self) -> None:
        self._factories: dict[str, MemoryChannelFactory] = {}
        self._aliases: dict[str, str] = {}

    @staticmethod
    def _normalize_name(name: str) -> str:
        return str(name or "").strip().lower()

    def register(
        self,
        *,
        name: str,
        factory: MemoryChannelFactory,
        aliases: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        canonical = self._normalize_name(name)
        if not canonical:
            raise ValueError("Channel name must not be empty")
        if canonical in self._factories:
            raise ValueError(f"Channel already registered: {canonical}")
        self._factories[canonical] = factory

        for alias in aliases or ():
            normalized_alias = self._normalize_name(alias)
            if not normalized_alias:
                continue
            owner = self._aliases.get(normalized_alias)
            if owner and owner != canonical:
                raise ValueError(
                    f"Alias '{normalized_alias}' already registered by '{owner}'"
                )
            self._aliases[normalized_alias] = canonical

    def canonical_name(self, channel: str) -> str:
        normalized = self._normalize_name(channel)
        if not normalized:
            raise KeyError("Channel name is empty")
        return self._aliases.get(normalized, normalized)

    def create(self, channel: str) -> MemoryProvider:
        canonical = self.canonical_name(channel)
        factory = self._factories.get(canonical)
        if factory is None:
            raise KeyError(f"Unsupported memory channel: {channel}")
        return factory()

