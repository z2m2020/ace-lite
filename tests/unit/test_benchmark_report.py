from __future__ import annotations

import json
from pathlib import Path

from ace_lite.benchmark.report import (
    ALL_METRIC_ORDER,
    build_report_markdown,
    build_results_summary,
    write_results,
)


def test_build_report_markdown_includes_baseline_and_regression() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-02-09T00:00:00Z",
            "repo": "demo",
            "case_count": 1,
            "threshold_profile": "strict",
            "warmup_runs": 2,
            "include_plan_payload": False,
            "include_case_details": False,
            "metrics": {
                "recall_at_k": 0.5,
                "precision_at_k": 0.5,
                "task_success_rate": 0.25,
                "utility_rate": 0.5,
                "noise_rate": 0.5,
                "dependency_recall": 0.5,
                "repomap_latency_p95_ms": 6.0,
                "repomap_latency_median_ms": 5.0,
                "latency_p95_ms": 10.0,
                "latency_median_ms": 9.0,
                "skills_route_latency_p95_ms": 0.2,
                "skills_hydration_latency_p95_ms": 0.4,
                "contextual_sidecar_parent_symbol_chunk_count_mean": 2.0,
                "contextual_sidecar_parent_symbol_coverage_ratio": 1.0,
                "contextual_sidecar_reference_hint_chunk_count_mean": 1.0,
                "contextual_sidecar_reference_hint_coverage_ratio": 0.5,
                "robust_signature_count_mean": 1.0,
                "robust_signature_coverage_ratio": 0.5,
                "graph_closure_enabled_ratio": 1.0,
                "graph_closure_boosted_chunk_count_mean": 2.0,
                "graph_closure_coverage_ratio": 0.5,
                "graph_closure_anchor_count_mean": 1.0,
                "graph_closure_support_edge_count_mean": 3.0,
                "graph_closure_total_mean": 0.14,
                "skills_selected_count_mean": 1.0,
                "skills_token_budget_mean": 600.0,
                "skills_token_budget_used_mean": 250.0,
                "skills_budget_exhausted_ratio": 1.0,
                "skills_skipped_for_budget_mean": 1.0,
                "skills_metadata_only_routing_ratio": 1.0,
                "skills_precomputed_route_ratio": 1.0,
                "plan_replay_cache_enabled_ratio": 1.0,
                "plan_replay_cache_hit_ratio": 0.5,
                "plan_replay_cache_stale_hit_safe_ratio": 1.0,
                "source_plan_direct_evidence_ratio": 0.75,
                "source_plan_symbol_count_mean": 1.0,
                "source_plan_signature_count_mean": 0.75,
                "source_plan_skeleton_count_mean": 0.5,
                "source_plan_robust_signature_count_mean": 0.25,
                "source_plan_symbol_ratio": 0.5,
                "source_plan_signature_ratio": 0.375,
                "source_plan_skeleton_ratio": 0.25,
                "source_plan_robust_signature_ratio": 0.125,
                "source_plan_neighbor_context_ratio": 0.25,
                "source_plan_hint_only_ratio": 0.0,
                "source_plan_graph_closure_preference_enabled_ratio": 1.0,
                "source_plan_graph_closure_bonus_candidate_count_mean": 2.0,
                "source_plan_graph_closure_preferred_count_mean": 1.0,
                "source_plan_granularity_preferred_count_mean": 1.0,
                "source_plan_focused_file_promoted_count_mean": 1.0,
                "source_plan_packed_path_count_mean": 2.0,
                "multi_channel_rrf_enabled_ratio": 1.0,
                "multi_channel_rrf_applied_ratio": 1.0,
                "multi_channel_rrf_granularity_count_mean": 2.0,
                "multi_channel_rrf_pool_size_mean": 4.0,
                "multi_channel_rrf_granularity_pool_ratio": 0.5,
                "multi_channel_rrf_granularity_case_ratio": 1.0,
                "graph_lookup_enabled_ratio": 1.0,
                "graph_lookup_guarded_ratio": 0.5,
                "graph_lookup_log_norm_ratio": 1.0,
                "graph_lookup_linear_norm_ratio": 0.0,
                "graph_lookup_boosted_count_mean": 2.0,
                "graph_lookup_weight_scip_mean": 0.3,
                "graph_lookup_weight_xref_mean": 0.2,
                "graph_lookup_weight_query_xref_mean": 0.2,
                "graph_lookup_weight_symbol_mean": 0.1,
                "graph_lookup_weight_import_mean": 0.1,
                "graph_lookup_weight_coverage_mean": 0.1,
                "graph_lookup_candidate_count_mean": 6.0,
                "graph_lookup_pool_size_mean": 4.0,
                "graph_lookup_query_terms_count_mean": 3.0,
                "graph_lookup_guard_max_candidates_mean": 4.0,
                "graph_lookup_guard_min_query_terms_mean": 1.0,
                "graph_lookup_guard_max_query_terms_mean": 5.0,
                "graph_lookup_query_hit_paths_mean": 1.0,
                "graph_lookup_scip_signal_paths_mean": 2.0,
                "graph_lookup_xref_signal_paths_mean": 3.0,
                "graph_lookup_symbol_hit_paths_mean": 1.0,
                "graph_lookup_import_hit_paths_mean": 1.0,
                "graph_lookup_coverage_hit_paths_mean": 2.0,
                "graph_lookup_max_inbound_mean": 4.0,
                "graph_lookup_max_xref_count_mean": 3.0,
                "graph_lookup_max_query_hits_mean": 2.0,
                "graph_lookup_max_symbol_hits_mean": 1.0,
                "graph_lookup_max_import_hits_mean": 1.0,
                "graph_lookup_max_query_coverage_mean": 0.6667,
                "graph_lookup_candidate_count_guard_ratio": 0.5,
                "graph_lookup_query_terms_too_few_ratio": 0.25,
                "graph_lookup_query_terms_too_many_ratio": 0.0,
                "graph_lookup_boosted_path_ratio": 0.5,
                "graph_lookup_query_hit_path_ratio": 0.25,
                "deep_symbol_case_count": 2.0,
                "deep_symbol_case_recall": 1.0,
                "native_scip_loaded_rate": 1.0,
                "native_scip_document_count_mean": 5.0,
                "native_scip_definition_occurrence_count_mean": 7.0,
                "native_scip_reference_occurrence_count_mean": 11.0,
                "native_scip_symbol_definition_count_mean": 3.0,
                "evidence_insufficient_rate": 0.5,
                "repomap_worktree_seed_count_mean": 1.0,
                "repomap_subgraph_seed_count_mean": 2.0,
                "repomap_seed_candidates_count_mean": 3.0,
                "repomap_cache_hit_ratio": 0.5,
                "repomap_precompute_hit_ratio": 1.0,
                "no_candidate_rate": 0.0,
                "low_support_chunk_rate": 0.5,
                "missing_validation_rate": 0.5,
                "budget_limited_recovery_rate": 0.0,
                "noisy_hit_rate": 0.5,
                "ltm_hit_ratio": 1.0,
                "ltm_false_help_rate": 0.25,
                "ltm_stale_hit_rate": 0.0,
            },
            "baseline_metrics": {
                "recall_at_k": 0.6,
                "precision_at_k": 0.6,
                "task_success_rate": 0.4,
                "utility_rate": 0.6,
                "noise_rate": 0.4,
                "dependency_recall": 0.6,
                "repomap_latency_p95_ms": 4.0,
                "repomap_latency_median_ms": 3.0,
                "latency_p95_ms": 8.0,
                "latency_median_ms": 7.0,
                "skills_route_latency_p95_ms": 0.3,
                "skills_hydration_latency_p95_ms": 0.5,
                "contextual_sidecar_parent_symbol_chunk_count_mean": 1.0,
                "contextual_sidecar_parent_symbol_coverage_ratio": 0.5,
                "contextual_sidecar_reference_hint_chunk_count_mean": 0.5,
                "contextual_sidecar_reference_hint_coverage_ratio": 0.25,
                "robust_signature_count_mean": 0.5,
                "robust_signature_coverage_ratio": 0.25,
                "graph_closure_enabled_ratio": 0.0,
                "graph_closure_boosted_chunk_count_mean": 0.0,
                "graph_closure_coverage_ratio": 0.0,
                "graph_closure_anchor_count_mean": 0.0,
                "graph_closure_support_edge_count_mean": 0.0,
                "graph_closure_total_mean": 0.0,
                "skills_selected_count_mean": 2.0,
                "skills_token_budget_mean": 800.0,
                "skills_token_budget_used_mean": 300.0,
                "skills_budget_exhausted_ratio": 0.0,
                "skills_skipped_for_budget_mean": 0.0,
                "skills_metadata_only_routing_ratio": 1.0,
                "skills_precomputed_route_ratio": 0.0,
                "plan_replay_cache_enabled_ratio": 0.0,
                "plan_replay_cache_hit_ratio": 0.0,
                "plan_replay_cache_stale_hit_safe_ratio": 0.0,
                "source_plan_direct_evidence_ratio": 0.5,
                "source_plan_symbol_count_mean": 0.5,
                "source_plan_signature_count_mean": 0.25,
                "source_plan_skeleton_count_mean": 0.25,
                "source_plan_robust_signature_count_mean": 0.0,
                "source_plan_symbol_ratio": 0.25,
                "source_plan_signature_ratio": 0.125,
                "source_plan_skeleton_ratio": 0.125,
                "source_plan_robust_signature_ratio": 0.0,
                "source_plan_neighbor_context_ratio": 0.25,
                "source_plan_hint_only_ratio": 0.25,
                "source_plan_graph_closure_preference_enabled_ratio": 0.0,
                "source_plan_graph_closure_bonus_candidate_count_mean": 0.0,
                "source_plan_graph_closure_preferred_count_mean": 0.0,
                "source_plan_granularity_preferred_count_mean": 0.0,
                "source_plan_focused_file_promoted_count_mean": 0.0,
                "source_plan_packed_path_count_mean": 1.0,
                "multi_channel_rrf_enabled_ratio": 0.0,
                "multi_channel_rrf_applied_ratio": 0.0,
                "multi_channel_rrf_granularity_count_mean": 0.0,
                "multi_channel_rrf_pool_size_mean": 0.0,
                "multi_channel_rrf_granularity_pool_ratio": 0.0,
                "multi_channel_rrf_granularity_case_ratio": 0.0,
                "graph_lookup_enabled_ratio": 0.0,
                "graph_lookup_boosted_count_mean": 0.0,
                "graph_lookup_pool_size_mean": 0.0,
                "graph_lookup_query_terms_count_mean": 0.0,
                "graph_lookup_query_hit_paths_mean": 0.0,
                "graph_lookup_scip_signal_paths_mean": 0.0,
                "graph_lookup_xref_signal_paths_mean": 0.0,
                "graph_lookup_symbol_hit_paths_mean": 0.0,
                "graph_lookup_import_hit_paths_mean": 0.0,
                "graph_lookup_coverage_hit_paths_mean": 0.0,
                "graph_lookup_boosted_path_ratio": 0.0,
                "graph_lookup_query_hit_path_ratio": 0.0,
                "deep_symbol_case_count": 0.0,
                "deep_symbol_case_recall": 0.0,
                "native_scip_loaded_rate": 0.0,
                "native_scip_document_count_mean": 0.0,
                "native_scip_definition_occurrence_count_mean": 0.0,
                "native_scip_reference_occurrence_count_mean": 0.0,
                "native_scip_symbol_definition_count_mean": 0.0,
                "evidence_insufficient_rate": 0.25,
                "no_candidate_rate": 0.0,
                "low_support_chunk_rate": 0.25,
                "missing_validation_rate": 0.25,
                "budget_limited_recovery_rate": 0.0,
                "noisy_hit_rate": 0.25,
                "ltm_hit_ratio": 0.5,
                "ltm_false_help_rate": 0.0,
                "ltm_stale_hit_rate": 0.25,
            },
            "delta": {
                "recall_at_k": -0.1,
                "precision_at_k": -0.1,
                "task_success_rate": -0.15,
                "utility_rate": -0.1,
                "noise_rate": 0.1,
                "dependency_recall": -0.1,
                "memory_latency_p95_ms": 1.0,
                "index_latency_p95_ms": 1.5,
                "repomap_latency_p95_ms": 2.0,
                "augment_latency_p95_ms": 0.5,
                "skills_latency_p95_ms": 0.25,
                "skills_route_latency_p95_ms": -0.1,
                "skills_hydration_latency_p95_ms": -0.1,
                "source_plan_latency_p95_ms": 1.0,
                "repomap_latency_median_ms": 2.0,
                "latency_p95_ms": 2.0,
                "latency_median_ms": 2.0,
                "contextual_sidecar_parent_symbol_chunk_count_mean": 1.0,
                "contextual_sidecar_parent_symbol_coverage_ratio": 0.5,
                "contextual_sidecar_reference_hint_chunk_count_mean": 0.5,
                "contextual_sidecar_reference_hint_coverage_ratio": 0.25,
                "robust_signature_count_mean": 0.5,
                "robust_signature_coverage_ratio": 0.25,
                "graph_closure_enabled_ratio": 1.0,
                "graph_closure_boosted_chunk_count_mean": 2.0,
                "graph_closure_coverage_ratio": 0.5,
                "graph_closure_anchor_count_mean": 1.0,
                "graph_closure_support_edge_count_mean": 3.0,
                "graph_closure_total_mean": 0.14,
                "skills_selected_count_mean": -1.0,
                "skills_token_budget_mean": -200.0,
                "skills_token_budget_used_mean": -50.0,
                "skills_budget_exhausted_ratio": 1.0,
                "skills_skipped_for_budget_mean": 1.0,
                "skills_metadata_only_routing_ratio": 0.0,
                "skills_precomputed_route_ratio": 1.0,
                "plan_replay_cache_enabled_ratio": 1.0,
                "plan_replay_cache_hit_ratio": 0.5,
                "plan_replay_cache_stale_hit_safe_ratio": 1.0,
                "source_plan_direct_evidence_ratio": 0.25,
                "source_plan_symbol_count_mean": 0.5,
                "source_plan_signature_count_mean": 0.5,
                "source_plan_skeleton_count_mean": 0.25,
                "source_plan_robust_signature_count_mean": 0.25,
                "source_plan_symbol_ratio": 0.25,
                "source_plan_signature_ratio": 0.25,
                "source_plan_skeleton_ratio": 0.125,
                "source_plan_robust_signature_ratio": 0.125,
                "source_plan_neighbor_context_ratio": 0.0,
                "source_plan_hint_only_ratio": -0.25,
                "source_plan_graph_closure_preference_enabled_ratio": 1.0,
                "source_plan_graph_closure_bonus_candidate_count_mean": 2.0,
                "source_plan_graph_closure_preferred_count_mean": 1.0,
                "source_plan_granularity_preferred_count_mean": 1.0,
                "source_plan_focused_file_promoted_count_mean": 1.0,
                "source_plan_packed_path_count_mean": 1.0,
                "evidence_insufficient_rate": 0.25,
                "no_candidate_rate": 0.0,
                "low_support_chunk_rate": 0.25,
                "missing_validation_rate": 0.25,
                "budget_limited_recovery_rate": 0.0,
                "noisy_hit_rate": 0.25,
                "ltm_hit_ratio": 0.5,
                "ltm_false_help_rate": 0.25,
                "ltm_stale_hit_rate": -0.25,
                "parallel_time_budget_ms_mean": 5.0,
                "embedding_time_budget_ms_mean": 4.0,
                "chunk_semantic_time_budget_ms_mean": 3.0,
                "xref_time_budget_ms_mean": 2.0,
                "parallel_docs_timeout_ratio": 0.2,
                "embedding_time_budget_exceeded_ratio": 0.1,
                "embedding_adaptive_budget_ratio": 0.3,
                "chunk_semantic_fallback_ratio": 0.1,
                "xref_budget_exhausted_ratio": 0.05,
                "slo_downgrade_case_rate": 0.25,
            },
            "regression_thresholds": {
                "precision_tolerance": 0.01,
                "noise_tolerance": 0.0,
                "latency_growth_factor": 1.1,
                "dependency_recall_floor": 0.8,
            },
            "regression": {
                "regressed": True,
                "failed_checks": ["precision_at_k"],
                "failed_thresholds": [
                    {
                        "metric": "precision_at_k",
                        "operator": "<",
                        "current": 0.5,
                        "threshold": 0.59,
                    }
                ],
            },
            "task_success_summary": {
                "case_count": 1,
                "positive_case_count": 0,
                "negative_control_case_count": 1,
                "task_success_rate": 0.25,
                "positive_task_success_rate": 0.0,
                "negative_control_task_success_rate": 0.25,
                "retrieval_task_gap_count": 1,
                "retrieval_task_gap_rate": 1.0,
            },
            "comparison_lane_summary": {
                "total_case_count": 1,
                "labeled_case_count": 1,
                "lane_count": 1,
                "lanes": [
                    {
                        "comparison_lane": "stale_majority",
                        "case_count": 1,
                        "task_success_rate": 0.0,
                        "recall_at_k": 1.0,
                        "chunk_guard_enabled_ratio": 1.0,
                        "chunk_guard_report_only_ratio": 1.0,
                        "chunk_guard_filtered_case_rate": 1.0,
                        "chunk_guard_filtered_count_mean": 1.0,
                        "chunk_guard_filter_ratio_mean": 0.3333,
                        "chunk_guard_expected_retained_hit_rate_mean": 1.0,
                        "chunk_guard_report_only_improved_rate": 1.0,
                        "chunk_guard_pairwise_conflict_count_mean": 2.0,
                    }
                ],
            },
            "evidence_insufficiency_summary": {
                "case_count": 1,
                "applicable_case_count": 1,
                "excluded_negative_control_case_count": 0,
                "evidence_insufficient_count": 1,
                "evidence_insufficient_rate": 1.0,
                "reasons": {"missing_validation": 1},
                "signals": {"missing_validation_tests": 1, "noisy_hit": 1},
            },
            "chunk_stage_miss_summary": {
                "case_count": 1,
                "oracle_case_count": 1,
                "classified_case_count": 1,
                "classified_case_rate": 1.0,
                "labels": {"source_plan_pack_miss": 1},
            },
            "decision_observability_summary": {
                "case_count": 1,
                "case_with_decisions_count": 1,
                "case_with_decisions_rate": 1.0,
                "decision_event_count": 2,
                "actions": {"retry": 1, "skip": 1},
                "targets": {
                    "candidate_postprocess": 1,
                    "skills_hydration": 1,
                },
                "reasons": {
                    "low_candidate_count": 1,
                    "token_budget_exhausted": 1,
                },
                "outcomes": {"applied": 1},
            },
            "ltm_explainability_summary": {
                "case_count": 1,
                "selected_case_count": 1,
                "selected_case_rate": 1.0,
                "selected_count_mean": 2.0,
                "attribution_case_count": 1,
                "attribution_case_rate": 1.0,
                "attribution_count_mean": 1.0,
                "graph_neighbor_case_count": 1,
                "graph_neighbor_case_rate": 1.0,
                "graph_neighbor_count_mean": 1.0,
                "plan_constraint_case_count": 1,
                "plan_constraint_case_rate": 1.0,
                "plan_constraint_count_mean": 1.0,
            },
            "stage_latency_summary": {
                "memory": {"mean_ms": 3.0, "p95_ms": 3.0},
                "index": {"mean_ms": 4.0, "p95_ms": 4.0},
                "repomap": {"mean_ms": 5.0, "p95_ms": 6.0},
                "augment": {"mean_ms": 1.0, "p95_ms": 1.0},
                "skills": {"mean_ms": 0.5, "p95_ms": 0.5},
                "source_plan": {"mean_ms": 2.0, "p95_ms": 2.0},
                "total": {"mean_ms": 10.0, "median_ms": 10.0, "p95_ms": 10.0},
            },
            "slo_budget_summary": {
                "case_count": 1,
                "budget_limits_ms": {
                    "parallel_time_budget_ms_mean": 40.0,
                    "embedding_time_budget_ms_mean": 60.0,
                    "chunk_semantic_time_budget_ms_mean": 25.0,
                    "xref_time_budget_ms_mean": 15.0,
                },
                "downgrade_case_count": 1,
                "downgrade_case_rate": 1.0,
                "signals": {
                    "parallel_docs_timeout_ratio": {"count": 1, "rate": 1.0},
                    "parallel_worktree_timeout_ratio": {"count": 0, "rate": 0.0},
                    "embedding_time_budget_exceeded_ratio": {"count": 1, "rate": 1.0},
                    "embedding_adaptive_budget_ratio": {"count": 1, "rate": 1.0},
                    "embedding_fallback_ratio": {"count": 0, "rate": 0.0},
                    "chunk_semantic_time_budget_exceeded_ratio": {"count": 0, "rate": 0.0},
                    "chunk_semantic_fallback_ratio": {"count": 1, "rate": 1.0},
                    "xref_budget_exhausted_ratio": {"count": 0, "rate": 0.0},
                },
            },
            "plugin_policy_summary": {
                "mode": "strict",
                "allowlist": ["observability.mcp_plugins"],
                "mode_distribution": {"strict": 1},
                "totals": {
                    "applied": 2,
                    "conflicts": 1,
                    "blocked": 1,
                    "warn": 0,
                    "remote_applied": 1,
                },
                "per_case_mean": {
                    "applied": 2.0,
                    "conflicts": 1.0,
                    "blocked": 1.0,
                    "warn": 0.0,
                    "remote_applied": 1.0,
                },
                "by_stage": [
                    {
                        "stage": "source_plan",
                        "applied": 2,
                        "conflicts": 1,
                        "blocked": 1,
                        "warn": 0,
                        "remote_applied": 1,
                    }
                ],
                "by_stage_per_case_mean": [
                    {
                        "stage": "source_plan",
                        "applied": 2.0,
                        "conflicts": 1.0,
                        "blocked": 1.0,
                        "warn": 0.0,
                        "remote_applied": 1.0,
                    }
                ],
            },
            "cases": [
                {
                    "case_id": "c1",
                    "query": "q",
                    "comparison_lane": "stale_majority",
                    "retrieval_surface": "deep_symbol",
                    "deep_symbol_case": 1.0,
                    "recall_hit": 1,
                    "task_success_hit": 0.0,
                    "task_success_mode": "negative_control",
                    "task_success_failed_checks": ["validation_tests"],
                    "evidence_insufficient": 1.0,
                    "evidence_insufficiency_reason": "missing_validation",
                    "evidence_insufficiency_signals": [
                        "missing_validation_tests",
                        "noisy_hit",
                    ],
                    "decision_trace": [
                        {
                            "stage": "index",
                            "action": "retry",
                            "target": "candidate_postprocess",
                            "reason": "low_candidate_count",
                            "outcome": "applied",
                        },
                        {
                            "stage": "skills",
                            "action": "skip",
                            "target": "skills_hydration",
                            "reason": "token_budget_exhausted",
                        },
                    ],
                    "stage_latency_ms": {
                        "memory": 3.0,
                        "index": 4.0,
                        "repomap": 6.0,
                        "augment": 1.0,
                        "skills": 0.5,
                        "source_plan": 2.0,
                    },
                    "slo_downgrade_signals": [
                        "parallel_docs_timeout",
                        "embedding_time_budget_exceeded",
                        "chunk_semantic_fallback",
                    ],
                    "precision_at_k": 0.5,
                    "noise_rate": 0.5,
                    "dependency_recall": 0.8,
                    "notes_hit_ratio": 0.5,
                    "profile_selected_count": 2.0,
                    "capture_triggered": 1.0,
                    "ltm_selected_count": 2.0,
                    "ltm_attribution_count": 1.0,
                    "ltm_graph_neighbor_count": 1.0,
                    "ltm_plan_constraint_count": 1.0,
                    "feedback_enabled": 1.0,
                    "feedback_matched_event_count": 2.0,
                    "feedback_boosted_count": 1.0,
                    "graph_lookup_enabled": 1.0,
                    "graph_lookup_boosted_count": 2.0,
                    "graph_lookup_query_hit_paths": 1.0,
                    "source_plan_direct_evidence_ratio": 0.75,
                    "source_plan_neighbor_context_ratio": 0.25,
                    "source_plan_hint_only_ratio": 0.0,
                    "graph_closure_enabled": 1.0,
                    "graph_closure_boosted_chunk_count": 2.0,
                    "graph_closure_coverage_ratio": 0.5,
                    "graph_closure_anchor_count": 1.0,
                    "graph_closure_support_edge_count": 3.0,
                    "graph_closure_total": 0.14,
                    "source_plan_graph_closure_preference_enabled": 1.0,
                    "source_plan_graph_closure_bonus_candidate_count": 2.0,
                    "source_plan_graph_closure_preferred_count": 1.0,
                    "source_plan_granularity_preferred_count": 1.0,
                    "source_plan_focused_file_promoted_count": 1.0,
                    "source_plan_packed_path_count": 2.0,
                    "robust_signature_count": 1.0,
                    "robust_signature_coverage_ratio": 0.5,
                    "plan_replay_cache_enabled": 1.0,
                    "plan_replay_cache_hit": 1.0,
                    "plan_replay_cache_stale_hit_safe": 1.0,
                    "chunk_guard_enabled": 1.0,
                    "chunk_guard_report_only": 1.0,
                    "chunk_guard_filtered_count": 1.0,
                    "chunk_guard_filter_ratio": 0.3333,
                    "chunk_guard_pairwise_conflict_count": 2.0,
                    "chunk_stage_miss": "source_plan_pack_miss",
                    "validation_test_count": 0,
                    "plan_replay_cache": {
                        "enabled": True,
                        "hit": True,
                        "stale_hit_safe": True,
                        "stage": "source_plan",
                        "reason": "hit",
                        "stored": False,
                    },
                    "repomap_seed": {
                        "worktree_seed_count": 1,
                        "subgraph_seed_count": 2,
                        "seed_candidates_count": 3,
                        "cache_hit": True,
                        "precompute_hit": False,
                    },
                    "chunk_stage_miss_details": {
                        "oracle_file_path": "src/ace_lite/benchmark/case_evaluation.py",
                        "file_present": True,
                        "raw_chunk_present": True,
                        "source_plan_chunk_present": False,
                    },
                    "robust_signature": {
                        "count": 1,
                        "coverage_ratio": 0.5,
                    },
                    "graph_closure": {
                        "enabled": True,
                        "boosted_chunk_count": 2,
                        "coverage_ratio": 0.5,
                        "anchor_count": 1,
                        "support_edge_count": 3,
                        "total": 0.14,
                    },
                    "index_fusion_granularity": {
                        "enabled": True,
                        "applied": True,
                        "granularity_count": 2,
                        "pool_size": 4,
                        "granularity_pool_ratio": 0.5,
                    },
                    "graph_lookup": {
                        "enabled": True,
                        "reason": "candidate_count_guarded",
                        "guarded": True,
                        "boosted_count": 2,
                        "weights": {
                            "scip": 0.3,
                            "xref": 0.2,
                            "query_xref": 0.2,
                            "symbol": 0.1,
                            "import": 0.1,
                            "coverage": 0.1,
                        },
                        "candidate_count": 6,
                        "pool_size": 4,
                        "query_terms_count": 3,
                        "normalization": "log1p",
                        "guard_max_candidates": 4,
                        "guard_min_query_terms": 1,
                        "guard_max_query_terms": 5,
                        "query_hit_paths": 1,
                        "scip_signal_paths": 2,
                        "xref_signal_paths": 3,
                        "symbol_hit_paths": 1,
                        "import_hit_paths": 1,
                        "coverage_hit_paths": 2,
                        "max_inbound": 4.0,
                        "max_xref_count": 3.0,
                        "max_query_hits": 2.0,
                        "max_symbol_hits": 1.0,
                        "max_import_hits": 1.0,
                        "max_query_coverage": 0.6667,
                        "boosted_path_ratio": 0.5,
                        "query_hit_path_ratio": 0.25,
                    },
                    "source_plan_packing": {
                        "graph_closure_preference_enabled": True,
                        "graph_closure_bonus_candidate_count": 2,
                        "graph_closure_preferred_count": 1,
                        "granularity_preferred_count": 1,
                        "focused_file_promoted_count": 1,
                        "packed_path_count": 2,
                        "reason": "graph_closure_preferred",
                    },
                    "preference_capture": {
                        "notes_hit_ratio": 0.5,
                        "profile_selected_count": 2,
                        "capture_triggered": True,
                    },
                    "ltm_explainability": {
                        "selected_count": 2,
                        "attribution_count": 1,
                        "graph_neighbor_count": 1,
                        "plan_constraint_count": 1,
                        "attribution_preview": [
                            "runtime.validation.git fallback_policy reuse_checkout_or_skip | graph: reuse_checkout_or_skip recommended_for runtime.validation.git"
                        ],
                    },
                    "feedback_boost": {
                        "enabled": True,
                        "reason": "ok",
                        "event_count": 4,
                        "matched_event_count": 2,
                        "boosted_candidate_count": 1,
                        "boosted_unique_paths": 1,
                    },
                    "chunk_guard": {
                        "mode": "report_only",
                        "reason": "report_only",
                        "candidate_pool": 3,
                        "filtered_count": 1,
                        "retained_count": 2,
                        "retained_refs": ["pkg.service_v1", "pkg.helper"],
                        "filtered_refs": ["pkg.service_v2"],
                    },
                    "chunk_guard_expectation": {
                        "scenario": "stale_majority",
                        "expected_retained_hit": True,
                        "expected_filtered_hit_count": 1,
                        "expected_filtered_hit_rate": 1.0,
                        "report_only_improved": True,
                    },
                    "latency_ms": 5,
                }
            ],
        }
    )

    assert "Threshold profile: strict" in report
    assert "Warmup runs: 2" in report
    assert "Include plans: false" in report
    assert "Include case details: false" in report
    assert "## Baseline" in report
    assert "## Delta vs Baseline" in report
    assert "## Task Success Summary" in report
    assert "## Comparison Lanes" in report
    assert "## Evidence Insufficiency Summary" in report
    assert "## Source Plan Granularity Summary" in report
    assert "## Graph Lookup Summary" in report
    assert "## Repomap Seed Summary" in report
    assert "Seed count means: worktree=1.00; subgraph=2.00; seed_candidates=3.00" in report
    assert "Cache hit ratios: cache=0.5000; precompute=1.0000" in report
    assert "Normalization ratios: log1p=1.0000; linear=0.0000" in report
    assert "Weight means: scip=0.30; xref=0.20; query_xref=0.20; symbol=0.10; import=0.10; coverage=0.10" in report
    assert "Guard summary: guarded=0.5000; candidate_count_mean=6.00; max_candidates_mean=4.00; min_terms_mean=1.00; max_terms_mean=5.00" in report
    assert "Signal maxima mean: inbound=4.00; xref=3.00; query=2.00; symbol=1.00; import=1.00; coverage=0.67" in report
    assert "Guard reason ratios: candidate_count=0.5000; query_terms_too_few=0.2500; query_terms_too_many=0.0000" in report
    assert "## Deep Symbol Summary" in report
    assert "## Chunk Stage Miss Summary" in report
    assert "## Decision Observability Summary" in report
    assert "## Long-Term Explainability Summary" in report
    assert "## Stage Latency Summary" in report
    assert "## SLO Budget Summary" in report
    assert "## Retrieval-to-Task Gaps" in report
    assert "## Regression Thresholds" in report
    assert "## Regression" in report
    assert "## Plugin Policy Summary" in report
    assert "Mode: strict" in report
    assert "| blocked | 1 |" in report
    assert "| remote_applied | 1.0000 |" in report
    assert "### By-stage Totals" in report
    assert "### By-stage Per-case Mean" in report
    assert "| source_plan | 2 | 1 | 1 | 0 | 1 |" in report
    assert "failed_checks: precision_at_k" in report
    assert "precision_at_k: 0.5000 < 0.5900" in report
    assert "dependency_recall" in report
    assert "task_success_rate" in report
    assert "task_success_mode: negative_control" in report
    assert "comparison_lane: stale_majority" in report
    assert "retrieval_surface: deep_symbol" in report
    assert "deep_symbol_case: 1.0000" in report
    assert "| stale_majority | 1 | 0.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.3333 | 1.0000 | 1.0000 | 2.0000 |" in report
    assert "task_success_failed_checks: validation_tests" in report
    assert "evidence_insufficiency_reason: missing_validation" in report
    assert "evidence_insufficiency_signals: missing_validation_tests, noisy_hit" in report
    assert "notes_hit_ratio: 0.5000" in report
    assert "profile_selected_count: 2.0000" in report
    assert "capture_triggered: 1.0000" in report
    assert "ltm_selected_count: 2.0000" in report
    assert "ltm_attribution_count: 1.0000" in report
    assert "ltm_graph_neighbor_count: 1.0000" in report
    assert "ltm_plan_constraint_count: 1.0000" in report
    assert "feedback_enabled: 1.0000" in report
    assert "feedback_boosted_count: 1.0000" in report
    assert "Selected cases: 1/1 (1.0000)" in report
    assert "Attribution cases: 1/1 (1.0000)" in report
    assert "Graph-neighbor cases: 1/1 (1.0000)" in report
    assert "Plan-constraint cases: 1/1 (1.0000)" in report
    assert "| selected_count_mean | 2.0000 |" in report
    assert "| attribution_count_mean | 1.0000 |" in report
    assert "| graph_neighbor_count_mean | 1.0000 |" in report
    assert "| plan_constraint_count_mean | 1.0000 |" in report
    assert "chunk_stage_miss: source_plan_pack_miss" in report
    assert "decision_event: index | retry | candidate_postprocess | reason=low_candidate_count | outcome=applied" in report
    assert "decision_event: skills | skip | skills_hydration | reason=token_budget_exhausted" in report
    assert "slo_downgrade_signals: parallel_docs_timeout, embedding_time_budget_exceeded, chunk_semantic_fallback" in report
    assert "parallel_docs_timeout_ratio" in report
    assert "skills_token_budget_used_mean" in report
    assert "skills_budget_exhausted_ratio" in report
    assert "skills_route_latency_p95_ms" in report
    assert "ltm_hit_ratio" in report
    assert "ltm_effective_hit_rate" in report
    assert "ltm_false_help_rate" in report
    assert "ltm_stale_hit_rate" in report
    assert "ltm_replay_drift_rate" in report
    assert "ltm_latency_overhead_ms" in report
    assert "dev_issue_capture_rate" in report
    assert "contextual_sidecar_parent_symbol_chunk_count_mean" in report
    assert "contextual_sidecar_reference_hint_coverage_ratio" in report
    assert "robust_signature_count_mean" in report
    assert "robust_signature_coverage_ratio" in report
    assert "graph_prior_chunk_count_mean" in report
    assert "graph_transfer_count_mean" in report
    assert "graph_closure_enabled_ratio" in report
    assert "graph_closure_boosted_chunk_count_mean" in report
    assert "graph_closure_support_edge_count_mean" in report
    assert "topological_shield_enabled_ratio" in report
    assert "topological_shield_attenuated_chunk_count_mean" in report
    assert "skills_precomputed_route_ratio" in report
    assert "plan_replay_cache_enabled_ratio" in report
    assert "plan_replay_cache_hit_ratio" in report
    assert "plan_replay_cache_stale_hit_safe_ratio" in report
    assert "validation_probe_enabled_ratio" in report
    assert "validation_probe_executed_count_mean" in report
    assert "validation_probe_failure_rate" in report
    assert "| source_plan_pack_miss | 1 | 1.0000 |" in report
    assert "source_plan_direct_evidence_ratio" in report
    assert "source_plan_symbol_count_mean" in report
    assert "source_plan_signature_count_mean" in report
    assert "source_plan_skeleton_count_mean" in report
    assert "source_plan_robust_signature_count_mean" in report
    assert "source_plan_symbol_ratio" in report
    assert "source_plan_signature_ratio" in report
    assert "source_plan_skeleton_ratio" in report
    assert "source_plan_robust_signature_ratio" in report
    assert "source_plan_neighbor_context_ratio" in report
    assert "source_plan_hint_only_ratio" in report
    assert "source_plan_graph_closure_preference_enabled_ratio" in report
    assert "source_plan_graph_closure_bonus_candidate_count_mean" in report
    assert "source_plan_granularity_preferred_count_mean" in report
    assert "source_plan_packed_path_count_mean" in report
    assert "multi_channel_rrf_granularity_count_mean" in report
    assert "multi_channel_rrf_granularity_pool_ratio" in report
    assert "Evidence mix: direct=0.7500, neighbor_context=0.2500, hint_only=0.0000" in report
    assert "Packing granularity-preferred count mean: 1.00" in report
    assert "Channel enabled ratio: 1.0000; applied ratio: 1.0000" in report
    assert "Granularity channel case ratio: 1.0000; count mean: 2.00" in report
    assert "Fusion pool size mean: 4.00; granularity/pool ratio: 0.5000" in report
    assert "Enabled ratio: 1.0000; boosted count mean: 2.00; pool size mean: 4.00" in report
    assert "Query terms mean: 3.00; query-hit mean: 1.00; boosted/pool ratio: 0.5000; query-hit/pool ratio: 0.2500" in report
    assert "Signal paths mean: scip=2.00, xref=3.00, symbol=1.00, import=1.00, coverage=2.00" in report
    assert "Deep symbol case count: 2.00; recall: 1.0000" in report
    assert "## Native SCIP Summary" in report
    assert "Native SCIP loaded rate: 1.0000" in report
    assert "native_scip_document_count_mean" in report
    assert "native_scip_definition_occurrence_count_mean" in report
    assert "native_scip_reference_occurrence_count_mean" in report
    assert "native_scip_symbol_definition_count_mean" in report
    assert "| symbol | 1.00 | 0.5000 |" in report
    assert "| signature | 0.75 | 0.3750 |" in report
    assert "| skeleton | 0.50 | 0.2500 |" in report
    assert "| robust_signature | 0.25 | 0.1250 |" in report
    assert "evidence_insufficient_rate" in report
    assert "missing_validation_rate" in report
    assert "parallel_time_budget_ms_mean" in report
    assert "validation_test_count: 0" in report
    assert "validation_test_count" in report
    assert "plan_replay_cache: stage=source_plan, reason=hit, stored=False" in report
    assert "repomap_seed: worktree_seed_count=1, subgraph_seed_count=2, seed_candidates_count=3, cache_hit=True, precompute_hit=False" in report
    assert "chunk_guard_expectation: scenario=stale_majority, expected_retained_hit=True, expected_filtered_hit_count=1, expected_filtered_hit_rate=1.0000, report_only_improved=True" in report
    assert "robust_signature: count=1, coverage_ratio=0.5000" in report
    assert "graph_closure: enabled=True, boosted_chunk_count=2, coverage_ratio=0.5000, anchor_count=1, support_edge_count=3, total=0.1400" in report
    assert "index_fusion_granularity: enabled=True, applied=True, granularity_count=2, pool_size=4, granularity_pool_ratio=0.5000" in report
    assert "graph_lookup: enabled=True, reason=candidate_count_guarded, guarded=True, boosted_count=2, weights=scip:0.3000|xref:0.2000|query_xref:0.2000|symbol:0.1000|import:0.1000|coverage:0.1000, candidate_count=6, pool_size=4, query_terms_count=3, normalization=log1p, guard_max_candidates=4, guard_min_query_terms=1, guard_max_query_terms=5, query_hit_paths=1, scip_signal_paths=2, xref_signal_paths=3, symbol_hit_paths=1, import_hit_paths=1, coverage_hit_paths=2, max_inbound=4.0000, max_xref_count=3.0000, max_query_hits=2.0000, max_symbol_hits=1.0000, max_import_hits=1.0000, max_query_coverage=0.6667, boosted_path_ratio=0.5000, query_hit_path_ratio=0.2500" in report
    assert "source_plan_packing: graph_closure_preference_enabled=True, graph_closure_bonus_candidate_count=2, graph_closure_preferred_count=1, granularity_preferred_count=1, focused_file_promoted_count=1, packed_path_count=2, reason=graph_closure_preferred" in report
    assert "preference_capture: notes_hit_ratio=0.5000, profile_selected_count=2, capture_triggered=True" in report
    assert "ltm_explainability: selected_count=2, attribution_count=1, graph_neighbor_count=1, plan_constraint_count=1" in report
    assert (
        "ltm_attribution_preview: runtime.validation.git fallback_policy reuse_checkout_or_skip | graph: reuse_checkout_or_skip recommended_for runtime.validation.git"
        in report
    )
    assert "feedback_boost: enabled=True, reason=ok, event_count=4, matched_event_count=2, boosted_candidate_count=1, boosted_unique_paths=1" in report
    assert "chunk_stage_miss_details: oracle_file_path=src/ace_lite/benchmark/case_evaluation.py, file_present=True, raw_chunk_present=True, source_plan_chunk_present=False" in report
    assert "embedding_similarity_mean" in report
    assert "latency_median_ms" in report


