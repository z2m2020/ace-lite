"""Aggregate benchmark summary helpers."""

from __future__ import annotations

from statistics import mean, median
from typing import Any

from ace_lite.benchmark.report_metrics import (
    COMPARABLE_METRIC_ORDER,
    build_zero_metrics,
    normalize_metrics,
)
from ace_lite.benchmark.summary_common import PIPELINE_STAGE_ORDER, p95 as _p95
from ace_lite.benchmark.summary_quality import (
    build_chunk_stage_miss_summary as _build_chunk_stage_miss_summary_impl,
    build_comparison_lane_summary as _build_comparison_lane_summary_impl,
    build_decision_observability_summary as _build_decision_observability_summary_impl,
    build_evidence_insufficiency_summary as _build_evidence_insufficiency_summary_impl,
    build_slo_budget_summary as _build_slo_budget_summary_impl,
    build_stage_latency_summary as _build_stage_latency_summary_impl,
)
from ace_lite.benchmark.summary_router import (
    build_adaptive_router_arm_summary as _build_adaptive_router_arm_summary_impl,
    build_adaptive_router_observability_summary as _build_adaptive_router_observability_summary_impl,
    build_adaptive_router_pair_summary as _build_adaptive_router_pair_summary_impl,
)

def aggregate_metrics(case_results: list[dict[str, Any]]) -> dict[str, float]:
    if not case_results:
        return build_zero_metrics()

    recalls = [float(item.get("recall_hit", 0.0)) for item in case_results]
    hit_at_1_values = [float(item.get("hit_at_1", 0.0)) for item in case_results]
    reciprocal_ranks = [
        float(item.get("reciprocal_rank", 0.0)) for item in case_results
    ]
    precisions = [float(item.get("precision_at_k", 0.0)) for item in case_results]
    task_successes = [
        float(item.get("task_success_hit", item.get("utility_hit", 0.0)) or 0.0)
        for item in case_results
    ]
    utilities = [float(item.get("utility_hit", 0.0)) for item in case_results]
    noises = [float(item.get("noise_rate", 0.0)) for item in case_results]
    docs_enabled = [float(item.get("docs_enabled", 0.0)) for item in case_results]
    docs_hits = [float(item.get("docs_hit", 0.0)) for item in case_results]
    hint_injects = [float(item.get("hint_inject", 0.0)) for item in case_results]
    dependencies = [float(item.get("dependency_recall", 0.0)) for item in case_results]
    memory_latencies = [float(item.get("memory_latency_ms", 0.0)) for item in case_results]
    index_latencies = [float(item.get("index_latency_ms", 0.0)) for item in case_results]
    repomap_latencies = [float(item.get("repomap_latency_ms", 0.0)) for item in case_results]
    augment_latencies = [float(item.get("augment_latency_ms", 0.0)) for item in case_results]
    skills_latencies = [float(item.get("skills_latency_ms", 0.0)) for item in case_results]
    skills_route_latencies = [
        float(item.get("skills_route_latency_ms", 0.0)) for item in case_results
    ]
    skills_hydration_latencies = [
        float(item.get("skills_hydration_latency_ms", 0.0)) for item in case_results
    ]
    source_plan_latencies = [
        float(item.get("source_plan_latency_ms", 0.0)) for item in case_results
    ]
    latencies = sorted(float(item.get("latency_ms", 0.0)) for item in case_results)
    chunk_hits = [float(item.get("chunk_hit_at_k", 0.0)) for item in case_results]
    chunks_per_file = [float(item.get("chunks_per_file_mean", 0.0)) for item in case_results]
    chunk_budget = [float(item.get("chunk_budget_used", 0.0)) for item in case_results]
    chunk_contract_fallback_counts = [
        float(item.get("chunk_contract_fallback_count", 0.0))
        for item in case_results
    ]
    chunk_contract_skeleton_chunk_counts = [
        float(item.get("chunk_contract_skeleton_chunk_count", 0.0))
        for item in case_results
    ]
    chunk_contract_fallback_ratios = [
        float(item.get("chunk_contract_fallback_ratio", 0.0))
        for item in case_results
    ]
    chunk_contract_skeleton_ratios = [
        float(item.get("chunk_contract_skeleton_ratio", 0.0))
        for item in case_results
    ]
    unsupported_language_fallback_counts = [
        float(item.get("unsupported_language_fallback_count", 0.0))
        for item in case_results
    ]
    unsupported_language_fallback_ratios = [
        float(item.get("unsupported_language_fallback_ratio", 0.0))
        for item in case_results
    ]
    subgraph_payload_enabled = [
        float(item.get("subgraph_payload_enabled", 0.0)) for item in case_results
    ]
    subgraph_seed_path_counts = [
        float(item.get("subgraph_seed_path_count", 0.0)) for item in case_results
    ]
    subgraph_edge_type_counts = [
        float(item.get("subgraph_edge_type_count", 0.0)) for item in case_results
    ]
    subgraph_edge_total_counts = [
        float(item.get("subgraph_edge_total_count", 0.0)) for item in case_results
    ]
    robust_signature_counts = [
        float(item.get("robust_signature_count", 0.0)) for item in case_results
    ]
    robust_signature_coverage = [
        float(item.get("robust_signature_coverage_ratio", 0.0))
        for item in case_results
    ]
    graph_prior_chunk_counts = [
        float(item.get("graph_prior_chunk_count", 0.0)) for item in case_results
    ]
    graph_prior_coverage = [
        float(item.get("graph_prior_coverage_ratio", 0.0)) for item in case_results
    ]
    graph_prior_totals = [
        float(item.get("graph_prior_total", 0.0)) for item in case_results
    ]
    graph_seeded_chunk_counts = [
        float(item.get("graph_seeded_chunk_count", 0.0)) for item in case_results
    ]
    graph_transfer_counts = [
        float(item.get("graph_transfer_count", 0.0)) for item in case_results
    ]
    graph_hub_suppressed_chunk_counts = [
        float(item.get("graph_hub_suppressed_chunk_count", 0.0))
        for item in case_results
    ]
    graph_hub_penalty_totals = [
        float(item.get("graph_hub_penalty_total", 0.0)) for item in case_results
    ]
    graph_closure_enabled = [
        float(item.get("graph_closure_enabled", 0.0)) for item in case_results
    ]
    graph_closure_boosted_chunk_counts = [
        float(item.get("graph_closure_boosted_chunk_count", 0.0))
        for item in case_results
    ]
    graph_closure_coverage = [
        float(item.get("graph_closure_coverage_ratio", 0.0)) for item in case_results
    ]
    graph_closure_anchor_counts = [
        float(item.get("graph_closure_anchor_count", 0.0)) for item in case_results
    ]
    graph_closure_support_edge_counts = [
        float(item.get("graph_closure_support_edge_count", 0.0))
        for item in case_results
    ]
    graph_closure_totals = [
        float(item.get("graph_closure_total", 0.0)) for item in case_results
    ]
    topological_shield_enabled = [
        float(item.get("topological_shield_enabled", 0.0)) for item in case_results
    ]
    topological_shield_report_only = [
        float(item.get("topological_shield_report_only", 0.0))
        for item in case_results
    ]
    topological_shield_attenuated_chunk_counts = [
        float(item.get("topological_shield_attenuated_chunk_count", 0.0))
        for item in case_results
    ]
    topological_shield_coverage = [
        float(item.get("topological_shield_coverage_ratio", 0.0))
        for item in case_results
    ]
    topological_shield_attenuation_totals = [
        float(item.get("topological_shield_attenuation_total", 0.0))
        for item in case_results
    ]
    chunk_guard_enabled = [
        float(item.get("chunk_guard_enabled", 0.0)) for item in case_results
    ]
    chunk_guard_report_only = [
        float(item.get("chunk_guard_report_only", 0.0)) for item in case_results
    ]
    chunk_guard_filtered_counts = [
        float(item.get("chunk_guard_filtered_count", 0.0)) for item in case_results
    ]
    chunk_guard_filter_ratios = [
        float(item.get("chunk_guard_filter_ratio", 0.0)) for item in case_results
    ]
    chunk_guard_pairwise_conflict_counts = [
        float(item.get("chunk_guard_pairwise_conflict_count", 0.0))
        for item in case_results
    ]
    chunk_guard_fallbacks = [
        float(item.get("chunk_guard_fallback", 0.0)) for item in case_results
    ]
    skills_selected_counts = [
        float(item.get("skills_selected_count", 0.0)) for item in case_results
    ]
    skills_token_budgets = [
        float(item.get("skills_token_budget", 0.0)) for item in case_results
    ]
    skills_token_budget_used = [
        float(item.get("skills_token_budget_used", 0.0)) for item in case_results
    ]
    skills_budget_exhausted = [
        float(item.get("skills_budget_exhausted", 0.0)) for item in case_results
    ]
    skills_skipped_for_budget = [
        float(item.get("skills_skipped_for_budget_count", 0.0))
        for item in case_results
    ]
    skills_metadata_only_routing = [
        float(item.get("skills_metadata_only_routing", 0.0)) for item in case_results
    ]
    skills_precomputed_route = [
        float(item.get("skills_precomputed_route", 0.0)) for item in case_results
    ]
    plan_replay_cache_enabled = [
        float(item.get("plan_replay_cache_enabled", 0.0)) for item in case_results
    ]
    plan_replay_cache_hits = [
        float(item.get("plan_replay_cache_hit", 0.0)) for item in case_results
    ]
    plan_replay_cache_stale_hit_safe = [
        float(item.get("plan_replay_cache_stale_hit_safe", 0.0))
        for item in case_results
    ]
    validation_counts = [float(item.get("validation_test_count", 0.0)) for item in case_results]
    source_plan_direct_ratios = [
        float(item.get("source_plan_direct_evidence_ratio", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_neighbor_context_ratios = [
        float(item.get("source_plan_neighbor_context_ratio", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_hint_only_ratios = [
        float(item.get("source_plan_hint_only_ratio", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_graph_closure_preference_enabled = [
        float(item.get("source_plan_graph_closure_preference_enabled", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_graph_closure_bonus_candidate_counts = [
        float(item.get("source_plan_graph_closure_bonus_candidate_count", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_graph_closure_preferred_counts = [
        float(item.get("source_plan_graph_closure_preferred_count", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_focused_file_promoted_counts = [
        float(item.get("source_plan_focused_file_promoted_count", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_packed_path_counts = [
        float(item.get("source_plan_packed_path_count", 0.0) or 0.0)
        for item in case_results
    ]
    evidence_insufficient = [
        float(item.get("evidence_insufficient", 0.0)) for item in case_results
    ]
    no_candidate = [
        float(item.get("evidence_no_candidate", 0.0)) for item in case_results
    ]
    low_support_chunks = [
        float(item.get("evidence_low_support_chunk", 0.0))
        for item in case_results
    ]
    missing_validation = [
        float(item.get("evidence_missing_validation", 0.0))
        for item in case_results
    ]
    budget_limited = [
        float(item.get("evidence_budget_limited", 0.0)) for item in case_results
    ]
    noisy_hits = [
        float(item.get("evidence_noisy_hit", 0.0)) for item in case_results
    ]
    notes_hit_ratios = [float(item.get("notes_hit_ratio", 0.0)) for item in case_results]
    profile_selected_counts = [float(item.get("profile_selected_count", 0.0)) for item in case_results]
    capture_triggered = [float(item.get("capture_triggered", 0.0)) for item in case_results]
    embedding_enabled = [float(item.get("embedding_enabled", 0.0)) for item in case_results]
    embedding_similarity_means = [
        float(item.get("embedding_similarity_mean", 0.0)) for item in case_results
    ]
    embedding_similarity_maxes = [
        float(item.get("embedding_similarity_max", 0.0)) for item in case_results
    ]
    embedding_rerank_ratios = [
        float(item.get("embedding_rerank_ratio", 0.0)) for item in case_results
    ]
    embedding_cache_hits = [
        float(item.get("embedding_cache_hit", 0.0)) for item in case_results
    ]
    embedding_fallbacks = [
        float(item.get("embedding_fallback", 0.0)) for item in case_results
    ]
    parallel_time_budgets = [
        float(item.get("parallel_time_budget_ms", 0.0)) for item in case_results
    ]
    embedding_time_budgets = [
        float(item.get("embedding_time_budget_ms", 0.0)) for item in case_results
    ]
    chunk_semantic_time_budgets = [
        float(item.get("chunk_semantic_time_budget_ms", 0.0))
        for item in case_results
    ]
    xref_time_budgets = [
        float(item.get("xref_time_budget_ms", 0.0)) for item in case_results
    ]
    parallel_docs_timeouts = [
        float(item.get("parallel_docs_timed_out", 0.0)) for item in case_results
    ]
    parallel_worktree_timeouts = [
        float(item.get("parallel_worktree_timed_out", 0.0)) for item in case_results
    ]
    embedding_budget_exceeded = [
        float(item.get("embedding_time_budget_exceeded", 0.0))
        for item in case_results
    ]
    embedding_adaptive_budget = [
        float(item.get("embedding_adaptive_budget_applied", 0.0))
        for item in case_results
    ]
    chunk_semantic_budget_exceeded = [
        float(item.get("chunk_semantic_time_budget_exceeded", 0.0))
        for item in case_results
    ]
    chunk_semantic_fallbacks = [
        float(item.get("chunk_semantic_fallback", 0.0)) for item in case_results
    ]
    xref_budget_exhausted = [
        float(item.get("xref_budget_exhausted", 0.0)) for item in case_results
    ]
    slo_downgrades = [
        float(item.get("slo_downgrade_triggered", 0.0)) for item in case_results
    ]

    p95 = _p95(latencies)
    latency_median = float(median(latencies))
    repomap_p95 = _p95(repomap_latencies)
    repomap_median = float(median(repomap_latencies))

    return {
        "recall_at_k": mean(recalls),
        "hit_at_1": mean(hit_at_1_values),
        "mrr": mean(reciprocal_ranks),
        "precision_at_k": mean(precisions),
        "task_success_rate": mean(task_successes),
        "utility_rate": mean(utilities),
        "noise_rate": mean(noises),
        "docs_enabled_ratio": mean(docs_enabled),
        "docs_hit_ratio": mean(docs_hits),
        "hint_inject_ratio": mean(hint_injects),
        "dependency_recall": mean(dependencies),
        "memory_latency_p95_ms": _p95(memory_latencies),
        "index_latency_p95_ms": _p95(index_latencies),
        "repomap_latency_p95_ms": repomap_p95,
        "augment_latency_p95_ms": _p95(augment_latencies),
        "skills_latency_p95_ms": _p95(skills_latencies),
        "skills_route_latency_p95_ms": _p95(skills_route_latencies),
        "skills_hydration_latency_p95_ms": _p95(skills_hydration_latencies),
        "source_plan_latency_p95_ms": _p95(source_plan_latencies),
        "repomap_latency_median_ms": repomap_median,
        "latency_p95_ms": p95,
        "latency_median_ms": latency_median,
        "chunk_hit_at_k": mean(chunk_hits),
        "chunks_per_file_mean": mean(chunks_per_file),
        "chunk_budget_used": mean(chunk_budget),
        "chunk_contract_fallback_count_mean": mean(
            chunk_contract_fallback_counts
        ),
        "chunk_contract_skeleton_chunk_count_mean": mean(
            chunk_contract_skeleton_chunk_counts
        ),
        "chunk_contract_fallback_ratio": mean(chunk_contract_fallback_ratios),
        "chunk_contract_skeleton_ratio": mean(chunk_contract_skeleton_ratios),
        "unsupported_language_fallback_count_mean": mean(
            unsupported_language_fallback_counts
        ),
        "unsupported_language_fallback_ratio": mean(
            unsupported_language_fallback_ratios
        ),
        "subgraph_payload_enabled_ratio": mean(subgraph_payload_enabled),
        "subgraph_seed_path_count_mean": mean(subgraph_seed_path_counts),
        "subgraph_edge_type_count_mean": mean(subgraph_edge_type_counts),
        "subgraph_edge_total_count_mean": mean(subgraph_edge_total_counts),
        "robust_signature_count_mean": mean(robust_signature_counts),
        "robust_signature_coverage_ratio": mean(robust_signature_coverage),
        "graph_prior_chunk_count_mean": mean(graph_prior_chunk_counts),
        "graph_prior_coverage_ratio": mean(graph_prior_coverage),
        "graph_prior_total_mean": mean(graph_prior_totals),
        "graph_seeded_chunk_count_mean": mean(graph_seeded_chunk_counts),
        "graph_transfer_count_mean": mean(graph_transfer_counts),
        "graph_hub_suppressed_chunk_count_mean": mean(
            graph_hub_suppressed_chunk_counts
        ),
        "graph_hub_penalty_total_mean": mean(graph_hub_penalty_totals),
        "graph_closure_enabled_ratio": mean(graph_closure_enabled),
        "graph_closure_boosted_chunk_count_mean": mean(
            graph_closure_boosted_chunk_counts
        ),
        "graph_closure_coverage_ratio": mean(graph_closure_coverage),
        "graph_closure_anchor_count_mean": mean(graph_closure_anchor_counts),
        "graph_closure_support_edge_count_mean": mean(
            graph_closure_support_edge_counts
        ),
        "graph_closure_total_mean": mean(graph_closure_totals),
        "topological_shield_enabled_ratio": mean(topological_shield_enabled),
        "topological_shield_report_only_ratio": mean(
            topological_shield_report_only
        ),
        "topological_shield_attenuated_chunk_count_mean": mean(
            topological_shield_attenuated_chunk_counts
        ),
        "topological_shield_coverage_ratio": mean(topological_shield_coverage),
        "topological_shield_attenuation_total_mean": mean(
            topological_shield_attenuation_totals
        ),
        "chunk_guard_enabled_ratio": mean(chunk_guard_enabled),
        "chunk_guard_report_only_ratio": mean(chunk_guard_report_only),
        "chunk_guard_filtered_count_mean": mean(chunk_guard_filtered_counts),
        "chunk_guard_filter_ratio": mean(chunk_guard_filter_ratios),
        "chunk_guard_pairwise_conflict_count_mean": mean(
            chunk_guard_pairwise_conflict_counts
        ),
        "chunk_guard_fallback_ratio": mean(chunk_guard_fallbacks),
        "skills_selected_count_mean": mean(skills_selected_counts),
        "skills_token_budget_mean": mean(skills_token_budgets),
        "skills_token_budget_used_mean": mean(skills_token_budget_used),
        "skills_budget_exhausted_ratio": mean(skills_budget_exhausted),
        "skills_skipped_for_budget_mean": mean(skills_skipped_for_budget),
        "skills_metadata_only_routing_ratio": mean(skills_metadata_only_routing),
        "skills_precomputed_route_ratio": mean(skills_precomputed_route),
        "plan_replay_cache_enabled_ratio": mean(plan_replay_cache_enabled),
        "plan_replay_cache_hit_ratio": mean(plan_replay_cache_hits),
        "plan_replay_cache_stale_hit_safe_ratio": mean(
            plan_replay_cache_stale_hit_safe
        ),
        "validation_test_count": mean(validation_counts),
        "source_plan_direct_evidence_ratio": mean(source_plan_direct_ratios),
        "source_plan_neighbor_context_ratio": mean(
            source_plan_neighbor_context_ratios
        ),
        "source_plan_hint_only_ratio": mean(source_plan_hint_only_ratios),
        "source_plan_graph_closure_preference_enabled_ratio": mean(
            source_plan_graph_closure_preference_enabled
        ),
        "source_plan_graph_closure_bonus_candidate_count_mean": mean(
            source_plan_graph_closure_bonus_candidate_counts
        ),
        "source_plan_graph_closure_preferred_count_mean": mean(
            source_plan_graph_closure_preferred_counts
        ),
        "source_plan_focused_file_promoted_count_mean": mean(
            source_plan_focused_file_promoted_counts
        ),
        "source_plan_packed_path_count_mean": mean(source_plan_packed_path_counts),
        "evidence_insufficient_rate": mean(evidence_insufficient),
        "no_candidate_rate": mean(no_candidate),
        "low_support_chunk_rate": mean(low_support_chunks),
        "missing_validation_rate": mean(missing_validation),
        "budget_limited_recovery_rate": mean(budget_limited),
        "noisy_hit_rate": mean(noisy_hits),
        "notes_hit_ratio": mean(notes_hit_ratios),
        "profile_selected_mean": mean(profile_selected_counts),
        "capture_trigger_ratio": mean(capture_triggered),
        "embedding_enabled_ratio": mean(embedding_enabled),
        "embedding_similarity_mean": mean(embedding_similarity_means),
        "embedding_similarity_max": mean(embedding_similarity_maxes),
        "embedding_rerank_ratio": mean(embedding_rerank_ratios),
        "embedding_cache_hit_ratio": mean(embedding_cache_hits),
        "embedding_fallback_ratio": mean(embedding_fallbacks),
        "parallel_time_budget_ms_mean": mean(parallel_time_budgets),
        "embedding_time_budget_ms_mean": mean(embedding_time_budgets),
        "chunk_semantic_time_budget_ms_mean": mean(chunk_semantic_time_budgets),
        "xref_time_budget_ms_mean": mean(xref_time_budgets),
        "parallel_docs_timeout_ratio": mean(parallel_docs_timeouts),
        "parallel_worktree_timeout_ratio": mean(parallel_worktree_timeouts),
        "embedding_time_budget_exceeded_ratio": mean(embedding_budget_exceeded),
        "embedding_adaptive_budget_ratio": mean(embedding_adaptive_budget),
        "chunk_semantic_time_budget_exceeded_ratio": mean(
            chunk_semantic_budget_exceeded
        ),
        "chunk_semantic_fallback_ratio": mean(chunk_semantic_fallbacks),
        "xref_budget_exhausted_ratio": mean(xref_budget_exhausted),
        "slo_downgrade_case_rate": mean(slo_downgrades),
    }


def compare_metrics(
    *,
    current: dict[str, float],
    baseline: dict[str, float],
) -> dict[str, float]:
    current_metrics = normalize_metrics(current)
    baseline_metrics = normalize_metrics(baseline)
    return {
        metric: float(current_metrics.get(metric, 0.0) or 0.0)
        - float(baseline_metrics.get(metric, 0.0) or 0.0)
        for metric in COMPARABLE_METRIC_ORDER
    }


def build_evidence_insufficiency_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_evidence_insufficiency_summary_impl(case_results)


def build_chunk_stage_miss_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_chunk_stage_miss_summary_impl(case_results)


def build_decision_observability_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_decision_observability_summary_impl(case_results)


def build_adaptive_router_arm_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_adaptive_router_arm_summary_impl(case_results)


def build_adaptive_router_pair_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_adaptive_router_pair_summary_impl(case_results)


def build_adaptive_router_observability_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_adaptive_router_observability_summary_impl(case_results)


def build_comparison_lane_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    return _build_comparison_lane_summary_impl(case_results)


def build_stage_latency_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    return _build_stage_latency_summary_impl(case_results)


def build_slo_budget_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    return _build_slo_budget_summary_impl(case_results)

__all__ = [
    "PIPELINE_STAGE_ORDER",
    "aggregate_metrics",
    "build_adaptive_router_arm_summary",
    "build_adaptive_router_observability_summary",
    "build_adaptive_router_pair_summary",
    "build_chunk_stage_miss_summary",
    "build_decision_observability_summary",
    "build_evidence_insufficiency_summary",
    "build_slo_budget_summary",
    "build_stage_latency_summary",
    "compare_metrics",
]
