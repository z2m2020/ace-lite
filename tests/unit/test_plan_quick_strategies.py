"""Unit tests for plan_quick_strategies module.

These tests verify the strategy registry refactoring maintains
backward compatibility while reducing code duplication.
"""

from __future__ import annotations

from datetime import date

import pytest

from ace_lite.plan_quick_strategies import (
    BoostResult,
    BoostStrategyRegistry,
    DomainMatch,
    DomainStrategy,
    DomainStrategyRegistry,
    IntentStrategyRegistry,
    NormalizationUtils,
    QueryFlags,
)


class TestNormalizationUtils:
    """Tests for NormalizationUtils."""

    def test_normalize_path_basic(self):
        """Test basic path normalization."""
        assert NormalizationUtils.normalize_path("C:\\Users\\Test\\file.py") == "c:/users/test/file.py"
        assert NormalizationUtils.normalize_path("/path/to/file.py") == "/path/to/file.py"
        assert NormalizationUtils.normalize_path(None) == ""
        assert NormalizationUtils.normalize_path("  /path/to/file.py  ") == "/path/to/file.py"

    def test_normalize_path_strip_lowercase(self):
        """Test that normalization strips and lowercases."""
        assert NormalizationUtils.normalize_path("  Hello/World  ") == "hello/world"

    def test_normalize_language(self):
        """Test language normalization."""
        assert NormalizationUtils.normalize_language("Python") == "python"
        assert NormalizationUtils.normalize_language("  JavaScript  ") == "javascript"
        assert NormalizationUtils.normalize_language(None) == ""

    def test_extract_path_stem(self):
        """Test stem extraction."""
        assert NormalizationUtils.extract_path_stem("/path/to/readme.md") == "readme"
        assert NormalizationUtils.extract_path_stem("/path/to/file.py") == "file"
        assert NormalizationUtils.extract_path_stem("/path/to/file") == "file"
        assert NormalizationUtils.extract_path_stem("file.tar.gz") == "file.tar"
        assert NormalizationUtils.extract_path_stem(None) == ""

    def test_is_markdown_path(self):
        """Test markdown path detection."""
        assert NormalizationUtils.is_markdown_path("/path/to/readme.md") is True
        assert NormalizationUtils.is_markdown_path("/path/to/readme.mdx") is True
        assert NormalizationUtils.is_markdown_path("/path/to/file.py") is False
        assert NormalizationUtils.is_markdown_path(None) is False

    def test_is_markdown_language(self):
        """Test markdown language detection."""
        assert NormalizationUtils.is_markdown_language("markdown") is True
        assert NormalizationUtils.is_markdown_language("md") is True
        assert NormalizationUtils.is_markdown_language("Markdown") is True
        assert NormalizationUtils.is_markdown_language("python") is False
        assert NormalizationUtils.is_markdown_language(None) is False


class TestQueryFlags:
    """Tests for QueryFlags."""

    def test_from_query_doc_sync(self):
        """Test doc_sync flag detection."""
        flags = QueryFlags.from_query("update the documentation")
        assert flags.doc_sync is True
        assert flags.onboarding is False

    def test_from_query_onboarding(self):
        """Test onboarding flag detection."""
        flags = QueryFlags.from_query("help me understand the codebase")
        assert flags.onboarding is True
        assert flags.doc_sync is False

    def test_from_query_latest(self):
        """Test latest_sensitive flag detection."""
        flags = QueryFlags.from_query("what is the latest status")
        assert flags.latest_sensitive is True

    def test_from_query_req_id(self):
        """Test requirement ID detection."""
        flags = QueryFlags.from_query("work on EXPL-01 and REQ-42")
        assert flags.has_req_id is True
        assert "EXPL-01" in flags.req_ids
        assert "REQ-42" in flags.req_ids

    def test_from_query_multiple_flags(self):
        """Test detection of multiple flags."""
        flags = QueryFlags.from_query("update the onboarding documentation for EXPL-01")
        assert flags.doc_sync is True
        assert flags.onboarding is True
        assert flags.has_req_id is True
        assert "EXPL-01" in flags.req_ids

    def test_from_query_no_flags(self):
        """Test query with no specific flags."""
        flags = QueryFlags.from_query("fix the login bug")
        assert flags.doc_sync is False
        assert flags.onboarding is False
        assert flags.latest_sensitive is False
        assert flags.has_req_id is False
        assert flags.req_ids == ()