def test_write_results_emits_summary_sidecar(tmp_path: Path) -> None:
    results = {
        "generated_at": "2026-02-12T00:00:00Z",
        "repo": "demo",
        "root": ".",
        "case_count": 1,
        "metrics": {
            "recall_at_k": 1.0,
            "precision_at_k": 0.5,
            "task_success_rate": 0.5,
            "utility_rate": 0.5,
            "noise_rate": 0.5,
            "dependency_recall": 0.6,
            "repomap_latency_p95_ms": 8.0,
            "repomap_latency_median_ms": 7.0,
            "latency_p95_ms": 11.0,
            "latency_median_ms": 9.0,
            "chunk_hit_at_k": 0.4,
            "chunks_per_file_mean": 2.0,
            "chunk_budget_used": 12.0,
            "robust_signature_count_mean": 1.0,
            "robust_signature_coverage_ratio": 0.5,
            "graph_closure_enabled_ratio": 1.0,
            "graph_closure_boosted_chunk_count_mean": 2.0,
            "source_plan_graph_closure_preference_enabled_ratio": 1.0,
            "source_plan_packed_path_count_mean": 2.0,
            "validation_test_count": 3.0,
            "plan_replay_cache_enabled_ratio": 1.0,
            "plan_replay_cache_hit_ratio": 0.5,
            "plan_replay_cache_stale_hit_safe_ratio": 1.0,
            "evidence_insufficient_rate": 0.5,
        },
        "regression": {
            "regressed": True,
            "failed_checks": ["precision_at_k", "validation_test_count"],
            "failed_thresholds": [],
        },
        "task_success_summary": {
            "case_count": 1,
            "positive_case_count": 0,
            "negative_control_case_count": 1,
            "task_success_rate": 0.5,
            "positive_task_success_rate": 0.0,
            "negative_control_task_success_rate": 0.5,
            "retrieval_task_gap_count": 1,
            "retrieval_task_gap_rate": 1.0,
        },
        "comparison_lane_summary": {
            "total_case_count": 1,
            "labeled_case_count": 1,
            "lane_count": 1,
            "lanes": [
                {
                    "comparison_lane": "stale_majority",
                    "case_count": 1,
                    "task_success_rate": 0.5,
                    "recall_at_k": 1.0,
                    "chunk_guard_enabled_ratio": 1.0,
                    "chunk_guard_report_only_ratio": 1.0,
                    "chunk_guard_filtered_case_rate": 1.0,
                    "chunk_guard_filtered_count_mean": 2.0,
                    "chunk_guard_filter_ratio_mean": 0.5,
                    "chunk_guard_expected_retained_hit_rate_mean": 1.0,
                    "chunk_guard_report_only_improved_rate": 1.0,
                    "chunk_guard_pairwise_conflict_count_mean": 3.0,
                }
            ],
        },
        "evidence_insufficiency_summary": {
            "case_count": 1,
            "applicable_case_count": 1,
            "excluded_negative_control_case_count": 0,
            "evidence_insufficient_count": 1,
            "evidence_insufficient_rate": 1.0,
            "reasons": {"missing_validation": 1},
            "signals": {"missing_validation_tests": 1},
        },
        "chunk_stage_miss_summary": {
            "case_count": 1,
            "oracle_case_count": 1,
            "classified_case_count": 1,
            "classified_case_rate": 1.0,
            "labels": {"candidate_chunks_miss": 1},
        },
        "decision_observability_summary": {
            "case_count": 1,
            "case_with_decisions_count": 1,
            "case_with_decisions_rate": 1.0,
            "decision_event_count": 1,
            "actions": {"retry": 1},
            "targets": {"candidate_postprocess": 1},
            "reasons": {"low_candidate_count": 1},
            "outcomes": {"applied": 1},
        },
        "ltm_explainability_summary": {
            "case_count": 1,
            "selected_case_count": 1,
            "selected_case_rate": 1.0,
            "selected_count_mean": 2.0,
            "attribution_case_count": 1,
            "attribution_case_rate": 1.0,
            "attribution_count_mean": 1.0,
            "graph_neighbor_case_count": 1,
            "graph_neighbor_case_rate": 1.0,
            "graph_neighbor_count_mean": 1.0,
            "plan_constraint_case_count": 1,
            "plan_constraint_case_rate": 1.0,
            "plan_constraint_count_mean": 1.0,
        },
        "cases": [],
    }

    outputs = write_results(results, output_dir=tmp_path)

    summary_path = Path(outputs["summary_json"])
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["regressed"] is True
    assert summary["failed_checks"] == ["precision_at_k", "validation_test_count"]
    assert summary["metrics"]["task_success_rate"] == 0.5
    assert summary["task_success_summary"]["retrieval_task_gap_count"] == 1
    assert summary["metrics"]["validation_test_count"] == 3.0
    assert summary["metrics"]["plan_replay_cache_hit_ratio"] == 0.5
    assert summary["metrics"]["robust_signature_count_mean"] == 1.0
    assert summary["metrics"]["robust_signature_coverage_ratio"] == 0.5
    assert summary["metrics"]["graph_closure_enabled_ratio"] == 1.0
    assert summary["metrics"]["source_plan_graph_closure_preference_enabled_ratio"] == 1.0
    assert summary["metrics"]["source_plan_direct_evidence_ratio"] == 0.0
    assert summary["metrics"]["evidence_insufficient_rate"] == 0.5
    assert summary["comparison_lane_summary"]["lane_count"] == 1
    assert summary["comparison_lane_summary"]["lanes"][0]["comparison_lane"] == "stale_majority"
    assert summary["evidence_insufficiency_summary"]["evidence_insufficient_count"] == 1
    assert summary["chunk_stage_miss_summary"]["labels"] == {
        "candidate_chunks_miss": 1
    }
    assert summary["decision_observability_summary"]["decision_event_count"] == 1
    assert summary["ltm_explainability_summary"]["selected_count_mean"] == 2.0
    assert summary["ltm_explainability_summary"]["plan_constraint_case_count"] == 1


