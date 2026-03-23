from __future__ import annotations

from ace_lite.benchmark.case_evaluation_payloads import count_unique_paths, safe_ratio
from ace_lite.benchmark.report_metrics import ALL_METRIC_ORDER, COMPARABLE_METRIC_ORDER
from ace_lite.benchmark.scoring import (
    aggregate_metrics,
    build_comparison_lane_summary,
    build_deep_symbol_summary,
    build_feedback_loop_summary,
    build_learning_router_rollout_summary,
    build_ltm_explainability_summary,
    build_missing_context_risk_summary,
    build_native_scip_summary,
    build_retrieval_frontier_gate_summary,
    build_retrieval_control_plane_gate_summary,
    build_source_plan_failure_signal_summary,
    build_validation_probe_summary,
    build_source_plan_validation_feedback_summary,
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
        "retrieval_surface": "deep_symbol",
    }
    payload = {
        "index": {
            "candidate_files": [
                {"path": "src/auth.py", "module": "src.auth"},
                {"path": "src/token.py", "module": "src.token"},
            ],
            "chunk_semantic_rerank": {
                "reason": "ok",
                "retrieval_context_pool_chunk_count": 1.0,
                "retrieval_context_pool_coverage_ratio": 0.5,
            },
            "chunk_metrics": {
                "retrieval_context_chunk_count": 2.0,
                "retrieval_context_coverage_ratio": 1.0,
                "retrieval_context_char_count_mean": 84.0,
                "contextual_sidecar_parent_symbol_chunk_count": 2.0,
                "contextual_sidecar_parent_symbol_coverage_ratio": 1.0,
                "contextual_sidecar_reference_hint_chunk_count": 1.0,
                "contextual_sidecar_reference_hint_coverage_ratio": 0.5,
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
                "candidate_ranking": {
                    "multi_channel_rrf_enabled": True,
                    "multi_channel_rrf_applied": True,
                    "multi_channel_rrf_granularity_count": 2,
                    "multi_channel_rrf_pool_size": 5,
                    "multi_channel_rrf_granularity_pool_ratio": 0.4,
                },
                "scip": {
                    "enabled": True,
                    "loaded": True,
                    "provider": "scip",
                    "document_count": 5,
                    "definition_occurrence_count": 7,
                    "reference_occurrence_count": 11,
                    "symbol_definition_count": 3,
                },
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
            "steps": [
                {
                    "stage": "validate",
                    "validation_feedback_summary": {
                        "status": "failed",
                        "issue_count": 2,
                        "probe_status": "failed",
                        "probe_issue_count": 1,
                        "probe_executed_count": 1,
                        "selected_test_count": 1,
                        "executed_test_count": 1,
                    },
                }
            ],
            "ltm_constraint_summary": {
                "selected_count": 1,
                "constraint_count": 0,
                "graph_neighbor_count": 0,
                "handles": [],
            },
            "evidence_summary": {
                "direct_count": 1.0,
                "neighbor_context_count": 0.0,
                "hint_only_count": 0.0,
                "direct_ratio": 1.0,
                "neighbor_context_ratio": 0.0,
                "hint_only_ratio": 0.0,
                "symbol_count": 1.0,
                "signature_count": 1.0,
                "skeleton_count": 1.0,
                "robust_signature_count": 1.0,
                "symbol_ratio": 1.0,
                "signature_ratio": 1.0,
                "skeleton_ratio": 1.0,
                "robust_signature_ratio": 1.0,
            },
            "packing": {
                "graph_closure_preference_enabled": True,
                "graph_closure_bonus_candidate_count": 2,
                "graph_closure_preferred_count": 1,
                "granularity_preferred_count": 1,
                "focused_file_promoted_count": 1,
                "packed_path_count": 2,
                "reason": "graph_closure_preferred",
            },
        },
        "repomap": {
            "worktree_seed_count": 1,
            "subgraph_seed_count": 2,
            "seed_candidates_count": 3,
            "cache": {"hit": True},
            "precompute": {"hit": False},
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
                "failure_signal_summary": {
                    "status": "failed",
                    "issue_count": 2,
                    "probe_status": "failed",
                    "probe_issue_count": 1,
                    "probe_executed_count": 1,
                    "selected_test_count": 1,
                    "executed_test_count": 1,
                    "has_failure": True,
                    "source": "source_plan.validate_step",
                },
            },
            "stage_metrics": [
                {"stage": "repomap", "elapsed_ms": 4.5},
                {
                    "stage": "validation",
                    "elapsed_ms": 1.2,
                    "tags": {
                        "validation_probe_enabled": True,
                        "validation_probe_status": "failed",
                        "validation_probe_executed_count": 2,
                        "validation_probe_issue_count": 1,
                    },
                },
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
    assert row["repomap_worktree_seed_count"] == 1.0
    assert row["repomap_subgraph_seed_count"] == 2.0
    assert row["repomap_seed_candidates_count"] == 3.0
    assert row["repomap_cache_hit"] == 1.0
    assert row["repomap_precompute_hit"] == 0.0
    assert row["validation_test_count"] == 1
    assert row["validation_probe_enabled"] == 1.0
    assert row["validation_probe_status"] == "failed"
    assert row["validation_probe_executed_count"] == 2.0
    assert row["validation_probe_issue_count"] == 1.0
    assert row["validation_probe_failed"] == 1.0
    assert row["source_plan_validation_feedback_present"] == 1.0
    assert row["source_plan_validation_feedback_status"] == "failed"
    assert row["source_plan_validation_feedback_issue_count"] == 2.0
    assert row["source_plan_validation_feedback_failed"] == 1.0
    assert row["source_plan_validation_feedback_probe_status"] == "failed"
    assert row["source_plan_validation_feedback_probe_issue_count"] == 1.0
    assert row["source_plan_validation_feedback_probe_executed_count"] == 1.0
    assert row["source_plan_validation_feedback_probe_failed"] == 1.0
    assert row["source_plan_validation_feedback_selected_test_count"] == 1.0
    assert row["source_plan_validation_feedback_executed_test_count"] == 1.0
    assert row["source_plan_failure_signal_origin"] == "plan_replay_cache"
    assert row["source_plan_failure_signal_present"] == 1.0
    assert row["source_plan_failure_signal_status"] == "failed"
    assert row["source_plan_failure_signal_issue_count"] == 2.0
    assert row["source_plan_failure_signal_failed"] == 1.0
    assert row["source_plan_failure_signal_probe_status"] == "failed"
    assert row["source_plan_failure_signal_probe_issue_count"] == 1.0
    assert row["source_plan_failure_signal_probe_executed_count"] == 1.0
    assert row["source_plan_failure_signal_probe_failed"] == 1.0
    assert row["source_plan_failure_signal_selected_test_count"] == 1.0
    assert row["source_plan_failure_signal_executed_test_count"] == 1.0
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
    assert row["retrieval_context_chunk_count"] == 2.0
    assert row["retrieval_context_coverage_ratio"] == 1.0
    assert row["retrieval_context_char_count_mean"] == 84.0
    assert row["contextual_sidecar_parent_symbol_chunk_count"] == 2.0
    assert row["contextual_sidecar_parent_symbol_coverage_ratio"] == 1.0
    assert row["contextual_sidecar_reference_hint_chunk_count"] == 1.0
    assert row["contextual_sidecar_reference_hint_coverage_ratio"] == 0.5
    assert row["retrieval_context_pool_chunk_count"] == 1.0
    assert row["retrieval_context_pool_coverage_ratio"] == 0.5
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
    assert row["source_plan_symbol_count"] == 1.0
    assert row["source_plan_signature_count"] == 1.0
    assert row["source_plan_skeleton_count"] == 1.0
    assert row["source_plan_robust_signature_count"] == 1.0
    assert row["source_plan_symbol_ratio"] == 1.0
    assert row["source_plan_signature_ratio"] == 1.0
    assert row["source_plan_skeleton_ratio"] == 1.0
    assert row["source_plan_robust_signature_ratio"] == 1.0
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
    assert row["source_plan_granularity_preferred_count"] == 1.0
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
        "failure_signal_summary": {
            "status": "failed",
            "issue_count": 2,
            "probe_status": "failed",
            "probe_issue_count": 1,
            "probe_executed_count": 1,
            "selected_test_count": 1,
            "executed_test_count": 1,
            "has_failure": True,
            "source": "source_plan.validate_step",
        },
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
        "symbol_count": 1.0,
        "signature_count": 1.0,
        "skeleton_count": 1.0,
        "robust_signature_count": 1.0,
        "symbol_ratio": 1.0,
        "signature_ratio": 1.0,
        "skeleton_ratio": 1.0,
        "robust_signature_ratio": 1.0,
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
    assert row["index_fusion_granularity"] == {
        "enabled": True,
        "applied": True,
        "granularity_count": 2,
        "pool_size": 5,
        "granularity_pool_ratio": 0.4,
    }
    assert row["native_scip"] == {
        "loaded": True,
        "document_count": 5,
        "definition_occurrence_count": 7,
        "reference_occurrence_count": 11,
        "symbol_definition_count": 3,
    }
    assert row["source_plan_packing"] == {
        "graph_closure_preference_enabled": True,
        "graph_closure_bonus_candidate_count": 2,
        "graph_closure_preferred_count": 1,
        "granularity_preferred_count": 1,
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
    assert row["retrieval_context"] == {
        "chunk_count": 2,
        "coverage_ratio": 1.0,
        "char_count_mean": 84.0,
        "parent_symbol_chunk_count": 2,
        "parent_symbol_coverage_ratio": 1.0,
        "reference_hint_chunk_count": 1,
        "reference_hint_coverage_ratio": 0.5,
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
    assert set(metrics.keys()) == set(ALL_METRIC_ORDER)
    assert metrics["adaptive_router_shadow_coverage"] == 0.0
    assert metrics["risk_upgrade_precision_gain"] == 0.0
    assert metrics["deep_symbol_case_count"] == 1.0
    assert metrics["deep_symbol_case_recall"] == 1.0
    assert metrics["native_scip_loaded_rate"] == 1.0
    assert metrics["native_scip_document_count_mean"] == 5.0
    assert metrics["native_scip_definition_occurrence_count_mean"] == 7.0
    assert metrics["native_scip_reference_occurrence_count_mean"] == 11.0
    assert metrics["native_scip_symbol_definition_count_mean"] == 3.0
    assert metrics["repomap_worktree_seed_count_mean"] == 1.0
    assert metrics["repomap_subgraph_seed_count_mean"] == 2.0
    assert metrics["repomap_seed_candidates_count_mean"] == 3.0
    assert metrics["repomap_cache_hit_ratio"] == 1.0
    assert metrics["repomap_precompute_hit_ratio"] == 0.0

    assert metrics["latency_p95_ms"] == 12.5
    assert metrics["latency_median_ms"] == 12.5
    assert metrics["repomap_latency_p95_ms"] == 4.5
    assert metrics["repomap_latency_median_ms"] == 4.5
    assert metrics["memory_latency_p95_ms"] == 0.0
    assert metrics["index_latency_p95_ms"] == 0.0


def test_aggregate_metrics_uses_chunk_stage_success_for_deep_symbol_recall() -> None:
    metrics = aggregate_metrics(
        [
            {
                "deep_symbol_case": 1.0,
                "recall_hit": 1.0,
                "chunk_stage_miss_applicable": 1.0,
                "chunk_stage_miss": "source_plan_pack_miss",
            },
            {
                "deep_symbol_case": 1.0,
                "recall_hit": 1.0,
                "chunk_stage_miss_applicable": 1.0,
                "chunk_stage_miss": "",
            },
        ]
    )

    assert metrics["deep_symbol_case_count"] == 2.0
    assert metrics["deep_symbol_case_recall"] == 0.5


def test_evaluate_case_result_and_aggregate_preserves_extended_metric_contract() -> None:
    case = {
        "case_id": "c1",
        "query": "where validate token",
        "expected_keys": ["validate_token", "auth"],
        "top_k": 4,
        "comparison_lane": "stale_majority",
        "retrieval_surface": "deep_symbol",
    }
    payload = {
        "index": {
            "candidate_files": [
                {"path": "src/auth.py", "module": "src.auth"},
                {"path": "src/token.py", "module": "src.token"},
            ],
            "chunk_semantic_rerank": {
                "reason": "ok",
                "retrieval_context_pool_chunk_count": 1.0,
                "retrieval_context_pool_coverage_ratio": 0.5,
            },
            "chunk_metrics": {
                "retrieval_context_chunk_count": 2.0,
                "retrieval_context_coverage_ratio": 1.0,
                "retrieval_context_char_count_mean": 84.0,
                "contextual_sidecar_parent_symbol_chunk_count": 2.0,
                "contextual_sidecar_parent_symbol_coverage_ratio": 1.0,
                "contextual_sidecar_reference_hint_chunk_count": 1.0,
                "contextual_sidecar_reference_hint_coverage_ratio": 0.5,
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
            "candidate_ranking": {
                "multi_channel_rrf_enabled": True,
                "multi_channel_rrf_applied": True,
                "multi_channel_rrf_granularity_count": 2,
                "multi_channel_rrf_pool_size": 5,
                "multi_channel_rrf_granularity_pool_ratio": 0.4,
                "graph_lookup_weight_scip": 0.3,
                "graph_lookup_weight_xref": 0.2,
                "graph_lookup_weight_query_xref": 0.2,
                "graph_lookup_weight_symbol": 0.1,
                "graph_lookup_weight_import": 0.1,
                "graph_lookup_weight_coverage": 0.1,
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
                "max_query_coverage": 0.666667,
            },
            "scip": {
                "enabled": True,
                "loaded": True,
                "provider": "scip",
                "document_count": 5,
                "definition_occurrence_count": 7,
                "reference_occurrence_count": 11,
                "symbol_definition_count": 3,
            },
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
            "steps": [
                {
                    "stage": "validate",
                    "validation_feedback_summary": {
                        "status": "failed",
                        "issue_count": 2,
                        "probe_status": "failed",
                        "probe_issue_count": 1,
                        "probe_executed_count": 1,
                        "selected_test_count": 1,
                        "executed_test_count": 1,
                    },
                }
            ],
            "ltm_constraint_summary": {
                "selected_count": 1,
                "constraint_count": 0,
                "graph_neighbor_count": 0,
                "handles": [],
            },
            "evidence_summary": {
                "direct_count": 1.0,
                "neighbor_context_count": 0.0,
                "hint_only_count": 0.0,
                "direct_ratio": 1.0,
                "neighbor_context_ratio": 0.0,
                "hint_only_ratio": 0.0,
                "symbol_count": 1.0,
                "signature_count": 1.0,
                "skeleton_count": 1.0,
                "robust_signature_count": 1.0,
                "symbol_ratio": 1.0,
                "signature_ratio": 1.0,
                "skeleton_ratio": 1.0,
                "robust_signature_ratio": 1.0,
            },
            "packing": {
                "graph_closure_preference_enabled": True,
                "graph_closure_bonus_candidate_count": 2,
                "graph_closure_preferred_count": 1,
                "granularity_preferred_count": 1,
                "focused_file_promoted_count": 1,
                "packed_path_count": 2,
                "reason": "graph_closure_preferred",
            },
        },
        "repomap": {"dependency_recall": {"hit_rate": 1.0}},
        "observability": {
            "plan_replay_cache": {
                "enabled": True,
                "hit": True,
                "stale_hit_safe": True,
                "stage": "source_plan",
                "reason": "hit",
                "stored": False,
                "failure_signal_summary": {
                    "status": "failed",
                    "issue_count": 2,
                    "probe_status": "failed",
                    "probe_issue_count": 1,
                    "probe_executed_count": 1,
                    "selected_test_count": 1,
                    "executed_test_count": 1,
                    "has_failure": True,
                    "source": "source_plan.validate_step",
                },
            },
            "stage_metrics": [
                {"stage": "repomap", "elapsed_ms": 4.5},
                {
                    "stage": "validation",
                    "elapsed_ms": 1.2,
                    "tags": {
                        "validation_probe_enabled": True,
                        "validation_probe_status": "failed",
                        "validation_probe_executed_count": 2,
                        "validation_probe_issue_count": 1,
                    },
                },
            ],
        },
    }

    metrics = aggregate_metrics(
        [evaluate_case_result(case=case, plan_payload=payload, latency_ms=12.5)]
    )

    assert metrics["chunk_contract_fallback_count_mean"] == 0.0
    assert metrics["chunk_contract_skeleton_chunk_count_mean"] == 0.0
    assert metrics["chunk_contract_fallback_ratio"] == 0.0
    assert metrics["chunk_contract_skeleton_ratio"] == 0.0
    assert metrics["unsupported_language_fallback_count_mean"] == 0.0
    assert metrics["unsupported_language_fallback_ratio"] == 0.0
    assert metrics["retrieval_context_chunk_count_mean"] == 2.0
    assert metrics["retrieval_context_coverage_ratio"] == 1.0
    assert metrics["retrieval_context_char_count_mean"] == 84.0
    assert metrics["contextual_sidecar_parent_symbol_chunk_count_mean"] == 2.0
    assert metrics["contextual_sidecar_parent_symbol_coverage_ratio"] == 1.0
    assert metrics["contextual_sidecar_reference_hint_chunk_count_mean"] == 1.0
    assert metrics["contextual_sidecar_reference_hint_coverage_ratio"] == 0.5
    assert metrics["subgraph_payload_enabled_ratio"] == 0.0
    assert metrics["subgraph_seed_path_count_mean"] == 0.0
    assert metrics["subgraph_edge_type_count_mean"] == 0.0
    assert metrics["subgraph_edge_total_count_mean"] == 0.0
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
    assert metrics["dev_issue_capture_rate"] == 0.0

    assert metrics["chunk_guard_pairwise_conflict_count_mean"] == 0.0
    assert metrics["chunk_guard_fallback_ratio"] == 0.0
    assert metrics["skills_route_latency_p95_ms"] == 0.3
    assert metrics["skills_hydration_latency_p95_ms"] == 0.7
    assert metrics["skills_metadata_only_routing_ratio"] == 1.0
    assert metrics["skills_precomputed_route_ratio"] == 1.0
    assert metrics["plan_replay_cache_enabled_ratio"] == 1.0
    assert metrics["plan_replay_cache_hit_ratio"] == 1.0
    assert metrics["plan_replay_cache_stale_hit_safe_ratio"] == 1.0
    assert metrics["validation_probe_enabled_ratio"] == 1.0
    assert metrics["validation_probe_executed_count_mean"] == 2.0
    assert metrics["validation_probe_failure_rate"] == 1.0
    assert metrics["source_plan_validation_feedback_present_ratio"] == 1.0
    assert metrics["source_plan_validation_feedback_issue_count_mean"] == 2.0
    assert metrics["source_plan_validation_feedback_failure_rate"] == 1.0
    assert metrics["source_plan_validation_feedback_probe_issue_count_mean"] == 1.0
    assert (
        metrics["source_plan_validation_feedback_probe_executed_count_mean"] == 1.0
    )
    assert metrics["source_plan_validation_feedback_probe_failure_rate"] == 1.0
    assert metrics["source_plan_validation_feedback_selected_test_count_mean"] == 1.0
    assert metrics["source_plan_validation_feedback_executed_test_count_mean"] == 1.0
    assert metrics["source_plan_failure_signal_present_ratio"] == 1.0
    assert metrics["source_plan_failure_signal_issue_count_mean"] == 2.0
    assert metrics["source_plan_failure_signal_failure_rate"] == 1.0
    assert metrics["source_plan_failure_signal_probe_issue_count_mean"] == 1.0
    assert metrics["source_plan_failure_signal_probe_executed_count_mean"] == 1.0
    assert metrics["source_plan_failure_signal_probe_failure_rate"] == 1.0
    assert metrics["source_plan_failure_signal_selected_test_count_mean"] == 1.0
    assert metrics["source_plan_failure_signal_executed_test_count_mean"] == 1.0
    assert metrics["source_plan_failure_signal_replay_cache_origin_ratio"] == 1.0
    assert metrics["source_plan_failure_signal_observability_origin_ratio"] == 0.0
    assert metrics["source_plan_failure_signal_source_plan_origin_ratio"] == 0.0
    assert metrics["source_plan_failure_signal_validate_step_origin_ratio"] == 0.0
    assert metrics["source_plan_direct_evidence_ratio"] == 1.0
    assert metrics["source_plan_graph_closure_preference_enabled_ratio"] == 1.0
    assert metrics["source_plan_graph_closure_bonus_candidate_count_mean"] == 2.0
    assert metrics["source_plan_graph_closure_preferred_count_mean"] == 1.0
    assert metrics["source_plan_granularity_preferred_count_mean"] == 1.0
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
    assert metrics["memory_helpful_task_success_rate"] == 0.0
    assert metrics["ltm_hit_ratio"] == 0.0
    assert metrics["ltm_effective_hit_rate"] == 0.0
    assert metrics["ltm_false_help_rate"] == 0.0
    assert metrics["ltm_stale_hit_rate"] == 0.0
    assert metrics["ltm_replay_drift_rate"] == 0.0
    assert metrics["ltm_latency_overhead_ms"] == 0.0


def test_feedback_loop_summary_and_metrics() -> None:
    case_results = [
        {
            "case_id": "issue-exported",
            "comparison_lane": "issue_report_feedback",
            "issue_report_issue_id": "iss_123",
            "issue_report_has_plan_ref": 1.0,
            "issue_report_resolved_at": "2026-03-19T12:00:00+00:00",
            "issue_report_time_to_fix_hours": 12.0,
            "feedback_surface": "issue_report_export_cli",
            "task_success_hit": 1.0,
        },
        {
            "case_id": "issue-manual",
            "comparison_lane": "issue_report_feedback",
            "issue_report_issue_id": "",
            "issue_report_has_plan_ref": 0.0,
            "issue_report_resolved_at": "",
            "issue_report_time_to_fix_hours": 0.0,
            "feedback_surface": "issue_report_export_mcp",
            "task_success_hit": 1.0,
        },
        {
            "case_id": "runtime-captured-cli",
            "comparison_lane": "dev_issue_capture",
            "feedback_surface": "runtime_issue_capture_cli",
            "dev_feedback_issue_count": 1.0,
            "task_success_hit": 1.0,
        },
        {
            "case_id": "runtime-captured-mcp",
            "comparison_lane": "dev_issue_capture",
            "feedback_surface": "runtime_issue_capture_mcp",
            "dev_feedback_issue_count": 1.0,
            "task_success_hit": 1.0,
        },
        {
            "case_id": "resolved",
            "comparison_lane": "dev_feedback_resolution",
            "feedback_surface": "issue_resolution_cli",
            "dev_feedback_issue_count": 1.0,
            "dev_feedback_linked_fix_issue_count": 1.0,
            "dev_feedback_resolved_issue_count": 1.0,
            "dev_feedback_issue_time_to_fix_hours": 6.0,
            "task_success_hit": 1.0,
        },
        {
            "case_id": "unresolved",
            "comparison_lane": "dev_feedback_resolution",
            "feedback_surface": "issue_resolution_mcp",
            "dev_feedback_issue_count": 1.0,
            "dev_feedback_linked_fix_issue_count": 0.0,
            "dev_feedback_resolved_issue_count": 0.0,
            "task_success_hit": 0.0,
        },
    ]

    metrics = aggregate_metrics(case_results)
    summary = build_feedback_loop_summary(case_results)

    assert metrics["issue_to_benchmark_case_conversion_rate"] == 0.5
    assert metrics["issue_report_linked_plan_rate"] == 1.0
    assert metrics["issue_report_time_to_fix_hours_mean"] == 12.0
    assert metrics["dev_issue_capture_rate"] == 1.0
    assert metrics["dev_feedback_resolution_rate"] == 0.5
    assert metrics["dev_issue_to_fix_rate"] == 0.5
    assert summary["issue_report_case_count"] == 2
    assert summary["issue_report_linked_case_count"] == 1
    assert summary["issue_report_linked_plan_case_count"] == 1
    assert summary["issue_report_resolved_case_count"] == 1
    assert summary["issue_report_resolution_rate"] == 0.5
    assert summary["issue_report_time_to_fix_case_count"] == 1
    assert summary["issue_report_time_to_fix_hours_mean"] == 12.0
    assert summary["dev_issue_capture_case_count"] == 2
    assert summary["dev_issue_captured_case_count"] == 2
    assert summary["dev_issue_capture_rate"] == 1.0
    assert summary["dev_feedback_resolution_case_count"] == 2
    assert summary["dev_feedback_resolved_case_count"] == 1
    assert summary["dev_feedback_issue_count"] == 2
    assert summary["dev_feedback_linked_fix_issue_count"] == 1
    assert summary["dev_feedback_resolved_issue_count"] == 1
    assert summary["dev_issue_to_fix_rate"] == 0.5
    assert summary["dev_feedback_issue_time_to_fix_case_count"] == 1
    assert summary["dev_feedback_issue_time_to_fix_hours_mean"] == 6.0
    assert summary["feedback_surfaces"] == {
        "issue_report_export_cli": 1,
        "issue_report_export_mcp": 1,
        "runtime_issue_capture_cli": 1,
        "runtime_issue_capture_mcp": 1,
        "issue_resolution_cli": 1,
        "issue_resolution_mcp": 1,
    }


def test_ltm_summary_metrics_use_lane_specific_plan_attribution_signals() -> None:
    case_results = [
        {
            "case_id": "helpful-hit",
            "comparison_lane": "memory-helpful",
            "ltm_plan_constraint_count": 1.0,
            "task_success_hit": 1.0,
            "memory_latency_ms": 8.0,
        },
        {
            "case_id": "helpful-miss",
            "comparison_lane": "memory-helpful",
            "ltm_plan_constraint_count": 0.0,
            "task_success_hit": 1.0,
            "memory_latency_ms": 4.0,
        },
        {
            "case_id": "harmful-polluted",
            "comparison_lane": "memory-harmful-negative-control",
            "ltm_plan_constraint_count": 1.0,
            "task_success_hit": 0.0,
            "memory_latency_ms": 8.0,
        },
        {
            "case_id": "harmful-clean",
            "comparison_lane": "memory-harmful-negative-control",
            "ltm_plan_constraint_count": 0.0,
            "task_success_hit": 1.0,
            "memory_latency_ms": 4.0,
        },
        {
            "case_id": "time-sensitive-stale",
            "comparison_lane": "time-sensitive",
            "ltm_plan_constraint_count": 1.0,
            "task_success_hit": 0.0,
            "plan_replay_cache_stale_hit_safe": 0.0,
            "memory_latency_ms": 8.0,
        },
        {
            "case_id": "time-sensitive-safe",
            "comparison_lane": "time-sensitive",
            "ltm_plan_constraint_count": 1.0,
            "task_success_hit": 1.0,
            "plan_replay_cache_stale_hit_safe": 1.0,
            "memory_latency_ms": 8.0,
        },
    ]

    metrics = aggregate_metrics(case_results)

    assert metrics["memory_helpful_task_success_rate"] == 1.0
    assert metrics["ltm_hit_ratio"] == 0.5
    assert metrics["ltm_effective_hit_rate"] == 1.0
    assert metrics["ltm_false_help_rate"] == 0.5
    assert metrics["ltm_stale_hit_rate"] == 0.5
    assert metrics["ltm_replay_drift_rate"] == 0.5
    assert metrics["ltm_latency_overhead_ms"] == 4.0


def test_build_ltm_explainability_summary_aggregates_case_level_signals() -> None:
    summary = build_ltm_explainability_summary(
        [
            {
                "case_id": "case-a",
                "ltm_selected_count": 2.0,
                "ltm_attribution_count": 1.0,
                "ltm_graph_neighbor_count": 1.0,
                "ltm_plan_constraint_count": 1.0,
            },
            {
                "case_id": "case-b",
                "ltm_selected_count": 0.0,
                "ltm_attribution_count": 0.0,
                "ltm_graph_neighbor_count": 0.0,
                "ltm_plan_constraint_count": 0.0,
            },
            {
                "case_id": "case-c",
                "ltm_selected_count": 1.0,
                "ltm_attribution_count": 1.0,
                "ltm_graph_neighbor_count": 0.0,
                "ltm_plan_constraint_count": 1.0,
            },
        ]
    )

    assert summary == {
        "case_count": 3,
        "selected_case_count": 2,
        "selected_case_rate": 2.0 / 3.0,
        "selected_count_mean": 1.0,
        "attribution_case_count": 2,
        "attribution_case_rate": 2.0 / 3.0,
        "attribution_count_mean": 2.0 / 3.0,
        "graph_neighbor_case_count": 1,
        "graph_neighbor_case_rate": 1.0 / 3.0,
        "graph_neighbor_count_mean": 1.0 / 3.0,
        "plan_constraint_case_count": 2,
        "plan_constraint_case_rate": 2.0 / 3.0,
        "plan_constraint_count_mean": 2.0 / 3.0,
    }


def test_evaluate_case_result_applies_candidate_path_exclusions() -> None:
    case = {
        "case_id": "c-filtered",
        "query": "where does validation stage build result",
        "expected_keys": ["validation", "result"],
        "top_k": 4,
        "filters": {
            "exclude_paths": ["tests/e2e/test_benchmark_case_files.py"],
            "exclude_globs": ["tests/e2e/test_*benchmark*.py"],
        },
    }
    payload = {
        "index": {
            "candidate_files": [
                {
                    "path": "tests/e2e/test_benchmark_case_files.py",
                    "module": "tests.e2e.test_benchmark_case_files",
                },
                {
                    "path": "src/ace_lite/pipeline/stages/validation.py",
                    "module": "ace.validation",
                },
                {"path": "src/ace_lite/schema.py", "module": "ace.schema"},
            ],
            "candidate_chunks": [
                {
                    "path": "tests/e2e/test_benchmark_case_files.py",
                    "qualified_name": "test_validation_rich_cases_cover_validation_and_agent_loop_surfaces",
                },
                {
                    "path": "src/ace_lite/pipeline/stages/validation.py",
                    "qualified_name": "build_validation_result_v1",
                },
            ],
        },
        "source_plan": {
            "candidate_chunks": [
                {
                    "path": "tests/e2e/test_benchmark_case_files.py",
                    "qualified_name": "test_validation_rich_cases_cover_validation_and_agent_loop_surfaces",
                },
                {
                    "path": "src/ace_lite/pipeline/stages/validation.py",
                    "qualified_name": "build_validation_result_v1",
                },
            ],
            "validation_tests": ["tests.test_validation::test_result"],
        },
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=9.0)

    assert row["candidate_paths"] == [
        "src/ace_lite/pipeline/stages/validation.py",
        "src/ace_lite/schema.py",
    ]
    assert row["candidate_chunk_refs"] == ["build_validation_result_v1"]
    assert row["noise_candidate_paths"] == ["src/ace_lite/schema.py"]
    assert row["candidate_path_filters"] == {
        "include_paths": [],
        "include_globs": [],
        "exclude_paths": ["tests/e2e/test_benchmark_case_files.py"],
        "exclude_globs": ["tests/e2e/test_*benchmark*.py"],
    }
    assert "tests/e2e/test_benchmark_case_files.py" not in row["candidate_paths"]


def test_evaluate_case_result_applies_candidate_path_inclusions() -> None:
    case = {
        "case_id": "c-include",
        "query": "where are maintainer docs",
        "expected_keys": ["releasing", "benchmarking", "maintainers"],
        "top_k": 4,
        "filters": {
            "include_globs": ["docs/maintainers/*.md"],
        },
    }
    payload = {
        "index": {
            "candidate_files": [
                {
                    "path": "docs/maintainers/RELEASING.md",
                    "module": "docs.maintainers.RELEASING",
                },
                {
                    "path": "docs/maintainers/BENCHMARKING.md",
                    "module": "docs.maintainers.BENCHMARKING",
                },
                {
                    "path": "scripts/run_quality_gate.py",
                    "module": "scripts.run_quality_gate",
                },
            ],
            "candidate_chunks": [
                {
                    "path": "docs/maintainers/RELEASING.md",
                    "qualified_name": "RELEASING",
                },
                {
                    "path": "scripts/run_quality_gate.py",
                    "qualified_name": "run_quality_gate",
                },
            ],
        },
        "source_plan": {
            "candidate_chunks": [
                {
                    "path": "docs/maintainers/RELEASING.md",
                    "qualified_name": "RELEASING",
                },
                {
                    "path": "scripts/run_quality_gate.py",
                    "qualified_name": "run_quality_gate",
                },
            ],
            "validation_tests": ["tests.test_docs::test_checkpoint"],
        },
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=6.0)

    assert row["candidate_paths"] == [
        "docs/maintainers/RELEASING.md",
        "docs/maintainers/BENCHMARKING.md",
    ]
    assert row["candidate_chunk_refs"] == ["RELEASING"]
    assert row["candidate_path_filters"] == {
        "include_paths": [],
        "include_globs": ["docs/maintainers/*.md"],
        "exclude_paths": [],
        "exclude_globs": [],
    }
    assert "scripts/run_quality_gate.py" not in row["candidate_paths"]


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


def test_missing_context_risk_summary_reports_risk_upgrade_precision_gain() -> None:
    summary = build_missing_context_risk_summary(
        [
            {
                "task_success_mode": "positive",
                "recall_hit": 1.0,
                "chunk_hit_at_k": 0.0,
                "noise_rate": 0.0,
                "evidence_insufficient": 1.0,
                "precision_at_k": 1.0,
                "decision_trace": [
                    {
                        "stage": "index",
                        "action": "retry",
                        "target": "deterministic_refine",
                        "reason": "low_candidate_count",
                        "outcome": "applied",
                    }
                ],
            },
            {
                "task_success_mode": "positive",
                "recall_hit": 1.0,
                "chunk_hit_at_k": 0.0,
                "noise_rate": 0.0,
                "evidence_insufficient": 1.0,
                "precision_at_k": 0.25,
                "decision_trace": [],
            },
        ]
    )

    assert summary["elevated_case_count"] == 2
    assert summary["risk_upgrade_case_count"] == 1
    assert summary["risk_upgrade_case_rate"] == 0.5
    assert summary["risk_upgrade_precision_mean"] == 1.0
    assert summary["risk_baseline_precision_mean"] == 0.25
    assert summary["risk_upgrade_precision_gain"] == 0.75


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


def test_compare_metrics_preserves_registry_order() -> None:
    delta = compare_metrics(current={"utility_rate": 0.5}, baseline={})

    assert list(delta.keys()) == list(COMPARABLE_METRIC_ORDER)
    assert delta["task_success_rate"] == 0.5
    assert delta["utility_rate"] == 0.5


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
    assert thresholds["memory_helpful_task_success_tolerance"] == 0.02
    assert thresholds["ltm_false_help_tolerance"] == 0.02
    assert thresholds["ltm_stale_hit_tolerance"] == 0.02
    assert thresholds["plan_replay_cache_stale_hit_safe_tolerance"] == 0.05
    assert thresholds["issue_report_linked_plan_tolerance"] == 0.05
    assert thresholds["issue_to_benchmark_case_conversion_tolerance"] == 0.05
    assert thresholds["dev_feedback_resolution_tolerance"] == 0.05
    assert thresholds["dev_issue_to_fix_tolerance"] == 0.05
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
        "validation_probe_enabled": 1.0,
        "validation_probe_executed_count": 2.0,
        "validation_probe_failed": 0.0,
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
    assert metrics["validation_probe_enabled_ratio"] == 1.0
    assert metrics["validation_probe_executed_count_mean"] == 2.0
    assert metrics["validation_probe_failure_rate"] == 0.0


def test_aggregate_metrics_empty_uses_registry_order() -> None:
    metrics = aggregate_metrics([])

    assert list(metrics.keys()) == list(ALL_METRIC_ORDER)
    assert all(value == 0.0 for value in metrics.values())


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
            "ltm": {
                "selected_count": 2,
                "attribution_count": 1,
                "attribution": [
                    {
                        "handle": "fact-1",
                        "summary": "runtime.validation.git fallback_policy reuse_checkout_or_skip",
                        "graph_neighborhood": {
                            "triple_count": 1,
                            "triples": [
                                {
                                    "subject": "reuse_checkout_or_skip",
                                    "predicate": "recommended_for",
                                    "object": "runtime.validation.git",
                                }
                            ],
                        },
                    }
                ],
            },
        },
        "source_plan": {
            "ltm_constraint_summary": {
                "selected_count": 2,
                "constraint_count": 1,
                "graph_neighbor_count": 1,
                "handles": ["fact-1"],
            },
        },
        "index": {
            "candidate_files": [{"path": "src/auth.py", "module": "src.auth"}],
            "candidate_ranking": {
                "feedback_enabled": True,
                "feedback_reason": "ok",
                "feedback_event_count": 4,
                "feedback_matched_event_count": 2,
                "feedback_boosted_count": 1,
                "feedback_boosted_paths": 1,
                "multi_channel_rrf_enabled": True,
                "multi_channel_rrf_applied": True,
                "multi_channel_rrf_granularity_count": 2,
                "multi_channel_rrf_pool_size": 5,
                "multi_channel_rrf_granularity_pool_ratio": 0.4,
            },
        },
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=9.0)

    assert row["notes_hit_ratio"] == 0.5
    assert row["profile_selected_count"] == 3.0
    assert row["capture_triggered"] == 1.0
    assert row["ltm_selected_count"] == 2.0
    assert row["ltm_attribution_count"] == 1.0
    assert row["ltm_graph_neighbor_count"] == 1.0
    assert row["ltm_plan_constraint_count"] == 1.0
    assert row["ltm_explainability"]["attribution_preview"] == [
        "runtime.validation.git fallback_policy reuse_checkout_or_skip | graph: reuse_checkout_or_skip recommended_for runtime.validation.git"
    ]
    assert row["feedback_enabled"] == 1.0
    assert row["feedback_reason"] == "ok"
    assert row["feedback_event_count"] == 4.0
    assert row["feedback_matched_event_count"] == 2.0
    assert row["feedback_boosted_count"] == 1.0
    assert row["feedback_boosted_paths"] == 1.0
    assert row["multi_channel_rrf_enabled"] == 1.0
    assert row["multi_channel_rrf_applied"] == 1.0
    assert row["multi_channel_rrf_granularity_count"] == 2.0
    assert row["multi_channel_rrf_pool_size"] == 5.0
    assert row["multi_channel_rrf_granularity_pool_ratio"] == 0.4


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


def test_detect_regression_for_feedback_loop_metric_drop() -> None:
    baseline = {
        "precision_at_k": 0.8,
        "task_success_rate": 0.8,
        "noise_rate": 0.2,
        "latency_p95_ms": 100.0,
        "dependency_recall": 0.8,
        "chunk_hit_at_k": 0.8,
        "chunk_budget_used": 20.0,
        "validation_test_count": 2.0,
        "issue_report_linked_plan_rate": 1.0,
        "issue_to_benchmark_case_conversion_rate": 0.8,
        "dev_feedback_resolution_rate": 0.9,
        "dev_issue_to_fix_rate": 0.8,
    }
    current = dict(baseline)
    current.update(
        {
            "issue_report_linked_plan_rate": 0.6,
            "issue_to_benchmark_case_conversion_rate": 0.5,
            "dev_feedback_resolution_rate": 0.6,
            "dev_issue_to_fix_rate": 0.5,
        }
    )

    regression = detect_regression(
        current=current,
        baseline=baseline,
        issue_report_linked_plan_tolerance=0.1,
        issue_to_benchmark_case_conversion_tolerance=0.1,
        dev_feedback_resolution_tolerance=0.1,
        dev_issue_to_fix_tolerance=0.1,
    )

    assert regression["regressed"] is True
    assert "issue_report_linked_plan_rate" in regression["failed_checks"]
    assert "issue_to_benchmark_case_conversion_rate" in regression["failed_checks"]
    assert "dev_feedback_resolution_rate" in regression["failed_checks"]
    assert "dev_issue_to_fix_rate" in regression["failed_checks"]


def test_detect_regression_for_memory_lane_and_replay_drift_metrics() -> None:
    baseline = {
        "precision_at_k": 0.8,
        "task_success_rate": 0.8,
        "noise_rate": 0.2,
        "latency_p95_ms": 100.0,
        "dependency_recall": 0.8,
        "memory_helpful_task_success_rate": 0.9,
        "chunk_hit_at_k": 0.8,
        "chunk_budget_used": 20.0,
        "validation_test_count": 2.0,
        "ltm_false_help_rate": 0.0,
        "ltm_stale_hit_rate": 0.0,
        "plan_replay_cache_stale_hit_safe_ratio": 1.0,
    }
    current = dict(baseline)
    current.update(
        {
            "memory_helpful_task_success_rate": 0.6,
            "ltm_false_help_rate": 0.2,
            "ltm_stale_hit_rate": 0.2,
            "plan_replay_cache_stale_hit_safe_ratio": 0.7,
        }
    )

    regression = detect_regression(
        current=current,
        baseline=baseline,
        memory_helpful_task_success_tolerance=0.1,
        ltm_false_help_tolerance=0.05,
        ltm_stale_hit_tolerance=0.05,
        plan_replay_cache_stale_hit_safe_tolerance=0.1,
    )

    assert regression["regressed"] is True
    assert "memory_helpful_task_success_rate" in regression["failed_checks"]
    assert "ltm_false_help_rate" in regression["failed_checks"]
    assert "ltm_stale_hit_rate" in regression["failed_checks"]
    assert "plan_replay_cache_stale_hit_safe_ratio" in regression["failed_checks"]


def test_detect_regression_for_ltm_latency_overhead_growth() -> None:
    baseline = {
        "precision_at_k": 0.8,
        "task_success_rate": 0.8,
        "noise_rate": 0.2,
        "latency_p95_ms": 100.0,
        "dependency_recall": 0.8,
        "chunk_hit_at_k": 0.8,
        "chunk_budget_used": 20.0,
        "validation_test_count": 2.0,
        "ltm_latency_overhead_ms": 4.0,
    }
    current = dict(baseline)
    current["ltm_latency_overhead_ms"] = 6.0

    regression = detect_regression(
        current=current,
        baseline=baseline,
        latency_growth_factor=1.25,
    )

    assert regression["regressed"] is True
    assert "ltm_latency_overhead_ms" in regression["failed_checks"]


def test_detect_regression_does_not_gate_ltm_latency_overhead_without_baseline() -> None:
    baseline = {
        "precision_at_k": 0.8,
        "task_success_rate": 0.8,
        "noise_rate": 0.2,
        "latency_p95_ms": 100.0,
        "dependency_recall": 0.8,
        "chunk_hit_at_k": 0.8,
        "chunk_budget_used": 20.0,
        "validation_test_count": 2.0,
        "ltm_latency_overhead_ms": 0.0,
    }
    current = dict(baseline)
    current["ltm_latency_overhead_ms"] = 20.0

    regression = detect_regression(
        current=current,
        baseline=baseline,
        latency_growth_factor=1.10,
    )

    assert "ltm_latency_overhead_ms" not in regression["failed_checks"]


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


def test_evaluate_case_result_reports_subgraph_payload_kpis() -> None:
    case = {
        "case_id": "c-subgraph",
        "query": "trace auth graph neighborhood",
        "expected_keys": ["auth", "token"],
        "top_k": 4,
    }
    payload = {
        "index": {
            "candidate_files": [{"path": "src/auth.py", "module": "src.auth"}],
            "candidate_chunks": [
                {
                    "path": "src/auth.py",
                    "qualified_name": "validate_token",
                    "signature": "def validate_token",
                }
            ],
            "subgraph_payload": {
                "enabled": True,
                "reason": "ok",
                "seed_paths": ["src/auth.py"],
                "edge_counts": {"graph_lookup": 1},
            },
        },
        "source_plan": {
            "validation_tests": [],
            "subgraph_payload": {
                "enabled": True,
                "reason": "ok",
                "seed_paths": ["src/auth.py", "src/session.py"],
                "edge_counts": {
                    "graph_lookup": 2,
                    "graph_prior": 1,
                    "graph_closure_bonus": 1,
                },
            },
        },
        "repomap": {"dependency_recall": {"hit_rate": 1.0}},
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=6.0)

    assert row["subgraph_payload_enabled"] == 1.0
    assert row["subgraph_seed_path_count"] == 2.0
    assert row["subgraph_edge_type_count"] == 3.0
    assert row["subgraph_edge_total_count"] == 4.0
    assert row["subgraph_payload"] == {
        "enabled": True,
        "reason": "ok",
        "seed_path_count": 2,
        "edge_type_count": 3,
        "edge_total_count": 4,
        "seed_paths": ["src/auth.py", "src/session.py"],
        "edge_counts": {
            "graph_lookup": 2,
            "graph_prior": 1,
            "graph_closure_bonus": 1,
        },
    }

    metrics = aggregate_metrics([row])
    assert metrics["subgraph_payload_enabled_ratio"] == 1.0
    assert metrics["subgraph_seed_path_count_mean"] == 2.0
    assert metrics["subgraph_edge_type_count_mean"] == 3.0
    assert metrics["subgraph_edge_total_count_mean"] == 4.0


def test_evaluate_case_result_reports_graph_lookup_kpis() -> None:
    case = {
        "case_id": "c-graph-lookup",
        "query": "trace auth graph lookup",
        "expected_keys": ["auth", "token"],
        "top_k": 4,
    }
    payload = {
        "index": {
            "candidate_files": [{"path": "src/auth.py", "module": "src.auth"}],
            "candidate_ranking": {
                "graph_lookup_weight_scip": 0.3,
                "graph_lookup_weight_xref": 0.2,
                "graph_lookup_weight_query_xref": 0.2,
                "graph_lookup_weight_symbol": 0.1,
                "graph_lookup_weight_import": 0.1,
                "graph_lookup_weight_coverage": 0.1,
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
                "max_query_coverage": 0.666667,
            },
        },
        "source_plan": {"validation_tests": []},
        "repomap": {"dependency_recall": {"hit_rate": 1.0}},
    }

    row = evaluate_case_result(case=case, plan_payload=payload, latency_ms=6.0)

    assert row["graph_lookup_enabled"] == 1.0
    assert row["graph_lookup_reason"] == "candidate_count_guarded"
    assert row["graph_lookup_guarded"] == 1.0
    assert row["graph_lookup_boosted_count"] == 2.0
    assert row["graph_lookup_weight_scip"] == 0.3
    assert row["graph_lookup_weight_xref"] == 0.2
    assert row["graph_lookup_weight_query_xref"] == 0.2
    assert row["graph_lookup_candidate_count"] == 6.0
    assert row["graph_lookup_pool_size"] == 4.0
    assert row["graph_lookup_query_terms_count"] == 3.0
    assert row["graph_lookup_normalization"] == "log1p"
    assert row["graph_lookup_guard_max_candidates"] == 4.0
    assert row["graph_lookup_guard_min_query_terms"] == 1.0
    assert row["graph_lookup_guard_max_query_terms"] == 5.0
    assert row["graph_lookup_query_hit_paths"] == 1.0
    assert row["graph_lookup_scip_signal_paths"] == 2.0
    assert row["graph_lookup_xref_signal_paths"] == 3.0
    assert row["graph_lookup_symbol_hit_paths"] == 1.0
    assert row["graph_lookup_import_hit_paths"] == 1.0
    assert row["graph_lookup_coverage_hit_paths"] == 2.0
    assert row["graph_lookup_max_inbound"] == 4.0
    assert row["graph_lookup_max_xref_count"] == 3.0
    assert row["graph_lookup_max_query_hits"] == 2.0
    assert row["graph_lookup_max_symbol_hits"] == 1.0
    assert row["graph_lookup_max_import_hits"] == 1.0
    assert row["graph_lookup_max_query_coverage"] == 0.666667
    assert row["graph_lookup_boosted_path_ratio"] == 0.5
    assert row["graph_lookup_query_hit_path_ratio"] == 0.25
    assert row["graph_lookup"] == {
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
        "max_query_coverage": 0.666667,
        "boosted_path_ratio": 0.5,
        "query_hit_path_ratio": 0.25,
    }

    metrics = aggregate_metrics([row])
    assert metrics["graph_lookup_enabled_ratio"] == 1.0
    assert metrics["graph_lookup_guarded_ratio"] == 1.0
    assert metrics["graph_lookup_log_norm_ratio"] == 1.0
    assert metrics["graph_lookup_linear_norm_ratio"] == 0.0
    assert metrics["graph_lookup_boosted_count_mean"] == 2.0
    assert metrics["graph_lookup_weight_scip_mean"] == 0.3
    assert metrics["graph_lookup_weight_xref_mean"] == 0.2
    assert metrics["graph_lookup_weight_query_xref_mean"] == 0.2
    assert metrics["graph_lookup_weight_symbol_mean"] == 0.1
    assert metrics["graph_lookup_weight_import_mean"] == 0.1
    assert metrics["graph_lookup_weight_coverage_mean"] == 0.1
    assert metrics["graph_lookup_candidate_count_mean"] == 6.0
    assert metrics["graph_lookup_pool_size_mean"] == 4.0
    assert metrics["graph_lookup_query_terms_count_mean"] == 3.0
    assert metrics["graph_lookup_guard_max_candidates_mean"] == 4.0
    assert metrics["graph_lookup_guard_min_query_terms_mean"] == 1.0
    assert metrics["graph_lookup_guard_max_query_terms_mean"] == 5.0
    assert metrics["graph_lookup_query_hit_paths_mean"] == 1.0
    assert metrics["graph_lookup_scip_signal_paths_mean"] == 2.0
    assert metrics["graph_lookup_xref_signal_paths_mean"] == 3.0
    assert metrics["graph_lookup_symbol_hit_paths_mean"] == 1.0
    assert metrics["graph_lookup_import_hit_paths_mean"] == 1.0
    assert metrics["graph_lookup_coverage_hit_paths_mean"] == 2.0
    assert metrics["graph_lookup_max_inbound_mean"] == 4.0
    assert metrics["graph_lookup_max_xref_count_mean"] == 3.0
    assert metrics["graph_lookup_max_query_hits_mean"] == 2.0
    assert metrics["graph_lookup_max_symbol_hits_mean"] == 1.0
    assert metrics["graph_lookup_max_import_hits_mean"] == 1.0
    assert metrics["graph_lookup_max_query_coverage_mean"] == 0.666667
    assert metrics["graph_lookup_candidate_count_guard_ratio"] == 1.0
    assert metrics["graph_lookup_query_terms_too_few_ratio"] == 0.0
    assert metrics["graph_lookup_query_terms_too_many_ratio"] == 0.0
    assert metrics["graph_lookup_boosted_path_ratio"] == 0.5
    assert metrics["graph_lookup_query_hit_path_ratio"] == 0.25


def test_build_retrieval_control_plane_gate_summary_requires_regression_evidence() -> None:
    summary = build_retrieval_control_plane_gate_summary(
        metrics={
            "adaptive_router_shadow_coverage": 0.91,
            "risk_upgrade_precision_gain": 0.04,
            "latency_p95_ms": 640.0,
        },
        regression=None,
    )

    assert summary == {
        "regression_evaluated": False,
        "benchmark_regression_detected": False,
        "benchmark_regression_passed": False,
        "failed_checks": [],
        "adaptive_router_shadow_coverage": 0.91,
        "adaptive_router_shadow_coverage_threshold": 0.8,
        "adaptive_router_shadow_coverage_passed": True,
        "risk_upgrade_precision_gain": 0.04,
        "risk_upgrade_precision_gain_threshold": 0.0,
        "risk_upgrade_precision_gain_passed": True,
        "latency_p95_ms": 640.0,
        "latency_p95_ms_threshold": 850.0,
        "latency_p95_ms_passed": True,
        "gate_passed": False,
    }


def test_build_retrieval_control_plane_gate_summary_reports_multi_check_failures() -> None:
    summary = build_retrieval_control_plane_gate_summary(
        metrics={
            "adaptive_router_shadow_coverage": 0.74,
            "risk_upgrade_precision_gain": -0.03,
            "latency_p95_ms": 880.0,
        },
        regression={
            "regressed": True,
            "failed_checks": [
                "precision_at_k",
                "latency_p95_ms",
            ],
        },
    )

    assert summary["regression_evaluated"] is True
    assert summary["benchmark_regression_detected"] is True
    assert summary["benchmark_regression_passed"] is False
    assert summary["adaptive_router_shadow_coverage_passed"] is False
    assert summary["risk_upgrade_precision_gain_passed"] is False
    assert summary["latency_p95_ms_passed"] is False
    assert summary["failed_checks"] == ["precision_at_k", "latency_p95_ms"]
    assert summary["gate_passed"] is False


def test_build_retrieval_frontier_gate_summary_passes_all_q3_checks() -> None:
    summary = build_retrieval_frontier_gate_summary(
        metrics={
            "deep_symbol_case_recall": 0.95,
            "native_scip_loaded_rate": 0.8,
            "precision_at_k": 0.66,
            "noise_rate": 0.31,
        }
    )

    assert summary == {
        "failed_checks": [],
        "deep_symbol_case_recall": 0.95,
        "deep_symbol_case_recall_threshold": 0.9,
        "deep_symbol_case_recall_passed": True,
        "native_scip_loaded_rate": 0.8,
        "native_scip_loaded_rate_threshold": 0.7,
        "native_scip_loaded_rate_passed": True,
        "precision_at_k": 0.66,
        "precision_at_k_threshold": 0.64,
        "precision_at_k_passed": True,
        "noise_rate": 0.31,
        "noise_rate_threshold": 0.36,
        "noise_rate_passed": True,
        "gate_passed": True,
    }


def test_build_retrieval_frontier_gate_summary_reports_multi_check_failures() -> None:
    summary = build_retrieval_frontier_gate_summary(
        metrics={
            "deep_symbol_case_recall": 0.82,
            "native_scip_loaded_rate": 0.55,
            "precision_at_k": 0.61,
            "noise_rate": 0.41,
        }
    )

    assert summary["failed_checks"] == [
        "deep_symbol_case_recall",
        "native_scip_loaded_rate",
        "precision_at_k",
        "noise_rate",
    ]
    assert summary["deep_symbol_case_recall_passed"] is False
    assert summary["native_scip_loaded_rate_passed"] is False
    assert summary["precision_at_k_passed"] is False
    assert summary["noise_rate_passed"] is False
    assert summary["gate_passed"] is False


def test_build_deep_symbol_summary_rounds_case_count_and_recall() -> None:
    summary = build_deep_symbol_summary(
        metrics={
            "deep_symbol_case_count": 3.1234567,
            "deep_symbol_case_recall": 0.9876543,
        }
    )

    assert summary == {
        "case_count": 3.123457,
        "recall": 0.987654,
    }


def test_build_native_scip_summary_rounds_core_metrics() -> None:
    summary = build_native_scip_summary(
        metrics={
            "native_scip_loaded_rate": 0.8123456,
            "native_scip_document_count_mean": 5.1234567,
            "native_scip_definition_occurrence_count_mean": 7.1234567,
            "native_scip_reference_occurrence_count_mean": 11.1234567,
            "native_scip_symbol_definition_count_mean": 3.1234567,
        }
    )

    assert summary == {
        "loaded_rate": 0.812346,
        "document_count_mean": 5.123457,
        "definition_occurrence_count_mean": 7.123457,
        "reference_occurrence_count_mean": 11.123457,
        "symbol_definition_count_mean": 3.123457,
    }


def test_build_validation_probe_summary_rounds_core_metrics() -> None:
    summary = build_validation_probe_summary(
        metrics={
            "validation_test_count": 1.2345678,
            "validation_probe_enabled_ratio": 0.8765432,
            "validation_probe_executed_count_mean": 2.3456789,
            "validation_probe_failure_rate": 0.4567891,
        }
    )

    assert summary == {
        "validation_test_count": 1.234568,
        "probe_enabled_ratio": 0.876543,
        "probe_executed_count_mean": 2.345679,
        "probe_failure_rate": 0.456789,
    }


def test_build_source_plan_validation_feedback_summary_rounds_core_metrics() -> None:
    summary = build_source_plan_validation_feedback_summary(
        metrics={
            "source_plan_validation_feedback_present_ratio": 1.0,
            "source_plan_validation_feedback_issue_count_mean": 2.3456789,
            "source_plan_validation_feedback_failure_rate": 0.5,
            "source_plan_validation_feedback_probe_issue_count_mean": 1.2345678,
            "source_plan_validation_feedback_probe_executed_count_mean": 1.9876543,
            "source_plan_validation_feedback_probe_failure_rate": 0.4567891,
            "source_plan_validation_feedback_selected_test_count_mean": 1.2345678,
            "source_plan_validation_feedback_executed_test_count_mean": 1.1234567,
        }
    )

    assert summary == {
        "present_ratio": 1.0,
        "issue_count_mean": 2.345679,
        "failure_rate": 0.5,
        "probe_issue_count_mean": 1.234568,
        "probe_executed_count_mean": 1.987654,
        "probe_failure_rate": 0.456789,
        "selected_test_count_mean": 1.234568,
        "executed_test_count_mean": 1.123457,
    }


def test_build_source_plan_failure_signal_summary_rounds_core_metrics() -> None:
    summary = build_source_plan_failure_signal_summary(
        metrics={
            "source_plan_failure_signal_present_ratio": 1.0,
            "source_plan_failure_signal_issue_count_mean": 2.3456789,
            "source_plan_failure_signal_failure_rate": 0.5,
            "source_plan_failure_signal_probe_issue_count_mean": 1.2345678,
            "source_plan_failure_signal_probe_executed_count_mean": 1.9876543,
            "source_plan_failure_signal_probe_failure_rate": 0.4567891,
            "source_plan_failure_signal_selected_test_count_mean": 1.2345678,
            "source_plan_failure_signal_executed_test_count_mean": 1.1234567,
            "source_plan_failure_signal_replay_cache_origin_ratio": 0.75,
            "source_plan_failure_signal_observability_origin_ratio": 0.25,
            "source_plan_failure_signal_source_plan_origin_ratio": 0.0,
            "source_plan_failure_signal_validate_step_origin_ratio": 0.0,
        }
    )

    assert summary == {
        "present_ratio": 1.0,
        "issue_count_mean": 2.345679,
        "failure_rate": 0.5,
        "probe_issue_count_mean": 1.234568,
        "probe_executed_count_mean": 1.987654,
        "probe_failure_rate": 0.456789,
        "selected_test_count_mean": 1.234568,
        "executed_test_count_mean": 1.123457,
        "replay_cache_origin_ratio": 0.75,
        "observability_origin_ratio": 0.25,
        "source_plan_origin_ratio": 0.0,
        "validate_step_origin_ratio": 0.0,
    }


def test_build_learning_router_rollout_summary_classifies_guarded_rollout_readiness() -> None:
    summary = build_learning_router_rollout_summary(
        [
            {
                "router_enabled": 0.0,
                "router_mode": "observe",
                "router_shadow_arm_id": "",
                "source_plan_evidence_card_count": 0.0,
                "source_plan_failure_signal_present": 0.0,
                "source_plan_failure_signal_failed": 0.0,
                "source_plan_failure_signal_issue_count": 0.0,
                "source_plan_failure_signal_probe_issue_count": 0.0,
            },
            {
                "router_enabled": 1.0,
                "router_mode": "observe",
                "router_shadow_arm_id": "",
                "source_plan_evidence_card_count": 1.0,
                "source_plan_failure_signal_present": 0.0,
                "source_plan_failure_signal_failed": 0.0,
                "source_plan_failure_signal_issue_count": 0.0,
                "source_plan_failure_signal_probe_issue_count": 0.0,
            },
            {
                "router_enabled": 1.0,
                "router_mode": "shadow",
                "router_shadow_arm_id": "",
                "source_plan_evidence_card_count": 1.0,
                "source_plan_failure_signal_present": 0.0,
                "source_plan_failure_signal_failed": 0.0,
                "source_plan_failure_signal_issue_count": 0.0,
                "source_plan_failure_signal_probe_issue_count": 0.0,
            },
            {
                "router_enabled": 1.0,
                "router_mode": "shadow",
                "router_shadow_arm_id": "general_heuristic",
                "source_plan_evidence_card_count": 0.0,
                "source_plan_failure_signal_present": 0.0,
                "source_plan_failure_signal_failed": 0.0,
                "source_plan_failure_signal_issue_count": 0.0,
                "source_plan_failure_signal_probe_issue_count": 0.0,
            },
            {
                "router_enabled": 1.0,
                "router_mode": "shadow",
                "router_shadow_arm_id": "general_heuristic",
                "source_plan_evidence_card_count": 2.0,
                "source_plan_failure_signal_present": 1.0,
                "source_plan_failure_signal_failed": 1.0,
                "source_plan_failure_signal_issue_count": 2.0,
                "source_plan_failure_signal_probe_issue_count": 1.0,
            },
            {
                "router_enabled": 1.0,
                "router_mode": "shadow",
                "router_shadow_arm_id": "general_heuristic",
                "source_plan_evidence_card_count": 2.0,
                "source_plan_failure_signal_present": 0.0,
                "source_plan_failure_signal_failed": 0.0,
                "source_plan_failure_signal_issue_count": 0.0,
                "source_plan_failure_signal_probe_issue_count": 0.0,
            },
        ]
    )

    assert summary == {
        "case_count": 6,
        "router_enabled_case_count": 5,
        "router_enabled_case_rate": 0.833333,
        "shadow_mode_case_count": 4,
        "shadow_mode_case_rate": 0.666667,
        "shadow_ready_case_count": 3,
        "shadow_ready_case_rate": 0.5,
        "source_plan_card_present_case_count": 4,
        "source_plan_card_present_case_rate": 0.666667,
        "failure_signal_blocked_case_count": 1,
        "failure_signal_blocked_case_rate": 0.166667,
        "eligible_case_count": 1,
        "eligible_case_rate": 0.166667,
        "reason_counts": {
            "adaptive_router_disabled": 1,
            "adaptive_router_not_shadow": 1,
            "eligible_pending_guarded_rollout": 1,
            "failure_signal_present": 1,
            "missing_source_plan_cards": 1,
            "shadow_arm_missing": 1,
        },
    }
