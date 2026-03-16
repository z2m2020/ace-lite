from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class BenchmarkCandidateFilterResult:
    candidates: list[dict[str, Any]]
    benchmark_filter_payload: dict[str, Any]


def apply_benchmark_candidate_filters(
    *,
    candidates: list[dict[str, Any]],
    benchmark_filter_payload: dict[str, Any],
    filter_candidate_rows_fn: Callable[..., tuple[list[dict[str, Any]], int]],
) -> BenchmarkCandidateFilterResult:
    updated_payload = dict(benchmark_filter_payload)
    if updated_payload.get("requested"):
        filtered_candidates, removed_count = filter_candidate_rows_fn(
            candidates,
            include_paths=list(updated_payload.get("include_paths", [])),
            include_globs=list(updated_payload.get("include_globs", [])),
            exclude_paths=list(updated_payload.get("exclude_paths", [])),
            exclude_globs=list(updated_payload.get("exclude_globs", [])),
        )
        updated_payload["dropped_candidate_count"] = int(removed_count)
        updated_payload["candidate_count_before"] = len(candidates)
        updated_payload["candidate_count_after"] = len(filtered_candidates)
        if filtered_candidates:
            updated_payload["applied"] = True
            updated_payload["fallback_to_unfiltered"] = False
            return BenchmarkCandidateFilterResult(
                candidates=list(filtered_candidates),
                benchmark_filter_payload=updated_payload,
            )
        updated_payload["applied"] = False
        updated_payload["fallback_to_unfiltered"] = True
        return BenchmarkCandidateFilterResult(
            candidates=list(candidates),
            benchmark_filter_payload=updated_payload,
        )

    updated_payload["dropped_candidate_count"] = 0
    updated_payload["candidate_count_before"] = len(candidates)
    updated_payload["candidate_count_after"] = len(candidates)
    updated_payload["applied"] = False
    updated_payload["fallback_to_unfiltered"] = False
    return BenchmarkCandidateFilterResult(
        candidates=list(candidates),
        benchmark_filter_payload=updated_payload,
    )


__all__ = [
    "BenchmarkCandidateFilterResult",
    "apply_benchmark_candidate_filters",
]