def test_build_results_summary_defaults_missing_fields() -> None:
    summary = build_results_summary({"repo": "demo"})

    assert summary["repo"] == "demo"
    assert summary["regressed"] is False
    assert summary["failed_checks"] == []
    assert list(summary["metrics"].keys()) == list(ALL_METRIC_ORDER)


def test_build_results_summary_preserves_adaptive_router_arm_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "adaptive_router_arm_summary": {
                "case_count": 2,
                "enabled_case_count": 2,
                "enabled_case_rate": 1.0,
                "executed": {
                    "arm_count": 1,
                    "observed_case_count": 2,
                    "arms": [{"arm_id": "feature", "case_count": 2, "case_rate": 1.0}],
                },
                "shadow": {
                    "arm_count": 1,
                    "observed_case_count": 2,
                    "arms": [
                        {"arm_id": "feature_graph", "case_count": 2, "case_rate": 1.0}
                    ],
                },
            },
        }
    )

    assert summary["adaptive_router_arm_summary"]["executed"]["arms"][0]["arm_id"] == "feature"
    assert summary["adaptive_router_arm_summary"]["shadow"]["arms"][0]["arm_id"] == "feature_graph"


def test_build_results_summary_preserves_adaptive_router_pair_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "adaptive_router_pair_summary": {
                "case_count": 2,
                "comparable_case_count": 2,
                "comparable_case_rate": 1.0,
                "disagreement_case_count": 2,
                "disagreement_rate": 1.0,
                "pairs": [
                    {
                        "executed_arm_id": "feature",
                        "shadow_arm_id": "feature_graph",
                        "case_count": 2,
                        "case_rate": 1.0,
                        "disagreement_case_count": 2,
                        "disagreement_rate": 1.0,
                        "latency_mean_ms": 12.0,
                        "latency_p95_ms": 14.0,
                        "index_latency_mean_ms": 4.0,
                        "index_latency_p95_ms": 5.0,
                    }
                ],
            },
        }
    )

    assert summary["adaptive_router_pair_summary"]["pairs"][0]["executed_arm_id"] == "feature"
    assert summary["adaptive_router_pair_summary"]["pairs"][0]["shadow_arm_id"] == "feature_graph"
    assert summary["adaptive_router_pair_summary"]["pairs"][0]["disagreement_rate"] == 1.0


