"""Domain classification strategies for plan_quick."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from ace_lite.plan_quick_strategies_shared import NormalizationUtils


@dataclass
class DomainMatch:
    """Result of domain classification."""

    domain: str
    confidence: float = 1.0
    matched_prefix: str | None = None


class DomainStrategy(ABC):
    """Base class for domain classification strategies."""

    DOMAIN: ClassVar[str] = "unknown"

    @classmethod
    @abstractmethod
    def match(self, path: str | None, normalized_path: str) -> DomainMatch | None:
        """Check if path matches this domain strategy."""

    @classmethod
    def classify_path(cls, path: str | None) -> str:
        """Classify path into domain category."""
        normalized = NormalizationUtils.normalize_path(path)
        if not normalized:
            return "unknown"

        for strategy_cls in _DOMAIN_STRATEGIES:
            match = strategy_cls.match(None, normalized)
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
        if (
            normalized_path.startswith(("reference/", "docs/reference/"))
            or "/reference/" in normalized_path
        ):
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
            match = strategy_cls.match(None, normalized)
            if match is not None:
                return match
        return DomainMatch(domain="code", confidence=1.0)


__all__ = [
    "DomainMatch",
    "DomainStrategy",
    "DomainStrategyRegistry",
]