class TestDomainStrategyRegistry:
    """Tests for DomainStrategyRegistry."""

    @pytest.mark.parametrize(
        "path,expected_domain",
        [
            ("docs/readme.md", "docs"),
            ("doc/api.md", "docs"),
            ("planning/roadmap.md", "planning"),
            ("plans/sprint-1.md", "planning"),
            ("milestones/v1.0.md", "planning"),
            ("phases/current.md", "planning"),
            ("state/snapshot.md", "planning"),
            ("repos/index.md", "repos"),
            ("reports/weekly.md", "reports"),
            ("research/papers/notes.md", "research"),
            ("reference/api.md", "reference"),
            ("tests/test_login.py", "tests"),
            ("test_helpers.py", "code"),
            ("src/main.py", "code"),
            ("readme.md", "markdown"),
            ("changelog.md", "markdown"),
            ("config.yaml", "code"),
        ],
    )
    def test_classify_path(self, path, expected_domain):
        """Test domain classification for various paths."""
        result = DomainStrategyRegistry.classify(path)
        assert result == expected_domain

    def test_classify_path_with_backslash(self):
        """Test path with Windows backslashes."""
        result = DomainStrategyRegistry.classify("docs\\readme.md")
        assert result == "docs"

    def test_classify_none_path(self):
        """Test classification of None path."""
        result = DomainStrategyRegistry.classify(None)
        assert result == "unknown"

    def test_classify_empty_path(self):
        """Test classification of empty path."""
        result = DomainStrategyRegistry.classify("")
        # Empty path after normalization returns "unknown"
        assert result == "unknown"

    def test_get_domain_match(self):
        """Test detailed domain match information."""
        match = DomainStrategyRegistry.get_domain_match("docs/readme.md")
        assert isinstance(match, DomainMatch)
        assert match.domain == "docs"
        assert match.matched_prefix == "docs/"


class TestIntentStrategyRegistry:
    """Tests for IntentStrategyRegistry."""

    def test_detect_intent_doc_sync(self):
        """Test doc sync intent detection."""
        registry = IntentStrategyRegistry.get_instance()
        flags = registry.detect_intent("sync the docs")

        assert flags.doc_sync is True
        assert flags.onboarding is False

    def test_detect_intent_onboarding(self):
        """Test onboarding intent detection."""
        registry = IntentStrategyRegistry.get_instance()
        flags = registry.detect_intent("familiarize with the codebase")

        assert flags.onboarding is True
        assert flags.doc_sync is False

    def test_detect_intent_combined(self):
        """Test combined intent detection."""
        registry = IntentStrategyRegistry.get_instance()
        flags = registry.detect_intent("onboarding docs for EXPL-01")

        assert flags.onboarding is True
        assert flags.doc_sync is True
        assert "EXPL-01" in flags.req_ids


class TestBoostStrategyRegistry:
    """Tests for BoostStrategyRegistry."""

    def test_calculate_no_boost_without_flags(self):
        """Test that no boost is applied without matching flags."""
        registry = BoostStrategyRegistry.get_instance()
        flags = QueryFlags()  # Empty flags

        boost = registry.calculate_total_boost(
            path="/path/to/readme.md",
            language="markdown",
            flags=flags,
            context={},
        )
        assert boost == 0.0

    def test_calculate_doc_sync_boost(self):
        """Test doc sync boost calculation."""
        registry = BoostStrategyRegistry.get_instance()
        flags = QueryFlags(doc_sync=True)
        context = {"newest_dated_doc": date(2026, 4, 1)}

        # Markdown file in docs directory should get positive boost
        boost = registry.calculate_total_boost(
            path="docs/readme.md",
            language="markdown",
            flags=flags,
            context=context,
        )
        assert boost > 0.0

    def test_calculate_research_penalty(self):
        """Test that research paths get penalized for doc sync."""
        registry = BoostStrategyRegistry.get_instance()
        flags = QueryFlags(doc_sync=True)

        boost = registry.calculate_total_boost(
            path="research/notes.md",
            language="markdown",
            flags=flags,
            context={},
        )
        assert boost < 0.0

    def test_calculate_latest_doc_boost(self):
        """Test latest doc boost calculation."""
        registry = BoostStrategyRegistry.get_instance()
        flags = QueryFlags(latest_sensitive=True)
        context = {"newest_dated_doc": date(2026, 4, 1)}

        boost = registry.calculate_total_boost(
            path="docs/status-2026-04-01.md",
            language="markdown",
            flags=flags,
            context=context,
        )
        # Should get positive boost for being the newest dated doc
        assert boost > 0.0

    def test_calculate_doc_sync_boost_component(self):
        """Test direct access to the doc-sync boost component."""
        registry = BoostStrategyRegistry.get_instance()
        flags = QueryFlags(doc_sync=True)

        boost = registry.calculate_doc_sync_boost(
            path="docs/readme.md",
            language="markdown",
            flags=flags,
            context={},
        )

        assert boost > 0.0

    def test_calculate_latest_doc_boost_component(self):
        """Test direct access to the latest-doc boost component."""
        registry = BoostStrategyRegistry.get_instance()
        flags = QueryFlags(latest_sensitive=True)
        context = {"newest_dated_doc": date(2026, 4, 1)}

        boost = registry.calculate_latest_doc_boost(
            path="docs/status-2026-04-01.md",
            language="markdown",
            flags=flags,
            context=context,
        )

        assert boost > 0.0