def test_build_results_summary_preserves_adaptive_router_observability_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "adaptive_router_observability_summary": {
                "case_count": 2,
                "enabled_case_count": 2,
                "enabled_case_rate": 1.0,
                "shadow_coverage_case_count": 2,
                "shadow_coverage_rate": 1.0,
                "comparable_case_count": 2,
                "comparable_case_rate": 1.0,
                "agreement_case_count": 1,
                "agreement_rate": 0.5,
                "disagreement_case_count": 1,
                "disagreement_rate": 0.5,
                "executed_arm_count": 1,
                "shadow_arm_count": 2,
                "shadow_source_counts": {"fallback": 1, "model": 1},
                "executed_arms": [{"arm_id": "feature", "case_count": 2, "case_rate": 1.0}],
                "shadow_arms": [
                    {"arm_id": "feature_graph", "case_count": 1, "case_rate": 0.5},
                    {"arm_id": "general_hybrid", "case_count": 1, "case_rate": 0.5},
                ],
            },
        }
    )

    assert summary["adaptive_router_observability_summary"]["agreement_rate"] == 0.5
    assert summary["adaptive_router_observability_summary"]["shadow_coverage_rate"] == 1.0
    assert summary["adaptive_router_observability_summary"]["executed_arms"][0]["arm_id"] == "feature"
    assert summary["adaptive_router_observability_summary"]["shadow_source_counts"] == {
        "fallback": 1,
        "model": 1,
    }


def test_build_results_summary_preserves_retrieval_control_plane_gate_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "retrieval_control_plane_gate_summary": {
                "regression_evaluated": True,
                "benchmark_regression_detected": False,
                "benchmark_regression_passed": True,
                "failed_checks": [],
                "adaptive_router_shadow_coverage": 0.9,
                "adaptive_router_shadow_coverage_threshold": 0.8,
                "adaptive_router_shadow_coverage_passed": True,
                "risk_upgrade_precision_gain": 0.12,
                "risk_upgrade_precision_gain_threshold": 0.0,
                "risk_upgrade_precision_gain_passed": True,
                "latency_p95_ms": 640.0,
                "latency_p95_ms_threshold": 850.0,
                "latency_p95_ms_passed": True,
                "gate_passed": True,
            },
        }
    )

    assert summary["retrieval_control_plane_gate_summary"]["gate_passed"] is True
    assert (
        summary["retrieval_control_plane_gate_summary"][
            "adaptive_router_shadow_coverage"
        ]
        == 0.9
    )


def test_build_results_summary_preserves_retrieval_frontier_gate_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "retrieval_frontier_gate_summary": {
                "failed_checks": ["precision_at_k"],
                "deep_symbol_case_recall": 0.95,
                "deep_symbol_case_recall_threshold": 0.9,
                "deep_symbol_case_recall_passed": True,
                "native_scip_loaded_rate": 0.8,
                "native_scip_loaded_rate_threshold": 0.7,
                "native_scip_loaded_rate_passed": True,
                "precision_at_k": 0.61,
                "precision_at_k_threshold": 0.64,
                "precision_at_k_passed": False,
                "noise_rate": 0.31,
                "noise_rate_threshold": 0.36,
                "noise_rate_passed": True,
                "gate_passed": False,
            },
        }
    )

    assert summary["retrieval_frontier_gate_summary"]["gate_passed"] is False
    assert summary["retrieval_frontier_gate_summary"]["failed_checks"] == [
        "precision_at_k"
    ]


def test_build_results_summary_preserves_repomap_seed_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "repomap_seed_summary": {
                "worktree_seed_count_mean": 1.5,
                "subgraph_seed_count_mean": 2.5,
                "seed_candidates_count_mean": 3.5,
                "cache_hit_ratio": 0.75,
                "precompute_hit_ratio": 0.25,
            },
        }
    )

    assert summary["repomap_seed_summary"] == {
        "worktree_seed_count_mean": 1.5,
        "subgraph_seed_count_mean": 2.5,
        "seed_candidates_count_mean": 3.5,
        "cache_hit_ratio": 0.75,
        "precompute_hit_ratio": 0.25,
    }


def test_build_results_summary_preserves_validation_probe_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "validation_probe_summary": {
                "validation_test_count": 1.5,
                "probe_enabled_ratio": 1.0,
                "probe_executed_count_mean": 2.0,
                "probe_failure_rate": 0.5,
            },
        }
    )

    assert summary["validation_probe_summary"] == {
        "validation_test_count": 1.5,
        "probe_enabled_ratio": 1.0,
        "probe_executed_count_mean": 2.0,
        "probe_failure_rate": 0.5,
    }


def test_build_results_summary_preserves_agent_loop_control_plane_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "agent_loop_control_plane_summary": {
                "case_count": 2,
                "observed_case_count": 2,
                "observed_case_rate": 1.0,
                "enabled_case_count": 2,
                "enabled_case_rate": 1.0,
                "attempted_case_count": 1,
                "attempted_case_rate": 0.5,
                "replay_safe_case_count": 2,
                "replay_safe_case_rate": 1.0,
                "actions_requested_mean": 1.0,
                "actions_executed_mean": 0.5,
                "request_more_context_case_count": 1,
                "request_more_context_case_rate": 0.5,
                "request_source_plan_retry_case_count": 1,
                "request_source_plan_retry_case_rate": 0.5,
                "request_validation_retry_case_count": 0,
                "request_validation_retry_case_rate": 0.0,
                "dominant_stop_reason": "completed",
                "dominant_last_policy_id": "source_plan_refresh",
            },
        }
    )

    assert summary["agent_loop_control_plane_summary"]["attempted_case_rate"] == 0.5
    assert (
        summary["agent_loop_control_plane_summary"]["dominant_last_policy_id"]
        == "source_plan_refresh"
    )


def test_build_results_summary_preserves_validation_branch_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "validation_branch_summary": {
                "case_count": 2.0,
                "case_rate": 0.5,
                "candidate_count_mean": 3.0,
                "rejected_count_mean": 2.0,
                "selection_present_ratio": 1.0,
                "patch_artifact_present_ratio": 1.0,
                "archive_present_ratio": 1.0,
                "parallel_case_rate": 1.0,
                "winner_pass_rate": 0.5,
                "winner_regressed_rate": 0.25,
                "winner_score_mean": 104.0,
                "winner_after_issue_count_mean": 0.5,
            },
        }
    )

    assert summary["validation_branch_summary"] == {
        "case_count": 2.0,
        "case_rate": 0.5,
        "candidate_count_mean": 3.0,
        "rejected_count_mean": 2.0,
        "selection_present_ratio": 1.0,
        "patch_artifact_present_ratio": 1.0,
        "archive_present_ratio": 1.0,
        "parallel_case_rate": 1.0,
        "winner_pass_rate": 0.5,
        "winner_regressed_rate": 0.25,
        "winner_score_mean": 104.0,
        "winner_after_issue_count_mean": 0.5,
    }


def test_build_results_summary_preserves_validation_branch_gate_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "validation_branch_gate_summary": {
                "failed_checks": ["validation_branch_archive_present_ratio"],
                "case_count": 1.0,
                "case_rate": 0.25,
                "case_count_threshold": 1.0,
                "case_count_passed": True,
                "selection_present_ratio": 1.0,
                "selection_present_ratio_threshold": 1.0,
                "selection_present_ratio_passed": True,
                "patch_artifact_present_ratio": 1.0,
                "patch_artifact_present_ratio_threshold": 1.0,
                "patch_artifact_present_ratio_passed": True,
                "archive_present_ratio": 0.0,
                "archive_present_ratio_threshold": 1.0,
                "archive_present_ratio_passed": False,
                "parallel_case_rate": 1.0,
                "parallel_case_rate_threshold": 1.0,
                "parallel_case_rate_passed": True,
                "gate_passed": False,
            },
        }
    )

    assert summary["validation_branch_gate_summary"]["failed_checks"] == [
        "validation_branch_archive_present_ratio"
    ]
    assert summary["validation_branch_gate_summary"]["gate_passed"] is False


def test_build_results_summary_preserves_source_plan_card_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "source_plan_card_summary": {
                "evidence_card_count_mean": 2.0,
                "file_card_count_mean": 3.0,
                "chunk_card_count_mean": 5.0,
                "validation_card_present_ratio": 0.5,
            },
        }
    )

    assert summary["source_plan_card_summary"] == {
        "evidence_card_count_mean": 2.0,
        "file_card_count_mean": 3.0,
        "chunk_card_count_mean": 5.0,
        "validation_card_present_ratio": 0.5,
    }


def test_build_results_summary_preserves_source_plan_validation_feedback_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "source_plan_validation_feedback_summary": {
                "present_ratio": 1.0,
                "issue_count_mean": 2.0,
                "failure_rate": 1.0,
                "probe_issue_count_mean": 1.0,
                "probe_executed_count_mean": 1.0,
                "probe_failure_rate": 1.0,
                "selected_test_count_mean": 1.0,
                "executed_test_count_mean": 1.0,
            },
        }
    )

    assert summary["source_plan_validation_feedback_summary"] == {
        "present_ratio": 1.0,
        "issue_count_mean": 2.0,
        "failure_rate": 1.0,
        "probe_issue_count_mean": 1.0,
        "probe_executed_count_mean": 1.0,
        "probe_failure_rate": 1.0,
        "selected_test_count_mean": 1.0,
        "executed_test_count_mean": 1.0,
    }


def test_build_results_summary_preserves_source_plan_failure_signal_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "source_plan_failure_signal_summary": {
                "present_ratio": 1.0,
                "issue_count_mean": 2.0,
                "failure_rate": 1.0,
                "probe_issue_count_mean": 1.0,
                "probe_executed_count_mean": 1.0,
                "probe_failure_rate": 1.0,
                "selected_test_count_mean": 1.0,
                "executed_test_count_mean": 1.0,
                "replay_cache_origin_ratio": 1.0,
                "observability_origin_ratio": 0.0,
                "source_plan_origin_ratio": 0.0,
                "validate_step_origin_ratio": 0.0,
            },
        }
    )

    assert summary["source_plan_failure_signal_summary"] == {
        "present_ratio": 1.0,
        "issue_count_mean": 2.0,
        "failure_rate": 1.0,
        "probe_issue_count_mean": 1.0,
        "probe_executed_count_mean": 1.0,
        "probe_failure_rate": 1.0,
        "selected_test_count_mean": 1.0,
        "executed_test_count_mean": 1.0,
        "replay_cache_origin_ratio": 1.0,
        "observability_origin_ratio": 0.0,
        "source_plan_origin_ratio": 0.0,
        "validate_step_origin_ratio": 0.0,
    }


def test_build_results_summary_preserves_learning_router_rollout_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "learning_router_rollout_summary": {
                "case_count": 4,
                "router_enabled_case_count": 3,
                "router_enabled_case_rate": 0.75,
                "shadow_mode_case_count": 2,
                "shadow_mode_case_rate": 0.5,
                "shadow_ready_case_count": 2,
                "shadow_ready_case_rate": 0.5,
                "source_plan_card_present_case_count": 3,
                "source_plan_card_present_case_rate": 0.75,
                "failure_signal_blocked_case_count": 1,
                "failure_signal_blocked_case_rate": 0.25,
                "eligible_case_count": 1,
                "eligible_case_rate": 0.25,
                "reason_counts": {
                    "adaptive_router_disabled": 1,
                    "eligible_pending_guarded_rollout": 1,
                },
            },
        }
    )

    assert summary["learning_router_rollout_summary"] == {
        "case_count": 4,
        "router_enabled_case_count": 3,
        "router_enabled_case_rate": 0.75,
        "shadow_mode_case_count": 2,
        "shadow_mode_case_rate": 0.5,
        "shadow_ready_case_count": 2,
        "shadow_ready_case_rate": 0.5,
        "source_plan_card_present_case_count": 3,
        "source_plan_card_present_case_rate": 0.75,
        "failure_signal_blocked_case_count": 1,
        "failure_signal_blocked_case_rate": 0.25,
        "eligible_case_count": 1,
        "eligible_case_rate": 0.25,
        "reason_counts": {
            "adaptive_router_disabled": 1,
            "eligible_pending_guarded_rollout": 1,
        },
    }


def test_build_results_summary_preserves_deep_symbol_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "deep_symbol_summary": {
                "case_count": 3.0,
                "recall": 0.95,
            },
        }
    )

    assert summary["deep_symbol_summary"] == {
        "case_count": 3.0,
        "recall": 0.95,
    }


def test_build_results_summary_preserves_native_scip_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "native_scip_summary": {
                "loaded_rate": 0.8,
                "document_count_mean": 5.0,
                "definition_occurrence_count_mean": 7.0,
                "reference_occurrence_count_mean": 11.0,
                "symbol_definition_count_mean": 3.0,
            },
        }
    )

    assert summary["native_scip_summary"] == {
        "loaded_rate": 0.8,
        "document_count_mean": 5.0,
        "definition_occurrence_count_mean": 7.0,
        "reference_occurrence_count_mean": 11.0,
        "symbol_definition_count_mean": 3.0,
    }


def test_build_report_markdown_prefers_top_level_repomap_seed_summary() -> None:
    report = build_report_markdown(
        {
            "repo": "demo",
            "metrics": {
                "task_success_rate": 1.0,
                "repomap_worktree_seed_count_mean": 0.0,
                "repomap_subgraph_seed_count_mean": 0.0,
                "repomap_seed_candidates_count_mean": 0.0,
                "repomap_cache_hit_ratio": 0.0,
                "repomap_precompute_hit_ratio": 0.0,
            },
            "repomap_seed_summary": {
                "worktree_seed_count_mean": 4.0,
                "subgraph_seed_count_mean": 5.0,
                "seed_candidates_count_mean": 6.0,
                "cache_hit_ratio": 0.75,
                "precompute_hit_ratio": 0.25,
            },
        }
    )

    assert "## Repomap Seed Summary" in report
    assert "Seed count means: worktree=4.00; subgraph=5.00; seed_candidates=6.00" in report
    assert "Cache hit ratios: cache=0.7500; precompute=0.2500" in report


