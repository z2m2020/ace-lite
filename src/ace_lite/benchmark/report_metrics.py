from __future__ import annotations

from typing import Any

METRIC_ORDER = (
    "recall_at_k",
    "hit_at_1",
    "mrr",
    "precision_at_k",
    "task_success_rate",
    "utility_rate",
    "noise_rate",
    "memory_helpful_task_success_rate",
    "docs_enabled_ratio",
    "docs_hit_ratio",
    "hint_inject_ratio",
    "dependency_recall",
    "repomap_latency_p95_ms",
    "repomap_latency_median_ms",
    "latency_p95_ms",
    "latency_median_ms",
    "skills_route_latency_p95_ms",
    "skills_hydration_latency_p95_ms",
    "chunk_hit_at_k",
    "chunks_per_file_mean",
    "chunk_budget_used",
    "retrieval_context_chunk_count_mean",
    "retrieval_context_coverage_ratio",
    "retrieval_context_char_count_mean",
    "contextual_sidecar_parent_symbol_chunk_count_mean",
    "contextual_sidecar_parent_symbol_coverage_ratio",
    "contextual_sidecar_reference_hint_chunk_count_mean",
    "contextual_sidecar_reference_hint_coverage_ratio",
    "chunk_contract_fallback_count_mean",
    "chunk_contract_skeleton_chunk_count_mean",
    "chunk_contract_fallback_ratio",
    "chunk_contract_skeleton_ratio",
    "unsupported_language_fallback_count_mean",
    "unsupported_language_fallback_ratio",
    "subgraph_payload_enabled_ratio",
    "subgraph_seed_path_count_mean",
    "subgraph_edge_type_count_mean",
    "subgraph_edge_total_count_mean",
    "robust_signature_count_mean",
    "robust_signature_coverage_ratio",
    "graph_prior_chunk_count_mean",
    "graph_prior_coverage_ratio",
    "graph_prior_total_mean",
    "graph_seeded_chunk_count_mean",
    "graph_transfer_count_mean",
    "graph_hub_suppressed_chunk_count_mean",
    "graph_hub_penalty_total_mean",
    "graph_closure_enabled_ratio",
    "graph_closure_boosted_chunk_count_mean",
    "graph_closure_coverage_ratio",
    "graph_closure_anchor_count_mean",
    "graph_closure_support_edge_count_mean",
    "graph_closure_total_mean",
    "topological_shield_enabled_ratio",
    "topological_shield_report_only_ratio",
    "topological_shield_attenuated_chunk_count_mean",
    "topological_shield_coverage_ratio",
    "topological_shield_attenuation_total_mean",
    "chunk_guard_enabled_ratio",
    "chunk_guard_report_only_ratio",
    "chunk_guard_filtered_count_mean",
    "chunk_guard_filter_ratio",
    "chunk_guard_pairwise_conflict_count_mean",
    "chunk_guard_fallback_ratio",
    "skills_selected_count_mean",
    "skills_token_budget_mean",
    "skills_token_budget_used_mean",
    "skills_budget_exhausted_ratio",
    "skills_skipped_for_budget_mean",
    "skills_metadata_only_routing_ratio",
    "skills_precomputed_route_ratio",
    "plan_replay_cache_enabled_ratio",
    "plan_replay_cache_hit_ratio",
    "plan_replay_cache_stale_hit_safe_ratio",
    "validation_test_count",
    "source_plan_direct_evidence_ratio",
    "source_plan_neighbor_context_ratio",
    "source_plan_hint_only_ratio",
    "source_plan_graph_closure_preference_enabled_ratio",
    "source_plan_graph_closure_bonus_candidate_count_mean",
    "source_plan_graph_closure_preferred_count_mean",
    "source_plan_focused_file_promoted_count_mean",
    "source_plan_packed_path_count_mean",
    "evidence_insufficient_rate",
    "no_candidate_rate",
    "low_support_chunk_rate",
    "missing_validation_rate",
    "budget_limited_recovery_rate",
    "noisy_hit_rate",
    "notes_hit_ratio",
    "profile_selected_mean",
    "capture_trigger_ratio",
    "ltm_hit_ratio",
    "ltm_effective_hit_rate",
    "ltm_false_help_rate",
    "ltm_stale_hit_rate",
    "ltm_replay_drift_rate",
    "issue_report_linked_plan_rate",
    "issue_to_benchmark_case_conversion_rate",
    "dev_feedback_resolution_rate",
    "embedding_enabled_ratio",
    "embedding_similarity_mean",
    "embedding_similarity_max",
    "embedding_rerank_ratio",
    "embedding_cache_hit_ratio",
    "embedding_fallback_ratio",
)

