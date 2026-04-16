from __future__ import annotations

from pathlib import Path

import yaml

from ace_lite.benchmark.runner import load_cases

FIXTURE_PATH = (
    Path(__file__).parent.parent.parent / "benchmark" / "cases" / "context_refine_cases.yaml"
)


def _load_raw_cases(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if isinstance(data, dict):
        return data.get("cases", [])
    if isinstance(data, list):
        return data
    return []


def test_context_refine_cases_yaml_loads() -> None:
    cases = _load_raw_cases(FIXTURE_PATH)
    assert len(cases) >= 4


def test_context_refine_cases_all_use_context_refine_lane() -> None:
    cases = _load_raw_cases(FIXTURE_PATH)
    for case in cases:
        assert case.get("comparison_lane") == "context_refine"


def test_context_refine_cases_load_through_runner() -> None:
    cases = load_cases(FIXTURE_PATH)
    assert len(cases) >= 4
    assert all(case.get("comparison_lane") == "context_refine" for case in cases)
