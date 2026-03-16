from __future__ import annotations

from typing import Any

from ace_lite.index_stage.benchmark_candidate_runtime import (
    apply_benchmark_candidate_filters,
)


def test_apply_benchmark_candidate_filters_applies_filtered_candidates() -> None:
    captured: dict[str, Any] = {}

    def fake_filter_candidate_rows(rows, **kwargs):  # type: ignore[no-untyped-def]
        captured["rows"] = rows
        captured["kwargs"] = kwargs
        return ([{"path": "src/alpha.py", "score": 8.0}], 1)

    result = apply_benchmark_candidate_filters(
        candidates=[
            {"path": "src/alpha.py", "score": 8.0},
            {"path": "src/beta.py", "score": 7.0},
        ],
        benchmark_filter_payload={
            "requested": True,
            "include_paths": ["src/alpha.py"],
            "include_globs": [],
            "exclude_paths": [],
            "exclude_globs": [],
        },
        filter_candidate_rows_fn=fake_filter_candidate_rows,
    )

    assert captured["kwargs"]["include_paths"] == ["src/alpha.py"]
    assert result.candidates == [{"path": "src/alpha.py", "score": 8.0}]
    assert result.benchmark_filter_payload["dropped_candidate_count"] == 1
    assert result.benchmark_filter_payload["candidate_count_before"] == 2
    assert result.benchmark_filter_payload["candidate_count_after"] == 1
    assert result.benchmark_filter_payload["applied"] is True
    assert result.benchmark_filter_payload["fallback_to_unfiltered"] is False


def test_apply_benchmark_candidate_filters_falls_back_when_filter_empties_pool() -> None:
    def fake_filter_candidate_rows(rows, **kwargs):  # type: ignore[no-untyped-def]
        _ = (rows, kwargs)
        return ([], 2)

    original_candidates = [
        {"path": "src/alpha.py", "score": 8.0},
        {"path": "src/beta.py", "score": 7.0},
    ]
    result = apply_benchmark_candidate_filters(
        candidates=original_candidates,
        benchmark_filter_payload={
            "requested": True,
            "include_paths": ["docs/guide.md"],
            "include_globs": [],
            "exclude_paths": [],
            "exclude_globs": [],
        },
        filter_candidate_rows_fn=fake_filter_candidate_rows,
    )

    assert result.candidates == original_candidates
    assert result.benchmark_filter_payload["dropped_candidate_count"] == 2
    assert result.benchmark_filter_payload["candidate_count_before"] == 2
    assert result.benchmark_filter_payload["candidate_count_after"] == 0
    assert result.benchmark_filter_payload["applied"] is False
    assert result.benchmark_filter_payload["fallback_to_unfiltered"] is True


def test_apply_benchmark_candidate_filters_reports_passthrough_when_not_requested() -> None:
    def fake_filter_candidate_rows(rows, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("filter helper should not be called when not requested")

    result = apply_benchmark_candidate_filters(
        candidates=[{"path": "src/alpha.py", "score": 8.0}],
        benchmark_filter_payload={"requested": False},
        filter_candidate_rows_fn=fake_filter_candidate_rows,
    )

    assert result.candidates == [{"path": "src/alpha.py", "score": 8.0}]
    assert result.benchmark_filter_payload["dropped_candidate_count"] == 0
    assert result.benchmark_filter_payload["candidate_count_before"] == 1
    assert result.benchmark_filter_payload["candidate_count_after"] == 1
    assert result.benchmark_filter_payload["applied"] is False
    assert result.benchmark_filter_payload["fallback_to_unfiltered"] is False
