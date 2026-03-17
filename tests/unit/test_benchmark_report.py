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
                "source_plan_neighbor_context_ratio": 0.25,
                "source_plan_hint_only_ratio": 0.0,
                "source_plan_graph_closure_preference_enabled_ratio": 1.0,
                "source_plan_graph_closure_bonus_candidate_count_mean": 2.0,
                "source_plan_graph_closure_preferred_count_mean": 1.0,
                "source_plan_focused_file_promoted_count_mean": 1.0,
                "source_plan_packed_path_count_mean": 2.0,
                "evidence_insufficient_rate": 0.5,
                "no_candidate_rate": 0.0,
                "low_support_chunk_rate": 0.5,
                "missing_validation_rate": 0.5,
                "budget_limited_recovery_rate": 0.0,
                "noisy_hit_rate": 0.5,
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
                "source_plan_neighbor_context_ratio": 0.25,
                "source_plan_hint_only_ratio": 0.25,
                "source_plan_graph_closure_preference_enabled_ratio": 0.0,
                "source_plan_graph_closure_bonus_candidate_count_mean": 0.0,
                "source_plan_graph_closure_preferred_count_mean": 0.0,
                "source_plan_focused_file_promoted_count_mean": 0.0,
                "source_plan_packed_path_count_mean": 1.0,
                "evidence_insufficient_rate": 0.25,
                "no_candidate_rate": 0.0,
                "low_support_chunk_rate": 0.25,
                "missing_validation_rate": 0.25,
                "budget_limited_recovery_rate": 0.0,
                "noisy_hit_rate": 0.25,
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
                "source_plan_neighbor_context_ratio": 0.0,
                "source_plan_hint_only_ratio": -0.25,
                "source_plan_graph_closure_preference_enabled_ratio": 1.0,
                "source_plan_graph_closure_bonus_candidate_count_mean": 2.0,
                "source_plan_graph_closure_preferred_count_mean": 1.0,
                "source_plan_focused_file_promoted_count_mean": 1.0,
                "source_plan_packed_path_count_mean": 1.0,
                "evidence_insufficient_rate": 0.25,
                "no_candidate_rate": 0.0,
                "low_support_chunk_rate": 0.25,
                "missing_validation_rate": 0.25,
                "budget_limited_recovery_rate": 0.0,
                "noisy_hit_rate": 0.25,
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
                    "source_plan_packing": {
                        "graph_closure_preference_enabled": True,
                        "graph_closure_bonus_candidate_count": 2,
                        "graph_closure_preferred_count": 1,
                        "focused_file_promoted_count": 1,
                        "packed_path_count": 2,
                        "reason": "graph_closure_preferred",
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
    assert "## Chunk Stage Miss Summary" in report
    assert "## Decision Observability Summary" in report
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
    assert "| stale_majority | 1 | 0.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.3333 | 1.0000 | 1.0000 | 2.0000 |" in report
    assert "task_success_failed_checks: validation_tests" in report
    assert "evidence_insufficiency_reason: missing_validation" in report
    assert "evidence_insufficiency_signals: missing_validation_tests, noisy_hit" in report
    assert "chunk_stage_miss: source_plan_pack_miss" in report
    assert "decision_event: index | retry | candidate_postprocess | reason=low_candidate_count | outcome=applied" in report
    assert "decision_event: skills | skip | skills_hydration | reason=token_budget_exhausted" in report
    assert "slo_downgrade_signals: parallel_docs_timeout, embedding_time_budget_exceeded, chunk_semantic_fallback" in report
    assert "parallel_docs_timeout_ratio" in report
    assert "skills_token_budget_used_mean" in report
    assert "skills_budget_exhausted_ratio" in report
    assert "skills_route_latency_p95_ms" in report
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
    assert "| source_plan_pack_miss | 1 | 1.0000 |" in report
    assert "source_plan_direct_evidence_ratio" in report
    assert "source_plan_neighbor_context_ratio" in report
    assert "source_plan_hint_only_ratio" in report
    assert "source_plan_graph_closure_preference_enabled_ratio" in report
    assert "source_plan_graph_closure_bonus_candidate_count_mean" in report
    assert "source_plan_packed_path_count_mean" in report
    assert "evidence_insufficient_rate" in report
    assert "missing_validation_rate" in report
    assert "parallel_time_budget_ms_mean" in report
    assert "validation_test_count: 0" in report
    assert "validation_test_count" in report
    assert "plan_replay_cache: stage=source_plan, reason=hit, stored=False" in report
    assert "chunk_guard_expectation: scenario=stale_majority, expected_retained_hit=True, expected_filtered_hit_count=1, expected_filtered_hit_rate=1.0000, report_only_improved=True" in report
    assert "robust_signature: count=1, coverage_ratio=0.5000" in report
    assert "graph_closure: enabled=True, boosted_chunk_count=2, coverage_ratio=0.5000, anchor_count=1, support_edge_count=3, total=0.1400" in report
    assert "source_plan_packing: graph_closure_preference_enabled=True, graph_closure_bonus_candidate_count=2, graph_closure_preferred_count=1, focused_file_promoted_count=1, packed_path_count=2, reason=graph_closure_preferred" in report
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
                "comparable_case_count": 2,
                "comparable_case_rate": 1.0,
                "agreement_case_count": 1,
                "agreement_rate": 0.5,
                "disagreement_case_count": 1,
                "disagreement_rate": 0.5,
                "executed_arm_count": 1,
                "shadow_arm_count": 2,
                "executed_arms": [{"arm_id": "feature", "case_count": 2, "case_rate": 1.0}],
                "shadow_arms": [
                    {"arm_id": "feature_graph", "case_count": 1, "case_rate": 0.5},
                    {"arm_id": "general_hybrid", "case_count": 1, "case_rate": 0.5},
                ],
            },
        }
    )

    assert summary["adaptive_router_observability_summary"]["agreement_rate"] == 0.5
    assert summary["adaptive_router_observability_summary"]["executed_arms"][0]["arm_id"] == "feature"


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


def test_build_results_summary_preserves_retrieval_context_observability_summary() -> None:
    summary = build_results_summary(
        {
            "repo": "demo",
            "retrieval_context_observability_summary": {
                "case_count": 2,
                "available_case_count": 2,
                "available_case_rate": 1.0,
                "pool_available_case_count": 1,
                "pool_available_case_rate": 0.5,
                "chunk_count_mean": 2.0,
                "coverage_ratio_mean": 1.0,
                "pool_chunk_count_mean": 1.0,
                "pool_coverage_ratio_mean": 0.5,
            },
        }
    )

    assert summary["retrieval_context_observability_summary"] == {
        "case_count": 2,
        "available_case_count": 2,
        "available_case_rate": 1.0,
        "pool_available_case_count": 1,
        "pool_available_case_rate": 0.5,
        "chunk_count_mean": 2.0,
        "coverage_ratio_mean": 1.0,
        "pool_chunk_count_mean": 1.0,
        "pool_coverage_ratio_mean": 0.5,
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
                "pool_available_case_count": 1,
                "pool_available_case_rate": 0.5,
                "chunk_count_mean": 2.0,
                "coverage_ratio_mean": 1.0,
                "pool_chunk_count_mean": 1.0,
                "pool_coverage_ratio_mean": 0.5,
            },
        }
    )

    assert "## Retrieval Context Observability Summary" in report
    assert "- Available cases: 2/2 (1.0000)" in report
    assert "- Pool-available cases: 1/2 (0.5000)" in report
    assert "| pool_coverage_ratio_mean | 0.5000 |" in report


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