def test_build_report_markdown_prefers_top_level_validation_probe_summary() -> None:
    report = build_report_markdown(
        {
            "repo": "demo",
            "metrics": {
                "task_success_rate": 1.0,
                "validation_test_count": 0.0,
                "validation_probe_enabled_ratio": 0.0,
                "validation_probe_executed_count_mean": 0.0,
                "validation_probe_failure_rate": 0.0,
            },
            "validation_probe_summary": {
                "validation_test_count": 1.5,
                "probe_enabled_ratio": 1.0,
                "probe_executed_count_mean": 2.0,
                "probe_failure_rate": 0.5,
            },
        }
    )

    assert "## Validation Probe Summary" in report
    assert "Validation tests mean: 1.5000; probe enabled ratio: 1.0000" in report
    assert "Probe executed count mean: 2.0000; failure rate: 0.5000" in report


def test_build_report_markdown_includes_graph_context_source_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-24T00:00:00Z",
            "repo": "demo",
            "case_count": 1,
            "include_plan_payload": False,
            "include_case_details": True,
            "metrics": {
                "recall_at_k": 1.0,
                "precision_at_k": 1.0,
                "task_success_rate": 1.0,
                "utility_rate": 1.0,
                "noise_rate": 0.0,
                "dependency_recall": 1.0,
                "repomap_latency_p95_ms": 1.0,
                "repomap_latency_median_ms": 1.0,
                "latency_p95_ms": 1.0,
                "latency_median_ms": 1.0,
                "graph_source_provider_loaded_ratio": 1.0,
                "graph_source_projection_fallback_ratio": 1.0,
                "graph_source_edge_count_mean": 5.0,
                "graph_source_inbound_signal_chunk_count_mean": 2.0,
                "graph_source_inbound_signal_coverage_ratio": 1.0,
                "graph_source_centrality_signal_chunk_count_mean": 2.0,
                "graph_source_centrality_signal_coverage_ratio": 1.0,
                "graph_source_pagerank_signal_chunk_count_mean": 1.0,
                "graph_source_pagerank_signal_coverage_ratio": 0.5,
            },
            "cases": [
                {
                    "case_id": "c1",
                    "query": "where graph source",
                    "policy_profile": "graph",
                    "docs_hit": 0.0,
                    "hint_inject": 0.0,
                    "recall_hit": 1.0,
                    "first_hit_rank": 1,
                    "hit_at_1": 1.0,
                    "reciprocal_rank": 1.0,
                    "task_success_hit": 1.0,
                    "task_success_mode": "positive",
                    "precision_at_k": 1.0,
                    "noise_rate": 0.0,
                    "notes_hit_ratio": 0.0,
                    "profile_selected_count": 0.0,
                    "capture_triggered": 0.0,
                    "ltm_selected_count": 0.0,
                    "ltm_attribution_count": 0.0,
                    "ltm_graph_neighbor_count": 0.0,
                    "ltm_plan_constraint_count": 0.0,
                    "feedback_enabled": 0.0,
                    "feedback_matched_event_count": 0.0,
                    "feedback_boosted_count": 0.0,
                    "multi_channel_rrf_applied": 0.0,
                    "multi_channel_rrf_granularity_count": 0.0,
                    "multi_channel_rrf_granularity_pool_ratio": 0.0,
                    "graph_lookup_enabled": 0.0,
                    "graph_lookup_boosted_count": 0.0,
                    "graph_lookup_query_hit_paths": 0.0,
                    "native_scip_loaded": 1.0,
                    "source_plan_direct_evidence_ratio": 0.0,
                    "source_plan_neighbor_context_ratio": 0.0,
                    "source_plan_hint_only_ratio": 0.0,
                    "graph_closure_enabled": 0.0,
                    "graph_closure_boosted_chunk_count": 0.0,
                    "graph_closure_coverage_ratio": 0.0,
                    "graph_closure_anchor_count": 0.0,
                    "graph_closure_support_edge_count": 0.0,
                    "graph_closure_total": 0.0,
                    "graph_source_provider_loaded": 1.0,
                    "graph_source_projection_fallback": 1.0,
                    "graph_source_edge_count": 5.0,
                    "graph_source_inbound_signal_chunk_count": 2.0,
                    "graph_source_inbound_signal_coverage_ratio": 1.0,
                    "graph_source_centrality_signal_chunk_count": 2.0,
                    "graph_source_centrality_signal_coverage_ratio": 1.0,
                    "graph_source_pagerank_signal_chunk_count": 1.0,
                    "graph_source_pagerank_signal_coverage_ratio": 0.5,
                    "source_plan_graph_closure_preference_enabled": 0.0,
                    "source_plan_graph_closure_bonus_candidate_count": 0.0,
                    "source_plan_graph_closure_preferred_count": 0.0,
                    "source_plan_focused_file_promoted_count": 0.0,
                    "source_plan_packed_path_count": 0.0,
                    "plan_replay_cache_enabled": 0.0,
                    "plan_replay_cache_hit": 0.0,
                    "plan_replay_cache_stale_hit_safe": 0.0,
                    "chunk_guard_enabled": 0.0,
                    "chunk_guard_report_only": 0.0,
                    "chunk_guard_filtered_count": 0.0,
                    "chunk_guard_filter_ratio": 0.0,
                    "chunk_guard_pairwise_conflict_count": 0.0,
                    "chunk_guard_fallback": 0.0,
                    "robust_signature_count": 0.0,
                    "robust_signature_coverage_ratio": 0.0,
                    "retrieval_context_chunk_count": 0.0,
                    "retrieval_context_coverage_ratio": 0.0,
                    "dependency_recall": 1.0,
                    "graph_context_source": {
                        "provider_loaded": True,
                        "projection_fallback": True,
                        "edge_count": 5,
                        "inbound_signal_chunk_count": 2,
                        "inbound_signal_coverage_ratio": 1.0,
                        "centrality_signal_chunk_count": 2,
                        "centrality_signal_coverage_ratio": 1.0,
                        "pagerank_signal_chunk_count": 1,
                        "pagerank_signal_coverage_ratio": 0.5,
                    },
                    "latency_ms": 1.0,
                }
            ],
        }
    )

    assert "## Graph Context Source Summary" in report
    assert "Source loaded ratio: 1.0000; projection fallback ratio: 1.0000; edge count mean: 5.00" in report
    assert "Inbound signal chunk count mean / coverage ratio: 2.00 / 1.0000" in report
    assert "Centrality signal chunk count mean / coverage ratio: 2.00 / 1.0000" in report
    assert "Pagerank signal chunk count mean / coverage ratio: 1.00 / 0.5000" in report
    assert "graph_source_provider_loaded: 1.0000" in report
    assert "graph_source_edge_count: 5.0000" in report
    assert "graph_context_source: provider_loaded=True, projection_fallback=True, edge_count=5, inbound_signal_chunk_count=2, inbound_signal_coverage_ratio=1.0000, centrality_signal_chunk_count=2, centrality_signal_coverage_ratio=1.0000, pagerank_signal_chunk_count=1, pagerank_signal_coverage_ratio=0.5000" in report


def test_build_report_markdown_prefers_top_level_validation_branch_summary() -> None:
    report = build_report_markdown(
        {
            "repo": "demo",
            "metrics": {
                "task_success_rate": 1.0,
                "validation_branch_case_count": 0.0,
                "validation_branch_case_rate": 0.0,
                "validation_branch_candidate_count_mean": 0.0,
                "validation_branch_rejected_count_mean": 0.0,
                "validation_branch_selection_present_ratio": 0.0,
                "validation_branch_patch_artifact_present_ratio": 0.0,
                "validation_branch_archive_present_ratio": 0.0,
                "validation_branch_parallel_case_rate": 0.0,
                "validation_branch_winner_pass_rate": 0.0,
                "validation_branch_winner_regressed_rate": 0.0,
                "validation_branch_winner_score_mean": 0.0,
                "validation_branch_winner_after_issue_count_mean": 0.0,
            },
            "validation_branch_summary": {
                "case_count": 2.0,
                "case_rate": 0.5,
                "candidate_count_mean": 3.0,
                "rejected_count_mean": 2.0,
                "selection_present_ratio": 1.0,
                "patch_artifact_present_ratio": 1.0,
                "archive_present_ratio": 1.0,
                "parallel_case_rate": 1.0,
                "winner_pass_rate": 0.5,
                "winner_regressed_rate": 0.0,
                "winner_score_mean": 104.0,
                "winner_after_issue_count_mean": 0.5,
            },
            "validation_branch_gate_summary": {
                "failed_checks": [],
                "case_count": 2.0,
                "case_rate": 0.5,
                "case_count_threshold": 1.0,
                "case_count_passed": True,
                "selection_present_ratio": 1.0,
                "selection_present_ratio_threshold": 1.0,
                "selection_present_ratio_passed": True,
                "patch_artifact_present_ratio": 1.0,
                "patch_artifact_present_ratio_threshold": 1.0,
                "patch_artifact_present_ratio_passed": True,
                "archive_present_ratio": 1.0,
                "archive_present_ratio_threshold": 1.0,
                "archive_present_ratio_passed": True,
                "parallel_case_rate": 1.0,
                "parallel_case_rate_threshold": 1.0,
                "parallel_case_rate_passed": True,
                "gate_passed": True,
            },
        }
    )

    assert "## Validation Branch Summary" in report
    assert "Applicable case count / rate: 2.00 / 0.5000" in report
    assert "Selection / winner artifact / loser archive ratios: 1.0000 / 1.0000 / 1.0000" in report
    assert "## Validation Branch Gate Summary" in report
    assert "- Gate passed: yes" in report


def test_build_report_markdown_prefers_top_level_source_plan_card_summary() -> None:
    report = build_report_markdown(
        {
            "repo": "demo",
            "metrics": {
                "task_success_rate": 1.0,
                "source_plan_evidence_card_count_mean": 0.0,
                "source_plan_file_card_count_mean": 0.0,
                "source_plan_chunk_card_count_mean": 0.0,
                "source_plan_validation_card_present_ratio": 0.0,
            },
            "source_plan_card_summary": {
                "evidence_card_count_mean": 2.0,
                "file_card_count_mean": 3.0,
                "chunk_card_count_mean": 5.0,
                "validation_card_present_ratio": 0.5,
            },
        }
    )

    assert "## Source Plan Card Summary" in report
    assert "Evidence/file/chunk card means: evidence=2.0000; file=3.0000; chunk=5.0000" in report
    assert "Validation card present ratio: 0.5000" in report


def test_build_report_markdown_includes_source_plan_validation_feedback_summary() -> None:
    report = build_report_markdown(
        {
            "repo": "demo",
            "metrics": {
                "task_success_rate": 1.0,
                "source_plan_validation_feedback_present_ratio": 1.0,
                "source_plan_validation_feedback_issue_count_mean": 2.0,
                "source_plan_validation_feedback_failure_rate": 1.0,
                "source_plan_validation_feedback_probe_issue_count_mean": 1.0,
                "source_plan_validation_feedback_probe_executed_count_mean": 1.0,
                "source_plan_validation_feedback_probe_failure_rate": 1.0,
                "source_plan_validation_feedback_selected_test_count_mean": 1.0,
                "source_plan_validation_feedback_executed_test_count_mean": 1.0,
            },
        }
    )

    assert "## Source Plan Validation Feedback Summary" in report
    assert "Present ratio: 1.0000; issue count mean: 2.0000; failure rate: 1.0000" in report
    assert "Probe issue count mean: 1.0000; probe executed count mean: 1.0000; probe failure rate: 1.0000" in report
    assert "Selected test count mean: 1.0000; executed test count mean: 1.0000" in report


def test_build_report_markdown_prefers_top_level_source_plan_validation_feedback_summary() -> None:
    report = build_report_markdown(
        {
            "repo": "demo",
            "metrics": {
                "task_success_rate": 1.0,
                "source_plan_validation_feedback_present_ratio": 0.0,
                "source_plan_validation_feedback_issue_count_mean": 0.0,
                "source_plan_validation_feedback_failure_rate": 0.0,
                "source_plan_validation_feedback_probe_issue_count_mean": 0.0,
                "source_plan_validation_feedback_probe_executed_count_mean": 0.0,
                "source_plan_validation_feedback_probe_failure_rate": 0.0,
                "source_plan_validation_feedback_selected_test_count_mean": 0.0,
                "source_plan_validation_feedback_executed_test_count_mean": 0.0,
            },
            "source_plan_validation_feedback_summary": {
                "present_ratio": 1.0,
                "issue_count_mean": 2.0,
                "failure_rate": 1.0,
                "probe_issue_count_mean": 1.0,
                "probe_executed_count_mean": 1.0,
                "probe_failure_rate": 1.0,
                "selected_test_count_mean": 1.0,
                "executed_test_count_mean": 1.0,
            },
        }
    )

    assert "## Source Plan Validation Feedback Summary" in report
    assert "Present ratio: 1.0000; issue count mean: 2.0000; failure rate: 1.0000" in report
    assert "Probe issue count mean: 1.0000; probe executed count mean: 1.0000; probe failure rate: 1.0000" in report
    assert "Selected test count mean: 1.0000; executed test count mean: 1.0000" in report


def test_build_report_markdown_includes_source_plan_failure_signal_summary() -> None:
    report = build_report_markdown(
        {
            "repo": "demo",
            "metrics": {
                "task_success_rate": 1.0,
                "source_plan_failure_signal_present_ratio": 1.0,
                "source_plan_failure_signal_issue_count_mean": 2.0,
                "source_plan_failure_signal_failure_rate": 1.0,
                "source_plan_failure_signal_probe_issue_count_mean": 1.0,
                "source_plan_failure_signal_probe_executed_count_mean": 1.0,
                "source_plan_failure_signal_probe_failure_rate": 1.0,
                "source_plan_failure_signal_selected_test_count_mean": 1.0,
                "source_plan_failure_signal_executed_test_count_mean": 1.0,
                "source_plan_failure_signal_replay_cache_origin_ratio": 1.0,
                "source_plan_failure_signal_observability_origin_ratio": 0.0,
                "source_plan_failure_signal_source_plan_origin_ratio": 0.0,
                "source_plan_failure_signal_validate_step_origin_ratio": 0.0,
            },
        }
    )

    assert "## Source Plan Failure Signal Summary" in report
    assert "Present ratio: 1.0000; issue count mean: 2.0000; failure rate: 1.0000" in report
    assert "Probe issue count mean: 1.0000; probe executed count mean: 1.0000; probe failure rate: 1.0000" in report
    assert "Selected test count mean: 1.0000; executed test count mean: 1.0000" in report
    assert "Origin ratios: replay_cache=1.0000; observability=0.0000; source_plan=0.0000; validate_step=0.0000" in report


