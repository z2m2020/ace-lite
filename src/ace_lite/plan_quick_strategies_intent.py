"""Intent detection strategies for plan_quick."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from ace_lite.plan_quick_strategies_shared import (
    QUERY_DOC_SYNC_MARKERS,
    QUERY_LATEST_MARKERS,
    QUERY_ONBOARDING_MARKERS,
    QueryFlags,
)


class IntentStrategy(ABC):
    """Base class for query intent detection strategies."""

    @abstractmethod
    def detect(self, query: str, flags: QueryFlags) -> bool:
        """Detect if query matches this intent."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for logging."""


class OnboardingIntentStrategy(IntentStrategy):
    """Detect onboarding/familiarization intent."""

    MARKERS = QUERY_ONBOARDING_MARKERS

    @property
    def name(self) -> str:
        return "onboarding"

    def detect(self, query: str, flags: QueryFlags) -> bool:
        lowered = str(query or "").strip().lower()
        return any(marker in lowered for marker in self.MARKERS)


class DocSyncIntentStrategy(IntentStrategy):
    """Detect documentation sync intent."""

    MARKERS = QUERY_DOC_SYNC_MARKERS

    @property
    def name(self) -> str:
        return "doc_sync"

    def detect(self, query: str, flags: QueryFlags) -> bool:
        lowered = str(query or "").strip().lower()
        return any(marker in lowered for marker in self.MARKERS)


class LatestIntentStrategy(IntentStrategy):
    """Detect latest/recent intent."""

    MARKERS = QUERY_LATEST_MARKERS

    @property
    def name(self) -> str:
        return "latest_sensitive"

    def detect(self, query: str, flags: QueryFlags) -> bool:
        lowered = str(query or "").strip().lower()
        return any(marker in lowered for marker in self.MARKERS)


class ReqIdIntentStrategy(IntentStrategy):
    """Detect requirement ID references."""

    @property
    def name(self) -> str:
        return "has_req_id"

    def detect(self, query: str, flags: QueryFlags) -> bool:
        return bool(flags.req_ids)


class IntentStrategyRegistry:
    """Registry for query intent detection strategies."""

    _instance: ClassVar[IntentStrategyRegistry | None] = None
    _strategies: ClassVar[list[IntentStrategy]] = [
        OnboardingIntentStrategy(),
        DocSyncIntentStrategy(),
        LatestIntentStrategy(),
        ReqIdIntentStrategy(),
    ]

    @classmethod
    def get_instance(cls) -> IntentStrategyRegistry:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def detect_intent(self, query: str) -> QueryFlags:
        """Detect all intents from query."""
        flags = QueryFlags.from_query(query)
        return flags

    def register_strategy(self, strategy: IntentStrategy) -> None:
        """Register a new intent strategy."""
        self._strategies.append(strategy)


__all__ = ["IntentStrategy", "IntentStrategyRegistry"]
