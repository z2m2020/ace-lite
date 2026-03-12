from __future__ import annotations

from ace_lite.benchmark.case_evaluation_payloads import count_unique_paths, safe_ratio
from ace_lite.benchmark.scoring import (
    aggregate_metrics,
    build_comparison_lane_summary,
    compare_metrics,
    detect_regression,
    evaluate_case_result,
    resolve_regression_thresholds,
)


def test_evaluate_case_result_and_aggregate() -> None:
    case = {
        "case_id": "c1",
        "query": "where validate token",
        "expected_keys": ["validate_token", "auth"],
        "top_k": 4,
        "comparison_lane": "stale_majority",
    }
    payload = {
        "index": {
            "candidate_files": [
                {"path": "src/auth.py", "module": "src.auth"},
                {"path": "src/token.py", "module": "src.token"},
            ],
            "chunk_metrics": {
                "robust_signature_count": 1.0,
                "robust_signature_coverage_ratio": 0.5,
                "graph_prior_chunk_count": 1.0,
                "graph_prior_coverage_ratio": 0.5,
                "graph_prior_total": 0.18,
                "graph_seeded_chunk_count": 1.0,
                "graph_transfer_count": 2.0,
                "graph_hub_suppressed_chunk_count": 1.0,
                "graph_hub_penalty_total": 0.08,
                "graph_closure_enabled": 1.0,
                "graph_closure_boosted_chunk_count": 2.0,
                "graph_closure_coverage_ratio": 0.5,
                "graph_closure_anchor_count": 1.0,
                "graph_closure_support_edge_count": 3.0,
                "graph_closure_total": 0.14,
                "topological_shield_enabled": 1.0,
                "topological_shield_report_only": 1.0,
                "topological_shield_attenuated_chunk_count": 1.0,
                "topological_shield_coverage_ratio": 0.5,
                "topological_shield_attenuation_total": 0.22,
            },
            "policy_name": "doc_intent",
            "metadata": {
                "docs_enabled": True,
                "docs_section_count": 2,
                "docs_injected_count": 1,
            },
            "docs": {"enabled": True, "section_count": 2},
            "embeddings": {
                "enabled": True,
                "cache_hit": True,
                "similarity_mean": 0.42,
                "similarity_max": 0.88,
                "rerank_pool": 4,
                "reranked_count": 2,
                "fallback": False,
            },
        },
        "skills": {
            "selected": [{"name": "skill-a"}],
            "routing_source": "precomputed",
            "routing_mode": "metadata_only",
            "metadata_only_routing": True,
            "route_latency_ms": 0.3,
            "hydration_latency_ms": 0.7,
            "token_budget": 600,
            "token_budget_used": 250,
            "budget_exhausted": True,
            "skipped_for_budget": [{"name": "skill-b"}],
        },
        "source_plan": {
            "validation_tests": ["tests.test_auth::test_token"],
            "evidence_summary": {
                "direct_count": 1.0,
                "neighbor_context_count": 0.0,
                "hint_only_count": 0.0,
                "direct_ratio": 1.0,
                "neighbor_context_ratio": 0.0,
                "hint_only_ratio": 0.0,
            },
            "packing": {
                "graph_closure_preference_enabled": True,
                "graph_closure_bonus_candidate_count": 2,
                "graph_closure_preferred_count": 1,
                "focused_file_promoted_count": 1,
                "packed_path_count": 2,
                "reason": "graph_closure_preferred",
            },
        },
        "repomap": {
            "dependency_recall": {
                "hit_rate": 1.0,
            }
        },
        "observability": {
            "plan_replay_cache": {
                "enabled": True,
                "hit": True,
                "stale_hit_safe": True,
                "stage": "source_plan",
                "reason": "hit",
                "stored": False,
            },
            "stage_metrics": [
                {"stage": "repomap", "elapsed_ms": 4.5},
            ]
        },
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=12.5)

    assert row["case_id"] == "c1"
    assert row["comparison_lane"] == "stale_majority"
    assert row["top_k"] == 4
    assert row["latency_ms"] == 12.5
    assert 0.0 <= row["precision_at_k"] <= 1.0
    assert row["first_hit_rank"] == 1
    assert row["hit_at_1"] == 1.0
    assert row["reciprocal_rank"] == 1.0
    assert row["dependency_recall"] == 1.0
    assert row["repomap_latency_ms"] == 4.5
    assert row["validation_test_count"] == 1
    assert row["task_success_hit"] == 1.0
    assert row["task_success_mode"] == "positive"
    assert row["evidence_insufficient"] == 0.0
    assert row["evidence_insufficiency_reason"] == ""
    assert row["evidence_insufficiency_signals"] == []
    assert row["validation_tests"] == ["tests.test_auth::test_token"]
    assert row["policy_profile"] == "doc_intent"
    assert row["docs_enabled"] == 1.0
    assert row["docs_hit"] == 1.0
    assert row["hint_inject"] == 1.0
    assert row["embedding_similarity_mean"] == 0.42
    assert row["embedding_rerank_ratio"] == 0.5
    assert row["embedding_cache_hit"] == 1.0
    assert row["embedding_fallback"] == 0.0
    assert row["skills_selected_count"] == 1.0
    assert row["skills_token_budget"] == 600.0
    assert row["skills_token_budget_used"] == 250.0
    assert row["skills_budget_exhausted"] == 1.0
    assert row["skills_skipped_for_budget_count"] == 1.0
    assert row["skills_route_latency_ms"] == 0.3
    assert row["skills_hydration_latency_ms"] == 0.7
    assert row["skills_metadata_only_routing"] == 1.0
    assert row["skills_precomputed_route"] == 1.0
    assert row["plan_replay_cache_enabled"] == 1.0
    assert row["plan_replay_cache_hit"] == 1.0
    assert row["plan_replay_cache_stale_hit_safe"] == 1.0
    assert row["source_plan_direct_evidence_ratio"] == 1.0
    assert row["source_plan_neighbor_context_ratio"] == 0.0
    assert row["source_plan_hint_only_ratio"] == 0.0
    assert row["robust_signature_count"] == 1.0
    assert row["robust_signature_coverage_ratio"] == 0.5
    assert row["graph_prior_chunk_count"] == 1.0
    assert row["graph_prior_coverage_ratio"] == 0.5
    assert row["graph_prior_total"] == 0.18
    assert row["graph_transfer_count"] == 2.0
    assert row["graph_closure_enabled"] == 1.0
    assert row["graph_closure_boosted_chunk_count"] == 2.0
    assert row["graph_closure_coverage_ratio"] == 0.5
    assert row["graph_closure_anchor_count"] == 1.0
    assert row["graph_closure_support_edge_count"] == 3.0
    assert row["graph_closure_total"] == 0.14
    assert row["topological_shield_enabled"] == 1.0
    assert row["topological_shield_report_only"] == 1.0
    assert row["topological_shield_attenuated_chunk_count"] == 1.0
    assert row["topological_shield_coverage_ratio"] == 0.5
    assert row["topological_shield_attenuation_total"] == 0.22
    assert row["source_plan_graph_closure_preference_enabled"] == 1.0
    assert row["source_plan_graph_closure_bonus_candidate_count"] == 2.0
    assert row["source_plan_graph_closure_preferred_count"] == 1.0
    assert row["source_plan_focused_file_promoted_count"] == 1.0
    assert row["source_plan_packed_path_count"] == 2.0
    assert row["memory_latency_ms"] == 0.0
    assert row["index_latency_ms"] == 0.0
    assert row["augment_latency_ms"] == 0.0
    assert row["source_plan_latency_ms"] == 0.0
    assert row["slo_downgrade_triggered"] == 0.0
    assert row["relevant_candidate_paths"] == ["src/auth.py"]
    assert row["noise_candidate_paths"] == ["src/token.py"]
    assert row["candidate_matches"] == [
        {"path": "src/auth.py", "matched_expected_keys": ["auth"]},
        {"path": "src/token.py", "matched_expected_keys": []},
    ]
    assert row["skills_routing"] == {
        "source": "precomputed",
        "mode": "metadata_only",
        "metadata_only_routing": True,
        "route_latency_ms": 0.3,
        "hydration_latency_ms": 0.7,
        "selected_manifest_token_estimate_total": 0.0,
        "hydrated_skill_count": 0,
        "hydrated_sections_count": 0,
    }
    assert row["plan_replay_cache"] == {
        "enabled": True,
        "hit": True,
        "stale_hit_safe": True,
        "stage": "source_plan",
        "reason": "hit",
        "stored": False,
    }
    assert row["chunk_stage_miss_applicable"] == 0.0
    assert row["chunk_stage_miss_classified"] == 0.0
    assert row["chunk_stage_miss"] == ""
    assert "chunk_stage_miss_details" not in row
    assert row["source_plan_evidence_summary"] == {
        "direct_count": 1.0,
        "neighbor_context_count": 0.0,
        "hint_only_count": 0.0,
        "direct_ratio": 1.0,
        "neighbor_context_ratio": 0.0,
        "hint_only_ratio": 0.0,
    }
    assert row["skills_budget"] == {
        "selected_count": 1,
        "token_budget": 600.0,
        "token_budget_used": 250.0,
        "utilization_ratio": round(250.0 / 600.0, 6),
        "budget_exhausted": True,
        "skipped_for_budget_count": 1,
    }
    assert row["graph_prior"] == {
        "chunk_count": 1,
        "coverage_ratio": 0.5,
        "total": 0.18,
        "seeded_chunk_count": 1,
        "transfer_count": 2,
        "transfer_per_seed_ratio": 2.0,
        "hub_suppressed_chunk_count": 1,
        "hub_penalty_total": 0.08,
    }
    assert row["topological_shield"] == {
        "enabled": True,
        "report_only": True,
        "attenuated_chunk_count": 1,
        "coverage_ratio": 0.5,
        "attenuation_total": 0.22,
        "attenuation_per_chunk": 0.22,
    }
    assert row["graph_closure"] == {
        "enabled": True,
        "boosted_chunk_count": 2,
        "coverage_ratio": 0.5,
        "anchor_count": 1,
        "support_edge_count": 3,
        "total": 0.14,
    }
    assert row["source_plan_packing"] == {
        "graph_closure_preference_enabled": True,
        "graph_closure_bonus_candidate_count": 2,
        "graph_closure_preferred_count": 1,
        "focused_file_promoted_count": 1,
        "packed_path_count": 2,
        "packed_path_ratio": 1.0,
        "chunk_retention_ratio": 0.0,
        "reason": "graph_closure_preferred",
    }
    assert row["chunk_contract"] == {
        "fallback_count": 0,
        "skeleton_chunk_count": 0,
        "fallback_ratio": 0.0,
        "skeleton_ratio": 0.0,
        "unsupported_language_fallback_count": 0,
        "unsupported_language_fallback_ratio": 0.0,
    }
    assert row["year2_normalized_kpis"] == {
        "skills_token_budget_utilization_ratio": round(250.0 / 600.0, 6),
        "source_plan_chunk_retention_ratio": 0.0,
        "source_plan_packed_path_ratio": 1.0,
        "graph_transfer_per_seed_ratio": 2.0,
        "chunk_guard_pairwise_conflict_density": 0.0,
        "topological_shield_attenuation_per_chunk": 0.22,
    }

    metrics = aggregate_metrics([row])
    assert set(metrics.keys()) == {
        "recall_at_k",
        "hit_at_1",
        "mrr",
        "precision_at_k",
        "task_success_rate",
        "utility_rate",
        "noise_rate",
        "docs_enabled_ratio",
        "docs_hit_ratio",
        "hint_inject_ratio",
        "dependency_recall",
        "memory_latency_p95_ms",
        "index_latency_p95_ms",
        "repomap_latency_p95_ms",
        "augment_latency_p95_ms",
        "skills_latency_p95_ms",
        "skills_route_latency_p95_ms",
        "skills_hydration_latency_p95_ms",
        "source_plan_latency_p95_ms",
        "repomap_latency_median_ms",
        "latency_p95_ms",
        "latency_median_ms",
        "chunk_hit_at_k",
        "chunks_per_file_mean",
        "chunk_budget_used",
        "chunk_contract_fallback_count_mean",
        "chunk_contract_skeleton_chunk_count_mean",
        "chunk_contract_fallback_ratio",
        "chunk_contract_skeleton_ratio",
        "unsupported_language_fallback_count_mean",
        "unsupported_language_fallback_ratio",
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
        "embedding_enabled_ratio",
        "embedding_similarity_mean",
        "embedding_similarity_max",
        "embedding_rerank_ratio",
        "embedding_cache_hit_ratio",
        "embedding_fallback_ratio",
        "parallel_time_budget_ms_mean",
        "embedding_time_budget_ms_mean",
        "chunk_semantic_time_budget_ms_mean",
        "xref_time_budget_ms_mean",
        "parallel_docs_timeout_ratio",
        "parallel_worktree_timeout_ratio",
        "embedding_time_budget_exceeded_ratio",
        "embedding_adaptive_budget_ratio",
        "chunk_semantic_time_budget_exceeded_ratio",
        "chunk_semantic_fallback_ratio",
        "xref_budget_exhausted_ratio",
        "slo_downgrade_case_rate",
    }
    assert metrics["latency_p95_ms"] == 12.5
    assert metrics["latency_median_ms"] == 12.5
    assert metrics["repomap_latency_p95_ms"] == 4.5
    assert metrics["repomap_latency_median_ms"] == 4.5
    assert metrics["memory_latency_p95_ms"] == 0.0
    assert metrics["index_latency_p95_ms"] == 0.0
    assert metrics["chunk_contract_fallback_count_mean"] == 0.0
    assert metrics["chunk_contract_skeleton_chunk_count_mean"] == 0.0
    assert metrics["chunk_contract_fallback_ratio"] == 0.0
    assert metrics["chunk_contract_skeleton_ratio"] == 0.0
    assert metrics["unsupported_language_fallback_count_mean"] == 0.0
    assert metrics["unsupported_language_fallback_ratio"] == 0.0
    assert metrics["skills_selected_count_mean"] == 1.0
    assert metrics["skills_token_budget_mean"] == 600.0
    assert metrics["skills_token_budget_used_mean"] == 250.0
    assert metrics["robust_signature_count_mean"] == 1.0
    assert metrics["robust_signature_coverage_ratio"] == 0.5
    assert metrics["graph_prior_chunk_count_mean"] == 1.0
    assert metrics["graph_prior_coverage_ratio"] == 0.5
    assert metrics["graph_prior_total_mean"] == 0.18
    assert metrics["graph_transfer_count_mean"] == 2.0
    assert metrics["graph_closure_enabled_ratio"] == 1.0
    assert metrics["graph_closure_boosted_chunk_count_mean"] == 2.0
    assert metrics["graph_closure_coverage_ratio"] == 0.5
    assert metrics["graph_closure_anchor_count_mean"] == 1.0
    assert metrics["graph_closure_support_edge_count_mean"] == 3.0
    assert metrics["graph_closure_total_mean"] == 0.14
    assert metrics["topological_shield_enabled_ratio"] == 1.0
    assert metrics["topological_shield_report_only_ratio"] == 1.0
    assert metrics["topological_shield_attenuated_chunk_count_mean"] == 1.0
    assert metrics["topological_shield_coverage_ratio"] == 0.5
    assert metrics["topological_shield_attenuation_total_mean"] == 0.22
    assert metrics["chunk_guard_enabled_ratio"] == 0.0
    assert metrics["chunk_guard_report_only_ratio"] == 0.0
    assert metrics["chunk_guard_filtered_count_mean"] == 0.0
    assert metrics["chunk_guard_filter_ratio"] == 0.0
    assert metrics["chunk_guard_pairwise_conflict_count_mean"] == 0.0
    assert metrics["chunk_guard_fallback_ratio"] == 0.0
    assert metrics["skills_route_latency_p95_ms"] == 0.3
    assert metrics["skills_hydration_latency_p95_ms"] == 0.7
    assert metrics["skills_metadata_only_routing_ratio"] == 1.0
    assert metrics["skills_precomputed_route_ratio"] == 1.0
    assert metrics["plan_replay_cache_enabled_ratio"] == 1.0
    assert metrics["plan_replay_cache_hit_ratio"] == 1.0
    assert metrics["plan_replay_cache_stale_hit_safe_ratio"] == 1.0
    assert metrics["source_plan_direct_evidence_ratio"] == 1.0
    assert metrics["source_plan_graph_closure_preference_enabled_ratio"] == 1.0
    assert metrics["source_plan_graph_closure_bonus_candidate_count_mean"] == 2.0
    assert metrics["source_plan_graph_closure_preferred_count_mean"] == 1.0
    assert metrics["source_plan_focused_file_promoted_count_mean"] == 1.0
    assert metrics["source_plan_packed_path_count_mean"] == 2.0
    assert metrics["source_plan_neighbor_context_ratio"] == 0.0
    assert metrics["source_plan_hint_only_ratio"] == 0.0
    assert metrics["skills_budget_exhausted_ratio"] == 1.0
    assert metrics["parallel_docs_timeout_ratio"] == 0.0
    assert metrics["slo_downgrade_case_rate"] == 0.0
    assert metrics["hit_at_1"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["docs_hit_ratio"] == 1.0
    assert metrics["task_success_rate"] == 1.0
    assert metrics["evidence_insufficient_rate"] == 0.0


def test_build_comparison_lane_summary_groups_chunk_guard_signals() -> None:
    summary = build_comparison_lane_summary(
        [
            {
                "comparison_lane": "stale_majority",
                "task_success_hit": 1.0,
                "recall_hit": 1.0,
                "chunk_guard_enabled": 1.0,
                "chunk_guard_report_only": 1.0,
                "chunk_guard_filtered_count": 2.0,
                "chunk_guard_filter_ratio": 0.5,
                "chunk_guard_pairwise_conflict_count": 3.0,
                "chunk_guard_expectation_applicable": 1.0,
                "chunk_guard_expected_retained_hit": 1.0,
                "chunk_guard_report_only_improved": 1.0,
                "chunk_guard_expected_filtered_hit_rate": 1.0,
            },
            {
                "comparison_lane": "stale_majority",
                "task_success_hit": 0.0,
                "recall_hit": 1.0,
                "chunk_guard_enabled": 1.0,
                "chunk_guard_report_only": 1.0,
                "chunk_guard_filtered_count": 0.0,
                "chunk_guard_filter_ratio": 0.0,
                "chunk_guard_pairwise_conflict_count": 1.0,
                "chunk_guard_expectation_applicable": 1.0,
                "chunk_guard_expected_retained_hit": 0.0,
                "chunk_guard_report_only_improved": 0.0,
                "chunk_guard_expected_filtered_hit_rate": 0.0,
            },
            {
                "comparison_lane": "adaptive_recovery",
                "task_success_hit": 1.0,
                "recall_hit": 1.0,
                "chunk_guard_enabled": 0.0,
                "chunk_guard_report_only": 0.0,
                "chunk_guard_filtered_count": 0.0,
                "chunk_guard_filter_ratio": 0.0,
                "chunk_guard_pairwise_conflict_count": 0.0,
            },
        ]
    )

    assert summary["total_case_count"] == 3
    assert summary["labeled_case_count"] == 3
    assert summary["lane_count"] == 2
    assert [item["comparison_lane"] for item in summary["lanes"]] == [
        "adaptive_recovery",
        "stale_majority",
    ]

    stale_majority = summary["lanes"][1]
    assert stale_majority["case_count"] == 2
    assert stale_majority["task_success_rate"] == 0.5
    assert stale_majority["recall_at_k"] == 1.0
    assert stale_majority["chunk_guard_enabled_ratio"] == 1.0
    assert stale_majority["chunk_guard_report_only_ratio"] == 1.0
    assert stale_majority["chunk_guard_filtered_case_rate"] == 0.5
    assert stale_majority["chunk_guard_filtered_count_mean"] == 1.0
    assert stale_majority["chunk_guard_filter_ratio_mean"] == 0.25
    assert stale_majority["chunk_guard_expected_retained_hit_rate_mean"] == 0.5
    assert stale_majority["chunk_guard_report_only_improved_rate"] == 0.5
    assert stale_majority["chunk_guard_expected_filtered_hit_rate_mean"] == 0.5
    assert stale_majority["chunk_guard_pairwise_conflict_count_mean"] == 2.0


def test_evaluate_case_result_tracks_chunk_guard_expectation_hits() -> None:
    case = {
        "case_id": "c-stale-majority",
        "query": "where stale majority chunk guard lives",
        "expected_keys": ["chunk_guard"],
        "top_k": 4,
        "comparison_lane": "stale_majority",
        "chunk_guard_expectation": {
            "scenario": "stale_majority",
            "expected_retained_refs": ["pkg.service_v1"],
            "expected_filtered_refs": ["pkg.service_v2"],
        },
    }
    payload = {
        "index": {
            "candidate_files": [
                {"path": "src/ace_lite/index_stage/chunk_guard.py", "module": "ace_lite.index_stage.chunk_guard"},
            ],
            "candidate_chunks": [
                {
                    "path": "src/ace_lite/index_stage/chunk_guard.py",
                    "qualified_name": "apply_chunk_guard",
                    "signature": "def apply_chunk_guard(...)",
                }
            ],
            "chunk_guard": {
                "mode": "report_only",
                "reason": "report_only",
                "candidate_pool": 3,
                "signed_chunk_count": 2,
                "filtered_count": 1,
                "retained_count": 2,
                "pairwise_conflict_count": 1,
                "max_conflict_penalty": 0.66,
                "retained_refs": ["pkg.service_v1", "pkg.helper"],
                "filtered_refs": ["pkg.service_v2"],
                "report_only": True,
                "fallback": False,
                "enabled": True,
            },
        },
        "source_plan": {},
        "repomap": {},
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=7.0)

    assert row["chunk_guard_expectation_applicable"] == 1.0
    assert row["chunk_guard_mode"] == "report_only"
    assert row["chunk_guard_reason"] == "report_only"
    assert row["chunk_guard_stale_majority_case"] == 1.0
    assert row["chunk_guard_expected_retained_hit"] == 1.0
    assert row["chunk_guard_expected_filtered_hit_count"] == 1.0
    assert row["chunk_guard_expected_filtered_hit_rate"] == 1.0
    assert row["chunk_guard_report_only_improved"] == 1.0
    assert row["chunk_guard_expectation"] == {
        "scenario": "stale_majority",
        "expected_retained_refs": ["pkg.service_v1"],
        "expected_filtered_refs": ["pkg.service_v2"],
        "retained_hits": ["pkg.service_v1"],
        "filtered_hits": ["pkg.service_v2"],
        "expected_retained_hit": True,
        "expected_filtered_hit_count": 1,
        "expected_filtered_hit_rate": 1.0,
        "report_only_improved": True,
    }


def test_evaluate_case_result_prefers_source_plan_chunks_even_when_empty() -> None:
    case = {
        "case_id": "c-source-plan-chunks",
        "query": "where worker planner lives",
        "expected_keys": ["worker"],
        "top_k": 2,
    }
    payload = {
        "index": {
            "candidate_files": [
                {"path": "src/worker.py", "module": "src.worker"},
            ],
            "candidate_chunks": [
                {
                    "path": "src/worker.py",
                    "qualified_name": "worker_impl",
                    "signature": "def worker_impl",
                }
            ],
            "chunk_metrics": {
                "chunks_per_file_mean": 4.0,
                "chunk_budget_used": 18.0,
            },
        },
        "source_plan": {
            "candidate_chunks": [],
            "chunk_budget_used": 0.0,
            "validation_tests": [],
        },
        "repomap": {"dependency_recall": {"hit_rate": 1.0}},
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=6.0)

    assert row["chunk_hit_at_k"] == 0.0
    assert row["candidate_chunk_refs"] == []
    assert row["chunk_hits"] == []
    assert row["chunk_budget_used"] == 0.0
    assert row["chunks_per_file_mean"] == 0.0


def test_evaluate_case_result_prefers_source_plan_chunks_when_present() -> None:
    case = {
        "case_id": "c-source-plan-win",
        "query": "where worker planner lives",
        "expected_keys": ["worker"],
        "top_k": 2,
    }
    payload = {
        "index": {
            "candidate_files": [
                {"path": "src/worker.py", "module": "src.worker"},
            ],
            "candidate_chunks": [
                {
                    "path": "src/noise.py",
                    "qualified_name": "noise_only",
                    "signature": "def noise_only",
                }
            ],
            "chunk_metrics": {
                "chunks_per_file_mean": 3.0,
                "chunk_budget_used": 21.0,
            },
        },
        "source_plan": {
            "candidate_chunks": [
                {
                    "path": "src/worker.py",
                    "qualified_name": "plan_worker",
                    "signature": "def plan_worker",
                }
            ],
            "chunk_budget_used": 7.0,
            "validation_tests": [],
        },
        "repomap": {"dependency_recall": {"hit_rate": 1.0}},
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=6.0)

    assert row["chunk_hit_at_k"] == 1.0
    assert row["candidate_chunk_refs"] == ["plan_worker"]
    assert row["chunk_hits"] == ["worker"]
    assert row["chunk_budget_used"] == 7.0
    assert row["chunks_per_file_mean"] == 1.0


def test_evaluate_case_result_classifies_chunk_stage_miss() -> None:
    base_case = {
        "case_id": "c-stage-miss",
        "query": "where worker planner lives",
        "expected_keys": ["worker"],
        "top_k": 2,
        "oracle_file_path": "src/worker.py",
        "oracle_chunk_ref": {
            "path": "src/worker.py",
            "qualified_name": "plan_worker",
        },
    }

    scenarios = [
        (
            "candidate_files_miss",
            {
                "index": {
                    "candidate_files": [
                        {"path": "src/noise.py", "module": "src.noise"},
                    ],
                    "candidate_chunks": [],
                },
                "source_plan": {"candidate_chunks": [], "validation_tests": []},
                "repomap": {"dependency_recall": {"hit_rate": 0.0}},
            },
        ),
        (
            "candidate_chunks_miss",
            {
                "index": {
                    "candidate_files": [
                        {"path": "src/worker.py", "module": "src.worker"},
                    ],
                    "candidate_chunks": [
                        {
                            "path": "src/worker.py",
                            "qualified_name": "noise_only",
                            "signature": "def noise_only",
                        }
                    ],
                },
                "source_plan": {"candidate_chunks": [], "validation_tests": []},
                "repomap": {"dependency_recall": {"hit_rate": 1.0}},
            },
        ),
        (
            "source_plan_pack_miss",
            {
                "index": {
                    "candidate_files": [
                        {"path": "src/worker.py", "module": "src.worker"},
                    ],
                    "candidate_chunks": [
                        {
                            "path": "src/worker.py",
                            "qualified_name": "plan_worker",
                            "signature": "def plan_worker",
                        }
                    ],
                },
                "source_plan": {"candidate_chunks": [], "validation_tests": []},
                "repomap": {"dependency_recall": {"hit_rate": 1.0}},
            },
        ),
        (
            "",
            {
                "index": {
                    "candidate_files": [
                        {"path": "src/worker.py", "module": "src.worker"},
                    ],
                    "candidate_chunks": [
                        {
                            "path": "src/worker.py",
                            "qualified_name": "plan_worker",
                            "signature": "def plan_worker",
                        }
                    ],
                },
                "source_plan": {
                    "candidate_chunks": [
                        {
                            "path": "src/worker.py",
                            "qualified_name": "plan_worker",
                            "signature": "def plan_worker",
                        }
                    ],
                    "validation_tests": [],
                },
                "repomap": {"dependency_recall": {"hit_rate": 1.0}},
            },
        ),
    ]

    for expected_label, payload in scenarios:
        row = evaluate_case_result(case=base_case, plan_payload=payload, latency_ms=6.0)
        assert row["chunk_stage_miss_applicable"] == 1.0
        assert row["chunk_stage_miss_classified"] == (
            1.0 if expected_label else 0.0
        )
        assert row["chunk_stage_miss"] == expected_label
        assert row["chunk_stage_miss_details"]["oracle_file_path"] == "src/worker.py"

    assert evaluate_case_result(
        case=base_case,
        plan_payload=scenarios[0][1],
        latency_ms=6.0,
    )["chunk_stage_miss_details"] == {
        "oracle_file_path": "src/worker.py",
        "oracle_chunk_ref": {
            "path": "src/worker.py",
            "qualified_name": "plan_worker",
        },
        "file_present": False,
        "raw_chunk_present": False,
        "source_plan_chunk_present": False,
    }


def test_compare_metrics_and_detect_regression() -> None:
    baseline = {
        "recall_at_k": 0.8,
        "precision_at_k": 0.8,
        "task_success_rate": 0.8,
        "utility_rate": 0.8,
        "noise_rate": 0.2,
        "dependency_recall": 0.9,
        "latency_p95_ms": 100.0,
    }
    current = {
        "recall_at_k": 0.7,
        "precision_at_k": 0.6,
        "task_success_rate": 0.7,
        "utility_rate": 0.7,
        "noise_rate": 0.4,
        "dependency_recall": 0.3,
        "latency_p95_ms": 130.0,
    }

    delta = compare_metrics(current=current, baseline=baseline)
    assert delta["precision_at_k"] == -0.20000000000000007

    regression = detect_regression(current=current, baseline=baseline, dependency_recall_floor=0.8)
    assert regression["regressed"] is True
    assert set(regression["failed_checks"]) == {"precision_at_k", "noise_rate", "latency_p95_ms", "dependency_recall"}
    assert len(regression["failed_thresholds"]) == 4


def test_resolve_regression_thresholds_with_profile_and_overrides() -> None:
    thresholds = resolve_regression_thresholds(
        profile="strict",
        overrides={
            "precision_tolerance": 0.02,
        },
    )

    assert thresholds["precision_tolerance"] == 0.02
    assert thresholds["latency_growth_factor"] == 1.1
    assert thresholds["dependency_recall_floor"] == 0.8
    assert thresholds["embedding_similarity_tolerance"] == 0.02



def test_aggregate_metrics_reports_latency_median() -> None:
    template = {
        "recall_hit": 1.0,
        "precision_at_k": 1.0,
        "utility_hit": 1.0,
        "noise_rate": 0.0,
        "dependency_recall": 1.0,
        "repomap_latency_ms": 3.0,
        "chunk_hit_at_k": 1.0,
        "chunks_per_file_mean": 1.0,
        "chunk_budget_used": 10.0,
        "validation_test_count": 2.0,
    }
    metrics = aggregate_metrics(
        [
            {**template, "latency_ms": 10.0},
            {**template, "latency_ms": 20.0},
            {**template, "latency_ms": 40.0},
        ]
    )

    assert metrics["latency_median_ms"] == 20.0
    assert metrics["latency_p95_ms"] == 40.0
    assert metrics["repomap_latency_median_ms"] == 3.0
    assert metrics["repomap_latency_p95_ms"] == 3.0


def test_evaluate_case_result_negative_control_can_expose_retrieval_task_gap() -> None:
    case = {
        "case_id": "c-gap",
        "query": "where benchmark guide lives",
        "expected_keys": ["benchmarking", "docs"],
        "top_k": 4,
        "task_success": {
            "mode": "negative_control",
            "min_validation_tests": 1,
        },
    }
    payload = {
        "index": {
            "candidate_files": [
                {"path": "docs/maintainers/BENCHMARKING.md", "module": "docs.maintainers.benchmarking"},
            ],
        },
        "source_plan": {"validation_tests": []},
        "repomap": {"dependency_recall": {"hit_rate": 0.5}},
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=8.0)

    assert row["recall_hit"] == 1.0
    assert row["utility_hit"] == 1.0
    assert row["task_success_hit"] == 0.0
    assert row["task_success_mode"] == "negative_control"
    assert row["task_success_failed_checks"] == ["validation_tests"]
    assert row["evidence_insufficient"] == 0.0
    assert row["evidence_insufficiency_reason"] == ""
    assert row["evidence_insufficiency_signals"] == []
    assert row["task_success_requirements"] == {
        "require_recall_hit": True,
        "min_validation_tests": 1,
    }

    metrics = aggregate_metrics([row])
    assert metrics["task_success_rate"] == 0.0
    assert metrics["utility_rate"] == 1.0
    assert metrics["missing_validation_rate"] == 0.0


def test_evaluate_case_result_reports_evidence_insufficiency_for_positive_failures() -> None:
    case = {
        "case_id": "c-insufficient",
        "query": "where benchmark guide lives",
        "expected_keys": ["benchmarking", "docs"],
        "top_k": 4,
        "task_success": {
            "mode": "positive",
            "min_validation_tests": 1,
        },
    }
    payload = {
        "index": {
            "candidate_files": [
                {
                    "path": "docs/maintainers/BENCHMARKING.md",
                    "module": "docs.maintainers.benchmarking",
                },
                {
                    "path": "src/noise.py",
                    "module": "src.noise",
                },
            ],
            "docs": {"enabled": True, "section_count": 0},
            "metadata": {
                "docs_enabled": True,
                "docs_section_count": 0,
                "docs_injected_count": 0,
            },
        },
        "source_plan": {
            "candidate_chunks": [],
            "validation_tests": [],
        },
        "repomap": {
            "dependency_recall": {"hit_rate": 0.0},
            "neighbor_paths": [],
        },
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=8.0)

    assert row["task_success_hit"] == 0.0
    assert row["evidence_insufficient"] == 1.0
    assert row["evidence_insufficiency_reason"] == "low_support"
    assert row["evidence_insufficiency_signals"] == [
        "missing_candidate_chunks",
        "low_chunk_support",
        "missing_validation_tests",
        "missing_docs_evidence",
        "missing_repomap_neighbors",
        "noisy_hit",
    ]
    assert row["evidence_no_candidate"] == 0.0
    assert row["evidence_low_support_chunk"] == 1.0
    assert row["evidence_missing_validation"] == 1.0
    assert row["evidence_budget_limited"] == 0.0
    assert row["evidence_noisy_hit"] == 1.0

    metrics = aggregate_metrics([row])
    assert metrics["evidence_insufficient_rate"] == 1.0
    assert metrics["no_candidate_rate"] == 0.0
    assert metrics["low_support_chunk_rate"] == 1.0
    assert metrics["missing_validation_rate"] == 1.0
    assert metrics["budget_limited_recovery_rate"] == 0.0
    assert metrics["noisy_hit_rate"] == 1.0


def test_evaluate_case_result_does_not_flag_missing_validation_when_not_required() -> None:
    case = {
        "case_id": "c-insufficient-no-validation-required",
        "query": "where worker planner lives",
        "expected_keys": ["worker"],
        "top_k": 4,
        "task_success": {
            "mode": "positive",
            "min_validation_tests": 0,
        },
    }
    payload = {
        "index": {
            "candidate_files": [
                {
                    "path": "docs/maintainers/BENCHMARKING.md",
                    "module": "docs.maintainers.benchmarking",
                },
                {
                    "path": "src/noise.py",
                    "module": "src.noise",
                },
            ],
            "docs": {"enabled": True, "section_count": 0},
            "metadata": {
                "docs_enabled": True,
                "docs_section_count": 0,
                "docs_injected_count": 0,
            },
        },
        "source_plan": {
            "candidate_chunks": [],
            "validation_tests": [],
        },
        "repomap": {
            "dependency_recall": {"hit_rate": 0.0},
            "neighbor_paths": [],
        },
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=8.0)

    assert row["task_success_failed_checks"] == ["recall_hit"]
    assert row["task_success_hit"] == 0.0
    assert row["evidence_insufficient"] == 1.0
    assert row["evidence_insufficiency_reason"] == "low_support"
    assert row["evidence_missing_validation"] == 0.0
    assert "missing_validation_tests" not in row["evidence_insufficiency_signals"]


def test_evaluate_case_result_reports_pure_missing_validation_failure() -> None:
    case = {
        "case_id": "c-missing-validation-only",
        "query": "where benchmark guide lives",
        "expected_keys": ["benchmarking", "docs"],
        "top_k": 4,
        "task_success": {
            "mode": "positive",
            "min_validation_tests": 1,
        },
    }
    payload = {
        "index": {
            "candidate_files": [
                {
                    "path": "docs/maintainers/BENCHMARKING.md",
                    "module": "docs.maintainers.benchmarking",
                }
            ],
            "candidate_chunks": [
                {
                    "path": "docs/maintainers/BENCHMARKING.md",
                    "qualified_name": "benchmarking_guide",
                    "signature": "benchmarking docs",
                }
            ],
            "docs": {"enabled": False, "section_count": 0},
            "metadata": {
                "docs_enabled": False,
                "docs_section_count": 0,
                "docs_injected_count": 0,
            },
        },
        "source_plan": {
            "candidate_chunks": [
                {
                    "path": "docs/maintainers/BENCHMARKING.md",
                    "qualified_name": "benchmarking_guide",
                    "signature": "benchmarking docs",
                }
            ],
            "validation_tests": [],
        },
        "repomap": {
            "dependency_recall": {"hit_rate": 1.0},
            "neighbor_paths": [
                "docs/maintainers/RELEASING.md",
            ],
        },
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=8.0)

    assert row["task_success_hit"] == 0.0
    assert row["task_success_failed_checks"] == ["validation_tests"]
    assert row["evidence_insufficient"] == 1.0
    assert row["evidence_insufficiency_reason"] == "missing_validation"
    assert row["evidence_insufficiency_signals"] == ["missing_validation_tests"]
    assert row["evidence_low_support_chunk"] == 0.0
    assert row["evidence_missing_validation"] == 1.0
    assert row["evidence_noisy_hit"] == 0.0


def test_evaluate_case_result_prefers_source_plan_chunks_for_chunk_metrics() -> None:
    case = {
        "case_id": "c-source-plan-chunks",
        "query": "where auth validation lives",
        "expected_keys": ["auth", "validate_token"],
        "top_k": 2,
    }
    payload = {
        "index": {
            "candidate_files": [
                {"path": "src/auth.py", "module": "src.auth"},
            ],
            "candidate_chunks": [
                {
                    "path": "src/noise.py",
                    "qualified_name": "noise",
                    "signature": "def noise",
                }
            ],
            "chunk_metrics": {
                "chunk_budget_used": 99.0,
                "chunks_per_file_mean": 4.0,
            },
        },
        "source_plan": {
            "candidate_chunks": [
                {
                    "path": "src/auth.py",
                    "qualified_name": "validate_token",
                    "signature": "def validate_token",
                },
                {
                    "path": "src/helper.py",
                    "qualified_name": "helper",
                    "signature": "def helper",
                },
            ],
            "chunk_budget_used": 12.0,
            "validation_tests": [],
        },
        "repomap": {"dependency_recall": {"hit_rate": 1.0}},
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=7.0)

    assert row["chunk_hit_at_k"] == 1.0
    assert row["candidate_chunk_refs"] == ["validate_token", "helper"]
    assert row["chunk_budget_used"] == 12.0
    assert row["chunks_per_file_mean"] == 1.0


def test_evaluate_case_result_falls_back_to_index_chunks_when_source_plan_missing() -> None:
    case = {
        "case_id": "c-index-chunks-fallback",
        "query": "where auth validation lives",
        "expected_keys": ["auth", "validate_token"],
        "top_k": 2,
    }
    payload = {
        "index": {
            "candidate_files": [
                {"path": "src/auth.py", "module": "src.auth"},
            ],
            "candidate_chunks": [
                {
                    "path": "src/auth.py",
                    "qualified_name": "validate_token",
                    "signature": "def validate_token",
                }
            ],
            "chunk_metrics": {
                "chunk_budget_used": 20.0,
                "chunks_per_file_mean": 2.0,
            },
        },
        "repomap": {"dependency_recall": {"hit_rate": 1.0}},
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=5.0)

    assert row["chunk_hit_at_k"] == 1.0
    assert row["candidate_chunk_refs"] == ["validate_token"]
    assert row["chunk_budget_used"] == 20.0
    assert row["chunks_per_file_mean"] == 2.0

def test_evaluate_case_result_can_omit_case_details() -> None:
    case = {
        "case_id": "c2",
        "query": "where auth",
        "expected_keys": ["auth"],
        "top_k": 4,
    }
    payload = {
        "index": {
            "candidate_files": [
                {"path": "src/auth.py", "module": "src.auth"},
            ],
            "candidate_chunks": [
                {"path": "src/auth.py", "qualified_name": "validate_token", "signature": "def validate_token"},
            ],
        },
        "repomap": {"dependency_recall": {"hit_rate": 1.0}},
    }

    row = evaluate_case_result(
        case=case,
        plan_payload=payload,
        latency_ms=5.0,
        include_case_details=False,
    )

    assert row["case_id"] == "c2"
    assert "candidate_paths" not in row
    assert "candidate_chunk_refs" not in row
    assert "expected_hits" not in row
    assert "chunk_hits" not in row
    assert "validation_tests" not in row
    assert "relevant_candidate_paths" not in row
    assert "noise_candidate_paths" not in row
    assert "candidate_matches" not in row

def test_detect_regression_for_validation_test_growth() -> None:
    baseline = {
        "recall_at_k": 0.9,
        "precision_at_k": 0.9,
        "task_success_rate": 0.9,
        "utility_rate": 0.9,
        "noise_rate": 0.1,
        "dependency_recall": 0.9,
        "latency_p95_ms": 100.0,
        "chunk_hit_at_k": 0.9,
        "chunk_budget_used": 20.0,
        "validation_test_count": 2.0,
    }
    current = dict(baseline)
    current["validation_test_count"] = 6.0

    regression = detect_regression(
        current=current,
        baseline=baseline,
        validation_test_growth_factor=2.0,
    )

    assert regression["regressed"] is True
    assert "validation_test_count" in regression["failed_checks"]


def test_evaluate_case_result_extracts_memory_metrics() -> None:
    case = {
        "case_id": "c3",
        "query": "fix auth memory",
        "expected_keys": ["auth"],
        "top_k": 4,
    }
    payload = {
        "index": {
            "candidate_files": [{"path": "src/auth.py", "module": "src.auth"}],
        },
        "memory": {
            "count": 4,
            "notes": {"selected_count": 2},
            "profile": {"selected_count": 3},
            "capture": {"triggered": True},
        },
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=9.0)

    assert row["notes_hit_ratio"] == 0.5
    assert row["profile_selected_count"] == 3.0
    assert row["capture_triggered"] == 1.0


def test_detect_regression_for_memory_metric_drop() -> None:
    baseline = {
        "recall_at_k": 0.9,
        "precision_at_k": 0.8,
        "task_success_rate": 0.9,
        "utility_rate": 0.9,
        "noise_rate": 0.2,
        "dependency_recall": 0.8,
        "latency_p95_ms": 100.0,
        "chunk_hit_at_k": 0.8,
        "chunk_budget_used": 20.0,
        "validation_test_count": 2.0,
        "notes_hit_ratio": 0.6,
        "profile_selected_mean": 2.5,
        "capture_trigger_ratio": 0.8,
    }
    current = dict(baseline)
    current.update(
        {
            "notes_hit_ratio": 0.3,
            "profile_selected_mean": 1.0,
            "capture_trigger_ratio": 0.4,
        }
    )

    regression = detect_regression(
        current=current,
        baseline=baseline,
        notes_hit_tolerance=0.1,
        profile_selected_tolerance=0.5,
        capture_trigger_tolerance=0.2,
    )

    assert regression["regressed"] is True
    assert "notes_hit_ratio" in regression["failed_checks"]
    assert "profile_selected_mean" in regression["failed_checks"]
    assert "capture_trigger_ratio" in regression["failed_checks"]


def test_detect_regression_for_embedding_metric_drop() -> None:
    baseline = {
        "precision_at_k": 0.8,
        "task_success_rate": 0.8,
        "noise_rate": 0.2,
        "latency_p95_ms": 100.0,
        "dependency_recall": 0.8,
        "chunk_hit_at_k": 0.8,
        "chunk_budget_used": 20.0,
        "validation_test_count": 2.0,
        "embedding_similarity_mean": 0.5,
        "embedding_rerank_ratio": 0.6,
        "embedding_cache_hit_ratio": 0.9,
        "embedding_fallback_ratio": 0.0,
    }
    current = dict(baseline)
    current.update(
        {
            "embedding_similarity_mean": 0.2,
            "embedding_rerank_ratio": 0.1,
            "embedding_cache_hit_ratio": 0.3,
            "embedding_fallback_ratio": 0.4,
        }
    )

    regression = detect_regression(
        current=current,
        baseline=baseline,
        embedding_similarity_tolerance=0.1,
        embedding_rerank_ratio_tolerance=0.2,
        embedding_cache_hit_tolerance=0.2,
        embedding_fallback_tolerance=0.1,
    )

    assert regression["regressed"] is True
    assert "embedding_similarity_mean" in regression["failed_checks"]
    assert "embedding_rerank_ratio" in regression["failed_checks"]
    assert "embedding_cache_hit_ratio" in regression["failed_checks"]
    assert "embedding_fallback_ratio" in regression["failed_checks"]


def test_evaluate_case_result_reports_year2_normalized_kpis() -> None:
    case = {
        "case_id": "c-year2-kpis",
        "query": "where auth validation lives",
        "expected_keys": ["auth", "validate_token"],
        "top_k": 4,
    }
    payload = {
        "index": {
            "candidate_files": [
                {"path": "src/auth.py", "module": "src.auth"},
                {"path": "src/token.py", "module": "src.token"},
                {"path": "src/helper.py", "module": "src.helper"},
            ],
            "candidate_chunks": [
                {
                    "path": "src/auth.py",
                    "qualified_name": "validate_token",
                    "signature": "def validate_token",
                },
                {
                    "path": "src/token.py",
                    "qualified_name": "load_token",
                    "signature": "def load_token",
                },
                {
                    "path": "src/helper.py",
                    "qualified_name": "helper",
                    "signature": "def helper",
                },
                {
                    "path": "src/helper.py",
                    "qualified_name": "helper_alt",
                    "signature": "def helper_alt",
                },
            ],
            "chunk_metrics": {
                "graph_seeded_chunk_count": 2.0,
                "graph_transfer_count": 3.0,
                "topological_shield_attenuated_chunk_count": 2.0,
                "topological_shield_attenuation_total": 0.5,
            },
            "topological_shield": {
                "enabled": True,
                "report_only": False,
                "attenuated_chunk_count": 2,
                "coverage_ratio": 0.5,
                "attenuation_total": 0.5,
            },
            "chunk_guard": {
                "enabled": True,
                "candidate_pool": 4,
                "pairwise_conflict_count": 3,
            },
        },
        "skills": {
            "selected": [{"name": "skill-a"}],
            "token_budget": 200,
            "token_budget_used": 50,
        },
        "source_plan": {
            "candidate_chunks": [
                {
                    "path": "src/auth.py",
                    "qualified_name": "validate_token",
                    "signature": "def validate_token",
                },
                {
                    "path": "src/token.py",
                    "qualified_name": "load_token",
                    "signature": "def load_token",
                },
            ],
            "packing": {
                "packed_path_count": 2,
            },
            "validation_tests": [],
        },
        "repomap": {"dependency_recall": {"hit_rate": 1.0}},
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=5.0)

    assert row["skills_token_budget_utilization_ratio"] == 0.25
    assert row["source_plan_chunk_retention_ratio"] == 0.5
    assert row["source_plan_packed_path_ratio"] == 2.0 / 3.0
    assert row["graph_transfer_per_seed_ratio"] == 1.5
    assert row["chunk_guard_pairwise_conflict_density"] == 0.75
    assert row["topological_shield_attenuation_per_chunk"] == 0.25
    assert row["skills_budget"]["utilization_ratio"] == 0.25
    assert row["graph_prior"]["transfer_per_seed_ratio"] == 1.5
    assert row["topological_shield"]["attenuation_per_chunk"] == 0.25
    assert row["source_plan_packing"]["packed_path_ratio"] == round(2.0 / 3.0, 6)
    assert row["source_plan_packing"]["chunk_retention_ratio"] == 0.5
    assert row["year2_normalized_kpis"] == {
        "skills_token_budget_utilization_ratio": 0.25,
        "source_plan_chunk_retention_ratio": 0.5,
        "source_plan_packed_path_ratio": round(2.0 / 3.0, 6),
        "graph_transfer_per_seed_ratio": 1.5,
        "chunk_guard_pairwise_conflict_density": 0.75,
        "topological_shield_attenuation_per_chunk": 0.25,
    }


def test_case_evaluation_payload_helpers_guard_zero_denominators() -> None:
    assert safe_ratio(5, 0) == 0.0
    assert safe_ratio(-2, 4) == 0.0
    assert count_unique_paths(
        [
            {"path": "src/auth.py"},
            {"path": "src/auth.py"},
            {"path": "src/token.py"},
            {"path": ""},
        ]
    ) == 2


def test_evaluate_case_result_reports_chunk_contract_fallback_kpis() -> None:
    case = {
        "case_id": "c-chunk-contract",
        "query": "find markdown auth docs",
        "expected_keys": ["guide", "auth"],
        "top_k": 3,
    }
    payload = {
        "index": {
            "candidate_files": [
                {"path": "docs/guide.md", "module": "docs.guide"},
                {"path": "docs/ops.md", "module": "docs.ops"},
            ],
            "candidate_chunks": [
                {
                    "path": "docs/guide.md",
                    "qualified_name": "guide",
                    "disclosure": "refs",
                    "disclosure_fallback_reason": "unsupported_language",
                },
                {
                    "path": "docs/ops.md",
                    "qualified_name": "ops",
                    "disclosure": "refs",
                    "disclosure_fallback_reason": "unsupported_language",
                },
                {
                    "path": "src/auth.py",
                    "qualified_name": "validate_token",
                    "disclosure": "skeleton_light",
                },
                {
                    "path": "src/token.py",
                    "qualified_name": "load_token",
                    "disclosure": "refs",
                    "disclosure_fallback_reason": "budget_guard",
                },
            ],
            "chunk_contract": {
                "fallback_count": 3,
                "skeleton_chunk_count": 1,
            },
        },
        "source_plan": {"validation_tests": []},
        "repomap": {"dependency_recall": {"hit_rate": 0.0}},
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=7.0)

    assert row["chunk_contract_fallback_count"] == 3.0
    assert row["chunk_contract_skeleton_chunk_count"] == 1.0
    assert row["chunk_contract_fallback_ratio"] == 0.75
    assert row["chunk_contract_skeleton_ratio"] == 0.25
    assert row["unsupported_language_fallback_count"] == 2.0
    assert row["unsupported_language_fallback_ratio"] == 0.5
    assert row["chunk_contract"] == {
        "fallback_count": 3,
        "skeleton_chunk_count": 1,
        "fallback_ratio": 0.75,
        "skeleton_ratio": 0.25,
        "unsupported_language_fallback_count": 2,
        "unsupported_language_fallback_ratio": 0.5,
    }

    metrics = aggregate_metrics([row])
    assert metrics["chunk_contract_fallback_count_mean"] == 3.0
    assert metrics["chunk_contract_skeleton_chunk_count_mean"] == 1.0
    assert metrics["chunk_contract_fallback_ratio"] == 0.75
    assert metrics["chunk_contract_skeleton_ratio"] == 0.25
    assert metrics["unsupported_language_fallback_count_mean"] == 2.0
    assert metrics["unsupported_language_fallback_ratio"] == 0.5