def test_build_report_markdown_prefers_top_level_source_plan_failure_signal_summary() -> None:
    report = build_report_markdown(
        {
            "repo": "demo",
            "metrics": {
                "task_success_rate": 1.0,
                "source_plan_failure_signal_present_ratio": 0.0,
                "source_plan_failure_signal_issue_count_mean": 0.0,
                "source_plan_failure_signal_failure_rate": 0.0,
                "source_plan_failure_signal_probe_issue_count_mean": 0.0,
                "source_plan_failure_signal_probe_executed_count_mean": 0.0,
                "source_plan_failure_signal_probe_failure_rate": 0.0,
                "source_plan_failure_signal_selected_test_count_mean": 0.0,
                "source_plan_failure_signal_executed_test_count_mean": 0.0,
                "source_plan_failure_signal_replay_cache_origin_ratio": 0.0,
                "source_plan_failure_signal_observability_origin_ratio": 0.0,
                "source_plan_failure_signal_source_plan_origin_ratio": 0.0,
                "source_plan_failure_signal_validate_step_origin_ratio": 0.0,
            },
            "source_plan_failure_signal_summary": {
                "present_ratio": 1.0,
                "issue_count_mean": 2.0,
                "failure_rate": 1.0,
                "probe_issue_count_mean": 1.0,
                "probe_executed_count_mean": 1.0,
                "probe_failure_rate": 1.0,
                "selected_test_count_mean": 1.0,
                "executed_test_count_mean": 1.0,
                "replay_cache_origin_ratio": 1.0,
                "observability_origin_ratio": 0.0,
                "source_plan_origin_ratio": 0.0,
                "validate_step_origin_ratio": 0.0,
            },
        }
    )

    assert "## Source Plan Failure Signal Summary" in report
    assert "Present ratio: 1.0000; issue count mean: 2.0000; failure rate: 1.0000" in report
    assert "Probe issue count mean: 1.0000; probe executed count mean: 1.0000; probe failure rate: 1.0000" in report
    assert "Selected test count mean: 1.0000; executed test count mean: 1.0000" in report
    assert "Origin ratios: replay_cache=1.0000; observability=0.0000; source_plan=0.0000; validate_step=0.0000" in report


def test_build_report_markdown_includes_learning_router_rollout_summary() -> None:
    report = build_report_markdown(
        {
            "repo": "demo",
            "metrics": {"task_success_rate": 1.0},
            "learning_router_rollout_summary": {
                "case_count": 4,
                "router_enabled_case_count": 3,
                "router_enabled_case_rate": 0.75,
                "shadow_mode_case_count": 2,
                "shadow_mode_case_rate": 0.5,
                "shadow_ready_case_count": 2,
                "shadow_ready_case_rate": 0.5,
                "source_plan_card_present_case_count": 3,
                "source_plan_card_present_case_rate": 0.75,
                "failure_signal_blocked_case_count": 1,
                "failure_signal_blocked_case_rate": 0.25,
                "eligible_case_count": 1,
                "eligible_case_rate": 0.25,
                "reason_counts": {
                    "adaptive_router_disabled": 1,
                    "eligible_pending_guarded_rollout": 1,
                },
            },
        }
    )

    assert "## Learning Router Rollout Summary" in report
    assert "Router enabled: 3/4 (0.7500)" in report
    assert "Shadow mode: 2/4 (0.5000); shadow-ready: 2/4 (0.5000)" in report
    assert "Source-plan cards present: 3/4 (0.7500); failure-signal blocked: 1/4 (0.2500)" in report
    assert "Guarded-rollout eligible: 1/4 (0.2500)" in report
    assert (
        "Reason counts: adaptive_router_disabled=1, eligible_pending_guarded_rollout=1"
        in report
    )


def test_build_report_markdown_prefers_frontier_gate_summary_for_deep_symbol_and_native_scip() -> None:
    report = build_report_markdown(
        {
            "repo": "demo",
            "metrics": {
                "deep_symbol_case_count": 2.0,
                "deep_symbol_case_recall": 0.0,
                "native_scip_loaded_rate": 0.0,
                "native_scip_document_count_mean": 5.0,
                "native_scip_definition_occurrence_count_mean": 7.0,
                "native_scip_reference_occurrence_count_mean": 11.0,
                "native_scip_symbol_definition_count_mean": 3.0,
            },
            "retrieval_frontier_gate_summary": {
                "deep_symbol_case_recall": 0.95,
                "native_scip_loaded_rate": 0.8,
            },
        }
    )

    assert "## Deep Symbol Summary" in report
    assert "Deep symbol case count: 2.00; recall: 0.9500" in report
    assert "## Native SCIP Summary" in report
    assert "Native SCIP loaded rate: 0.8000" in report
    assert "| native_scip_document_count_mean | 5.00 |" in report


def test_build_report_markdown_prefers_top_level_deep_symbol_and_native_scip_summaries() -> None:
    report = build_report_markdown(
        {
            "repo": "demo",
            "metrics": {
                "deep_symbol_case_count": 0.0,
                "deep_symbol_case_recall": 0.0,
                "native_scip_loaded_rate": 0.0,
                "native_scip_document_count_mean": 0.0,
                "native_scip_definition_occurrence_count_mean": 0.0,
                "native_scip_reference_occurrence_count_mean": 0.0,
                "native_scip_symbol_definition_count_mean": 0.0,
            },
            "retrieval_frontier_gate_summary": {
                "deep_symbol_case_recall": 0.4,
                "native_scip_loaded_rate": 0.5,
            },
            "deep_symbol_summary": {
                "case_count": 2.0,
                "recall": 0.95,
            },
            "native_scip_summary": {
                "loaded_rate": 0.8,
                "document_count_mean": 5.0,
                "definition_occurrence_count_mean": 7.0,
                "reference_occurrence_count_mean": 11.0,
                "symbol_definition_count_mean": 3.0,
            },
        }
    )

    assert "## Deep Symbol Summary" in report
    assert "Deep symbol case count: 2.00; recall: 0.9500" in report
    assert "## Native SCIP Summary" in report
    assert "Native SCIP loaded rate: 0.8000" in report
    assert "| native_scip_document_count_mean | 5.00 |" in report
    assert "| native_scip_definition_occurrence_count_mean | 7.00 |" in report


def test_build_results_summary_preserves_reward_log_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "reward_log_summary": {
                "enabled": True,
                "active": False,
                "status": "degraded",
                "path": "context-map/router/rewards.jsonl",
                "eligible_case_count": 2,
                "submitted_count": 1,
                "written_count": 1,
                "pending_count": 0,
                "error_count": 1,
                "last_error": "disk full",
            },
        }
    )

    assert summary["reward_log_summary"]["status"] == "degraded"
    assert summary["reward_log_summary"]["path"] == "context-map/router/rewards.jsonl"
    assert summary["reward_log_summary"]["error_count"] == 1


def test_build_results_summary_preserves_tuning_context_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "tuning_context_summary": {
                "report_only": True,
                "retrieval": {"top_k_files": 8},
                "chunk": {"top_k": 10},
            },
        }
    )

    assert summary["tuning_context_summary"]["report_only"] is True
    assert summary["tuning_context_summary"]["retrieval"]["top_k_files"] == 8
    assert summary["tuning_context_summary"]["chunk"]["top_k"] == 10


def test_build_results_summary_preserves_retrieval_context_observability_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "retrieval_context_observability_summary": {
                "case_count": 2,
                "available_case_count": 2,
                "available_case_rate": 1.0,
                "parent_symbol_available_case_count": 2,
                "parent_symbol_available_case_rate": 1.0,
                "reference_hint_available_case_count": 1,
                "reference_hint_available_case_rate": 0.5,
                "pool_available_case_count": 1,
                "pool_available_case_rate": 0.5,
                "chunk_count_mean": 2.0,
                "coverage_ratio_mean": 1.0,
                "parent_symbol_chunk_count_mean": 2.0,
                "parent_symbol_coverage_ratio_mean": 1.0,
                "reference_hint_chunk_count_mean": 1.0,
                "reference_hint_coverage_ratio_mean": 0.5,
                "pool_chunk_count_mean": 1.0,
                "pool_coverage_ratio_mean": 0.5,
            },
        }
    )

    assert summary["retrieval_context_observability_summary"] == {
        "case_count": 2,
        "available_case_count": 2,
        "available_case_rate": 1.0,
        "parent_symbol_available_case_count": 2,
        "parent_symbol_available_case_rate": 1.0,
        "reference_hint_available_case_count": 1,
        "reference_hint_available_case_rate": 0.5,
        "pool_available_case_count": 1,
        "pool_available_case_rate": 0.5,
        "chunk_count_mean": 2.0,
        "coverage_ratio_mean": 1.0,
        "parent_symbol_chunk_count_mean": 2.0,
        "parent_symbol_coverage_ratio_mean": 1.0,
        "reference_hint_chunk_count_mean": 1.0,
        "reference_hint_coverage_ratio_mean": 0.5,
        "pool_chunk_count_mean": 1.0,
        "pool_coverage_ratio_mean": 0.5,
    }


def test_build_results_summary_preserves_retrieval_default_strategy_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "retrieval_default_strategy_summary": {
                "case_count": 2,
                "retrieval_context_available_case_count": 2,
                "retrieval_context_available_case_rate": 1.0,
                "parent_symbol_available_case_count": 2,
                "parent_symbol_available_case_rate": 1.0,
                "reference_hint_available_case_count": 1,
                "reference_hint_available_case_rate": 0.5,
                "semantic_rerank_configured_case_count": 2,
                "semantic_rerank_configured_case_rate": 1.0,
                "semantic_rerank_enabled_case_count": 2,
                "semantic_rerank_enabled_case_rate": 1.0,
                "semantic_rerank_applied_case_count": 1,
                "semantic_rerank_applied_case_rate": 0.5,
                "semantic_rerank_cross_encoder_case_count": 2,
                "semantic_rerank_cross_encoder_case_rate": 1.0,
                "semantic_rerank_dominant_provider": "hash_colbert",
                "semantic_rerank_dominant_mode": "cross_encoder",
                "semantic_rerank_provider_case_counts": {
                    "hash_colbert": 1,
                    "hash_cross": 1,
                },
                "graph_lookup_enabled_case_count": 2,
                "graph_lookup_enabled_case_rate": 1.0,
                "graph_lookup_guarded_case_count": 1,
                "graph_lookup_guarded_case_rate": 0.5,
                "graph_lookup_dominant_normalization": "log1p",
                "graph_lookup_pool_size_mean": 4.0,
                "graph_lookup_guard_max_candidates_mean": 4.0,
                "graph_lookup_guard_min_query_terms_mean": 1.0,
                "graph_lookup_guard_max_query_terms_mean": 5.0,
                "graph_lookup_weight_means": {
                    "scip": 0.3,
                    "xref": 0.2,
                    "query_xref": 0.2,
                    "symbol": 0.1,
                    "import": 0.1,
                    "coverage": 0.1,
                },
                "topological_shield_enabled_case_count": 2,
                "topological_shield_enabled_case_rate": 1.0,
                "topological_shield_report_only_case_count": 2,
                "topological_shield_report_only_case_rate": 1.0,
                "topological_shield_dominant_mode": "report_only",
                "topological_shield_max_attenuation_mean": 0.6,
                "topological_shield_shared_parent_attenuation_mean": 0.2,
                "topological_shield_adjacency_attenuation_mean": 0.5,
            },
        }
    )

    assert summary["retrieval_default_strategy_summary"] == {
        "case_count": 2,
        "retrieval_context_available_case_count": 2,
        "retrieval_context_available_case_rate": 1.0,
        "parent_symbol_available_case_count": 2,
        "parent_symbol_available_case_rate": 1.0,
        "reference_hint_available_case_count": 1,
        "reference_hint_available_case_rate": 0.5,
        "semantic_rerank_configured_case_count": 2,
        "semantic_rerank_configured_case_rate": 1.0,
        "semantic_rerank_enabled_case_count": 2,
        "semantic_rerank_enabled_case_rate": 1.0,
        "semantic_rerank_applied_case_count": 1,
        "semantic_rerank_applied_case_rate": 0.5,
        "semantic_rerank_cross_encoder_case_count": 2,
        "semantic_rerank_cross_encoder_case_rate": 1.0,
        "semantic_rerank_dominant_provider": "hash_colbert",
        "semantic_rerank_dominant_mode": "cross_encoder",
        "semantic_rerank_provider_case_counts": {
            "hash_colbert": 1,
            "hash_cross": 1,
        },
        "graph_lookup_enabled_case_count": 2,
        "graph_lookup_enabled_case_rate": 1.0,
        "graph_lookup_guarded_case_count": 1,
        "graph_lookup_guarded_case_rate": 0.5,
        "graph_lookup_dominant_normalization": "log1p",
        "graph_lookup_pool_size_mean": 4.0,
        "graph_lookup_guard_max_candidates_mean": 4.0,
        "graph_lookup_guard_min_query_terms_mean": 1.0,
        "graph_lookup_guard_max_query_terms_mean": 5.0,
        "graph_lookup_weight_means": {
            "scip": 0.3,
            "xref": 0.2,
            "query_xref": 0.2,
            "symbol": 0.1,
            "import": 0.1,
            "coverage": 0.1,
        },
        "topological_shield_enabled_case_count": 2,
        "topological_shield_enabled_case_rate": 1.0,
        "topological_shield_report_only_case_count": 2,
        "topological_shield_report_only_case_rate": 1.0,
        "topological_shield_dominant_mode": "report_only",
        "topological_shield_max_attenuation_mean": 0.6,
        "topological_shield_shared_parent_attenuation_mean": 0.2,
        "topological_shield_adjacency_attenuation_mean": 0.5,
    }


def test_build_results_summary_preserves_missing_context_risk_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "missing_context_risk_summary": {
                "case_count": 2,
                "applicable_case_count": 2,
                "excluded_negative_control_case_count": 0,
                "elevated_case_count": 1,
                "high_risk_case_count": 1,
                "elevated_case_rate": 0.5,
                "high_risk_case_rate": 0.5,
                "risk_score_mean": 0.625,
                "risk_score_p95": 0.85,
                "risk_upgrade_case_count": 1,
                "risk_upgrade_case_rate": 0.5,
                "risk_upgrade_precision_mean": 0.7,
                "risk_baseline_precision_mean": 0.4,
                "risk_upgrade_precision_gain": 0.3,
                "levels": {"elevated": 1, "high": 1},
                "signals": {
                    "budget_exhausted": 1,
                    "evidence_insufficient": 1,
                    "recall_miss": 1,
                },
            },
        }
    )

    assert summary["missing_context_risk_summary"] == {
        "case_count": 2,
        "applicable_case_count": 2,
        "excluded_negative_control_case_count": 0,
        "elevated_case_count": 1,
        "high_risk_case_count": 1,
        "elevated_case_rate": 0.5,
        "high_risk_case_rate": 0.5,
        "risk_score_mean": 0.625,
        "risk_score_p95": 0.85,
        "risk_upgrade_case_count": 1,
        "risk_upgrade_case_rate": 0.5,
        "risk_upgrade_precision_mean": 0.7,
        "risk_baseline_precision_mean": 0.4,
        "risk_upgrade_precision_gain": 0.3,
        "levels": {"elevated": 1, "high": 1},
        "signals": {
            "budget_exhausted": 1,
            "evidence_insufficient": 1,
            "recall_miss": 1,
        },
    }


def test_build_results_summary_preserves_preference_observability_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "preference_observability_summary": {
                "case_count": 2,
                "observed_case_count": 2,
                "observed_case_rate": 1.0,
                "notes_hit_case_count": 1,
                "notes_hit_case_rate": 0.5,
                "profile_selected_case_count": 2,
                "profile_selected_case_rate": 1.0,
                "capture_triggered_case_count": 1,
                "capture_triggered_case_rate": 0.5,
                "notes_hit_ratio_mean": 0.5,
                "profile_selected_count_mean": 1.5,
            },
        }
    )

    assert summary["preference_observability_summary"] == {
        "case_count": 2,
        "observed_case_count": 2,
        "observed_case_rate": 1.0,
        "notes_hit_case_count": 1,
        "notes_hit_case_rate": 0.5,
        "profile_selected_case_count": 2,
        "profile_selected_case_rate": 1.0,
        "capture_triggered_case_count": 1,
        "capture_triggered_case_rate": 0.5,
        "notes_hit_ratio_mean": 0.5,
        "profile_selected_count_mean": 1.5,
    }


