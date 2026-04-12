"""ASF-8914: Session replay benchmark for 2026-04-12 feedback.

This module replays the key queries from the 2026-04-12 session feedback
to measure:
1. Top-k distribution across docs/planning/code/tests domains
2. Time to first correct file set
3. Planning document visibility in first screen
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ace_lite.plan_quick import build_plan_quick


# Query groups from the 2026-04-12 session feedback
SESSION_QUERIES_GROUP_1 = [
    # Design/requirements clarification queries (first round)
    "explain the current requirements for explainability",
    "what is the state of EXPL-01 and EXPL-02",
    "requirements milestone phase state",
]

SESSION_QUERIES_GROUP_2 = [
    # Second round queries with explicit requirement IDs
    "EXPL-01 requirements contract",
    "EXPL-02 explainability state",
]


def _write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _setup_test_repo(tmp_path: Path) -> Path:
    """Create a test repo structure similar to the session feedback scenario."""
    # Planning docs in hidden directory (common pattern)
    _write_file(
        tmp_path / ".planning/REQUIREMENTS.md",
        "# Requirements\n\n## EXPL-01: Explainability for model decisions\n\nDetails...\n",
    )
    _write_file(
        tmp_path / ".planning/STATE.md",
        "# State\n\nCurrent implementation state of EXPL-01 and EXPL-02.\n",
    )
    _write_file(
        tmp_path / ".planning/ROADMAP.md",
        "# Roadmap\n\nMilestones and phases.\n",
    )

    # Regular docs
    _write_file(
        tmp_path / "docs/architecture.md",
        "# Architecture\n\nSystem architecture overview.\n",
    )
    _write_file(
        tmp_path / "docs/guide.md",
        "# User Guide\n\nHow to use the system.\n",
    )

    # Source code
    _write_file(
        tmp_path / "src/explainability/engine.py",
        "class ExplainabilityEngine:\n    def explain(self, decision):\n        pass\n",
    )
    _write_file(
        tmp_path / "src/explainability/renderer.py",
        "class ExplanationRenderer:\n    def render(self, explanation):\n        pass\n",
    )
    _write_file(
        tmp_path / "src/main.py",
        "def main():\n    pass\n",
    )

    # Tests
    _write_file(
        tmp_path / "tests/test_explainability.py",
        "def test_explain():\n    pass\n",
    )

    return tmp_path


class TestSessionReplayQueries:
    """Replay benchmark for 2026-04-12 session feedback queries."""

    def test_group_1_queries_have_planning_in_top_5(self, tmp_path: Path) -> None:
        """Success criteria: First 5 results contain at least 2 planning/docs files."""
        root = _setup_test_repo(tmp_path)

        for query in SESSION_QUERIES_GROUP_1:
            result = build_plan_quick(
                query=query,
                root=root,
                languages="python,markdown",
                top_k_files=5,
                repomap_top_k=12,
            )

            planning_count = sum(
                1 for path in result["candidate_files"]
                if ".planning/" in path or "docs/" in path
            )
            assert planning_count >= 2, (
                f"Query '{query}' should have at least 2 planning/docs files "
                f"in top 5, got {planning_count}"
            )

    def test_group_2_queries_with_req_id_have_planning_first(self, tmp_path: Path) -> None:
        """Success criteria: Queries with requirement IDs show planning files first."""
        root = _setup_test_repo(tmp_path)

        for query in SESSION_QUERIES_GROUP_2:
            result = build_plan_quick(
                query=query,
                root=root,
                languages="python,markdown",
                top_k_files=5,
                repomap_top_k=12,
            )

            # At least one .planning/ file should be in top 3
            planning_in_top_3 = any(
                ".planning/" in path
                for path in result["candidate_files"][:3]
            )
            assert planning_in_top_3, (
                f"Query '{query}' should have .planning/ file in top 3"
            )

    def test_hidden_planning_dirs_recognized_as_planning_domain(self, tmp_path: Path) -> None:
        """Success criteria: .planning/ paths are classified as planning domain."""
        root = _setup_test_repo(tmp_path)

        result = build_plan_quick(
            query="requirements state",
            root=root,
            languages="python,markdown",
            top_k_files=8,
            repomap_top_k=12,
        )

        # Check that .planning files have correct domain
        for detail in result["candidate_details"]:
            if ".planning/" in detail["path"]:
                assert detail["semantic_domain"] == "planning", (
                    f"Path {detail['path']} should have domain='planning', "
                    f"got '{detail['semantic_domain']}'"
                )

    def test_candidate_details_have_picked_because(self, tmp_path: Path) -> None:
        """Success criteria: All candidate details include picked_because field."""
        root = _setup_test_repo(tmp_path)

        result = build_plan_quick(
            query="EXPL-01 requirements",
            root=root,
            languages="python,markdown",
            top_k_files=5,
            repomap_top_k=12,
        )

        for detail in result["candidate_details"]:
            assert "picked_because" in detail, (
                f"Candidate {detail['path']} missing 'picked_because'"
            )
            assert isinstance(detail["picked_because"], str)
            assert len(detail["picked_because"]) > 0

    def test_domain_mixed_refinement_suggested_for_req_queries(self, tmp_path: Path) -> None:
        """Success criteria: Requirement queries get domain_mixed refinement."""
        root = _setup_test_repo(tmp_path)

        result = build_plan_quick(
            query="EXPL-01 requirements",
            root=root,
            languages="python,markdown",
            top_k_files=5,
            repomap_top_k=12,
        )

        codes = [r["code"] for r in result.get("suggested_query_refinements", [])]
        assert "domain_mixed" in codes, (
            "Expected 'domain_mixed' refinement for requirement query"
        )

    def test_query_profile_has_req_id_flags(self, tmp_path: Path) -> None:
        """Success criteria: Query profile correctly identifies requirement IDs."""
        root = _setup_test_repo(tmp_path)

        result = build_plan_quick(
            query="What about EXPL-01 and REQ-02?",
            root=root,
            languages="python,markdown",
            top_k_files=5,
            repomap_top_k=12,
        )

        profile = result["query_profile"]
        assert profile["has_req_id"] is True
        assert "EXPL-01" in profile["req_ids"]
        assert "REQ-02" in profile["req_ids"]


class TestBenchmarkMetrics:
    """Metrics collection for the session replay."""

    def test_measure_top_k_domain_distribution(self, tmp_path: Path) -> None:
        """Collect domain distribution metrics for analysis."""
        root = _setup_test_repo(tmp_path)

        all_metrics: list[dict] = []
        for query in SESSION_QUERIES_GROUP_1 + SESSION_QUERIES_GROUP_2:
            result = build_plan_quick(
                query=query,
                root=root,
                languages="python,markdown",
                top_k_files=5,
                repomap_top_k=12,
            )

            domain_counts: dict[str, int] = {}
            for detail in result["candidate_details"]:
                domain = detail["semantic_domain"]
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

            all_metrics.append({
                "query": query,
                "domains": domain_counts,
                "planning_in_top_3": any(
                    ".planning/" in path
                    for path in result["candidate_files"][:3]
                ),
            })

        # At least 50% of queries should have planning in top 3
        planning_first_count = sum(1 for m in all_metrics if m["planning_in_top_3"])
        assert planning_first_count >= len(all_metrics) // 2, (
            f"Only {planning_first_count}/{len(all_metrics)} queries "
            f"have planning files in top 3"
        )