class TestBackwardCompatibility:
    """Tests to ensure backward compatibility with existing plan_quick.py."""

    def test_marker_collections_exported(self):
        """Test that marker collections are still accessible."""
        from ace_lite.plan_quick_strategies import (
            DOC_PREFERRED_PREFIXES,
            DOC_PRIMARY_NAME_MARKERS,
            DOC_SECONDARY_NAME_MARKERS,
            QUERY_DOC_SYNC_MARKERS,
        )

        assert "doc" in QUERY_DOC_SYNC_MARKERS
        assert "readme" in DOC_SECONDARY_NAME_MARKERS  # readme is in secondary markers
        assert "progress" in DOC_PRIMARY_NAME_MARKERS
        assert "docs/" in DOC_PREFERRED_PREFIXES

    def test_path_date_extraction(self):
        """Test date extraction from path."""
        from ace_lite.plan_quick_strategies import _extract_path_date

        assert _extract_path_date("path/to/file-2026-04-12.md") == date(2026, 4, 12)
        assert _extract_path_date("path/to/file-2025-01-01.md") == date(2025, 1, 1)
        assert _extract_path_date("path/to/file.md") is None
        assert _extract_path_date(None) is None

    def test_req_id_extraction(self):
        """Test requirement ID extraction."""
        from ace_lite.plan_quick_strategies import _extract_req_ids

        assert "EXPL-01" in _extract_req_ids("work on EXPL-01")
        assert "REQ-42" in _extract_req_ids("fix REQ-42 and TASK-99")
        assert "PQ-007" in _extract_req_ids("review PQ-007")
        assert _extract_req_ids("no ids here") == []


class TestStrategyPattern:
    """Tests for strategy pattern compliance."""

    def test_domain_strategy_interface(self):
        """Test DomainStrategy abstract interface."""
        # DomainStrategy should be abstract
        with pytest.raises(TypeError):
            DomainStrategy()  # type: ignore

    def test_intent_strategy_interface(self):
        """Test IntentStrategy abstract interface."""
        from ace_lite.plan_quick_strategies import IntentStrategy

        # IntentStrategy should be abstract
        with pytest.raises(TypeError):
            IntentStrategy()  # type: ignore

    def test_boost_strategy_interface(self):
        """Test BoostStrategy abstract interface."""
        from ace_lite.plan_quick_strategies import BoostStrategy

        # BoostStrategy should be abstract
        with pytest.raises(TypeError):
            BoostStrategy()  # type: ignore

    def test_boost_result_dataclass(self):
        """Test BoostResult dataclass."""
        result = BoostResult(boost=2.5, reason="test_reason", weight=1.0)
        assert result.boost == 2.5
        assert result.reason == "test_reason"
        assert result.weight == 1.0

    def test_domain_match_dataclass(self):
        """Test DomainMatch dataclass."""
        match = DomainMatch(domain="docs", confidence=0.9, matched_prefix="docs/")
        assert match.domain == "docs"
        assert match.confidence == 0.9
        assert match.matched_prefix == "docs/"
