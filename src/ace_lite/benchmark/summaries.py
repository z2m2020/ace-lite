"""Aggregate benchmark summary helpers."""

from __future__ import annotations

from statistics import mean, median
from typing import Any

from ace_lite.benchmark.report_metrics import (
    COMPARABLE_METRIC_ORDER,
    build_zero_metrics,
    normalize_metrics,
)
from ace_lite.benchmark.summary_common import PIPELINE_STAGE_ORDER
from ace_lite.benchmark.summary_common import p95 as _p95
from ace_lite.benchmark.summary_quality import (
    build_agent_loop_control_plane_summary as _build_agent_loop_control_plane_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_chunk_stage_miss_summary as _build_chunk_stage_miss_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_comparison_lane_summary as _build_comparison_lane_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_context_refine_summary as _build_context_refine_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_decision_observability_summary as _build_decision_observability_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_evidence_insufficiency_summary as _build_evidence_insufficiency_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_feedback_loop_summary as _build_feedback_loop_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_feedback_observability_summary as _build_feedback_observability_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_missing_context_risk_summary as _build_missing_context_risk_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_preference_observability_summary as _build_preference_observability_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_retrieval_context_observability_summary as _build_retrieval_context_observability_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_retrieval_default_strategy_summary as _build_retrieval_default_strategy_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_slo_budget_summary as _build_slo_budget_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_stage_latency_summary as _build_stage_latency_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    build_wave1_context_governance_summary as _build_wave1_context_governance_summary_impl,
)
from ace_lite.benchmark.summary_quality import (
    is_risk_upgrade_case as _is_risk_upgrade_case_impl,
)
from ace_lite.benchmark.summary_quality import (
    summarize_missing_context_risk_case as _summarize_missing_context_risk_case_impl,
)
from ace_lite.benchmark.summary_router import (
    build_adaptive_router_arm_summary as _build_adaptive_router_arm_summary_impl,
)
from ace_lite.benchmark.summary_router import (
    build_adaptive_router_observability_summary as _build_adaptive_router_observability_summary_impl,
)
from ace_lite.benchmark.summary_router import (
    build_adaptive_router_pair_summary as _build_adaptive_router_pair_summary_impl,
)
from ace_lite.benchmark.summary_router import (
    build_learning_router_rollout_summary as _build_learning_router_rollout_summary_impl,
)

