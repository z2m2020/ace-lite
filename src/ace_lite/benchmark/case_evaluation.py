"""Case-level benchmark evaluation helpers."""

from __future__ import annotations

from typing import Any, cast

from ace_lite.benchmark.case_evaluation_context import build_candidate_context
from ace_lite.benchmark.case_evaluation_details import classify_chunk_stage_miss
from ace_lite.benchmark.case_evaluation_diagnostics_builder import (
    build_case_evaluation_diagnostics_from_namespace,
)
from ace_lite.benchmark.case_evaluation_inputs import build_case_evaluation_inputs
from ace_lite.benchmark.case_evaluation_matching import (
    collect_candidate_match_details,
    collect_chunk_match_details,
)
from ace_lite.benchmark.case_evaluation_metrics import (
    build_case_evaluation_metrics,
)
from ace_lite.benchmark.case_evaluation_payload_builders import (
    build_case_detail_payload_from_namespace,
    build_case_evaluation_row_from_namespace,
)
from ace_lite.benchmark.case_evaluation_payloads import coerce_chunk_refs


def evaluate_case_result(
    *,
    case: dict[str, Any],
    plan_payload: dict[str, Any],
    latency_ms: float,
    include_case_details: bool = True,
) -> dict[str, Any]:
    inputs = build_case_evaluation_inputs(case=case, plan_payload=plan_payload)
    comparison_lane = inputs.comparison_lane
    expected = inputs.expected
    top_k = inputs.top_k
    index_payload = inputs.index_payload
    index_metadata = inputs.index_metadata
    index_benchmark_filters = inputs.index_benchmark_filters
    source_plan_payload = inputs.source_plan_payload
    candidate_context = build_candidate_context(
        case=case,
        index_payload=index_payload,
        index_benchmark_filters=index_benchmark_filters,
        source_plan_payload=source_plan_payload,
        coerce_chunk_refs=coerce_chunk_refs,
    )
    candidate_files = candidate_context.candidate_files
    raw_candidate_chunks = candidate_context.raw_candidate_chunks
    source_plan_has_candidate_chunks = candidate_context.source_plan_has_candidate_chunks
    source_plan_candidate_chunks = candidate_context.source_plan_candidate_chunks
    candidate_chunks = candidate_context.candidate_chunks
    metrics = build_case_evaluation_metrics(
        plan_payload=plan_payload,
        index_payload=index_payload,
        index_metadata=index_metadata,
        source_plan_payload=source_plan_payload,
        candidate_files=candidate_files,
        raw_candidate_chunks=raw_candidate_chunks,
        candidate_chunks=candidate_chunks,
        source_plan_has_candidate_chunks=source_plan_has_candidate_chunks,
    )
    chunk_stage_miss = classify_chunk_stage_miss(
        case=case,
        candidate_files=candidate_files,
        raw_candidate_chunks=raw_candidate_chunks,
        source_plan_candidate_chunks=source_plan_candidate_chunks,
        source_plan_has_candidate_chunks=source_plan_has_candidate_chunks,
    )

    top_candidates = candidate_files[:top_k]
    top_chunks = candidate_chunks[: max(1, top_k * 3)]

    candidate_match_details = collect_candidate_match_details(
        top_candidates=top_candidates,
        expected=expected,
        top_k=top_k,
    )

    chunk_match_details = collect_chunk_match_details(
        top_chunks=top_chunks,
        expected=expected,
    )
    diagnostics = build_case_evaluation_diagnostics_from_namespace(
        namespace=locals()
    )

    payload = build_case_evaluation_row_from_namespace(namespace=locals())
    if comparison_lane:
        payload["comparison_lane"] = comparison_lane
    if include_case_details:
        payload.update(build_case_detail_payload_from_namespace(namespace=locals()))
    return cast(dict[str, Any], payload)


__all__ = ["evaluate_case_result"]
