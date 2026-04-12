"""Tests for paired_eval_cases.yaml (ALH1-0201.T1).

Verifies that the paired eval case set is well-formed:
- All cases have required fields (case_id, query, comparison_lane, paired_eval_type)
- Quick and full cases within each pair share the same query
- All cases use comparison_lane: paired_eval
- paired_eval_type is either "quick" or "full"
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pytest
import yaml

from ace_lite.benchmark.case_contracts import normalize_benchmark_case
from ace_lite.benchmark.runner import load_cases

FIXTURE_PATH = (
    Path(__file__).parent.parent.parent / "benchmark" / "cases" / "paired_eval_cases.yaml"
)


def _load_raw_cases(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if isinstance(data, dict):
        return data.get("cases", [])
    if isinstance(data, list):
        return data
    return []


class TestPairedEvalCaseSet:
    """ALH1-0201.T1 acceptance criteria for paired_eval_cases.yaml."""

    def test_paired_eval_yaml_loads(self) -> None:
        """Paired eval YAML must load without schema errors."""
        cases = _load_raw_cases(FIXTURE_PATH)
        assert len(cases) > 0, "paired_eval_cases.yaml must contain at least one case"

    def test_all_cases_have_required_fields(self) -> None:
        """Every case must have case_id, query, comparison_lane, paired_eval_type."""
        cases = _load_raw_cases(FIXTURE_PATH)
        required = {"case_id", "query", "comparison_lane", "paired_eval_type"}
        for case in cases:
            missing = required - set(case.keys())
            assert not missing, f"case {case.get('case_id', '?')}: missing fields {missing}"

    def test_comparison_lane_is_paired_eval(self) -> None:
        """All cases must use comparison_lane: paired_eval."""
        cases = _load_raw_cases(FIXTURE_PATH)
        for case in cases:
            assert case.get("comparison_lane") == "paired_eval", (
                f"case {case['case_id']}: comparison_lane must be 'paired_eval'"
            )

    def test_paired_eval_type_is_quick_or_full(self) -> None:
        """paired_eval_type must be either 'quick' or 'full'."""
        cases = _load_raw_cases(FIXTURE_PATH)
        valid_types = {"quick", "full"}
        for case in cases:
            t = case.get("paired_eval_type")
            assert t in valid_types, (
                f"case {case['case_id']}: paired_eval_type must be 'quick' or 'full', got {t!r}"
            )

    def test_quick_and_full_cases_share_same_query(self) -> None:
        """Quick and full variants of the same pair must have identical queries."""
        cases = _load_raw_cases(FIXTURE_PATH)

        # Group by pair index extracted from case_id: "pq-{N}-{type}"
        pairs: dict[int, dict] = defaultdict(dict)
        for case in cases:
            case_id = str(case.get("case_id", ""))
            parts = case_id.split("-")
            if len(parts) >= 2 and parts[0] == "pq":
                try:
                    pair_idx = int(parts[1])
                except ValueError:
                    pytest.fail(f"case_id {case_id!r} does not match pq-N-type pattern")
                pairs[pair_idx][case.get("paired_eval_type")] = case.get("query")

        # Verify each pair has both quick and full
        for pair_idx, variants in sorted(pairs.items()):
            assert "quick" in variants, f"pair pq-{pair_idx}: missing 'quick' variant"
            assert "full" in variants, f"pair pq-{pair_idx}: missing 'full' variant"
            assert variants["quick"] == variants["full"], (
                f"pair pq-{pair_idx}: quick and full queries differ: "
                f"{variants['quick']!r} != {variants['full']!r}"
            )

    def test_paired_cases_normalize_without_crash(self) -> None:
        """Each paired eval case must survive normalization without raising."""
        cases = _load_raw_cases(FIXTURE_PATH)
        for case in cases:
            normalized = normalize_benchmark_case(dict(case))
            assert normalized.get("case_id") == case.get("case_id")
            assert normalized.get("query") == case.get("query")

    def test_load_cases_accepts_paired_eval_yaml(self) -> None:
        """The benchmark case loader (load_cases) must accept paired_eval_cases.yaml."""
        cases = load_cases(FIXTURE_PATH)
        # Must have loaded all 8 cases (4 pairs x 2)
        assert len(cases) == 8, f"expected 8 cases, got {len(cases)}"

    def test_load_cases_returns_normalized_cases(self) -> None:
        """load_cases returns normalized cases with required schema fields."""
        cases = load_cases(FIXTURE_PATH)
        for case in cases:
            assert case.get("case_id", "").startswith("pq-"), (
                f"unexpected case_id: {case['case_id']}"
            )
            assert case.get("query"), "normalized case must have query"
            assert case.get("comparison_lane") == "paired_eval"