RETRIEVAL_CONTROL_PLANE_LATENCY_P95_THRESHOLD_MS = 650.0


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
    repomap_worktree_seed_counts = [
        float(item.get("repomap_worktree_seed_count", 0.0)) for item in case_results
    ]
    repomap_subgraph_seed_counts = [
        float(item.get("repomap_subgraph_seed_count", 0.0)) for item in case_results
    ]
    repomap_seed_candidates_counts = [
        float(item.get("repomap_seed_candidates_count", 0.0))
        for item in case_results
    ]
    repomap_cache_hits = [
        float(item.get("repomap_cache_hit", 0.0)) for item in case_results
    ]
    repomap_precompute_hits = [
        float(item.get("repomap_precompute_hit", 0.0)) for item in case_results
    ]
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
    retrieval_context_chunk_counts = [
        float(item.get("retrieval_context_chunk_count", 0.0)) for item in case_results
    ]
    retrieval_context_coverage = [
        float(item.get("retrieval_context_coverage_ratio", 0.0))
        for item in case_results
    ]
    retrieval_context_char_counts = [
        float(item.get("retrieval_context_char_count_mean", 0.0))
        for item in case_results
    ]
    contextual_sidecar_parent_symbol_chunk_counts = [
        float(item.get("contextual_sidecar_parent_symbol_chunk_count", 0.0))
        for item in case_results
    ]
    contextual_sidecar_parent_symbol_coverage = [
        float(item.get("contextual_sidecar_parent_symbol_coverage_ratio", 0.0))
        for item in case_results
    ]
    contextual_sidecar_reference_hint_chunk_counts = [
        float(item.get("contextual_sidecar_reference_hint_chunk_count", 0.0))
        for item in case_results
    ]
    contextual_sidecar_reference_hint_coverage = [
        float(item.get("contextual_sidecar_reference_hint_coverage_ratio", 0.0))
        for item in case_results
    ]
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
    chunk_cache_contract_present = [
        float(item.get("chunk_cache_contract_present", 0.0))
        for item in case_results
    ]
    chunk_cache_contract_fingerprint_present = [
        float(item.get("chunk_cache_contract_fingerprint_present", 0.0))
        for item in case_results
    ]
    chunk_cache_contract_metadata_aligned = [
        float(item.get("chunk_cache_contract_metadata_aligned", 0.0))
        for item in case_results
    ]
    chunk_cache_contract_file_counts = [
        float(item.get("chunk_cache_contract_file_count", 0.0))
        for item in case_results
    ]
    chunk_cache_contract_chunk_counts = [
        float(item.get("chunk_cache_contract_chunk_count", 0.0))
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
    graph_source_provider_loaded = [
        float(item.get("graph_source_provider_loaded", 0.0) or 0.0)
        for item in case_results
    ]
    graph_source_projection_fallback = [
        float(item.get("graph_source_projection_fallback", 0.0) or 0.0)
        for item in case_results
    ]
    graph_source_edge_counts = [
        float(item.get("graph_source_edge_count", 0.0) or 0.0)
        for item in case_results
    ]
    graph_source_inbound_signal_chunk_counts = [
        float(item.get("graph_source_inbound_signal_chunk_count", 0.0) or 0.0)
        for item in case_results
    ]
    graph_source_inbound_signal_coverage = [
        float(item.get("graph_source_inbound_signal_coverage_ratio", 0.0) or 0.0)
        for item in case_results
    ]
    graph_source_centrality_signal_chunk_counts = [
        float(item.get("graph_source_centrality_signal_chunk_count", 0.0) or 0.0)
        for item in case_results
    ]
    graph_source_centrality_signal_coverage = [
        float(
            item.get("graph_source_centrality_signal_coverage_ratio", 0.0) or 0.0
        )
        for item in case_results
    ]
    graph_source_pagerank_signal_chunk_counts = [
        float(item.get("graph_source_pagerank_signal_chunk_count", 0.0) or 0.0)
        for item in case_results
    ]
    graph_source_pagerank_signal_coverage = [
        float(item.get("graph_source_pagerank_signal_coverage_ratio", 0.0) or 0.0)
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
    candidate_rows_materialized_counts = [
        float(item.get("candidate_rows_materialized_count", 0.0) or 0.0)
        for item in case_results
    ]
    candidate_chunks_materialized_counts = [
        float(item.get("candidate_chunks_materialized_count", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_candidate_chunks_materialized_counts = [
        float(item.get("source_plan_candidate_chunks_materialized_count", 0.0) or 0.0)
        for item in case_results
    ]
    skills_markdown_bytes_loaded = [
        float(item.get("skills_markdown_bytes_loaded", 0.0) or 0.0)
        for item in case_results
    ]
    budget_abort_cases = [
        float(item.get("budget_abort", 0.0) or 0.0) for item in case_results
    ]
    fallback_taken_cases = [
        float(item.get("fallback_taken", 0.0) or 0.0) for item in case_results
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
    adaptive_router_enabled_cases = [
        item
        for item in case_results
        if float(item.get("router_enabled", 0.0) or 0.0) > 0.0
    ]
    adaptive_router_shadow_cases = [
        item
        for item in adaptive_router_enabled_cases
        if str(item.get("router_shadow_arm_id") or "").strip()
    ]
    elevated_risk_cases = [
        item
        for item in case_results
        if isinstance(item, dict)
        and _summarize_missing_context_risk_case_impl(item)[0]
        and _summarize_missing_context_risk_case_impl(item)[2] in {"elevated", "high"}
    ]
    risk_upgrade_cases = [
        item for item in elevated_risk_cases if _is_risk_upgrade_case_impl(item)
    ]
    risk_baseline_cases = [
        item for item in elevated_risk_cases if not _is_risk_upgrade_case_impl(item)
    ]
    validation_counts = [float(item.get("validation_test_count", 0.0)) for item in case_results]
    validation_probe_enabled = [
        float(item.get("validation_probe_enabled", 0.0) or 0.0)
        for item in case_results
    ]
    validation_probe_executed_counts = [
        float(item.get("validation_probe_executed_count", 0.0) or 0.0)
        for item in case_results
    ]
    validation_probe_failed = [
        float(item.get("validation_probe_failed", 0.0) or 0.0)
        for item in case_results
    ]
    validation_branch_cases = [
        item
        for item in case_results
        if float(item.get("validation_branch_case", 0.0) or 0.0) > 0.0
    ]
    validation_branch_case_flags = [
        float(item.get("validation_branch_case", 0.0) or 0.0) for item in case_results
    ]
    validation_branch_candidate_counts = [
        float(item.get("validation_branch_candidate_count", 0.0) or 0.0)
        for item in validation_branch_cases
    ]
    validation_branch_rejected_counts = [
        float(item.get("validation_branch_rejected_count", 0.0) or 0.0)
        for item in validation_branch_cases
    ]
    validation_branch_selection_present = [
        float(item.get("validation_branch_selection_present", 0.0) or 0.0)
        for item in validation_branch_cases
    ]
    validation_branch_patch_artifact_present = [
        float(item.get("validation_branch_patch_artifact_present", 0.0) or 0.0)
        for item in validation_branch_cases
    ]
    validation_branch_archive_present = [
        float(item.get("validation_branch_archive_present", 0.0) or 0.0)
        for item in validation_branch_cases
    ]
    validation_branch_parallel = [
        float(item.get("validation_branch_parallel", 0.0) or 0.0)
        for item in validation_branch_cases
    ]
    validation_branch_winner_passed = [
        float(item.get("validation_branch_winner_passed", 0.0) or 0.0)
        for item in validation_branch_cases
    ]
    validation_branch_winner_regressed = [
        float(item.get("validation_branch_winner_regressed", 0.0) or 0.0)
        for item in validation_branch_cases
    ]
    validation_branch_winner_scores = [
        float(item.get("validation_branch_winner_score", 0.0) or 0.0)
        for item in validation_branch_cases
    ]
    validation_branch_winner_after_issue_counts = [
        float(item.get("validation_branch_winner_after_issue_count", 0.0) or 0.0)
        for item in validation_branch_cases
    ]
    source_plan_validation_feedback_present = [
        float(item.get("source_plan_validation_feedback_present", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_validation_feedback_issue_counts = [
        float(item.get("source_plan_validation_feedback_issue_count", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_validation_feedback_failed = [
        float(item.get("source_plan_validation_feedback_failed", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_validation_feedback_probe_issue_counts = [
        float(
            item.get("source_plan_validation_feedback_probe_issue_count", 0.0)
            or 0.0
        )
        for item in case_results
    ]
    source_plan_validation_feedback_probe_executed_counts = [
        float(
            item.get("source_plan_validation_feedback_probe_executed_count", 0.0)
            or 0.0
        )
        for item in case_results
    ]
    source_plan_validation_feedback_probe_failed = [
        float(item.get("source_plan_validation_feedback_probe_failed", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_validation_feedback_selected_test_counts = [
        float(
            item.get("source_plan_validation_feedback_selected_test_count", 0.0)
            or 0.0
        )
        for item in case_results
    ]
    source_plan_validation_feedback_executed_test_counts = [
        float(
            item.get("source_plan_validation_feedback_executed_test_count", 0.0)
            or 0.0
        )
        for item in case_results
    ]
    source_plan_failure_signal_present = [
        float(item.get("source_plan_failure_signal_present", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_failure_signal_issue_counts = [
        float(item.get("source_plan_failure_signal_issue_count", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_failure_signal_failed = [
        float(item.get("source_plan_failure_signal_failed", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_failure_signal_probe_issue_counts = [
        float(
            item.get("source_plan_failure_signal_probe_issue_count", 0.0)
            or 0.0
        )
        for item in case_results
    ]
    source_plan_failure_signal_probe_executed_counts = [
        float(
            item.get("source_plan_failure_signal_probe_executed_count", 0.0)
            or 0.0
        )
        for item in case_results
    ]
    source_plan_failure_signal_probe_failed = [
        float(item.get("source_plan_failure_signal_probe_failed", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_failure_signal_selected_test_counts = [
        float(
            item.get("source_plan_failure_signal_selected_test_count", 0.0)
            or 0.0
        )
        for item in case_results
    ]
    source_plan_failure_signal_executed_test_counts = [
        float(
            item.get("source_plan_failure_signal_executed_test_count", 0.0)
            or 0.0
        )
        for item in case_results
    ]
    source_plan_failure_signal_replay_cache_origin = [
        1.0
        if str(item.get("source_plan_failure_signal_origin") or "").strip()
        == "plan_replay_cache"
        else 0.0
        for item in case_results
    ]
    source_plan_failure_signal_observability_origin = [
        1.0
        if str(item.get("source_plan_failure_signal_origin") or "").strip()
        == "observability"
        else 0.0
        for item in case_results
    ]
    source_plan_failure_signal_source_plan_origin = [
        1.0
        if str(item.get("source_plan_failure_signal_origin") or "").strip()
        == "source_plan"
        else 0.0
        for item in case_results
    ]
    source_plan_failure_signal_validate_step_origin = [
        1.0
        if str(item.get("source_plan_failure_signal_origin") or "").strip()
        == "validate_step"
        else 0.0
        for item in case_results
    ]
    source_plan_evidence_card_counts = [
        float(item.get("source_plan_evidence_card_count", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_file_card_counts = [
        float(item.get("source_plan_file_card_count", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_chunk_card_counts = [
        float(item.get("source_plan_chunk_card_count", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_validation_card_present = [
        float(item.get("source_plan_validation_card_present", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_direct_ratios = [
        float(item.get("source_plan_direct_evidence_ratio", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_symbol_counts = [
        float(item.get("source_plan_symbol_count", 0.0) or 0.0) for item in case_results
    ]
    source_plan_signature_counts = [
        float(item.get("source_plan_signature_count", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_skeleton_counts = [
        float(item.get("source_plan_skeleton_count", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_robust_signature_counts = [
        float(item.get("source_plan_robust_signature_count", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_symbol_ratios = [
        float(item.get("source_plan_symbol_ratio", 0.0) or 0.0) for item in case_results
    ]
    source_plan_signature_ratios = [
        float(item.get("source_plan_signature_ratio", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_skeleton_ratios = [
        float(item.get("source_plan_skeleton_ratio", 0.0) or 0.0)
        for item in case_results
    ]
    source_plan_robust_signature_ratios = [
        float(item.get("source_plan_robust_signature_ratio", 0.0) or 0.0)
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
    source_plan_granularity_preferred_counts = [
        float(item.get("source_plan_granularity_preferred_count", 0.0) or 0.0)
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
    memory_helpful_cases = [
        item
        for item in case_results
        if str(item.get("comparison_lane") or "").strip() == "memory-helpful"
    ]
    memory_helpful_task_success_hits = [
        float(item.get("task_success_hit", item.get("utility_hit", 0.0)) or 0.0)
        for item in memory_helpful_cases
    ]
    ltm_hit_cases = [
        item
        for item in memory_helpful_cases
        if float(item.get("ltm_plan_constraint_count", 0.0) or 0.0) > 0.0
    ]
    ltm_latency_cases = [
        float(item.get("memory_latency_ms", 0.0) or 0.0)
        for item in case_results
        if float(item.get("ltm_plan_constraint_count", 0.0) or 0.0) > 0.0
    ]
    non_ltm_latency_cases = [
        float(item.get("memory_latency_ms", 0.0) or 0.0)
        for item in case_results
        if float(item.get("ltm_plan_constraint_count", 0.0) or 0.0) <= 0.0
    ]
    ltm_effective_hit_cases = [
        item
        for item in ltm_hit_cases
        if float(item.get("task_success_hit", item.get("utility_hit", 0.0)) or 0.0)
        > 0.0
    ]
    memory_harmful_negative_control_cases = [
        item
        for item in case_results
        if str(item.get("comparison_lane") or "").strip()
        == "memory-harmful-negative-control"
    ]
    ltm_false_help_cases = [
        item
        for item in memory_harmful_negative_control_cases
        if float(item.get("ltm_plan_constraint_count", 0.0) or 0.0) > 0.0
    ]
    time_sensitive_cases = [
        item
        for item in case_results
        if str(item.get("comparison_lane") or "").strip() == "time-sensitive"
    ]
    ltm_stale_hit_cases = [
        item
        for item in time_sensitive_cases
        if float(item.get("ltm_plan_constraint_count", 0.0) or 0.0) > 0.0
        and float(item.get("task_success_hit", item.get("utility_hit", 0.0)) or 0.0)
        <= 0.0
    ]
    ltm_time_sensitive_hit_cases = [
        item
        for item in time_sensitive_cases
        if float(item.get("ltm_plan_constraint_count", 0.0) or 0.0) > 0.0
    ]
    ltm_replay_drift_cases = [
        item
        for item in ltm_time_sensitive_hit_cases
        if float(item.get("plan_replay_cache_stale_hit_safe", 1.0) or 0.0) <= 0.0
    ]
    issue_report_feedback_cases = [
        item
        for item in case_results
        if str(item.get("comparison_lane") or "").strip() == "issue_report_feedback"
    ]
    issue_report_linked_cases = [
        item
        for item in issue_report_feedback_cases
        if str(item.get("issue_report_issue_id") or "").strip()
    ]
    issue_report_linked_plan_cases = [
        item
        for item in issue_report_linked_cases
        if float(item.get("issue_report_has_plan_ref", 0.0) or 0.0) > 0.0
    ]
    issue_report_time_to_fix_hours = [
        float(item.get("issue_report_time_to_fix_hours", 0.0) or 0.0)
        for item in issue_report_feedback_cases
        if float(item.get("issue_report_time_to_fix_hours", 0.0) or 0.0) > 0.0
    ]
    dev_feedback_resolution_cases = [
        item
        for item in case_results
        if str(item.get("comparison_lane") or "").strip() == "dev_feedback_resolution"
    ]
    dev_issue_capture_cases = [
        item
        for item in case_results
        if str(item.get("comparison_lane") or "").strip() == "dev_issue_capture"
    ]
    dev_issue_captured_cases = [
        item
        for item in dev_issue_capture_cases
        if float(item.get("dev_feedback_issue_count", 0.0) or 0.0) > 0.0
    ]
    dev_feedback_resolution_hits = [
        float(item.get("task_success_hit", item.get("utility_hit", 0.0)) or 0.0)
        for item in dev_feedback_resolution_cases
    ]
    dev_feedback_issue_count = sum(
        float(item.get("dev_feedback_issue_count", 0.0) or 0.0)
        for item in dev_feedback_resolution_cases
    )
    dev_feedback_linked_fix_issue_count = sum(
        float(item.get("dev_feedback_linked_fix_issue_count", 0.0) or 0.0)
        for item in dev_feedback_resolution_cases
    )
    embedding_enabled = [float(item.get("embedding_enabled", 0.0)) for item in case_results]
    multi_channel_rrf_enabled = [
        float(item.get("multi_channel_rrf_enabled", 0.0) or 0.0)
        for item in case_results
    ]
    multi_channel_rrf_applied = [
        float(item.get("multi_channel_rrf_applied", 0.0) or 0.0)
        for item in case_results
    ]
    multi_channel_rrf_granularity_counts = [
        float(item.get("multi_channel_rrf_granularity_count", 0.0) or 0.0)
        for item in case_results
    ]
    multi_channel_rrf_pool_sizes = [
        float(item.get("multi_channel_rrf_pool_size", 0.0) or 0.0)
        for item in case_results
    ]
    multi_channel_rrf_granularity_pool_ratios = [
        float(item.get("multi_channel_rrf_granularity_pool_ratio", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_enabled = [
        float(item.get("graph_lookup_enabled", 0.0) or 0.0) for item in case_results
    ]
    graph_lookup_guarded = [
        float(item.get("graph_lookup_guarded", 0.0) or 0.0) for item in case_results
    ]
    graph_lookup_boosted_counts = [
        float(item.get("graph_lookup_boosted_count", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_weight_scip = [
        float(item.get("graph_lookup_weight_scip", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_weight_xref = [
        float(item.get("graph_lookup_weight_xref", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_weight_query_xref = [
        float(item.get("graph_lookup_weight_query_xref", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_weight_symbol = [
        float(item.get("graph_lookup_weight_symbol", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_weight_import = [
        float(item.get("graph_lookup_weight_import", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_weight_coverage = [
        float(item.get("graph_lookup_weight_coverage", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_candidate_counts = [
        float(item.get("graph_lookup_candidate_count", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_normalizations = [
        str(item.get("graph_lookup_normalization", "") or "").strip()
        for item in case_results
    ]
    graph_lookup_pool_sizes = [
        float(item.get("graph_lookup_pool_size", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_query_terms_counts = [
        float(item.get("graph_lookup_query_terms_count", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_guard_max_candidates = [
        float(item.get("graph_lookup_guard_max_candidates", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_guard_min_query_terms = [
        float(item.get("graph_lookup_guard_min_query_terms", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_guard_max_query_terms = [
        float(item.get("graph_lookup_guard_max_query_terms", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_query_hit_paths = [
        float(item.get("graph_lookup_query_hit_paths", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_scip_signal_paths = [
        float(item.get("graph_lookup_scip_signal_paths", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_xref_signal_paths = [
        float(item.get("graph_lookup_xref_signal_paths", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_symbol_hit_paths = [
        float(item.get("graph_lookup_symbol_hit_paths", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_import_hit_paths = [
        float(item.get("graph_lookup_import_hit_paths", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_coverage_hit_paths = [
        float(item.get("graph_lookup_coverage_hit_paths", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_max_inbound = [
        float(item.get("graph_lookup_max_inbound", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_max_xref_count = [
        float(item.get("graph_lookup_max_xref_count", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_max_query_hits = [
        float(item.get("graph_lookup_max_query_hits", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_max_symbol_hits = [
        float(item.get("graph_lookup_max_symbol_hits", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_max_import_hits = [
        float(item.get("graph_lookup_max_import_hits", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_max_query_coverage = [
        float(item.get("graph_lookup_max_query_coverage", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_boosted_path_ratios = [
        float(item.get("graph_lookup_boosted_path_ratio", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_query_hit_path_ratios = [
        float(item.get("graph_lookup_query_hit_path_ratio", 0.0) or 0.0)
        for item in case_results
    ]
    graph_lookup_reasons = [
        str(item.get("graph_lookup_reason", "") or "").strip()
        for item in case_results
    ]
    native_scip_loaded = [
        float(item.get("native_scip_loaded", 0.0) or 0.0) for item in case_results
    ]
    native_scip_document_counts = [
        float(item.get("native_scip_document_count", 0.0) or 0.0)
        for item in case_results
    ]
    native_scip_definition_occurrence_counts = [
        float(item.get("native_scip_definition_occurrence_count", 0.0) or 0.0)
        for item in case_results
    ]
    native_scip_reference_occurrence_counts = [
        float(item.get("native_scip_reference_occurrence_count", 0.0) or 0.0)
        for item in case_results
    ]
    native_scip_symbol_definition_counts = [
        float(item.get("native_scip_symbol_definition_count", 0.0) or 0.0)
        for item in case_results
    ]
    deep_symbol_cases = [
        item
        for item in case_results
        if float(item.get("deep_symbol_case", 0.0) or 0.0) > 0.0
    ]
    deep_symbol_recalls = [
        (
            1.0
            if not str(item.get("chunk_stage_miss") or "").strip()
            else 0.0
        )
        if float(item.get("chunk_stage_miss_applicable", 0.0) or 0.0) > 0.0
        else float(item.get("recall_hit", 0.0) or 0.0)
        for item in deep_symbol_cases
    ]
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
        "memory_helpful_task_success_rate": (
            mean(memory_helpful_task_success_hits)
            if memory_helpful_task_success_hits
            else 0.0
        ),
        "docs_enabled_ratio": mean(docs_enabled),
        "docs_hit_ratio": mean(docs_hits),
        "hint_inject_ratio": mean(hint_injects),
        "multi_channel_rrf_enabled_ratio": mean(multi_channel_rrf_enabled),
        "multi_channel_rrf_applied_ratio": mean(multi_channel_rrf_applied),
        "multi_channel_rrf_granularity_count_mean": mean(
            multi_channel_rrf_granularity_counts
        ),
        "multi_channel_rrf_pool_size_mean": mean(multi_channel_rrf_pool_sizes),
        "multi_channel_rrf_granularity_pool_ratio": mean(
            multi_channel_rrf_granularity_pool_ratios
        ),
        "multi_channel_rrf_granularity_case_ratio": mean(
            [
                1.0 if value > 0.0 else 0.0
                for value in multi_channel_rrf_granularity_counts
            ]
        ),
        "graph_lookup_enabled_ratio": mean(graph_lookup_enabled),
        "graph_lookup_guarded_ratio": mean(graph_lookup_guarded),
        "graph_lookup_log_norm_ratio": mean(
            [1.0 if value == "log1p" else 0.0 for value in graph_lookup_normalizations]
        ),
        "graph_lookup_linear_norm_ratio": mean(
            [1.0 if value == "linear" else 0.0 for value in graph_lookup_normalizations]
        ),
        "graph_lookup_boosted_count_mean": mean(graph_lookup_boosted_counts),
        "graph_lookup_weight_scip_mean": mean(graph_lookup_weight_scip),
        "graph_lookup_weight_xref_mean": mean(graph_lookup_weight_xref),
        "graph_lookup_weight_query_xref_mean": mean(graph_lookup_weight_query_xref),
        "graph_lookup_weight_symbol_mean": mean(graph_lookup_weight_symbol),
        "graph_lookup_weight_import_mean": mean(graph_lookup_weight_import),
        "graph_lookup_weight_coverage_mean": mean(graph_lookup_weight_coverage),
        "graph_lookup_candidate_count_mean": mean(graph_lookup_candidate_counts),
        "graph_lookup_pool_size_mean": mean(graph_lookup_pool_sizes),
        "graph_lookup_query_terms_count_mean": mean(graph_lookup_query_terms_counts),
        "graph_lookup_guard_max_candidates_mean": mean(
            graph_lookup_guard_max_candidates
        ),
        "graph_lookup_guard_min_query_terms_mean": mean(
            graph_lookup_guard_min_query_terms
        ),
        "graph_lookup_guard_max_query_terms_mean": mean(
            graph_lookup_guard_max_query_terms
        ),
        "graph_lookup_query_hit_paths_mean": mean(graph_lookup_query_hit_paths),
        "graph_lookup_scip_signal_paths_mean": mean(graph_lookup_scip_signal_paths),
        "graph_lookup_xref_signal_paths_mean": mean(graph_lookup_xref_signal_paths),
        "graph_lookup_symbol_hit_paths_mean": mean(graph_lookup_symbol_hit_paths),
        "graph_lookup_import_hit_paths_mean": mean(graph_lookup_import_hit_paths),
        "graph_lookup_coverage_hit_paths_mean": mean(
            graph_lookup_coverage_hit_paths
        ),
        "graph_lookup_max_inbound_mean": mean(graph_lookup_max_inbound),
        "graph_lookup_max_xref_count_mean": mean(graph_lookup_max_xref_count),
        "graph_lookup_max_query_hits_mean": mean(graph_lookup_max_query_hits),
        "graph_lookup_max_symbol_hits_mean": mean(graph_lookup_max_symbol_hits),
        "graph_lookup_max_import_hits_mean": mean(graph_lookup_max_import_hits),
        "graph_lookup_max_query_coverage_mean": mean(
            graph_lookup_max_query_coverage
        ),
        "graph_lookup_candidate_count_guard_ratio": mean(
            [1.0 if reason == "candidate_count_guarded" else 0.0 for reason in graph_lookup_reasons]
        ),
        "graph_lookup_query_terms_too_few_ratio": mean(
            [1.0 if reason == "query_terms_too_few" else 0.0 for reason in graph_lookup_reasons]
        ),
        "graph_lookup_query_terms_too_many_ratio": mean(
            [1.0 if reason == "query_terms_too_many" else 0.0 for reason in graph_lookup_reasons]
        ),
        "graph_lookup_boosted_path_ratio": mean(graph_lookup_boosted_path_ratios),
        "graph_lookup_query_hit_path_ratio": mean(graph_lookup_query_hit_path_ratios),
        "deep_symbol_case_count": float(len(deep_symbol_cases)),
        "deep_symbol_case_recall": (
            mean(deep_symbol_recalls) if deep_symbol_recalls else 0.0
        ),
        "native_scip_loaded_rate": mean(native_scip_loaded),
        "native_scip_document_count_mean": mean(native_scip_document_counts),
        "native_scip_definition_occurrence_count_mean": mean(
            native_scip_definition_occurrence_counts
        ),
        "native_scip_reference_occurrence_count_mean": mean(
            native_scip_reference_occurrence_counts
        ),
        "native_scip_symbol_definition_count_mean": mean(
            native_scip_symbol_definition_counts
        ),
        "dependency_recall": mean(dependencies),
        "repomap_worktree_seed_count_mean": mean(repomap_worktree_seed_counts),
        "repomap_subgraph_seed_count_mean": mean(repomap_subgraph_seed_counts),
        "repomap_seed_candidates_count_mean": mean(
            repomap_seed_candidates_counts
        ),
        "repomap_cache_hit_ratio": mean(repomap_cache_hits),
        "repomap_precompute_hit_ratio": mean(repomap_precompute_hits),
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
        "retrieval_context_chunk_count_mean": mean(retrieval_context_chunk_counts),
        "retrieval_context_coverage_ratio": mean(retrieval_context_coverage),
        "retrieval_context_char_count_mean": mean(retrieval_context_char_counts),
        "contextual_sidecar_parent_symbol_chunk_count_mean": mean(
            contextual_sidecar_parent_symbol_chunk_counts
        ),
        "contextual_sidecar_parent_symbol_coverage_ratio": mean(
            contextual_sidecar_parent_symbol_coverage
        ),
        "contextual_sidecar_reference_hint_chunk_count_mean": mean(
            contextual_sidecar_reference_hint_chunk_counts
        ),
        "contextual_sidecar_reference_hint_coverage_ratio": mean(
            contextual_sidecar_reference_hint_coverage
        ),
        "chunk_contract_fallback_count_mean": mean(
            chunk_contract_fallback_counts
        ),
        "chunk_contract_skeleton_chunk_count_mean": mean(
            chunk_contract_skeleton_chunk_counts
        ),
        "chunk_contract_fallback_ratio": mean(chunk_contract_fallback_ratios),
        "chunk_contract_skeleton_ratio": mean(chunk_contract_skeleton_ratios),
        "chunk_cache_contract_present_ratio": mean(
            chunk_cache_contract_present
        ),
        "chunk_cache_contract_fingerprint_present_ratio": mean(
            chunk_cache_contract_fingerprint_present
        ),
        "chunk_cache_contract_metadata_aligned_ratio": mean(
            chunk_cache_contract_metadata_aligned
        ),
        "chunk_cache_contract_file_count_mean": mean(
            chunk_cache_contract_file_counts
        ),
        "chunk_cache_contract_chunk_count_mean": mean(
            chunk_cache_contract_chunk_counts
        ),
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
        "graph_source_provider_loaded_ratio": mean(graph_source_provider_loaded),
        "graph_source_projection_fallback_ratio": mean(
            graph_source_projection_fallback
        ),
        "graph_source_edge_count_mean": mean(graph_source_edge_counts),
        "graph_source_inbound_signal_chunk_count_mean": mean(
            graph_source_inbound_signal_chunk_counts
        ),
        "graph_source_inbound_signal_coverage_ratio": mean(
            graph_source_inbound_signal_coverage
        ),
        "graph_source_centrality_signal_chunk_count_mean": mean(
            graph_source_centrality_signal_chunk_counts
        ),
        "graph_source_centrality_signal_coverage_ratio": mean(
            graph_source_centrality_signal_coverage
        ),
        "graph_source_pagerank_signal_chunk_count_mean": mean(
            graph_source_pagerank_signal_chunk_counts
        ),
        "graph_source_pagerank_signal_coverage_ratio": mean(
            graph_source_pagerank_signal_coverage
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
        "candidate_rows_materialized_mean": mean(candidate_rows_materialized_counts),
        "candidate_chunks_materialized_mean": mean(
            candidate_chunks_materialized_counts
        ),
        "source_plan_candidate_chunks_materialized_mean": mean(
            source_plan_candidate_chunks_materialized_counts
        ),
        "skills_markdown_bytes_loaded_mean": mean(skills_markdown_bytes_loaded),
        "budget_abort_ratio": mean(budget_abort_cases),
        "fallback_taken_ratio": mean(fallback_taken_cases),
        "plan_replay_cache_enabled_ratio": mean(plan_replay_cache_enabled),
        "plan_replay_cache_hit_ratio": mean(plan_replay_cache_hits),
        "plan_replay_cache_stale_hit_safe_ratio": mean(
            plan_replay_cache_stale_hit_safe
        ),
        "adaptive_router_shadow_coverage": (
            float(len(adaptive_router_shadow_cases))
            / float(len(adaptive_router_enabled_cases))
            if adaptive_router_enabled_cases
            else 0.0
        ),
        "risk_upgrade_precision_gain": (
            mean(float(item.get("precision_at_k", 0.0) or 0.0) for item in risk_upgrade_cases)
            - mean(
                float(item.get("precision_at_k", 0.0) or 0.0)
                for item in risk_baseline_cases
            )
            if risk_upgrade_cases and risk_baseline_cases
            else 0.0
        ),
        "validation_test_count": mean(validation_counts),
        "validation_probe_enabled_ratio": mean(validation_probe_enabled),
        "validation_probe_executed_count_mean": mean(
            validation_probe_executed_counts
        ),
        "validation_probe_failure_rate": mean(validation_probe_failed),
        "validation_branch_case_count": float(len(validation_branch_cases)),
        "validation_branch_case_rate": mean(validation_branch_case_flags),
        "validation_branch_candidate_count_mean": (
            mean(validation_branch_candidate_counts)
            if validation_branch_candidate_counts
            else 0.0
        ),
        "validation_branch_rejected_count_mean": (
            mean(validation_branch_rejected_counts)
            if validation_branch_rejected_counts
            else 0.0
        ),
        "validation_branch_selection_present_ratio": (
            mean(validation_branch_selection_present)
            if validation_branch_selection_present
            else 0.0
        ),
        "validation_branch_patch_artifact_present_ratio": (
            mean(validation_branch_patch_artifact_present)
            if validation_branch_patch_artifact_present
            else 0.0
        ),
        "validation_branch_archive_present_ratio": (
            mean(validation_branch_archive_present)
            if validation_branch_archive_present
            else 0.0
        ),
        "validation_branch_parallel_case_rate": (
            mean(validation_branch_parallel) if validation_branch_parallel else 0.0
        ),
        "validation_branch_winner_pass_rate": (
            mean(validation_branch_winner_passed)
            if validation_branch_winner_passed
            else 0.0
        ),
        "validation_branch_winner_regressed_rate": (
            mean(validation_branch_winner_regressed)
            if validation_branch_winner_regressed
            else 0.0
        ),
        "validation_branch_winner_score_mean": (
            mean(validation_branch_winner_scores)
            if validation_branch_winner_scores
            else 0.0
        ),
        "validation_branch_winner_after_issue_count_mean": (
            mean(validation_branch_winner_after_issue_counts)
            if validation_branch_winner_after_issue_counts
            else 0.0
        ),
        "source_plan_evidence_card_count_mean": mean(
            source_plan_evidence_card_counts
        ),
        "source_plan_file_card_count_mean": mean(source_plan_file_card_counts),
        "source_plan_chunk_card_count_mean": mean(source_plan_chunk_card_counts),
        "source_plan_validation_card_present_ratio": mean(
            source_plan_validation_card_present
        ),
        "source_plan_validation_feedback_present_ratio": mean(
            source_plan_validation_feedback_present
        ),
        "source_plan_validation_feedback_issue_count_mean": mean(
            source_plan_validation_feedback_issue_counts
        ),
        "source_plan_validation_feedback_failure_rate": mean(
            source_plan_validation_feedback_failed
        ),
        "source_plan_validation_feedback_probe_issue_count_mean": mean(
            source_plan_validation_feedback_probe_issue_counts
        ),
        "source_plan_validation_feedback_probe_executed_count_mean": mean(
            source_plan_validation_feedback_probe_executed_counts
        ),
        "source_plan_validation_feedback_probe_failure_rate": mean(
            source_plan_validation_feedback_probe_failed
        ),
        "source_plan_validation_feedback_selected_test_count_mean": mean(
            source_plan_validation_feedback_selected_test_counts
        ),
        "source_plan_validation_feedback_executed_test_count_mean": mean(
            source_plan_validation_feedback_executed_test_counts
        ),
        "source_plan_failure_signal_present_ratio": mean(
            source_plan_failure_signal_present
        ),
        "source_plan_failure_signal_issue_count_mean": mean(
            source_plan_failure_signal_issue_counts
        ),
        "source_plan_failure_signal_failure_rate": mean(
            source_plan_failure_signal_failed
        ),
        "source_plan_failure_signal_probe_issue_count_mean": mean(
            source_plan_failure_signal_probe_issue_counts
        ),
        "source_plan_failure_signal_probe_executed_count_mean": mean(
            source_plan_failure_signal_probe_executed_counts
        ),
        "source_plan_failure_signal_probe_failure_rate": mean(
            source_plan_failure_signal_probe_failed
        ),
        "source_plan_failure_signal_selected_test_count_mean": mean(
            source_plan_failure_signal_selected_test_counts
        ),
        "source_plan_failure_signal_executed_test_count_mean": mean(
            source_plan_failure_signal_executed_test_counts
        ),
        "source_plan_failure_signal_replay_cache_origin_ratio": mean(
            source_plan_failure_signal_replay_cache_origin
        ),
        "source_plan_failure_signal_observability_origin_ratio": mean(
            source_plan_failure_signal_observability_origin
        ),
        "source_plan_failure_signal_source_plan_origin_ratio": mean(
            source_plan_failure_signal_source_plan_origin
        ),
        "source_plan_failure_signal_validate_step_origin_ratio": mean(
            source_plan_failure_signal_validate_step_origin
        ),
        "source_plan_direct_evidence_ratio": mean(source_plan_direct_ratios),
        "source_plan_symbol_count_mean": mean(source_plan_symbol_counts),
        "source_plan_signature_count_mean": mean(source_plan_signature_counts),
        "source_plan_skeleton_count_mean": mean(source_plan_skeleton_counts),
        "source_plan_robust_signature_count_mean": mean(
            source_plan_robust_signature_counts
        ),
        "source_plan_symbol_ratio": mean(source_plan_symbol_ratios),
        "source_plan_signature_ratio": mean(source_plan_signature_ratios),
        "source_plan_skeleton_ratio": mean(source_plan_skeleton_ratios),
        "source_plan_robust_signature_ratio": mean(
            source_plan_robust_signature_ratios
        ),
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
        "source_plan_granularity_preferred_count_mean": mean(
            source_plan_granularity_preferred_counts
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
        "ltm_hit_ratio": (
            float(len(ltm_hit_cases)) / float(len(memory_helpful_cases))
            if memory_helpful_cases
            else 0.0
        ),
        "ltm_effective_hit_rate": (
            float(len(ltm_effective_hit_cases)) / float(len(ltm_hit_cases))
            if ltm_hit_cases
            else 0.0
        ),
        "ltm_false_help_rate": (
            float(len(ltm_false_help_cases))
            / float(len(memory_harmful_negative_control_cases))
            if memory_harmful_negative_control_cases
            else 0.0
        ),
        "ltm_stale_hit_rate": (
            float(len(ltm_stale_hit_cases)) / float(len(time_sensitive_cases))
            if time_sensitive_cases
            else 0.0
        ),
        "ltm_replay_drift_rate": (
            float(len(ltm_replay_drift_cases))
            / float(len(ltm_time_sensitive_hit_cases))
            if ltm_time_sensitive_hit_cases
            else 0.0
        ),
        "ltm_latency_overhead_ms": (
            max(0.0, mean(ltm_latency_cases) - mean(non_ltm_latency_cases))
            if ltm_latency_cases and non_ltm_latency_cases
            else 0.0
        ),
        "issue_report_linked_plan_rate": (
            float(len(issue_report_linked_plan_cases))
            / float(len(issue_report_linked_cases))
            if issue_report_linked_cases
            else 0.0
        ),
        "issue_to_benchmark_case_conversion_rate": (
            float(len(issue_report_linked_cases))
            / float(len(issue_report_feedback_cases))
            if issue_report_feedback_cases
            else 0.0
        ),
        "issue_report_time_to_fix_hours_mean": (
            mean(issue_report_time_to_fix_hours)
            if issue_report_time_to_fix_hours
            else 0.0
        ),
        "dev_issue_capture_rate": (
            float(len(dev_issue_captured_cases)) / float(len(dev_issue_capture_cases))
            if dev_issue_capture_cases
            else 0.0
        ),
        "dev_feedback_resolution_rate": (
            mean(dev_feedback_resolution_hits)
            if dev_feedback_resolution_hits
            else 0.0
        ),
        "dev_issue_to_fix_rate": (
            float(dev_feedback_linked_fix_issue_count) / float(dev_feedback_issue_count)
            if dev_feedback_issue_count > 0.0
            else 0.0
        ),
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


def build_retrieval_control_plane_gate_summary(
    *,
    metrics: dict[str, Any],
    regression: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_metrics = normalize_metrics(metrics)
    regression_payload = regression if isinstance(regression, dict) else {}
    failed_checks_raw = regression_payload.get("failed_checks", [])
    failed_checks = (
        [str(item) for item in failed_checks_raw if str(item).strip()]
        if isinstance(failed_checks_raw, list)
        else []
    )
    regression_evaluated = bool(regression_payload)
    benchmark_regression_detected = bool(regression_payload.get("regressed", False))
    adaptive_router_shadow_coverage = float(
        normalized_metrics.get("adaptive_router_shadow_coverage", 0.0) or 0.0
    )
    risk_upgrade_precision_gain = float(
        normalized_metrics.get("risk_upgrade_precision_gain", 0.0) or 0.0
    )
    latency_p95_ms = float(normalized_metrics.get("latency_p95_ms", 0.0) or 0.0)

    shadow_coverage_threshold = 0.8
    risk_upgrade_precision_gain_threshold = 0.0
    latency_p95_ms_threshold = RETRIEVAL_CONTROL_PLANE_LATENCY_P95_THRESHOLD_MS

    benchmark_regression_passed = (
        regression_evaluated and not benchmark_regression_detected
    )
    shadow_coverage_passed = (
        adaptive_router_shadow_coverage >= shadow_coverage_threshold
    )
    risk_upgrade_precision_gain_passed = (
        risk_upgrade_precision_gain >= risk_upgrade_precision_gain_threshold
    )
    latency_p95_ms_passed = latency_p95_ms <= latency_p95_ms_threshold

    return {
        "regression_evaluated": regression_evaluated,
        "benchmark_regression_detected": benchmark_regression_detected,
        "benchmark_regression_passed": benchmark_regression_passed,
        "failed_checks": failed_checks,
        "adaptive_router_shadow_coverage": round(adaptive_router_shadow_coverage, 6),
        "adaptive_router_shadow_coverage_threshold": shadow_coverage_threshold,
        "adaptive_router_shadow_coverage_passed": shadow_coverage_passed,
        "risk_upgrade_precision_gain": round(risk_upgrade_precision_gain, 6),
        "risk_upgrade_precision_gain_threshold": (
            risk_upgrade_precision_gain_threshold
        ),
        "risk_upgrade_precision_gain_passed": risk_upgrade_precision_gain_passed,
        "latency_p95_ms": round(latency_p95_ms, 6),
        "latency_p95_ms_threshold": latency_p95_ms_threshold,
        "latency_p95_ms_passed": latency_p95_ms_passed,
        "gate_passed": (
            benchmark_regression_passed
            and shadow_coverage_passed
            and risk_upgrade_precision_gain_passed
            and latency_p95_ms_passed
        ),
    }


def build_retrieval_frontier_gate_summary(
    *,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    normalized_metrics = normalize_metrics(metrics)
    deep_symbol_case_recall = float(
        normalized_metrics.get("deep_symbol_case_recall", 0.0) or 0.0
    )
    native_scip_loaded_rate = float(
        normalized_metrics.get("native_scip_loaded_rate", 0.0) or 0.0
    )
    precision_at_k = float(normalized_metrics.get("precision_at_k", 0.0) or 0.0)
    noise_rate = float(normalized_metrics.get("noise_rate", 0.0) or 0.0)

    deep_symbol_case_recall_threshold = 0.9
    native_scip_loaded_rate_threshold = 0.7
    precision_at_k_threshold = 0.64
    noise_rate_threshold = 0.36

    deep_symbol_case_recall_passed = (
        deep_symbol_case_recall >= deep_symbol_case_recall_threshold
    )
    native_scip_loaded_rate_passed = (
        native_scip_loaded_rate >= native_scip_loaded_rate_threshold
    )
    precision_at_k_passed = precision_at_k >= precision_at_k_threshold
    noise_rate_passed = noise_rate <= noise_rate_threshold

    failed_checks: list[str] = []
    if not deep_symbol_case_recall_passed:
        failed_checks.append("deep_symbol_case_recall")
    if not native_scip_loaded_rate_passed:
        failed_checks.append("native_scip_loaded_rate")
    if not precision_at_k_passed:
        failed_checks.append("precision_at_k")
    if not noise_rate_passed:
        failed_checks.append("noise_rate")

    return {
        "failed_checks": failed_checks,
        "deep_symbol_case_recall": round(deep_symbol_case_recall, 6),
        "deep_symbol_case_recall_threshold": deep_symbol_case_recall_threshold,
        "deep_symbol_case_recall_passed": deep_symbol_case_recall_passed,
        "native_scip_loaded_rate": round(native_scip_loaded_rate, 6),
        "native_scip_loaded_rate_threshold": native_scip_loaded_rate_threshold,
        "native_scip_loaded_rate_passed": native_scip_loaded_rate_passed,
        "precision_at_k": round(precision_at_k, 6),
        "precision_at_k_threshold": precision_at_k_threshold,
        "precision_at_k_passed": precision_at_k_passed,
        "noise_rate": round(noise_rate, 6),
        "noise_rate_threshold": noise_rate_threshold,
        "noise_rate_passed": noise_rate_passed,
        "gate_passed": (
            deep_symbol_case_recall_passed
            and native_scip_loaded_rate_passed
            and precision_at_k_passed
            and noise_rate_passed
        ),
    }


def build_repomap_seed_summary(*, metrics: dict[str, Any]) -> dict[str, float]:
    normalized_metrics = normalize_metrics(metrics)
    return {
        "worktree_seed_count_mean": round(
            float(normalized_metrics.get("repomap_worktree_seed_count_mean", 0.0) or 0.0),
            6,
        ),
        "subgraph_seed_count_mean": round(
            float(normalized_metrics.get("repomap_subgraph_seed_count_mean", 0.0) or 0.0),
            6,
        ),
        "seed_candidates_count_mean": round(
            float(
                normalized_metrics.get("repomap_seed_candidates_count_mean", 0.0)
                or 0.0
            ),
            6,
        ),
        "cache_hit_ratio": round(
            float(normalized_metrics.get("repomap_cache_hit_ratio", 0.0) or 0.0),
            6,
        ),
        "precompute_hit_ratio": round(
            float(normalized_metrics.get("repomap_precompute_hit_ratio", 0.0) or 0.0),
            6,
        ),
    }


def build_workload_taxonomy_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {"case_count": 0, "taxonomy_count": 0, "taxonomies": []}

    counts: dict[str, int] = {}
    for item in case_results:
        if not isinstance(item, dict):
            continue
        taxonomy = str(item.get("workload_taxonomy") or "").strip() or "unknown"
        counts[taxonomy] = counts.get(taxonomy, 0) + 1

    rows = [
        {
            "workload_taxonomy": name,
            "count": count,
            "rate": float(count) / float(case_count),
        }
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "case_count": case_count,
        "taxonomy_count": len(rows),
        "dominant_workload_taxonomy": rows[0]["workload_taxonomy"] if rows else "",
        "taxonomies": rows,
    }


def build_deep_symbol_summary(*, metrics: dict[str, Any]) -> dict[str, float]:
    normalized_metrics = normalize_metrics(metrics)
    return {
        "case_count": round(
            float(normalized_metrics.get("deep_symbol_case_count", 0.0) or 0.0),
            6,
        ),
        "recall": round(
            float(normalized_metrics.get("deep_symbol_case_recall", 0.0) or 0.0),
            6,
        ),
    }


def build_native_scip_summary(*, metrics: dict[str, Any]) -> dict[str, float]:
    normalized_metrics = normalize_metrics(metrics)
    return {
        "loaded_rate": round(
            float(normalized_metrics.get("native_scip_loaded_rate", 0.0) or 0.0),
            6,
        ),
        "document_count_mean": round(
            float(
                normalized_metrics.get("native_scip_document_count_mean", 0.0) or 0.0
            ),
            6,
        ),
        "definition_occurrence_count_mean": round(
            float(
                normalized_metrics.get(
                    "native_scip_definition_occurrence_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "reference_occurrence_count_mean": round(
            float(
                normalized_metrics.get(
                    "native_scip_reference_occurrence_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "symbol_definition_count_mean": round(
            float(
                normalized_metrics.get("native_scip_symbol_definition_count_mean", 0.0)
                or 0.0
            ),
            6,
        ),
    }


def build_validation_probe_summary(*, metrics: dict[str, Any]) -> dict[str, float]:
    normalized_metrics = normalize_metrics(metrics)
    return {
        "validation_test_count": round(
            float(normalized_metrics.get("validation_test_count", 0.0) or 0.0),
            6,
        ),
        "probe_enabled_ratio": round(
            float(
                normalized_metrics.get("validation_probe_enabled_ratio", 0.0) or 0.0
            ),
            6,
        ),
        "probe_executed_count_mean": round(
            float(
                normalized_metrics.get("validation_probe_executed_count_mean", 0.0)
                or 0.0
            ),
            6,
        ),
        "probe_failure_rate": round(
            float(
                normalized_metrics.get("validation_probe_failure_rate", 0.0) or 0.0
            ),
            6,
        ),
    }


def build_validation_branch_summary(*, metrics: dict[str, Any]) -> dict[str, float]:
    normalized_metrics = normalize_metrics(metrics)
    return {
        "case_count": round(
            float(normalized_metrics.get("validation_branch_case_count", 0.0) or 0.0),
            6,
        ),
        "case_rate": round(
            float(normalized_metrics.get("validation_branch_case_rate", 0.0) or 0.0),
            6,
        ),
        "candidate_count_mean": round(
            float(
                normalized_metrics.get(
                    "validation_branch_candidate_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "rejected_count_mean": round(
            float(
                normalized_metrics.get(
                    "validation_branch_rejected_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "selection_present_ratio": round(
            float(
                normalized_metrics.get(
                    "validation_branch_selection_present_ratio", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "patch_artifact_present_ratio": round(
            float(
                normalized_metrics.get(
                    "validation_branch_patch_artifact_present_ratio", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "archive_present_ratio": round(
            float(
                normalized_metrics.get(
                    "validation_branch_archive_present_ratio", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "parallel_case_rate": round(
            float(
                normalized_metrics.get("validation_branch_parallel_case_rate", 0.0)
                or 0.0
            ),
            6,
        ),
        "winner_pass_rate": round(
            float(
                normalized_metrics.get("validation_branch_winner_pass_rate", 0.0)
                or 0.0
            ),
            6,
        ),
        "winner_regressed_rate": round(
            float(
                normalized_metrics.get(
                    "validation_branch_winner_regressed_rate", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "winner_score_mean": round(
            float(
                normalized_metrics.get("validation_branch_winner_score_mean", 0.0)
                or 0.0
            ),
            6,
        ),
        "winner_after_issue_count_mean": round(
            float(
                normalized_metrics.get(
                    "validation_branch_winner_after_issue_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
    }


def build_validation_branch_gate_summary(
    *, metrics: dict[str, Any]
) -> dict[str, Any]:
    normalized_metrics = normalize_metrics(metrics)
    case_count = float(normalized_metrics.get("validation_branch_case_count", 0.0) or 0.0)
    case_rate = float(normalized_metrics.get("validation_branch_case_rate", 0.0) or 0.0)
    selection_present_ratio = float(
        normalized_metrics.get("validation_branch_selection_present_ratio", 0.0)
        or 0.0
    )
    patch_artifact_present_ratio = float(
        normalized_metrics.get("validation_branch_patch_artifact_present_ratio", 0.0)
        or 0.0
    )
    archive_present_ratio = float(
        normalized_metrics.get("validation_branch_archive_present_ratio", 0.0) or 0.0
    )
    parallel_case_rate = float(
        normalized_metrics.get("validation_branch_parallel_case_rate", 0.0) or 0.0
    )

    case_count_threshold = 1.0
    selection_present_ratio_threshold = 1.0
    patch_artifact_present_ratio_threshold = 1.0
    archive_present_ratio_threshold = 1.0
    parallel_case_rate_threshold = 1.0

    case_count_passed = case_count >= case_count_threshold
    selection_present_ratio_passed = (
        selection_present_ratio >= selection_present_ratio_threshold
    )
    patch_artifact_present_ratio_passed = (
        patch_artifact_present_ratio >= patch_artifact_present_ratio_threshold
    )
    archive_present_ratio_passed = (
        archive_present_ratio >= archive_present_ratio_threshold
    )
    parallel_case_rate_passed = parallel_case_rate >= parallel_case_rate_threshold

    failed_checks: list[str] = []
    if not case_count_passed:
        failed_checks.append("validation_branch_case_count")
    if not selection_present_ratio_passed:
        failed_checks.append("validation_branch_selection_present_ratio")
    if not patch_artifact_present_ratio_passed:
        failed_checks.append("validation_branch_patch_artifact_present_ratio")
    if not archive_present_ratio_passed:
        failed_checks.append("validation_branch_archive_present_ratio")
    if not parallel_case_rate_passed:
        failed_checks.append("validation_branch_parallel_case_rate")

    return {
        "failed_checks": failed_checks,
        "case_count": round(case_count, 6),
        "case_rate": round(case_rate, 6),
        "case_count_threshold": case_count_threshold,
        "case_count_passed": case_count_passed,
        "selection_present_ratio": round(selection_present_ratio, 6),
        "selection_present_ratio_threshold": selection_present_ratio_threshold,
        "selection_present_ratio_passed": selection_present_ratio_passed,
        "patch_artifact_present_ratio": round(patch_artifact_present_ratio, 6),
        "patch_artifact_present_ratio_threshold": (
            patch_artifact_present_ratio_threshold
        ),
        "patch_artifact_present_ratio_passed": (
            patch_artifact_present_ratio_passed
        ),
        "archive_present_ratio": round(archive_present_ratio, 6),
        "archive_present_ratio_threshold": archive_present_ratio_threshold,
        "archive_present_ratio_passed": archive_present_ratio_passed,
        "parallel_case_rate": round(parallel_case_rate, 6),
        "parallel_case_rate_threshold": parallel_case_rate_threshold,
        "parallel_case_rate_passed": parallel_case_rate_passed,
        "gate_passed": (
            case_count_passed
            and selection_present_ratio_passed
            and patch_artifact_present_ratio_passed
            and archive_present_ratio_passed
            and parallel_case_rate_passed
        ),
    }


def build_source_plan_card_summary(*, metrics: dict[str, Any]) -> dict[str, float]:
    normalized_metrics = normalize_metrics(metrics)
    return {
        "evidence_card_count_mean": round(
            float(normalized_metrics.get("source_plan_evidence_card_count_mean", 0.0) or 0.0),
            6,
        ),
        "file_card_count_mean": round(
            float(normalized_metrics.get("source_plan_file_card_count_mean", 0.0) or 0.0),
            6,
        ),
        "chunk_card_count_mean": round(
            float(normalized_metrics.get("source_plan_chunk_card_count_mean", 0.0) or 0.0),
            6,
        ),
        "validation_card_present_ratio": round(
            float(
                normalized_metrics.get("source_plan_validation_card_present_ratio", 0.0)
                or 0.0
            ),
            6,
        ),
    }


def build_source_plan_validation_feedback_summary(
    *, metrics: dict[str, Any]
) -> dict[str, float]:
    normalized_metrics = normalize_metrics(metrics)
    return {
        "present_ratio": round(
            float(
                normalized_metrics.get(
                    "source_plan_validation_feedback_present_ratio", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "issue_count_mean": round(
            float(
                normalized_metrics.get(
                    "source_plan_validation_feedback_issue_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "failure_rate": round(
            float(
                normalized_metrics.get(
                    "source_plan_validation_feedback_failure_rate", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "probe_issue_count_mean": round(
            float(
                normalized_metrics.get(
                    "source_plan_validation_feedback_probe_issue_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "probe_executed_count_mean": round(
            float(
                normalized_metrics.get(
                    "source_plan_validation_feedback_probe_executed_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "probe_failure_rate": round(
            float(
                normalized_metrics.get(
                    "source_plan_validation_feedback_probe_failure_rate", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "selected_test_count_mean": round(
            float(
                normalized_metrics.get(
                    "source_plan_validation_feedback_selected_test_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "executed_test_count_mean": round(
            float(
                normalized_metrics.get(
                    "source_plan_validation_feedback_executed_test_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
    }


def build_source_plan_failure_signal_summary(
    *, metrics: dict[str, Any]
) -> dict[str, float]:
    normalized_metrics = normalize_metrics(metrics)
    return {
        "present_ratio": round(
            float(
                normalized_metrics.get("source_plan_failure_signal_present_ratio", 0.0)
                or 0.0
            ),
            6,
        ),
        "issue_count_mean": round(
            float(
                normalized_metrics.get(
                    "source_plan_failure_signal_issue_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "failure_rate": round(
            float(
                normalized_metrics.get(
                    "source_plan_failure_signal_failure_rate", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "probe_issue_count_mean": round(
            float(
                normalized_metrics.get(
                    "source_plan_failure_signal_probe_issue_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "probe_executed_count_mean": round(
            float(
                normalized_metrics.get(
                    "source_plan_failure_signal_probe_executed_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "probe_failure_rate": round(
            float(
                normalized_metrics.get(
                    "source_plan_failure_signal_probe_failure_rate", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "selected_test_count_mean": round(
            float(
                normalized_metrics.get(
                    "source_plan_failure_signal_selected_test_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "executed_test_count_mean": round(
            float(
                normalized_metrics.get(
                    "source_plan_failure_signal_executed_test_count_mean", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "replay_cache_origin_ratio": round(
            float(
                normalized_metrics.get(
                    "source_plan_failure_signal_replay_cache_origin_ratio", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "observability_origin_ratio": round(
            float(
                normalized_metrics.get(
                    "source_plan_failure_signal_observability_origin_ratio", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "source_plan_origin_ratio": round(
            float(
                normalized_metrics.get(
                    "source_plan_failure_signal_source_plan_origin_ratio", 0.0
                )
                or 0.0
            ),
            6,
        ),
        "validate_step_origin_ratio": round(
            float(
                normalized_metrics.get(
                    "source_plan_failure_signal_validate_step_origin_ratio", 0.0
                )
                or 0.0
            ),
            6,
        ),
    }


def build_evidence_insufficiency_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_evidence_insufficiency_summary_impl(case_results)


def build_missing_context_risk_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_missing_context_risk_summary_impl(case_results)


def build_chunk_stage_miss_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_chunk_stage_miss_summary_impl(case_results)


def build_decision_observability_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_decision_observability_summary_impl(case_results)


def build_retrieval_context_observability_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_retrieval_context_observability_summary_impl(case_results)


def build_retrieval_default_strategy_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_retrieval_default_strategy_summary_impl(case_results)


def build_agent_loop_control_plane_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_agent_loop_control_plane_summary_impl(case_results)


def build_preference_observability_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_preference_observability_summary_impl(case_results)


def build_feedback_observability_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_feedback_observability_summary_impl(case_results)


def build_feedback_loop_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_feedback_loop_summary_impl(case_results)


def build_ltm_explainability_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    feedback_signal_names = ("helpful", "stale", "harmful")

    def _build_feedback_signal_rows(
        *,
        case_total: float,
        case_counts: dict[str, int],
        total_counts: dict[str, int],
    ) -> list[dict[str, Any]]:
        return [
            {
                "feedback_signal": signal,
                "case_count": int(case_counts.get(signal, 0) or 0),
                "case_rate": (
                    float(case_counts.get(signal, 0) or 0) / case_total
                    if case_total > 0.0
                    else 0.0
                ),
                "total_count": int(total_counts.get(signal, 0) or 0),
                "count_mean": (
                    float(total_counts.get(signal, 0) or 0) / case_total
                    if case_total > 0.0
                    else 0.0
                ),
            }
            for signal in feedback_signal_names
        ]

    case_count = len(case_results)
    if case_count <= 0:
        zero_feedback_case_counts = {signal: 0 for signal in feedback_signal_names}
        zero_feedback_total_counts = {signal: 0 for signal in feedback_signal_names}
        return {
            "case_count": 0,
            "selected_case_count": 0,
            "selected_case_rate": 0.0,
            "selected_count_mean": 0.0,
            "attribution_case_count": 0,
            "attribution_case_rate": 0.0,
            "attribution_count_mean": 0.0,
            "graph_neighbor_case_count": 0,
            "graph_neighbor_case_rate": 0.0,
            "graph_neighbor_count_mean": 0.0,
            "plan_constraint_case_count": 0,
            "plan_constraint_case_rate": 0.0,
            "plan_constraint_count_mean": 0.0,
            "feedback_signal_observed_case_count": 0,
            "feedback_signal_observed_case_rate": 0.0,
            "feedback_signals": _build_feedback_signal_rows(
                case_total=0.0,
                case_counts=zero_feedback_case_counts,
                total_counts=zero_feedback_total_counts,
            ),
            "attribution_scope_count": 0,
            "attribution_scope_observed_case_count": 0,
            "attribution_scope_observed_case_rate": 0.0,
            "attribution_scopes": [],
        }

    selected_counts = [
        float(item.get("ltm_selected_count", 0.0) or 0.0) for item in case_results
    ]
    attribution_counts = [
        float(item.get("ltm_attribution_count", 0.0) or 0.0) for item in case_results
    ]
    graph_neighbor_counts = [
        float(item.get("ltm_graph_neighbor_count", 0.0) or 0.0)
        for item in case_results
    ]
    plan_constraint_counts = [
        float(item.get("ltm_plan_constraint_count", 0.0) or 0.0)
        for item in case_results
    ]

    def _positive_case_count(values: list[float]) -> int:
        return sum(1 for value in values if value > 0.0)

    selected_case_count = _positive_case_count(selected_counts)
    attribution_case_count = _positive_case_count(attribution_counts)
    graph_neighbor_case_count = _positive_case_count(graph_neighbor_counts)
    plan_constraint_case_count = _positive_case_count(plan_constraint_counts)

    feedback_signal_case_counts = {signal: 0 for signal in feedback_signal_names}
    feedback_signal_total_counts = {signal: 0 for signal in feedback_signal_names}
    feedback_signal_observed_case_count = 0
    attribution_scope_case_counts: dict[str, int] = {}
    attribution_scope_total_counts: dict[str, int] = {}
    attribution_scope_observed_case_count = 0

    for item in case_results:
        payload_raw = item.get("ltm_explainability")
        payload: dict[str, Any] = payload_raw if isinstance(payload_raw, dict) else {}

        raw_feedback_counts = payload.get("feedback_signal_counts")
        feedback_counts = {
            signal: max(
                0,
                int(
                    (
                        raw_feedback_counts.get(signal, 0)
                        if isinstance(raw_feedback_counts, dict)
                        else 0
                    )
                    or 0
                ),
            )
            for signal in feedback_signal_names
        }
        if any(feedback_counts.values()):
            feedback_signal_observed_case_count += 1
        for signal in feedback_signal_names:
            count = feedback_counts[signal]
            feedback_signal_total_counts[signal] += count
            if count > 0:
                feedback_signal_case_counts[signal] += 1

        raw_scope_counts = payload.get("attribution_scope_counts")
        scope_counts: dict[str, int] = {}
        if isinstance(raw_scope_counts, dict):
            scope_counts = {
                str(key).strip(): max(0, int(value or 0))
                for key, value in raw_scope_counts.items()
                if str(key).strip()
            }
        if any(count > 0 for count in scope_counts.values()):
            attribution_scope_observed_case_count += 1
        for scope, count in scope_counts.items():
            attribution_scope_total_counts[scope] = (
                int(attribution_scope_total_counts.get(scope, 0) or 0) + count
            )
            if count > 0:
                attribution_scope_case_counts[scope] = (
                    int(attribution_scope_case_counts.get(scope, 0) or 0) + 1
                )

    total = float(case_count)
    return {
        "case_count": case_count,
        "selected_case_count": selected_case_count,
        "selected_case_rate": float(selected_case_count) / total,
        "selected_count_mean": mean(selected_counts),
        "attribution_case_count": attribution_case_count,
        "attribution_case_rate": float(attribution_case_count) / total,
        "attribution_count_mean": mean(attribution_counts),
        "graph_neighbor_case_count": graph_neighbor_case_count,
        "graph_neighbor_case_rate": float(graph_neighbor_case_count) / total,
        "graph_neighbor_count_mean": mean(graph_neighbor_counts),
        "plan_constraint_case_count": plan_constraint_case_count,
        "plan_constraint_case_rate": float(plan_constraint_case_count) / total,
        "plan_constraint_count_mean": mean(plan_constraint_counts),
        "feedback_signal_observed_case_count": feedback_signal_observed_case_count,
        "feedback_signal_observed_case_rate": (
            float(feedback_signal_observed_case_count) / total
        ),
        "feedback_signals": _build_feedback_signal_rows(
            case_total=total,
            case_counts=feedback_signal_case_counts,
            total_counts=feedback_signal_total_counts,
        ),
        "attribution_scope_count": len(attribution_scope_total_counts),
        "attribution_scope_observed_case_count": attribution_scope_observed_case_count,
        "attribution_scope_observed_case_rate": (
            float(attribution_scope_observed_case_count) / total
        ),
        "attribution_scopes": [
            {
                "attribution_scope": scope,
                "case_count": int(attribution_scope_case_counts.get(scope, 0) or 0),
                "case_rate": float(attribution_scope_case_counts.get(scope, 0) or 0)
                / total,
                "total_count": int(attribution_scope_total_counts.get(scope, 0) or 0),
                "count_mean": float(attribution_scope_total_counts.get(scope, 0) or 0)
                / total,
            }
            for scope in sorted(
                attribution_scope_total_counts,
                key=lambda item: (
                    -int(attribution_scope_total_counts.get(item, 0) or 0),
                    -int(attribution_scope_case_counts.get(item, 0) or 0),
                    item,
                ),
            )
        ],
    }


def build_adaptive_router_arm_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_adaptive_router_arm_summary_impl(case_results)


def build_learning_router_rollout_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_learning_router_rollout_summary_impl(case_results)


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


def build_wave1_context_governance_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_wave1_context_governance_summary_impl(case_results)


def build_context_refine_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_context_refine_summary_impl(case_results)


def build_chunk_cache_contract_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "present_case_count": 0,
            "present_case_rate": 0.0,
            "fingerprint_present_case_count": 0,
            "fingerprint_present_case_rate": 0.0,
            "metadata_aligned_case_count": 0,
            "metadata_aligned_case_rate": 0.0,
            "file_count_mean": 0.0,
            "chunk_count_mean": 0.0,
        }

    present_case_count = 0
    fingerprint_present_case_count = 0
    metadata_aligned_case_count = 0
    file_counts: list[float] = []
    chunk_counts: list[float] = []
    for item in case_results:
        if not isinstance(item, dict):
            continue
        if float(item.get("chunk_cache_contract_present", 0.0) or 0.0) > 0.0:
            present_case_count += 1
        if (
            float(item.get("chunk_cache_contract_fingerprint_present", 0.0) or 0.0)
            > 0.0
        ):
            fingerprint_present_case_count += 1
        if (
            float(item.get("chunk_cache_contract_metadata_aligned", 0.0) or 0.0)
            > 0.0
        ):
            metadata_aligned_case_count += 1
        file_counts.append(float(item.get("chunk_cache_contract_file_count", 0.0) or 0.0))
        chunk_counts.append(
            float(item.get("chunk_cache_contract_chunk_count", 0.0) or 0.0)
        )

    return {
        "case_count": case_count,
        "present_case_count": present_case_count,
        "present_case_rate": float(present_case_count) / float(case_count),
        "fingerprint_present_case_count": fingerprint_present_case_count,
        "fingerprint_present_case_rate": (
            float(fingerprint_present_case_count) / float(case_count)
        ),
        "metadata_aligned_case_count": metadata_aligned_case_count,
        "metadata_aligned_case_rate": (
            float(metadata_aligned_case_count) / float(case_count)
        ),
        "file_count_mean": mean(file_counts),
        "chunk_count_mean": mean(chunk_counts),
    }

__all__ = [
    "PIPELINE_STAGE_ORDER",
    "aggregate_metrics",
    "build_adaptive_router_arm_summary",
    "build_adaptive_router_observability_summary",
    "build_adaptive_router_pair_summary",
    "build_agent_loop_control_plane_summary",
    "build_chunk_cache_contract_summary",
    "build_chunk_stage_miss_summary",
    "build_context_refine_summary",
    "build_decision_observability_summary",
    "build_deep_symbol_summary",
    "build_evidence_insufficiency_summary",
    "build_feedback_loop_summary",
    "build_feedback_observability_summary",
    "build_learning_router_rollout_summary",
    "build_ltm_explainability_summary",
    "build_missing_context_risk_summary",
    "build_native_scip_summary",
    "build_preference_observability_summary",
    "build_repomap_seed_summary",
    "build_retrieval_context_observability_summary",
    "build_retrieval_control_plane_gate_summary",
    "build_retrieval_default_strategy_summary",
    "build_retrieval_frontier_gate_summary",
    "build_slo_budget_summary",
    "build_source_plan_card_summary",
    "build_source_plan_failure_signal_summary",
    "build_source_plan_validation_feedback_summary",
    "build_stage_latency_summary",
    "build_validation_branch_gate_summary",
    "build_validation_branch_summary",
    "build_validation_probe_summary",
    "build_wave1_context_governance_summary",
    "build_workload_taxonomy_summary",
    "compare_metrics",
]