def test_build_results_summary_preserves_feedback_observability_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "feedback_observability_summary": {
                "case_count": 2,
                "enabled_case_count": 2,
                "enabled_case_rate": 1.0,
                "matched_case_count": 1,
                "matched_case_rate": 0.5,
                "boosted_case_count": 1,
                "boosted_case_rate": 0.5,
                "event_count_mean": 4.0,
                "matched_event_count_mean": 1.5,
                "boosted_candidate_count_mean": 0.5,
                "boosted_unique_paths_mean": 0.5,
                "reasons": {"ok": 1, "no_events": 1},
            },
        }
    )

    assert summary["feedback_observability_summary"] == {
        "case_count": 2,
        "enabled_case_count": 2,
        "enabled_case_rate": 1.0,
        "matched_case_count": 1,
        "matched_case_rate": 0.5,
        "boosted_case_count": 1,
        "boosted_case_rate": 0.5,
        "event_count_mean": 4.0,
        "matched_event_count_mean": 1.5,
        "boosted_candidate_count_mean": 0.5,
        "boosted_unique_paths_mean": 0.5,
        "reasons": {"ok": 1, "no_events": 1},
    }


def test_build_report_markdown_includes_adaptive_router_observability_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-10T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {},
            "adaptive_router_observability_summary": {
                "case_count": 2,
                "enabled_case_count": 2,
                "enabled_case_rate": 1.0,
                "comparable_case_count": 2,
                "comparable_case_rate": 1.0,
                "agreement_case_count": 1,
                "agreement_rate": 0.5,
                "disagreement_case_count": 1,
                "disagreement_rate": 0.5,
                "executed_arm_count": 1,
                "shadow_arm_count": 2,
                "shadow_source_counts": {"fallback": 1, "model": 1},
                "executed_arms": [{"arm_id": "feature", "case_count": 2, "case_rate": 1.0}],
                "shadow_arms": [
                    {"arm_id": "feature_graph", "case_count": 1, "case_rate": 0.5},
                    {"arm_id": "general_hybrid", "case_count": 1, "case_rate": 0.5},
                ],
            },
        }
    )

    assert "## Adaptive Router Observability" in report
    assert "- Agreement: 1/2 (0.5000)" in report
    assert "- Shadow sources: fallback=1, model=1" in report
    assert "### Executed Arms" in report
    assert "- feature: cases=2 rate=1.0000 task_success=0.0000 mrr=0.0000 fallback_cases=0 downgrade_cases=0" in report
    assert "### Shadow Arms" in report


def test_build_report_markdown_includes_retrieval_context_observability_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-17T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {},
            "retrieval_context_observability_summary": {
                "case_count": 2,
                "available_case_count": 2,
                "available_case_rate": 1.0,
                "parent_symbol_available_case_count": 2,
                "parent_symbol_available_case_rate": 1.0,
                "reference_hint_available_case_count": 1,
                "reference_hint_available_case_rate": 0.5,
                "pool_available_case_count": 1,
                "pool_available_case_rate": 0.5,
                "chunk_count_mean": 2.0,
                "coverage_ratio_mean": 1.0,
                "parent_symbol_chunk_count_mean": 2.0,
                "parent_symbol_coverage_ratio_mean": 1.0,
                "reference_hint_chunk_count_mean": 1.0,
                "reference_hint_coverage_ratio_mean": 0.5,
                "pool_chunk_count_mean": 1.0,
                "pool_coverage_ratio_mean": 0.5,
            },
        }
    )

    assert "## Retrieval Context Observability Summary" in report
    assert "- Available cases: 2/2 (1.0000)" in report
    assert "- Parent-symbol cases: 2/2 (1.0000)" in report
    assert "- Reference-hint cases: 1/2 (0.5000)" in report
    assert "- Pool-available cases: 1/2 (0.5000)" in report
    assert "| parent_symbol_chunk_count_mean | 2.0000 |" in report
    assert "| reference_hint_coverage_ratio_mean | 0.5000 |" in report
    assert "| pool_coverage_ratio_mean | 0.5000 |" in report


def test_build_report_markdown_includes_retrieval_default_strategy_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-24T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {},
            "retrieval_default_strategy_summary": {
                "case_count": 2,
                "retrieval_context_available_case_count": 2,
                "retrieval_context_available_case_rate": 1.0,
                "parent_symbol_available_case_count": 2,
                "parent_symbol_available_case_rate": 1.0,
                "reference_hint_available_case_count": 1,
                "reference_hint_available_case_rate": 0.5,
                "semantic_rerank_configured_case_count": 2,
                "semantic_rerank_configured_case_rate": 1.0,
                "semantic_rerank_enabled_case_count": 2,
                "semantic_rerank_enabled_case_rate": 1.0,
                "semantic_rerank_applied_case_count": 1,
                "semantic_rerank_applied_case_rate": 0.5,
                "semantic_rerank_cross_encoder_case_count": 2,
                "semantic_rerank_cross_encoder_case_rate": 1.0,
                "semantic_rerank_dominant_provider": "hash_colbert",
                "semantic_rerank_dominant_mode": "cross_encoder",
                "semantic_rerank_provider_case_counts": {
                    "hash_colbert": 1,
                    "hash_cross": 1,
                },
                "graph_lookup_enabled_case_count": 2,
                "graph_lookup_enabled_case_rate": 1.0,
                "graph_lookup_guarded_case_count": 1,
                "graph_lookup_guarded_case_rate": 0.5,
                "graph_lookup_dominant_normalization": "log1p",
                "graph_lookup_pool_size_mean": 4.0,
                "graph_lookup_guard_max_candidates_mean": 4.0,
                "graph_lookup_guard_min_query_terms_mean": 1.0,
                "graph_lookup_guard_max_query_terms_mean": 5.0,
                "graph_lookup_weight_means": {
                    "scip": 0.3,
                    "xref": 0.2,
                    "query_xref": 0.2,
                    "symbol": 0.1,
                    "import": 0.1,
                    "coverage": 0.1,
                },
                "topological_shield_enabled_case_count": 2,
                "topological_shield_enabled_case_rate": 1.0,
                "topological_shield_report_only_case_count": 2,
                "topological_shield_report_only_case_rate": 1.0,
                "topological_shield_dominant_mode": "report_only",
                "topological_shield_max_attenuation_mean": 0.6,
                "topological_shield_shared_parent_attenuation_mean": 0.2,
                "topological_shield_adjacency_attenuation_mean": 0.5,
            },
        }
    )

    assert "## Retrieval Default Strategy Summary" in report
    assert "- Retrieval-context cases: 2/2 (1.0000); parent-symbol: 2/2 (1.0000); reference-hint: 1/2 (0.5000)" in report
    assert "- Semantic rerank default: configured=2/2 (1.0000); enabled=2/2 (1.0000); applied=1/2 (0.5000); mode=cross_encoder; provider=hash_colbert" in report
    assert "- Semantic rerank providers: hash_colbert=1, hash_cross=1" in report
    assert "- Graph lookup default: enabled=2/2 (1.0000); guarded=1/2 (0.5000); normalization=log1p" in report
    assert "- Graph lookup guard means: pool=4.0000; max_candidates=4.0000; min_query_terms=1.0000; max_query_terms=5.0000" in report
    assert "- Topological shield default: enabled=2/2 (1.0000); report_only=2/2 (1.0000); mode=report_only" in report
    assert "- Topological shield attenuation means: max=0.6000; shared_parent=0.2000; adjacency=0.5000" in report


def test_build_report_markdown_includes_missing_context_risk_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-22T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {},
            "missing_context_risk_summary": {
                "case_count": 2,
                "applicable_case_count": 2,
                "excluded_negative_control_case_count": 0,
                "elevated_case_count": 1,
                "high_risk_case_count": 1,
                "elevated_case_rate": 0.5,
                "high_risk_case_rate": 0.5,
                "risk_score_mean": 0.625,
                "risk_score_p95": 0.85,
                "risk_upgrade_case_count": 1,
                "risk_upgrade_case_rate": 0.5,
                "risk_upgrade_precision_mean": 0.7,
                "risk_baseline_precision_mean": 0.4,
                "risk_upgrade_precision_gain": 0.3,
                "levels": {"elevated": 1, "high": 1},
                "signals": {
                    "budget_exhausted": 1,
                    "evidence_insufficient": 1,
                    "recall_miss": 1,
                },
            },
        }
    )

    assert "## Missing-Context Risk Summary" in report
    assert "- Elevated cases: 1 (0.5000)" in report
    assert "- High-risk cases: 1 (0.5000)" in report
    assert "- Risk score mean / p95: 0.6250 / 0.8500" in report
    assert "- Risk-driven upgrades: 1/1 (0.5000)" in report
    assert "- Risk-upgrade precision mean / baseline / gain: 0.7000 / 0.4000 / 0.3000" in report
    assert "| high | 1 | 0.5000 |" in report
    assert "| evidence_insufficient | 1 |" in report


def test_build_report_markdown_includes_retrieval_control_plane_gate_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-22T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {},
            "retrieval_control_plane_gate_summary": {
                "regression_evaluated": True,
                "benchmark_regression_detected": False,
                "benchmark_regression_passed": True,
                "failed_checks": [],
                "adaptive_router_shadow_coverage": 0.9,
                "adaptive_router_shadow_coverage_threshold": 0.8,
                "adaptive_router_shadow_coverage_passed": True,
                "risk_upgrade_precision_gain": 0.12,
                "risk_upgrade_precision_gain_threshold": 0.0,
                "risk_upgrade_precision_gain_passed": True,
                "latency_p95_ms": 640.0,
                "latency_p95_ms_threshold": 850.0,
                "latency_p95_ms_passed": True,
                "gate_passed": True,
            },
        }
    )

    assert "## Retrieval Control Plane Gate Summary" in report
    assert "- Gate passed: yes" in report
    assert "- Regression evaluated: yes" in report
    assert "- Benchmark regression detected: no" in report
    assert "- Benchmark regression gate: pass" in report
    assert (
        "- Adaptive router shadow coverage: 0.9000 (threshold >= 0.8000, pass)"
        in report
    )
    assert "- Risk-upgrade precision gain: 0.1200 (threshold >= 0.0000, pass)" in report
    assert "- Latency p95 ms: 640.00 (threshold <= 850.00, pass)" in report


def test_build_report_markdown_includes_agent_loop_control_plane_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-24T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {},
            "agent_loop_control_plane_summary": {
                "case_count": 2,
                "observed_case_count": 2,
                "observed_case_rate": 1.0,
                "enabled_case_count": 2,
                "enabled_case_rate": 1.0,
                "attempted_case_count": 1,
                "attempted_case_rate": 0.5,
                "replay_safe_case_count": 2,
                "replay_safe_case_rate": 1.0,
                "actions_requested_mean": 1.0,
                "actions_executed_mean": 0.5,
                "request_more_context_case_count": 1,
                "request_more_context_case_rate": 0.5,
                "request_source_plan_retry_case_count": 1,
                "request_source_plan_retry_case_rate": 0.5,
                "request_validation_retry_case_count": 0,
                "request_validation_retry_case_rate": 0.0,
                "dominant_stop_reason": "completed",
                "dominant_last_policy_id": "source_plan_refresh",
            },
        }
    )

    assert "## Agent Loop Control Plane Summary" in report
    assert "Observed=2/2 (1.0000); enabled=2/2 (1.0000); attempted=1/2 (0.5000)" in report
    assert "dominant_stop_reason=completed; dominant_policy=source_plan_refresh" in report
    assert "source_plan_retry=1/2 (0.5000)" in report


def test_build_report_markdown_includes_retrieval_control_plane_gate_failure_state() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-22T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {},
            "retrieval_control_plane_gate_summary": {
                "regression_evaluated": True,
                "benchmark_regression_detected": True,
                "benchmark_regression_passed": False,
                "failed_checks": [
                    "benchmark_regression_detected",
                    "adaptive_router_shadow_coverage",
                ],
                "adaptive_router_shadow_coverage": 0.74,
                "adaptive_router_shadow_coverage_threshold": 0.8,
                "adaptive_router_shadow_coverage_passed": False,
                "risk_upgrade_precision_gain": -0.03,
                "risk_upgrade_precision_gain_threshold": 0.0,
                "risk_upgrade_precision_gain_passed": False,
                "latency_p95_ms": 880.0,
                "latency_p95_ms_threshold": 850.0,
                "latency_p95_ms_passed": False,
                "gate_passed": False,
            },
        }
    )

    assert "- Gate passed: no" in report
    assert "- Benchmark regression detected: yes" in report
    assert "- Benchmark regression gate: fail" in report
    assert (
        "- Adaptive router shadow coverage: 0.7400 (threshold >= 0.8000, fail)"
        in report
    )
    assert "- Risk-upgrade precision gain: -0.0300 (threshold >= 0.0000, fail)" in report
    assert "- Latency p95 ms: 880.00 (threshold <= 850.00, fail)" in report
    assert (
        "- Failed checks: benchmark_regression_detected, adaptive_router_shadow_coverage"
        in report
    )


def test_build_report_markdown_includes_retrieval_frontier_gate_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-22T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {},
            "retrieval_frontier_gate_summary": {
                "failed_checks": ["precision_at_k"],
                "deep_symbol_case_recall": 0.95,
                "deep_symbol_case_recall_threshold": 0.9,
                "deep_symbol_case_recall_passed": True,
                "native_scip_loaded_rate": 0.8,
                "native_scip_loaded_rate_threshold": 0.7,
                "native_scip_loaded_rate_passed": True,
                "precision_at_k": 0.61,
                "precision_at_k_threshold": 0.64,
                "precision_at_k_passed": False,
                "noise_rate": 0.31,
                "noise_rate_threshold": 0.36,
                "noise_rate_passed": True,
                "gate_passed": False,
            },
        }
    )

    assert "## Retrieval Frontier Gate Summary" in report
    assert "- Gate passed: no" in report
    assert "- Deep-symbol recall: 0.9500 (threshold >= 0.9000, pass)" in report
    assert "- Native SCIP loaded rate: 0.8000 (threshold >= 0.7000, pass)" in report
    assert "- Precision@k: 0.6100 (threshold >= 0.6400, fail)" in report
    assert "- Noise rate: 0.3100 (threshold <= 0.3600, pass)" in report
    assert "- Failed checks: precision_at_k" in report


def test_build_report_markdown_includes_preference_observability_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-17T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {},
            "preference_observability_summary": {
                "case_count": 2,
                "observed_case_count": 2,
                "observed_case_rate": 1.0,
                "notes_hit_case_count": 1,
                "notes_hit_case_rate": 0.5,
                "profile_selected_case_count": 2,
                "profile_selected_case_rate": 1.0,
                "capture_triggered_case_count": 1,
                "capture_triggered_case_rate": 0.5,
                "notes_hit_ratio_mean": 0.5,
                "profile_selected_count_mean": 1.5,
            },
        }
    )

    assert "## Preference Observability Summary" in report
    assert "- Observed cases: 2/2 (1.0000)" in report
    assert "- Notes-hit cases: 1/2 (0.5000)" in report
    assert "- Capture-triggered cases: 1/2 (0.5000)" in report
    assert "| profile_selected_count_mean | 1.5000 |" in report


def test_build_report_markdown_includes_feedback_observability_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-17T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {},
            "feedback_observability_summary": {
                "case_count": 2,
                "enabled_case_count": 2,
                "enabled_case_rate": 1.0,
                "matched_case_count": 1,
                "matched_case_rate": 0.5,
                "boosted_case_count": 1,
                "boosted_case_rate": 0.5,
                "event_count_mean": 4.0,
                "matched_event_count_mean": 1.5,
                "boosted_candidate_count_mean": 0.5,
                "boosted_unique_paths_mean": 0.5,
                "reasons": {"ok": 1, "no_events": 1},
            },
        }
    )

    assert "## Feedback Observability Summary" in report
    assert "- Enabled cases: 2/2 (1.0000)" in report
    assert "- Matched cases: 1/2 (0.5000)" in report
    assert "| boosted_candidate_count_mean | 0.5000 |" in report
    assert "| no_events | 1 |" in report


