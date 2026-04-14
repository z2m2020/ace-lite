from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CaseEvaluationInputs:
    comparison_lane: str
    expected: list[str]
    top_k: int
    index_payload: dict[str, Any]
    index_metadata: dict[str, Any]
    index_benchmark_filters: dict[str, Any]
    source_plan_payload: dict[str, Any]


def build_case_evaluation_inputs(
    *,
    case: dict[str, Any],
    plan_payload: dict[str, Any],
) -> CaseEvaluationInputs:
    comparison_lane = str(case.get("comparison_lane") or "").strip()
    expected_keys = case.get("expected_keys", [])
    if isinstance(expected_keys, str):
        expected = [item.strip() for item in expected_keys.split(";") if item.strip()]
    else:
        expected = [str(item).strip() for item in expected_keys if str(item).strip()]

    top_k = int(case.get("top_k", 8))
    index_payload = (
        plan_payload.get("index", {})
        if isinstance(plan_payload.get("index"), dict)
        else {}
    )
    index_metadata = (
        index_payload.get("metadata", {})
        if isinstance(index_payload.get("metadata"), dict)
        else {}
    )
    index_benchmark_filters = (
        index_payload.get("benchmark_filters", {})
        if isinstance(index_payload.get("benchmark_filters"), dict)
        else {}
    )
    source_plan_payload = (
        plan_payload.get("source_plan", {})
        if isinstance(plan_payload.get("source_plan"), dict)
        else {}
    )
    return CaseEvaluationInputs(
        comparison_lane=comparison_lane,
        expected=expected,
        top_k=top_k,
        index_payload=index_payload,
        index_metadata=index_metadata,
        index_benchmark_filters=index_benchmark_filters,
        source_plan_payload=source_plan_payload,
    )


__all__ = ["CaseEvaluationInputs", "build_case_evaluation_inputs"]
