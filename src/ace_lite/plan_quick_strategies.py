"""Intent and Domain Strategy Registry for Plan Quick Optimization

This module provides a registry-based approach to managing plan_quick's
marker, domain, and boost/penalty rules. The goal is to reduce code
duplication and improve maintainability.

Architecture:
- Strategy base classes define the interface
- Concrete strategies implement specific behaviors
- Registry manages strategy registration and lookup
- NormalizationUtils provides shared path/string utilities

Usage:
    from ace_lite.plan_quick_strategies import (
        IntentStrategyRegistry,
        DomainStrategyRegistry,
        NormalizationUtils,
    )

    # Detect intent
    registry = IntentStrategyRegistry.get_instance()
    flags = registry.detect_intent("explain the codebase structure")

    # Classify domain
    domain = DomainStrategyRegistry.classify("/path/to/docs/readme.md")
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from typing import Any, ClassVar

# =============================================================================
# Normalization Utilities
# =============================================================================


class NormalizationUtils:
    """Shared utilities for path and string normalization.

    Centralizes repeated normalization patterns like:
    - str(path or "").strip().replace("\\", "/").lower()
    - Path stem extraction
    - Language normalization
    """

    @staticmethod
    def normalize_path(path: str | None) -> str:
        """Normalize a path to POSIX format with lowercase.

        Replaces backslashes, strips whitespace, and converts to lowercase.
        """
        return str(path or "").strip().replace("\\", "/").lower()

    @staticmethod
    def normalize_language(language: str | None) -> str:
        """Normalize a language identifier."""
        return str(language or "").strip().lower()

    @staticmethod
    def extract_path_stem(path: str | None) -> str:
        """Extract the stem (filename without extension) from a path."""
        normalized = NormalizationUtils.normalize_path(path)
        basename = normalized.rsplit("/", 1)[-1]
        stem = basename.rsplit(".", 1)[0]
        return stem

    @staticmethod
    @lru_cache(maxsize=1024)
    def is_markdown_path(path: str | None) -> bool:
        """Check if path points to a markdown file."""
        normalized = NormalizationUtils.normalize_path(path)
        return normalized.endswith((".md", ".mdx"))

    @staticmethod
    @lru_cache(maxsize=1024)
    def is_markdown_language(language: str | None) -> bool:
        """Check if language is markdown."""
        normalized = NormalizationUtils.normalize_language(language)
        return normalized in frozenset({"markdown", "md"})


# =============================================================================
# Query Flags Dataclass
# =============================================================================


@dataclass(frozen=True)
class QueryFlags:
    """Structured representation of query intent flags."""

    doc_sync: bool = False
    latest_sensitive: bool = False
    onboarding: bool = False
    has_req_id: bool = False
    req_ids: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_query(cls, query: str) -> QueryFlags:
        """Detect flags from a query string."""
        lowered = str(query or "").strip().lower()
        return cls(
            doc_sync=any(m in lowered for m in QUERY_DOC_SYNC_MARKERS),
            latest_sensitive=any(m in lowered for m in QUERY_LATEST_MARKERS),
            onboarding=any(m in lowered for m in QUERY_ONBOARDING_MARKERS),
            has_req_id=bool(_extract_req_ids(query)),
            req_ids=tuple(_extract_req_ids(query)),
        )


# =============================================================================
# Marker Collections
# =============================================================================

QUERY_DOC_SYNC_MARKERS: tuple[str, ...] = (
    "doc",
    "docs",
    "markdown",
    "readme",
    "planning",
    "plan",
    "progress",
    "status",
    "report",
    "roadmap",
    "runbook",
    "sync",
    "update",
    "latest",
    "requirements",
    "milestone",
    "phase",
    "state",
    "explainability",
    "contract",
    "文档",
    "说明",
    "同步",
    "更新",
    "最新",
    "状态",
    "进展",
    "报告",
    "路线图",
    "需求",
    "里程碑",
    "阶段",
    "可解释性",
    "合同",
    "契约",
)

QUERY_LATEST_MARKERS: tuple[str, ...] = (
    "latest",
    "recent",
    "sync",
    "update",
    "current",
    "最近",
    "最新",
    "同步",
    "更新",
    "当前",
)

QUERY_ONBOARDING_MARKERS: tuple[str, ...] = (
    "onboarding",
    "familiarize",
    "familiarise",
    "familiarization",
    "familiarisation",
    "understand",
    "overview",
    "read first",
    "where to start",
    "entrypoint",
    "codebase",
    "repo map",
    "project structure",
    "熟悉",
    "先读",
    "先看",
    "入口",
    "上手",
    "导览",
    "代码地图",
    "架构概览",
)

DOC_PRIMARY_NAME_MARKERS: tuple[str, ...] = (
    "progress",
    "status",
    "runbook",
    "sync",
    "update",
    "latest",
    "current",
)

DOC_SECONDARY_NAME_MARKERS: tuple[str, ...] = (
    "readme",
    "report",
    "roadmap",
    "overview",
    "summary",
    "changelog",
)

DOC_PREFERRED_PREFIXES: tuple[str, ...] = (
    "docs/",
    "doc/",
    "planning/",
    ".planning/",
    "plans/",
    ".plans/",
    "repos/",
    "reports/",
    "milestones/",
    "phases/",
    "state/",
)

DOC_ENTRYPOINT_BASENAMES: frozenset[str] = frozenset({
    "readme",
    "index",
    "overview",
})

_MARKDOWN_LANGUAGES: frozenset[str] = frozenset({"markdown", "md"})

_LATEST_DOC_DOMAINS: frozenset[str] = frozenset(
    {"docs", "planning", "repos", "reports", "reference", "markdown"}
)

# Regex patterns
_PATH_DATE_PATTERN = re.compile(r"(?<!\d)((?:19|20)\d{2})-(\d{2})-(\d{2})(?!\d)")
_REQ_ID_PATTERN = re.compile(r"\b([A-Z]{2,})-(\d+)\b", re.IGNORECASE)


def _extract_req_ids(query: str) -> list[str]:
    """Extract requirement IDs like EXPL-01, REQ-01 from query."""
    normalized = str(query or "").strip()
    matches = _REQ_ID_PATTERN.findall(normalized)
    return [f"{str(prefix).upper()}-{num}" for prefix, num in matches]


def _extract_path_date(path: str | None) -> date | None:
    """Extract date from path if present."""
    normalized = str(path or "").strip().replace("\\", "/")
    matched = _PATH_DATE_PATTERN.search(normalized)
    if not matched:
        return None
    try:
        return datetime.strptime(matched.group(0), "%Y-%m-%d").date()
    except ValueError:
        return None


# =============================================================================
# Domain Strategy
# =============================================================================


@dataclass
class DomainMatch:
    """Result of domain classification."""

    domain: str
    confidence: float = 1.0
    matched_prefix: str | None = None


class DomainStrategy(ABC):
    """Base class for domain classification strategies."""

    DOMAIN: ClassVar[str] = "unknown"

    @abstractmethod
    def match(self, path: str, normalized_path: str) -> DomainMatch | None:
        """Check if path matches this domain strategy."""
        ...

    @classmethod
    def classify_path(cls, path: str | None) -> str:
        """Classify path into domain category."""
        normalized = NormalizationUtils.normalize_path(path)
        if not normalized:
            return "unknown"

        # Check strategies in order of specificity
        for strategy_cls in _DOMAIN_STRATEGIES:
            match = strategy_cls.match(None, normalized)  # type: ignore
            if match is not None:
                return match.domain

        return "code"


class PlanningDomainStrategy(DomainStrategy):
    """Strategy for planning-related paths."""

    DOMAIN = "planning"
    PREFIXES = (
        ("planning/", 1.0),
        ("plans/", 1.0),
        (".planning/", 1.0),
        (".plans/", 1.0),
        ("/planning/", 0.9),
        ("/.planning/", 0.9),
        ("/plans/", 0.9),
        ("/.plans/", 0.9),
        ("milestones/", 0.8),
        (".milestones/", 0.8),
        ("/milestones/", 0.7),
        ("phases/", 0.8),
        (".phases/", 0.8),
        ("/phases/", 0.7),
        ("state/", 0.7),
        (".state/", 0.7),
        ("/state/", 0.6),
    )

    @classmethod
    def match(cls, path: str | None, normalized_path: str) -> DomainMatch | None:
        for prefix, confidence in cls.PREFIXES:
            if normalized_path.startswith(prefix) or f"/{prefix.lstrip('/')}" in normalized_path:
                return DomainMatch(domain=cls.DOMAIN, confidence=confidence, matched_prefix=prefix)
        return None


class ReposDomainStrategy(DomainStrategy):
    """Strategy for repos-related paths."""

    DOMAIN = "repos"

    @classmethod
    def match(cls, path: str | None, normalized_path: str) -> DomainMatch | None:
        if normalized_path.startswith("repos/"):
            return DomainMatch(domain=cls.DOMAIN, confidence=1.0, matched_prefix="repos/")
        return None


class ReportsDomainStrategy(DomainStrategy):
    """Strategy for reports-related paths."""

    DOMAIN = "reports"

    @classmethod
    def match(cls, path: str | None, normalized_path: str) -> DomainMatch | None:
        if normalized_path.startswith("reports/"):
            return DomainMatch(domain=cls.DOMAIN, confidence=1.0, matched_prefix="reports/")
        return None


class ResearchDomainStrategy(DomainStrategy):
    """Strategy for research-related paths."""

    DOMAIN = "research"

    @classmethod
    def match(cls, path: str | None, normalized_path: str) -> DomainMatch | None:
        if normalized_path.startswith("research/") or "/research/" in normalized_path:
            return DomainMatch(domain=cls.DOMAIN, confidence=1.0, matched_prefix="research/")
        return None


class ReferenceDomainStrategy(DomainStrategy):
    """Strategy for reference-related paths."""

    DOMAIN = "reference"

    @classmethod
    def match(cls, path: str | None, normalized_path: str) -> DomainMatch | None:
        if normalized_path.startswith(("reference/", "docs/reference/")) or "/reference/" in normalized_path:
            return DomainMatch(domain=cls.DOMAIN, confidence=1.0, matched_prefix="reference/")
        return None


class DocsDomainStrategy(DomainStrategy):
    """Strategy for docs-related paths."""

    DOMAIN = "docs"

    @classmethod
    def match(cls, path: str | None, normalized_path: str) -> DomainMatch | None:
        if normalized_path.startswith(("docs/", "doc/")):
            return DomainMatch(domain=cls.DOMAIN, confidence=1.0, matched_prefix="docs/")
        return None


class TestsDomainStrategy(DomainStrategy):
    """Strategy for tests-related paths."""

    DOMAIN = "tests"

    @classmethod
    def match(cls, path: str | None, normalized_path: str) -> DomainMatch | None:
        if normalized_path.startswith(("tests/", "test/")):
            return DomainMatch(domain=cls.DOMAIN, confidence=1.0, matched_prefix="tests/")
        return None


class MarkdownDomainStrategy(DomainStrategy):
    """Strategy for markdown files."""

    DOMAIN = "markdown"

    @classmethod
    def match(cls, path: str | None, normalized_path: str) -> DomainMatch | None:
        if normalized_path.endswith((".md", ".mdx")):
            return DomainMatch(domain=cls.DOMAIN, confidence=0.9, matched_prefix=None)
        return None


# Registry of domain strategies (checked in order)
_DOMAIN_STRATEGIES: list[type[DomainStrategy]] = [
    PlanningDomainStrategy,
    ReposDomainStrategy,
    ReportsDomainStrategy,
    ResearchDomainStrategy,
    ReferenceDomainStrategy,
    DocsDomainStrategy,
    TestsDomainStrategy,
    MarkdownDomainStrategy,
]


class DomainStrategyRegistry:
    """Registry for domain classification strategies."""

    @staticmethod
    def classify(path: str | None) -> str:
        """Classify a path into its domain category."""
        return DomainStrategy.classify_path(path)

    @staticmethod
    def get_domain_match(path: str | None) -> DomainMatch:
        """Get detailed domain match information."""
        normalized = NormalizationUtils.normalize_path(path)
        for strategy_cls in _DOMAIN_STRATEGIES:
            match = strategy_cls.match(None, normalized)  # type: ignore
            if match is not None:
                return match
        return DomainMatch(domain="code", confidence=1.0)


# =============================================================================
# Intent Strategy (for query intent detection)
# =============================================================================


class IntentStrategy(ABC):
    """Base class for query intent detection strategies."""

    @abstractmethod
    def detect(self, query: str, flags: QueryFlags) -> bool:
        """Detect if query matches this intent."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for logging."""
        ...


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

    _strategies: ClassVar[list[IntentStrategy]] = [
        OnboardingIntentStrategy(),
        DocSyncIntentStrategy(),
        LatestIntentStrategy(),
        ReqIdIntentStrategy(),
    ]

    @classmethod
    def get_instance(cls) -> IntentStrategyRegistry:
        """Get singleton instance."""
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance

    def detect_intent(self, query: str) -> QueryFlags:
        """Detect all intents from query."""
        flags = QueryFlags.from_query(query)
        return flags

    def register_strategy(self, strategy: IntentStrategy) -> None:
        """Register a new intent strategy."""
        self._strategies.append(strategy)