def test_build_report_markdown_includes_feedback_loop_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-19T00:00:00Z",
            "repo": "demo",
            "case_count": 4,
            "metrics": {},
            "feedback_loop_summary": {
                "case_count": 4,
                "issue_report_case_count": 2,
                "issue_report_linked_case_count": 1,
                "issue_report_linked_plan_case_count": 1,
                "issue_report_resolved_case_count": 1,
                "issue_to_benchmark_case_conversion_rate": 0.5,
                "issue_report_linked_plan_rate": 1.0,
                "issue_report_resolution_rate": 0.5,
                "issue_report_time_to_fix_case_count": 1,
                "issue_report_time_to_fix_hours_mean": 12.0,
                "dev_feedback_resolution_case_count": 2,
                "dev_feedback_resolved_case_count": 1,
                "dev_feedback_resolution_rate": 0.5,
                "dev_feedback_issue_count": 2,
                "dev_feedback_linked_fix_issue_count": 1,
                "dev_feedback_resolved_issue_count": 1,
                "dev_issue_to_fix_rate": 0.5,
                "dev_feedback_issue_time_to_fix_case_count": 1,
                "dev_feedback_issue_time_to_fix_hours_mean": 6.0,
                "feedback_surfaces": {
                    "issue_report_export_cli": 1,
                    "issue_resolution_cli": 1,
                },
            },
        }
    )

    assert "## Feedback Loop Summary" in report
    assert "- Converted issue-report benchmark cases: 1 rate=0.5000" in report
    assert "- Linked-plan issue reports: 1 rate=1.0000" in report
    assert "- Resolved issue reports: 1 rate=0.5000 time_to_fix_mean=12.00h" in report
    assert (
        "- Dev-feedback issue linkage: issues=2 linked_fixes=1 resolved_issues=1 issue_to_fix_rate=0.5000 time_to_fix_mean=6.00h"
        in report
    )
    assert "| issue_to_benchmark_case_conversion_rate | 0.5000 |" in report
    assert "| issue_report_time_to_fix_hours_mean | 12.00 |" in report
    assert "| dev_feedback_resolution_rate | 0.5000 |" in report
    assert "| dev_issue_to_fix_rate | 0.5000 |" in report
    assert "| issue_report_export_cli | 1 |" in report


def test_build_results_summary_preserves_feedback_loop_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "feedback_loop_summary": {
                "case_count": 4,
                "issue_report_case_count": 2,
                "issue_report_linked_case_count": 1,
                "issue_report_linked_plan_case_count": 1,
                "issue_report_resolved_case_count": 1,
                "issue_to_benchmark_case_conversion_rate": 0.5,
                "issue_report_linked_plan_rate": 1.0,
                "issue_report_resolution_rate": 0.5,
                "issue_report_time_to_fix_case_count": 1,
                "issue_report_time_to_fix_hours_mean": 12.0,
                "dev_feedback_resolution_case_count": 2,
                "dev_feedback_resolved_case_count": 1,
                "dev_feedback_resolution_rate": 0.5,
                "dev_feedback_issue_count": 2,
                "dev_feedback_linked_fix_issue_count": 1,
                "dev_feedback_resolved_issue_count": 1,
                "dev_issue_to_fix_rate": 0.5,
                "dev_feedback_issue_time_to_fix_case_count": 1,
                "dev_feedback_issue_time_to_fix_hours_mean": 6.0,
                "feedback_surfaces": {"issue_report_export_cli": 1},
            },
        }
    )

    assert summary["feedback_loop_summary"]["issue_report_case_count"] == 2
    assert summary["feedback_loop_summary"]["dev_feedback_resolution_rate"] == 0.5
    assert summary["feedback_loop_summary"]["dev_issue_to_fix_rate"] == 0.5
    assert summary["feedback_loop_summary"]["issue_report_time_to_fix_hours_mean"] == 12.0


def test_build_report_markdown_includes_reward_log_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-10T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {},
            "reward_log_summary": {
                "enabled": True,
                "active": False,
                "status": "degraded",
                "path": "context-map/router/rewards.jsonl",
                "eligible_case_count": 2,
                "submitted_count": 1,
                "written_count": 1,
                "pending_count": 0,
                "error_count": 1,
                "last_error": "disk full",
            },
        }
    )

    assert "## Reward Log Summary" in report
    assert "- Status: degraded" in report
    assert "- Enabled: True" in report
    assert "- Path: context-map/router/rewards.jsonl" in report
    assert "- Error count: 1" in report
    assert "- Last error: disk full" in report


def test_build_report_markdown_includes_runtime_stats_preference_snapshot() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-17T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {
                "ltm_latency_overhead_ms": 3.5,
            },
            "runtime_stats_summary": {
                "db_path": "runtime_state.db",
                "latest_match": {
                    "session_id": "sess-1",
                    "repo_key": "demo",
                    "profile_key": "default",
                    "finished_at": "2026-03-17T00:00:00Z",
                },
                "summary": {
                    "session": {
                        "counters": {
                            "invocation_count": 1,
                            "success_count": 1,
                            "degraded_count": 0,
                            "failure_count": 0,
                        },
                        "latency": {"latency_ms_avg": 12.0},
                    }
                },
                "memory_health_summary": {
                    "scope_kind": "session",
                    "reason_count": 1,
                    "runtime_event_count": 1,
                    "issue_count": 1,
                    "open_issue_count": 1,
                    "fix_count": 1,
                    "resolution_rate": 1.0,
                    "open_issue_rate": 1.0,
                    "memory_stage_latency_ms_avg": 5.0,
                    "reasons": [
                        {
                            "reason_code": "memory_fallback",
                            "runtime_event_count": 1,
                            "manual_issue_count": 1,
                            "open_issue_count": 1,
                            "fix_count": 1,
                            "last_seen_at": "2026-03-17T00:00:00Z",
                        }
                    ],
                },
                "next_cycle_input_summary": {
                    "primary_stream": "memory",
                    "priority_count": 1,
                    "priorities": [
                        {
                            "reason_code": "memory_fallback",
                            "reason_family": "memory",
                            "capture_class": "memory",
                            "total_count": 3,
                            "open_issue_count": 1,
                            "fix_count": 1,
                            "action_hint": "Stabilize memory fallback and capture quality before expanding retrieval breadth.",
                        }
                    ],
                    "memory_focus": {
                        "reason_count": 1,
                        "runtime_event_count": 1,
                        "open_issue_count": 1,
                        "fix_count": 1,
                        "resolution_rate": 1.0,
                        "action_hint": "Stabilize memory fallback and capture quality before expanding retrieval breadth.",
                    },
                },
                "preference_snapshot": {
                    "preference_observability_summary": {
                        "case_count": 2,
                        "observed_case_count": 2,
                        "observed_case_rate": 1.0,
                        "notes_hit_ratio_mean": 0.5,
                        "profile_selected_count_mean": 1.5,
                    },
                    "feedback_observability_summary": {
                        "case_count": 2,
                        "boosted_case_count": 1,
                        "boosted_case_rate": 0.5,
                        "matched_event_count_mean": 1.5,
                        "boosted_candidate_count_mean": 0.5,
                    },
                    "durable_preference_capture_summary": {
                        "enabled": True,
                        "store_path": "preference_capture.db",
                        "configured_path": "profile.json",
                        "repo_key": "demo",
                        "preference_kind": "selection_feedback",
                        "signal_source": "feedback_store",
                        "event_count": 3,
                        "distinct_target_path_count": 2,
                        "total_weight": 3.0,
                        "latest_created_at": "2026-03-18T00:00:00Z",
                        "by_kind": {"selection_feedback": 3},
                        "by_signal_source": {"feedback_store": 3},
                    },
                    "durable_preference_capture_scoped_summary": {
                        "enabled": True,
                        "store_path": "preference_capture.db",
                        "configured_path": "profile.json",
                        "user_id": "bench-user",
                        "repo_key": "demo",
                        "profile_key": "bugfix",
                        "preference_kind": "selection_feedback",
                        "signal_source": "feedback_store",
                        "event_count": 1,
                        "distinct_target_path_count": 1,
                        "total_weight": 1.0,
                        "latest_created_at": "2026-03-18T00:00:00Z",
                        "by_kind": {"selection_feedback": 1},
                        "by_signal_source": {"feedback_store": 1},
                    },
                    "durable_retrieval_preference_summary": {
                        "enabled": True,
                        "store_path": "preference_capture.db",
                        "configured_path": "profile.json",
                        "user_id": "bench-user",
                        "repo_key": "demo",
                        "preference_kind": "retrieval_preference",
                        "signal_source": "benchmark",
                        "event_count": 1,
                        "distinct_target_path_count": 1,
                        "total_weight": 0.75,
                        "latest_created_at": "2026-03-18T00:00:00Z",
                        "by_kind": {"retrieval_preference": 1},
                        "by_signal_source": {"benchmark": 1},
                    },
                    "durable_packing_preference_summary": {
                        "enabled": True,
                        "store_path": "preference_capture.db",
                        "configured_path": "profile.json",
                        "user_id": "bench-user",
                        "repo_key": "demo",
                        "preference_kind": "packing_preference",
                        "signal_source": "benchmark",
                        "event_count": 1,
                        "distinct_target_path_count": 1,
                        "total_weight": 1.0,
                        "latest_created_at": "2026-03-18T00:00:00Z",
                        "by_kind": {"packing_preference": 1},
                        "by_signal_source": {"benchmark": 1},
                    },
                    "durable_validation_preference_summary": {
                        "enabled": True,
                        "store_path": "preference_capture.db",
                        "configured_path": "profile.json",
                        "user_id": "bench-user",
                        "repo_key": "demo",
                        "preference_kind": "validation_preference",
                        "signal_source": "benchmark",
                        "event_count": 1,
                        "distinct_target_path_count": 1,
                        "total_weight": 0.25,
                        "latest_created_at": "2026-03-18T00:00:00Z",
                        "by_kind": {"validation_preference": 1},
                        "by_signal_source": {"benchmark": 1},
                    },
                },
            },
        }
    )

    assert "## Runtime Stats Summary" in report
    assert "### Memory Health" in report
    assert "Scope: session" in report
    assert "Runtime memory events: 1" in report
    assert "Developer issues: 1 open=1 fixes=1 resolution_rate=1.0000" in report
    assert "Memory stage latency avg: 5.00 ms" in report
    assert "Benchmark LTM latency overhead: 3.50 ms" in report
    assert "Benchmark/runtime alignment gap: 1.50 ms" in report
    assert "Benchmark/runtime ratio: 0.7000" in report
    assert "| memory_fallback | 1 | 1 | 1 | 1 | 2026-03-17T00:00:00Z |" in report
    assert "### Next Cycle Input" in report
    assert "Primary stream: memory" in report
    assert "| memory_fallback | memory | memory | 3 | 1 | 1 |" in report
    assert "Memory focus: reasons=1 runtime_events=1 open_issues=1 fixes=1 resolution_rate=1.0000" in report
    assert "### Preference Snapshot" in report
    assert "- Preference observed cases: 2/2 (1.0000)" in report
    assert "- Preference profile-selected mean: 1.5000" in report
    assert "- Feedback boosted cases: 1/2 (0.5000)" in report
    assert "- Feedback boosted-candidate mean: 0.5000" in report
    assert "- Durable preference store: preference_capture.db" in report
    assert "- Durable preference events: 3 paths=2 total_weight=3.0000" in report
    assert "- Durable preference scoped store: preference_capture.db" in report
    assert "- Durable preference scoped user_id: bench-user" in report
    assert "- Durable preference scoped profile_key: bugfix" in report
    assert "- Durable preference scoped events: 1 paths=1 total_weight=1.0000" in report
    assert "- Durable retrieval-preference store: preference_capture.db" in report
    assert "- Durable retrieval-preference user_id: bench-user" in report
    assert "- Durable retrieval-preference events: 1 paths=1 total_weight=0.7500" in report
    assert "- Durable packing-preference store: preference_capture.db" in report
    assert "- Durable packing-preference user_id: bench-user" in report
    assert "- Durable packing-preference events: 1 paths=1 total_weight=1.0000" in report
    assert "- Durable validation-preference store: preference_capture.db" in report
    assert "- Durable validation-preference user_id: bench-user" in report
    assert "- Durable validation-preference events: 1 paths=1 total_weight=0.2500" in report


def test_build_report_markdown_includes_dev_issue_capture_feedback_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-21T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {},
            "feedback_loop_summary": {
                "case_count": 2,
                "issue_report_case_count": 0,
                "issue_report_linked_case_count": 0,
                "issue_report_linked_plan_case_count": 0,
                "issue_report_resolved_case_count": 0,
                "issue_to_benchmark_case_conversion_rate": 0.0,
                "issue_report_linked_plan_rate": 0.0,
                "issue_report_resolution_rate": 0.0,
                "issue_report_time_to_fix_case_count": 0,
                "issue_report_time_to_fix_hours_mean": 0.0,
                "dev_issue_capture_case_count": 2,
                "dev_issue_captured_case_count": 2,
                "dev_issue_capture_rate": 1.0,
                "dev_feedback_resolution_case_count": 0,
                "dev_feedback_resolved_case_count": 0,
                "dev_feedback_resolution_rate": 0.0,
                "dev_feedback_issue_count": 2,
                "dev_feedback_linked_fix_issue_count": 0,
                "dev_feedback_resolved_issue_count": 0,
                "dev_issue_to_fix_rate": 0.0,
                "dev_feedback_issue_time_to_fix_case_count": 0,
                "dev_feedback_issue_time_to_fix_hours_mean": 0.0,
                "feedback_surfaces": {
                    "runtime_issue_capture_cli": 1,
                    "runtime_issue_capture_mcp": 1,
                },
            },
        }
    )

    assert "Dev-issue capture cases: 2 captured=2 rate=1.0000" in report
    assert "| dev_issue_capture_rate | 1.0000 |" in report
    assert "| runtime_issue_capture_cli | 1 |" in report
    assert "| runtime_issue_capture_mcp | 1 |" in report


def test_build_report_markdown_includes_validation_probe_summary() -> None:
    report = build_report_markdown(
        {
            "generated_at": "2026-03-23T00:00:00Z",
            "repo": "demo",
            "case_count": 2,
            "metrics": {
                "validation_test_count": 1.5,
                "validation_probe_enabled_ratio": 1.0,
                "validation_probe_executed_count_mean": 2.0,
                "validation_probe_failure_rate": 0.5,
            },
        }
    )

    assert "## Validation Probe Summary" in report
    assert "Validation tests mean: 1.5000; probe enabled ratio: 1.0000" in report
    assert "Probe executed count mean: 2.0000; failure rate: 0.5000" in report


def test_build_results_summary_backfills_task_success_alias() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "metrics": {
                "utility_rate": 0.75,
            },
        }
    )

    assert summary["metrics"]["task_success_rate"] == 0.75
    assert summary["metrics"]["utility_rate"] == 0.75


def test_build_results_summary_includes_ltm_latency_alignment_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "metrics": {
                "ltm_latency_overhead_ms": 4.0,
            },
            "runtime_stats_summary": {
                "memory_health_summary": {
                    "memory_stage_latency_ms_avg": 5.0,
                }
            },
        }
    )

    assert summary["ltm_latency_alignment_summary"] == {
        "benchmark_ltm_latency_overhead_ms": 4.0,
        "runtime_memory_stage_latency_ms_avg": 5.0,
        "alignment_gap_ms": 1.0,
        "benchmark_to_runtime_ratio": 0.8,
        "has_runtime_reference": True,
        "has_benchmark_signal": True,
        "comparable": True,
    }
