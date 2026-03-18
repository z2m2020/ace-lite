"""Compatibility facade for benchmark scoring helpers."""

from __future__ import annotations

from ace_lite.benchmark.case_evaluation import evaluate_case_result
from ace_lite.benchmark.regression_checks import (
    REGRESSION_THRESHOLD_PROFILES,
    detect_regression,
    resolve_regression_thresholds,
)
from ace_lite.benchmark.summaries import (
    PIPELINE_STAGE_ORDER,
    aggregate_metrics,
    build_adaptive_router_arm_summary,
    build_adaptive_router_observability_summary,
    build_adaptive_router_pair_summary,
    build_comparison_lane_summary,
    build_chunk_stage_miss_summary,
    build_decision_observability_summary,
    build_evidence_insufficiency_summary,
    build_feedback_observability_summary,
    build_preference_observability_summary,
    build_retrieval_context_observability_summary,
    build_slo_budget_summary,
    build_stage_latency_summary,
    compare_metrics,
)

__all__ = [
    "PIPELINE_STAGE_ORDER",
    "REGRESSION_THRESHOLD_PROFILES",
    "aggregate_metrics",
    "build_adaptive_router_arm_summary",
    "build_adaptive_router_observability_summary",
    "build_adaptive_router_pair_summary",
    "build_comparison_lane_summary",
    "build_chunk_stage_miss_summary",
    "build_decision_observability_summary",
    "build_evidence_insufficiency_summary",
    "build_feedback_observability_summary",
    "build_preference_observability_summary",
    "build_retrieval_context_observability_summary",
    "build_slo_budget_summary",
    "build_stage_latency_summary",
    "compare_metrics",
    "detect_regression",
    "evaluate_case_result",
    "resolve_regression_thresholds",
]
