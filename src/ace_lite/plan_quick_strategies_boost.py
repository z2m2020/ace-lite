"""Boost and penalty strategies for plan_quick."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from ace_lite.plan_quick_strategies_domain import DomainStrategyRegistry
from ace_lite.plan_quick_strategies_shared import (
    _LATEST_DOC_DOMAINS,
    DOC_ENTRYPOINT_BASENAMES,
    DOC_PREFERRED_PREFIXES,
    DOC_PRIMARY_NAME_MARKERS,
    DOC_SECONDARY_NAME_MARKERS,
    NormalizationUtils,
    QueryFlags,
    _extract_path_date,
)


@dataclass
class BoostResult:
    """Result of boost calculation."""

    boost: float
    reason: str
    weight: float = 1.0


class BoostStrategy(ABC):
    """Base class for boost/penalty calculation strategies."""

    @abstractmethod
    def calculate(
        self,
        path: str | None,
        language: str | None,
        flags: QueryFlags,
        context: dict[str, Any],
    ) -> BoostResult:
        """Calculate boost for a path given query flags."""


class DocSyncBoostStrategy(BoostStrategy):
    """Calculate boost for documentation sync intents."""

    PENALIZED_PREFIXES: tuple[tuple[str, float], ...] = (
        ("tests/", -3.5),
        ("test/", -3.5),
        ("research/", -6.0),
        ("reference/", -6.0),
        ("src/", -2.0),
        ("internal/", -2.0),
        ("pkg/", -2.0),
    )

    SECONDARY_NAME_PENALTIES: tuple[tuple[str, float], ...] = (
        ("weekly", -2.5),
        ("matrix", -1.0),
    )

    def calculate(
        self,
        path: str | None,
        language: str | None,
        flags: QueryFlags,
        context: dict[str, Any],
    ) -> BoostResult:
        if not flags.doc_sync:
            return BoostResult(boost=0.0, reason="no_doc_sync_intent")

        normalized_path = NormalizationUtils.normalize_path(path)
        domain = DomainStrategyRegistry.classify(path)

        boost = 0.0
        reasons: list[str] = []

        is_markdown = NormalizationUtils.is_markdown_path(
            path
        ) or NormalizationUtils.is_markdown_language(language)
        if is_markdown:
            boost += 4.0
            reasons.append("markdown_file")

        if normalized_path.startswith(DOC_PREFERRED_PREFIXES):
            boost += 3.0
            reasons.append("preferred_prefix")

        stem = NormalizationUtils.extract_path_stem(path)
        primary_hits = sum(1 for marker in DOC_PRIMARY_NAME_MARKERS if marker in normalized_path)
        secondary_hits = sum(
            1 for marker in DOC_SECONDARY_NAME_MARKERS if marker in normalized_path
        )

        boost += min(4.0, float(primary_hits) * 1.5)
        if primary_hits > 0:
            reasons.append(f"primary_markers({primary_hits})")

        boost += min(1.5, float(secondary_hits) * 0.75)
        if secondary_hits > 0:
            reasons.append(f"secondary_markers({secondary_hits})")

        if stem in DOC_ENTRYPOINT_BASENAMES and domain in {
            "docs",
            "planning",
            "repos",
            "reference",
            "markdown",
        }:
            boost += 3.0
            reasons.append("entrypoint")

        for prefix, penalty in self.PENALIZED_PREFIXES:
            if normalized_path.startswith(prefix):
                boost += penalty
                reasons.append(f"penalized({prefix})")
                break

        if domain == "research":
            boost -= 4.0
            reasons.append("domain_penalty(research)")
        elif domain == "reports" and primary_hits == 0:
            boost -= 1.5
            reasons.append("domain_penalty(reports)")

        for marker, penalty in self.SECONDARY_NAME_PENALTIES:
            if marker in normalized_path:
                boost += penalty
                reasons.append(f"name_penalty({marker})")

        return BoostResult(
            boost=boost,
            reason="doc_sync:" + ",".join(reasons) if reasons else "doc_sync:no_hits",
        )


class LatestDocBoostStrategy(BoostStrategy):
    """Calculate boost for latest document intents."""

    SECONDARY_NAME_PENALTIES: tuple[tuple[str, float], ...] = (
        ("weekly", -2.5),
        ("matrix", -1.0),
    )

    def calculate(
        self,
        path: str | None,
        language: str | None,
        flags: QueryFlags,
        context: dict[str, Any],
    ) -> BoostResult:
        if not flags.latest_sensitive:
            return BoostResult(boost=0.0, reason="no_latest_intent")

        normalized_path = NormalizationUtils.normalize_path(path)
        domain = DomainStrategyRegistry.classify(path)

        if domain not in _LATEST_DOC_DOMAINS:
            return BoostResult(boost=0.0, reason="domain_not_latest")

        if not NormalizationUtils.is_markdown_path(path):
            return BoostResult(boost=0.0, reason="not_markdown")

        boost = 0.0
        reasons: list[str] = []

        if normalized_path.startswith(DOC_PREFERRED_PREFIXES):
            boost += 1.0
            reasons.append("preferred_prefix")

        primary_hits = sum(1 for marker in DOC_PRIMARY_NAME_MARKERS if marker in normalized_path)
        secondary_hits = sum(
            1 for marker in DOC_SECONDARY_NAME_MARKERS if marker in normalized_path
        )

        boost += min(2.5, float(primary_hits))
        if primary_hits > 0:
            reasons.append(f"primary_markers({primary_hits})")

        boost += min(0.75, float(secondary_hits) * 0.5)
        if secondary_hits > 0:
            reasons.append(f"secondary_markers({secondary_hits})")

        stem = NormalizationUtils.extract_path_stem(path)
        if stem in DOC_ENTRYPOINT_BASENAMES:
            boost += 1.5
            reasons.append("entrypoint")

        if "current" in normalized_path or "latest" in normalized_path:
            boost += 0.75
            reasons.append("latest_keyword")

        newest_dated_doc = context.get("newest_dated_doc")
        path_date = _extract_path_date(path)
        if newest_dated_doc is not None and path_date is not None:
            lag_days = max(0, (newest_dated_doc - path_date).days)
            if lag_days == 0:
                boost += 3.0
                reasons.append("date_match")
            elif lag_days <= 30:
                boost += 2.0
                reasons.append("date_30days")
            elif lag_days <= 90:
                boost += 1.0
                reasons.append("date_90days")

        if domain == "reports" and primary_hits == 0:
            boost -= 0.75
            reasons.append("domain_penalty(reports)")

        for marker, penalty in self.SECONDARY_NAME_PENALTIES:
            if marker in normalized_path:
                boost += penalty * 0.5
                reasons.append(f"name_penalty({marker})")

        return BoostResult(
            boost=boost,
            reason="latest_doc:" + ",".join(reasons) if reasons else "latest_doc:no_hits",
        )


class BoostStrategyRegistry:
    """Registry for boost/penalty calculation strategies."""

    _instance: ClassVar[BoostStrategyRegistry | None] = None
    _strategies: ClassVar[list[BoostStrategy]] = [
        DocSyncBoostStrategy(),
        LatestDocBoostStrategy(),
    ]

    @classmethod
    def get_instance(cls) -> BoostStrategyRegistry:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def calculate_total_boost(
        self,
        path: str | None,
        language: str | None,
        flags: QueryFlags,
        context: dict[str, Any],
    ) -> float:
        """Calculate total boost from all strategies."""
        return sum(
            result.boost
            for result in self._calculate_results(
                path=path,
                language=language,
                flags=flags,
                context=context,
            )
        )

    def _calculate_results(
        self,
        *,
        path: str | None,
        language: str | None,
        flags: QueryFlags,
        context: dict[str, Any],
    ) -> list[BoostResult]:
        """Evaluate all registered strategies and return their results."""
        return [strategy.calculate(path, language, flags, context) for strategy in self._strategies]

    def calculate_doc_sync_boost(
        self,
        *,
        path: str | None,
        language: str | None,
        flags: QueryFlags,
        context: dict[str, Any],
    ) -> float:
        """Calculate only the documentation-sync boost component."""
        return self._calculate_strategy_type(
            strategy_type=DocSyncBoostStrategy,
            path=path,
            language=language,
            flags=flags,
            context=context,
        )

    def calculate_latest_doc_boost(
        self,
        *,
        path: str | None,
        language: str | None,
        flags: QueryFlags,
        context: dict[str, Any],
    ) -> float:
        """Calculate only the latest-document recency boost component."""
        return self._calculate_strategy_type(
            strategy_type=LatestDocBoostStrategy,
            path=path,
            language=language,
            flags=flags,
            context=context,
        )

    def _calculate_strategy_type(
        self,
        *,
        strategy_type: type[BoostStrategy],
        path: str | None,
        language: str | None,
        flags: QueryFlags,
        context: dict[str, Any],
    ) -> float:
        """Calculate the boost from a specific strategy class."""
        total = 0.0
        for strategy in self._strategies:
            if isinstance(strategy, strategy_type):
                result = strategy.calculate(path, language, flags, context)
                total += result.boost
        return total

    def register_strategy(self, strategy: BoostStrategy) -> None:
        """Register a new boost strategy."""
        self._strategies.append(strategy)


__all__ = [
    "BoostResult",
    "BoostStrategy",
    "BoostStrategyRegistry",
]