STAGE_LATENCY_ORDER = (
    ("memory", "memory_latency_p95_ms"),
    ("index", "index_latency_p95_ms"),
    ("repomap", "repomap_latency_p95_ms"),
    ("augment", "augment_latency_p95_ms"),
    ("skills", "skills_latency_p95_ms"),
    ("source_plan", "source_plan_latency_p95_ms"),
)

SLO_BUDGET_LIMIT_ORDER = (
    "parallel_time_budget_ms_mean",
    "embedding_time_budget_ms_mean",
    "chunk_semantic_time_budget_ms_mean",
    "xref_time_budget_ms_mean",
)

SLO_SIGNAL_ORDER = (
    "parallel_docs_timeout_ratio",
    "parallel_worktree_timeout_ratio",
    "embedding_time_budget_exceeded_ratio",
    "embedding_adaptive_budget_ratio",
    "embedding_fallback_ratio",
    "chunk_semantic_time_budget_exceeded_ratio",
    "chunk_semantic_fallback_ratio",
    "xref_budget_exhausted_ratio",
    "slo_downgrade_case_rate",
)

ALL_METRIC_ORDER = METRIC_ORDER + tuple(
    metric for _, metric in STAGE_LATENCY_ORDER if metric not in METRIC_ORDER
) + tuple(
    metric for metric in SLO_BUDGET_LIMIT_ORDER if metric not in METRIC_ORDER
) + tuple(metric for metric in SLO_SIGNAL_ORDER if metric not in METRIC_ORDER)

COMPARABLE_METRIC_ORDER = ALL_METRIC_ORDER

LATENCY_STYLE_METRICS = {
    "repomap_latency_p95_ms",
    "repomap_latency_median_ms",
    "latency_p95_ms",
    "latency_median_ms",
    "skills_route_latency_p95_ms",
    "skills_hydration_latency_p95_ms",
    "chunk_guard_filtered_count_mean",
    "chunk_guard_pairwise_conflict_count_mean",
    "chunk_contract_fallback_count_mean",
    "chunk_contract_skeleton_chunk_count_mean",
    "unsupported_language_fallback_count_mean",
    "subgraph_seed_path_count_mean",
    "subgraph_edge_type_count_mean",
    "subgraph_edge_total_count_mean",
    "retrieval_context_chunk_count_mean",
    "retrieval_context_char_count_mean",
    "contextual_sidecar_parent_symbol_chunk_count_mean",
    "contextual_sidecar_reference_hint_chunk_count_mean",
    "robust_signature_count_mean",
    "graph_prior_chunk_count_mean",
    "graph_seeded_chunk_count_mean",
    "graph_transfer_count_mean",
    "graph_closure_boosted_chunk_count_mean",
    "graph_closure_anchor_count_mean",
    "graph_closure_support_edge_count_mean",
    "topological_shield_attenuated_chunk_count_mean",
    "skills_selected_count_mean",
    "skills_token_budget_mean",
    "skills_token_budget_used_mean",
    "skills_skipped_for_budget_mean",
    "source_plan_graph_closure_bonus_candidate_count_mean",
    "source_plan_graph_closure_preferred_count_mean",
    "source_plan_focused_file_promoted_count_mean",
    "source_plan_packed_path_count_mean",
    *(metric for _, metric in STAGE_LATENCY_ORDER),
    *SLO_BUDGET_LIMIT_ORDER,
}


def normalize_metrics(raw: Any) -> dict[str, Any]:
    metrics = raw if isinstance(raw, dict) else {}
    normalized = dict(metrics)
    if "task_success_rate" not in normalized and "utility_rate" in normalized:
        normalized["task_success_rate"] = normalized["utility_rate"]
    if "utility_rate" not in normalized and "task_success_rate" in normalized:
        normalized["utility_rate"] = normalized["task_success_rate"]
    return normalized


def format_metric(name: str, value: Any, *, signed: bool = False) -> str:
    number = float(value or 0.0)
    if name in LATENCY_STYLE_METRICS:
        return f"{number:+.2f}" if signed else f"{number:.2f}"
    return f"{number:+.4f}" if signed else f"{number:.4f}"


def format_optional_metric(
    name: str,
    value: Any | None,
    *,
    signed: bool = False,
) -> str:
    if value is None:
        return "-"
    return format_metric(name, value, signed=signed)


def build_zero_metrics() -> dict[str, float]:
    return {metric: 0.0 for metric in ALL_METRIC_ORDER}


__all__ = [
    "ALL_METRIC_ORDER",
    "COMPARABLE_METRIC_ORDER",
    "LATENCY_STYLE_METRICS",
    "METRIC_ORDER",
    "SLO_BUDGET_LIMIT_ORDER",
    "SLO_SIGNAL_ORDER",
    "STAGE_LATENCY_ORDER",
    "build_zero_metrics",
    "format_metric",
    "format_optional_metric",
    "normalize_metrics",
]