# =============================================================================
# Boost/Penalty Strategy
# =============================================================================


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
        ...


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

        # Markdown bonus
        is_markdown = NormalizationUtils.is_markdown_path(path) or NormalizationUtils.is_markdown_language(language)
        if is_markdown:
            boost += 4.0
            reasons.append("markdown_file")

        # Preferred prefix bonus
        if normalized_path.startswith(DOC_PREFERRED_PREFIXES):
            boost += 3.0
            reasons.append("preferred_prefix")

        # Name marker bonuses
        stem = NormalizationUtils.extract_path_stem(path)
        primary_hits = sum(1 for m in DOC_PRIMARY_NAME_MARKERS if m in normalized_path)
        secondary_hits = sum(1 for m in DOC_SECONDARY_NAME_MARKERS if m in normalized_path)

        boost += min(4.0, float(primary_hits) * 1.5)
        if primary_hits > 0:
            reasons.append(f"primary_markers({primary_hits})")

        boost += min(1.5, float(secondary_hits) * 0.75)
        if secondary_hits > 0:
            reasons.append(f"secondary_markers({secondary_hits})")

        # Entrypoint bonus
        if stem in DOC_ENTRYPOINT_BASENAMES and domain in {"docs", "planning", "repos", "reference", "markdown"}:
            boost += 3.0
            reasons.append("entrypoint")

        # Penalized prefixes
        for prefix, penalty in self.PENALIZED_PREFIXES:
            if normalized_path.startswith(prefix):
                boost += penalty
                reasons.append(f"penalized({prefix})")
                break

        # Domain penalties
        if domain == "research":
            boost -= 4.0
            reasons.append("domain_penalty(research)")
        elif domain == "reports" and primary_hits == 0:
            boost -= 1.5
            reasons.append("domain_penalty(reports)")

        # Secondary name penalties
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

        # Preferred prefix
        if normalized_path.startswith(DOC_PREFERRED_PREFIXES):
            boost += 1.0
            reasons.append("preferred_prefix")

        # Name markers
        primary_hits = sum(1 for m in DOC_PRIMARY_NAME_MARKERS if m in normalized_path)
        secondary_hits = sum(1 for m in DOC_SECONDARY_NAME_MARKERS if m in normalized_path)

        boost += min(2.5, float(primary_hits))
        if primary_hits > 0:
            reasons.append(f"primary_markers({primary_hits})")

        boost += min(0.75, float(secondary_hits) * 0.5)
        if secondary_hits > 0:
            reasons.append(f"secondary_markers({secondary_hits})")

        # Entrypoint
        stem = NormalizationUtils.extract_path_stem(path)
        if stem in DOC_ENTRYPOINT_BASENAMES:
            boost += 1.5
            reasons.append("entrypoint")

        # Current/latest keyword
        if "current" in normalized_path or "latest" in normalized_path:
            boost += 0.75
            reasons.append("latest_keyword")

        # Date-based boost
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

        # Domain penalties
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

    _strategies: ClassVar[list[BoostStrategy]] = [
        DocSyncBoostStrategy(),
        LatestDocBoostStrategy(),
    ]

    @classmethod
    def get_instance(cls) -> BoostStrategyRegistry:
        """Get singleton instance."""
        if not hasattr(cls, "_instance"):
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
        return [
            strategy.calculate(path, language, flags, context)
            for strategy in self._strategies
        ]

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


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "DOC_ENTRYPOINT_BASENAMES",
    "DOC_PREFERRED_PREFIXES",
    "DOC_PRIMARY_NAME_MARKERS",
    "DOC_SECONDARY_NAME_MARKERS",
    "QUERY_DOC_SYNC_MARKERS",
    "QUERY_LATEST_MARKERS",
    "QUERY_ONBOARDING_MARKERS",
    "BoostResult",
    "BoostStrategy",
    "BoostStrategyRegistry",
    "DomainMatch",
    "DomainStrategy",
    "DomainStrategyRegistry",
    "IntentStrategy",
    "IntentStrategyRegistry",
    "NormalizationUtils",
    "QueryFlags",
]
