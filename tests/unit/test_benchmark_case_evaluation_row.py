from __future__ import annotations

from ace_lite.benchmark.case_evaluation_row import build_case_evaluation_row


def _base_row_kwargs() -> dict[str, object]:
    return {
        "case": {
            "case_id": "c1",
            "query": "where validate token",
            "retrieval_surface": "deep_symbol",
            "issue_report": {
                "issue_id": "iss_demo1234",
                "status": "resolved",
                "plan_payload_ref": "run-123",
                "occurred_at": "2026-03-19T00:00:00+00:00",
                "resolved_at": "2026-03-19T12:00:00+00:00",
                "created_at": "2026-03-19T00:00:00+00:00",
                "updated_at": "2026-03-19T12:00:00+00:00",
                "resolution_note": "patched validation payload",
            },
            "dev_feedback": {
                "issue_count": 1,
                "linked_fix_issue_count": 1,
                "resolved_issue_count": 1,
                "created_at": "2026-03-19T00:00:00+00:00",
                "resolved_at": "2026-03-19T06:00:00+00:00",
            },
            "feedback_surface": "issue_report_export_cli",
        },
        "expected": ["validate_token"],
        "top_k": 4,
        "recall_hit": 1.0,
        "precision": 0.5,
        "first_hit_rank": 1,
        "hit_at_1": 1.0,
        "reciprocal_rank": 1.0,
        "utility": 1.0,
        "task_success_hit": 1.0,
        "task_success_config": {
            "mode": "positive",
            "require_recall_hit": True,
            "min_validation_tests": 1,
        },
        "task_success_failed_checks": [],
        "noise": 0.5,
        "dependency_recall": 0.75,
        "memory_latency_ms": 1.0,
        "index_latency_ms": 2.0,
        "repomap_latency_ms": 3.0,
        "repomap_worktree_seed_count": 1,
        "repomap_subgraph_seed_count": 2,
        "repomap_seed_candidates_count": 3,
        "repomap_cache_hit": True,
        "repomap_precompute_hit": False,
        "augment_latency_ms": 4.0,
        "skills_latency_ms": 5.0,
        "source_plan_latency_ms": 6.0,
        "latency_ms": 12.5,
        "chunk_hit_at_k": 1.0,
        "chunks_per_file_mean": 1.0,
        "chunk_budget_used": 9.0,
        "retrieval_context_chunk_count": 2,
        "retrieval_context_coverage_ratio": 1.0,
        "retrieval_context_char_count_mean": 84.0,
        "contextual_sidecar_parent_symbol_chunk_count": 2,
        "contextual_sidecar_parent_symbol_coverage_ratio": 1.0,
        "contextual_sidecar_reference_hint_chunk_count": 1,
        "contextual_sidecar_reference_hint_coverage_ratio": 0.5,
        "retrieval_context_pool_chunk_count": 1,
        "retrieval_context_pool_coverage_ratio": 0.5,
        "chunk_contract_fallback_count": 1,
        "chunk_contract_skeleton_chunk_count": 0,
        "chunk_contract_fallback_ratio": 0.5,
        "chunk_contract_skeleton_ratio": 0.0,
        "unsupported_language_fallback_count": 1,
        "unsupported_language_fallback_ratio": 0.5,
        "subgraph_payload_enabled": True,
        "subgraph_seed_path_count": 2,
        "subgraph_edge_type_count": 1,
        "subgraph_edge_total_count": 2,
        "robust_signature_count": 1,
        "robust_signature_coverage_ratio": 0.5,
        "graph_prior_chunk_count": 1,
        "graph_prior_coverage_ratio": 0.5,
        "graph_prior_total": 0.2,
        "graph_seeded_chunk_count": 1,
        "graph_transfer_count": 2,
        "graph_hub_suppressed_chunk_count": 0,
        "graph_hub_penalty_total": 0.0,
        "graph_closure_enabled": True,
        "graph_closure_boosted_chunk_count": 1,
        "graph_closure_coverage_ratio": 0.5,
        "graph_closure_anchor_count": 1,
        "graph_closure_support_edge_count": 2,
        "graph_closure_total": 0.1,
        "topological_shield_enabled": True,
        "topological_shield_mode": "report_only",
        "topological_shield_report_only": False,
        "topological_shield_max_attenuation": 0.6,
        "topological_shield_shared_parent_attenuation": 0.2,
        "topological_shield_adjacency_attenuation": 0.5,
        "topological_shield_attenuated_chunk_count": 1,
        "topological_shield_coverage_ratio": 0.5,
        "topological_shield_attenuation_total": 0.2,
        "topological_shield_attenuation_per_chunk": 0.2,
        "graph_source_provider_loaded": True,
        "graph_source_projection_fallback": True,
        "graph_source_edge_count": 5,
        "graph_source_inbound_signal_chunk_count": 2,
        "graph_source_inbound_signal_coverage_ratio": 1.0,
        "graph_source_centrality_signal_chunk_count": 2,
        "graph_source_centrality_signal_coverage_ratio": 1.0,
        "graph_source_pagerank_signal_chunk_count": 1,
        "graph_source_pagerank_signal_coverage_ratio": 0.5,
        "skills_selected_count": 2.0,
        "skills_token_budget": 500.0,
        "skills_token_budget_used": 200.0,
        "skills_token_budget_utilization_ratio": 0.4,
        "skills_budget_exhausted": True,
        "skills_skipped_for_budget_count": 1.0,
        "skills_route_latency_ms": 1.2,
        "skills_hydration_latency_ms": 2.4,
        "skills_metadata_only_routing": True,
        "skills_precomputed_route": True,
        "skills_manifest_metadata_only_selected_count": 1,
        "skills_manifest_body_scan_selected_count": 1,
        "skills_selected_matched_count_mean": 2.0,
        "skills_selected_signal_count_mean": 1.5,
        "skills_selected_priority_mean": 3.0,
        "candidate_rows_materialized_count": 4,
        "candidate_chunks_materialized_count": 2,
        "source_plan_candidate_chunks_materialized_count": 1,
        "skills_markdown_bytes_loaded": 512,
        "plan_replay_cache_enabled": True,
        "plan_replay_cache_hit": True,
        "plan_replay_cache_stale_hit_safe": True,
        "chunk_stage_miss": {"applicable": False, "label": ""},
        "validation_tests": ["tests.test_auth::test_token"],
        "validation_probe_enabled": True,
        "validation_probe_status": "failed",
        "validation_probe_executed_count": 2,
        "validation_probe_issue_count": 1,
        "validation_branch_case": True,
        "validation_branch_candidate_count": 3,
        "validation_branch_rejected_count": 2,
        "validation_branch_selection_present": True,
        "validation_branch_patch_artifact_present": True,
        "validation_branch_archive_present": True,
        "validation_branch_parallel": True,
        "validation_branch_winner_passed": True,
        "validation_branch_winner_regressed": False,
        "validation_branch_winner_score": 0.9,
        "validation_branch_winner_after_issue_count": 0,
        "agent_loop_observed": True,
        "agent_loop_enabled": True,
        "agent_loop_attempted": True,
        "agent_loop_actions_requested": 2,
        "agent_loop_actions_executed": 1,
        "agent_loop_stop_reason": "completed",
        "agent_loop_replay_safe": True,
        "agent_loop_last_policy_id": "source_plan_refresh",
        "agent_loop_request_more_context_count": 1,
        "agent_loop_request_source_plan_retry_count": 1,
        "agent_loop_request_validation_retry_count": 0,
        "source_plan_validation_feedback_present": True,
        "source_plan_validation_feedback_status": "failed",
        "source_plan_validation_feedback_issue_count": 2,
        "source_plan_validation_feedback_probe_status": "failed",
        "source_plan_validation_feedback_probe_issue_count": 1,
        "source_plan_validation_feedback_probe_executed_count": 1,
        "source_plan_validation_feedback_selected_test_count": 1,
        "source_plan_validation_feedback_executed_test_count": 1,
        "source_plan_failure_signal_origin": "plan_replay_cache",
        "source_plan_failure_signal_present": True,
        "source_plan_failure_signal_status": "failed",
        "source_plan_failure_signal_issue_count": 2,
        "source_plan_failure_signal_probe_status": "failed",
        "source_plan_failure_signal_probe_issue_count": 1,
        "source_plan_failure_signal_probe_executed_count": 1,
        "source_plan_failure_signal_selected_test_count": 1,
        "source_plan_failure_signal_executed_test_count": 1,
        "source_plan_failure_signal_has_failure": True,
        "source_plan_evidence_card_count": 2,
        "source_plan_file_card_count": 1,
        "source_plan_chunk_card_count": 1,
        "source_plan_validation_card_present": True,
        "source_plan_evidence_summary": {
            "direct_ratio": 0.5,
            "neighbor_context_ratio": 0.5,
            "hint_only_ratio": 0.0,
        },
        "source_plan_graph_closure_preference_enabled": True,
        "source_plan_graph_closure_bonus_candidate_count": 2,
        "source_plan_graph_closure_preferred_count": 1,
        "source_plan_granularity_preferred_count": 1,
        "source_plan_focused_file_promoted_count": 1,
        "source_plan_packed_path_count": 1,
        "source_plan_chunk_retention_ratio": 0.5,
        "source_plan_packed_path_ratio": 0.5,
        "notes_hit_ratio": 0.25,
        "profile_selected_count": 2,
        "capture_triggered": True,
        "ltm_selected_count": 2,
        "ltm_attribution_count": 1,
        "ltm_graph_neighbor_count": 1,
        "ltm_plan_constraint_count": 1,
        "ltm_feedback_signal_counts": {
            "helpful": 1,
            "stale": 0,
            "harmful": 1,
        },
        "ltm_attribution_scope_counts": {
            "explicit_selection_only": 1,
        },
        "ltm_attribution_preview": [
            "runtime.validation.git fallback_policy reuse_checkout_or_skip | graph: reuse_checkout_or_skip recommended_for runtime.validation.git"
        ],
        "feedback_enabled": True,
        "feedback_reason": "ok",
        "feedback_event_count": 4,
        "feedback_matched_event_count": 2,
        "feedback_boosted_count": 1,
        "feedback_boosted_paths": 1,
        "multi_channel_rrf_enabled": True,
        "multi_channel_rrf_applied": True,
        "multi_channel_rrf_granularity_count": 2,
        "multi_channel_rrf_pool_size": 4,
        "multi_channel_rrf_granularity_pool_ratio": 0.5,
        "graph_lookup_enabled": True,
        "graph_lookup_reason": "candidate_count_guarded",
        "graph_lookup_guarded": True,
        "graph_lookup_boosted_count": 2,
        "graph_lookup_weight_scip": 0.3,
        "graph_lookup_weight_xref": 0.2,
        "graph_lookup_weight_query_xref": 0.2,
        "graph_lookup_weight_symbol": 0.1,
        "graph_lookup_weight_import": 0.1,
        "graph_lookup_weight_coverage": 0.1,
        "graph_lookup_candidate_count": 6,
        "graph_lookup_pool_size": 4,
        "graph_lookup_query_terms_count": 3,
        "graph_lookup_normalization": "log1p",
        "graph_lookup_guard_max_candidates": 4,
        "graph_lookup_guard_min_query_terms": 1,
        "graph_lookup_guard_max_query_terms": 5,
        "graph_lookup_query_hit_paths": 1,
        "graph_lookup_scip_signal_paths": 2,
        "graph_lookup_xref_signal_paths": 3,
        "graph_lookup_symbol_hit_paths": 1,
        "graph_lookup_import_hit_paths": 1,
        "graph_lookup_coverage_hit_paths": 2,
        "graph_lookup_max_inbound": 4.0,
        "graph_lookup_max_xref_count": 3.0,
        "graph_lookup_max_query_hits": 2.0,
        "graph_lookup_max_symbol_hits": 1.0,
        "graph_lookup_max_import_hits": 1.0,
        "graph_lookup_max_query_coverage": 0.666667,
        "graph_lookup_boosted_path_ratio": 0.5,
        "graph_lookup_query_hit_path_ratio": 0.25,
        "native_scip_loaded": True,
        "native_scip_document_count": 5,
        "native_scip_definition_occurrence_count": 7,
        "native_scip_reference_occurrence_count": 11,
        "native_scip_symbol_definition_count": 3,
        "policy_profile": "doc_intent",
        "graph_transfer_per_seed_ratio": 2.0,
        "router_enabled": True,
        "router_mode": "adaptive",
        "router_arm_set": "default",
        "router_arm_id": "arm-a",
        "router_confidence": 0.82,
        "router_shadow_arm_id": "arm-b",
        "router_shadow_source": "model",
        "router_shadow_confidence": 0.21,
        "router_online_bandit_requested": True,
        "router_experiment_enabled": True,
        "router_online_bandit_active": True,
        "router_is_exploration": False,
        "router_exploration_probability": 0.15,
        "router_fallback_applied": True,
        "router_fallback_reason": "low_confidence",
        "router_online_bandit_reason": "policy_eval",
        "docs_enabled_flag": True,
        "docs_hit": 1.0,
        "hint_inject": 1.0,
        "embedding_enabled": True,
        "embedding_runtime_provider": "hash_cross",
        "embedding_strategy_mode": "cross_encoder",
        "embedding_semantic_rerank_applied": True,
        "embedding_similarity_mean": 0.44,
        "embedding_similarity_max": 0.91,
        "embedding_rerank_ratio": 0.5,
        "embedding_cache_hit": True,
        "embedding_fallback": False,
        "parallel_time_budget_ms": 60.0,
        "embedding_time_budget_ms": 40.0,
        "chunk_semantic_time_budget_ms": 50.0,
        "xref_time_budget_ms": 30.0,
        "parallel_docs_timed_out": True,
        "parallel_worktree_timed_out": False,
        "embedding_time_budget_exceeded": True,
        "embedding_adaptive_budget_applied": True,
        "chunk_semantic_time_budget_exceeded": True,
        "chunk_semantic_fallback": True,
        "chunk_guard_enabled": True,
        "chunk_guard_mode": "strict",
        "chunk_guard_reason": "pairwise_conflict",
        "chunk_guard_report_only": False,
        "chunk_guard_filtered_count": 1,
        "chunk_guard_filter_ratio": 0.25,
        "chunk_guard_pairwise_conflict_count": 2,
        "chunk_guard_pairwise_conflict_density": 0.5,
        "chunk_guard_fallback": False,
        "chunk_guard_expectation": {
            "applicable": True,
            "scenario": "stale_majority",
            "expected_retained_hit": True,
            "expected_filtered_hit_count": 1,
            "expected_filtered_hit_rate": 0.5,
            "report_only_improved": False,
        },
        "xref_budget_exhausted": True,
        "slo_downgrade_signals": ["parallel_docs_timeout"],
        "decision_trace": [{"stage": "memory"}],
        "evidence_insufficiency": {
            "evidence_insufficient": 0.0,
            "evidence_insufficiency_reason": "",
            "evidence_insufficiency_signals": [],
        },
    }


def test_build_case_evaluation_row_contract() -> None:
    row = build_case_evaluation_row(**_base_row_kwargs())

    assert row["case_id"] == "c1"
    assert row["retrieval_surface"] == "deep_symbol"
    assert row["deep_symbol_case"] == 1.0
    assert row["task_success_mode"] == "positive"
    assert row["chunk_contract_fallback_count"] == 1.0
    assert row["source_plan_validation_feedback_present"] == 1.0
    assert row["source_plan_validation_feedback_status"] == "failed"
    assert row["source_plan_validation_feedback_issue_count"] == 2.0
    assert row["agent_loop_observed"] == 1.0
    assert row["agent_loop_enabled"] == 1.0
    assert row["agent_loop_attempted"] == 1.0
    assert row["agent_loop_actions_requested"] == 2.0
    assert row["agent_loop_actions_executed"] == 1.0
    assert row["agent_loop_stop_reason"] == "completed"
    assert row["agent_loop_last_policy_id"] == "source_plan_refresh"
    assert row["agent_loop_request_source_plan_retry_count"] == 1.0
    assert row["source_plan_validation_feedback_failed"] == 1.0
    assert row["source_plan_validation_feedback_probe_status"] == "failed"
    assert row["source_plan_validation_feedback_probe_issue_count"] == 1.0
    assert row["source_plan_validation_feedback_probe_executed_count"] == 1.0
    assert row["source_plan_validation_feedback_probe_failed"] == 1.0
    assert row["source_plan_validation_feedback_selected_test_count"] == 1.0
    assert row["source_plan_validation_feedback_executed_test_count"] == 1.0
    assert row["skills_budget_exhausted"] == 1.0
    assert row["skills_manifest_metadata_only_selected_count"] == 1.0
    assert row["skills_manifest_body_scan_selected_count"] == 1.0
    assert row["skills_selected_matched_count_mean"] == 2.0
    assert row["skills_selected_signal_count_mean"] == 1.5
    assert row["skills_selected_priority_mean"] == 3.0
    assert row["candidate_rows_materialized_count"] == 4.0
    assert row["candidate_chunks_materialized_count"] == 2.0
    assert row["source_plan_candidate_chunks_materialized_count"] == 1.0
    assert row["skills_markdown_bytes_loaded"] == 512.0
    assert row["budget_abort"] == 1.0
    assert row["fallback_taken"] == 1.0
    assert row["workload_taxonomy"] == "mixed_general"
    assert row["plan_replay_cache_hit"] == 1.0
    assert row["source_plan_granularity_preferred_count"] == 1.0
    assert row["source_plan_packed_path_ratio"] == 0.5
    assert row["multi_channel_rrf_enabled"] == 1.0
    assert row["multi_channel_rrf_granularity_count"] == 2.0
    assert row["multi_channel_rrf_granularity_pool_ratio"] == 0.5
    assert row["repomap_worktree_seed_count"] == 1.0
    assert row["repomap_subgraph_seed_count"] == 2.0
    assert row["repomap_seed_candidates_count"] == 3.0
    assert row["repomap_cache_hit"] == 1.0
    assert row["repomap_precompute_hit"] == 0.0
    assert row["graph_lookup_reason"] == "candidate_count_guarded"
    assert row["graph_lookup_guarded"] == 1.0
    assert row["graph_lookup_candidate_count"] == 6.0
    assert row["graph_lookup_normalization"] == "log1p"
    assert row["graph_lookup_max_inbound"] == 4.0
    assert row["contextual_sidecar_parent_symbol_chunk_count"] == 2.0
    assert row["contextual_sidecar_reference_hint_coverage_ratio"] == 0.5
    assert row["router_fallback_reason"] == "low_confidence"
    assert row["router_shadow_source"] == "model"
    assert row["docs_enabled"] == 1.0
    assert row["embedding_runtime_provider"] == "hash_cross"
    assert row["embedding_strategy_mode"] == "cross_encoder"
    assert row["embedding_semantic_rerank_applied"] == 1.0
    assert row["chunk_guard_mode"] == "strict"
    assert row["graph_source_provider_loaded"] == 1.0
    assert row["graph_source_projection_fallback"] == 1.0
    assert row["graph_source_edge_count"] == 5.0
    assert row["graph_source_inbound_signal_chunk_count"] == 2.0
    assert row["graph_source_inbound_signal_coverage_ratio"] == 1.0
    assert row["graph_source_centrality_signal_chunk_count"] == 2.0
    assert row["graph_source_centrality_signal_coverage_ratio"] == 1.0
    assert row["graph_source_pagerank_signal_chunk_count"] == 1.0
    assert row["graph_source_pagerank_signal_coverage_ratio"] == 0.5
    assert row["decision_trace_count"] == 1
    assert row["issue_report_issue_id"] == "iss_demo1234"
    assert row["issue_report_status"] == "resolved"
    assert row["issue_report_time_to_fix_hours"] == 12.0
    assert row["dev_feedback_issue_count"] == 1.0
    assert row["dev_feedback_linked_fix_issue_count"] == 1.0
    assert row["dev_feedback_resolved_issue_count"] == 1.0
    assert row["dev_feedback_issue_time_to_fix_hours"] == 6.0
    assert row["dev_issue_to_fix_rate"] == 1.0
    assert row["preference_capture"] == {
        "notes_hit_ratio": 0.25,
        "profile_selected_count": 2,
        "capture_triggered": True,
    }
    assert row["ltm_explainability"] == {
        "selected_count": 2,
        "attribution_count": 1,
        "graph_neighbor_count": 1,
        "plan_constraint_count": 1,
        "feedback_signal_counts": {
            "helpful": 1,
            "stale": 0,
            "harmful": 1,
        },
        "attribution_scope_counts": {
            "explicit_selection_only": 1,
        },
        "attribution_preview": [
            "runtime.validation.git fallback_policy reuse_checkout_or_skip | graph: reuse_checkout_or_skip recommended_for runtime.validation.git"
        ],
    }
    assert row["feedback_boost"] == {
        "enabled": True,
        "reason": "ok",
        "event_count": 4,
        "matched_event_count": 2,
        "boosted_candidate_count": 1,
        "boosted_unique_paths": 1,
    }
    assert row["multi_channel_rrf_enabled"] == 1.0
    assert row["multi_channel_rrf_applied"] == 1.0
    assert row["multi_channel_rrf_granularity_count"] == 2.0
    assert row["multi_channel_rrf_pool_size"] == 4.0
    assert row["multi_channel_rrf_granularity_pool_ratio"] == 0.5
    assert row["graph_lookup_enabled"] == 1.0
    assert row["graph_lookup_weight_scip"] == 0.3
    assert row["graph_lookup_boosted_count"] == 2.0
    assert row["graph_lookup_query_hit_paths"] == 1.0
    assert row["graph_lookup_boosted_path_ratio"] == 0.5
    assert row["multi_channel_fusion"] == {
        "enabled": True,
        "applied": True,
        "granularity_count": 2,
        "pool_size": 4,
        "granularity_pool_ratio": 0.5,
    }
    assert row["graph_context_source"] == {
        "provider_loaded": True,
        "projection_fallback": True,
        "edge_count": 5,
        "inbound_signal_chunk_count": 2,
        "inbound_signal_coverage_ratio": 1.0,
        "centrality_signal_chunk_count": 2,
        "centrality_signal_coverage_ratio": 1.0,
        "pagerank_signal_chunk_count": 1,
        "pagerank_signal_coverage_ratio": 0.5,
    }
    assert row["repomap_seed"] == {
        "worktree_seed_count": 1,
        "subgraph_seed_count": 2,
        "seed_candidates_count": 3,
        "cache_hit": True,
        "precompute_hit": False,
    }
    assert row["graph_lookup"] == {
        "enabled": True,
        "boosted_count": 2,
        "reason": "candidate_count_guarded",
        "guarded": True,
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
    assert row["native_scip_loaded"] == 1.0
    assert row["native_scip_document_count"] == 5.0
    assert row["native_scip_definition_occurrence_count"] == 7.0
    assert row["native_scip_reference_occurrence_count"] == 11.0
    assert row["native_scip_symbol_definition_count"] == 3.0
    assert row["native_scip"] == {
        "loaded": True,
        "document_count": 5,
        "definition_occurrence_count": 7,
        "reference_occurrence_count": 11,
        "symbol_definition_count": 3,
    }
    assert row["agent_loop_control_plane"] == {
        "observed": True,
        "enabled": True,
        "attempted": True,
        "actions_requested": 2,
        "actions_executed": 1,
        "stop_reason": "completed",
        "replay_safe": True,
        "last_policy_id": "source_plan_refresh",
        "last_action_reason": "",
        "request_more_context_count": 1,
        "request_source_plan_retry_count": 1,
        "request_validation_retry_count": 0,
        "validation_findings_refine_applied": False,
        "validation_findings_refine_focus_path_count": 0,
    }
    assert row["feedback_loop"] == {
        "feedback_surface": "issue_report_export_cli",
        "issue_report_issue_id": "iss_demo1234",
        "issue_report_has_plan_ref": True,
        "issue_report_status": "resolved",
        "issue_report_occurred_at": "2026-03-19T00:00:00+00:00",
        "issue_report_resolved_at": "2026-03-19T12:00:00+00:00",
        "issue_report_time_to_fix_hours": 12.0,
        "dev_feedback_issue_count": 1,
        "dev_feedback_linked_fix_issue_count": 1,
        "dev_feedback_resolved_issue_count": 1,
        "dev_feedback_created_at": "2026-03-19T00:00:00+00:00",
        "dev_feedback_resolved_at": "2026-03-19T06:00:00+00:00",
        "dev_feedback_issue_time_to_fix_hours": 6.0,
        "dev_issue_to_fix_rate": 1.0,
    }


def test_build_case_evaluation_row_derives_runtime_issue_capture_feedback() -> None:
    kwargs = _base_row_kwargs()
    case = dict(kwargs["case"])
    case.pop("dev_feedback")
    case["comparison_lane"] = "dev_issue_capture"
    case["feedback_surface"] = "runtime_issue_capture_cli"
    kwargs["case"] = case

    row = build_case_evaluation_row(**kwargs)

    assert row["dev_feedback_issue_count"] == 1.0
    assert row["dev_feedback_linked_fix_issue_count"] == 0.0
    assert row["dev_feedback_resolved_issue_count"] == 0.0
    assert row["dev_feedback_created_at"] == "2026-03-19T00:00:00+00:00"
    assert row["dev_issue_to_fix_rate"] == 0.0
    assert row["feedback_loop"]["feedback_surface"] == "runtime_issue_capture_cli"
    assert row["feedback_loop"]["dev_feedback_issue_count"] == 1
    assert row["feedback_loop"]["dev_feedback_linked_fix_issue_count"] == 0
    assert row["feedback_loop"]["dev_feedback_resolved_issue_count"] == 0


def test_build_case_evaluation_row_derives_issue_resolution_feedback() -> None:
    kwargs = _base_row_kwargs()
    case = dict(kwargs["case"])
    case.pop("dev_feedback")
    case["comparison_lane"] = "dev_feedback_resolution"
    case["feedback_surface"] = "issue_resolution_mcp"
    kwargs["case"] = case

    row = build_case_evaluation_row(**kwargs)

    assert row["dev_feedback_issue_count"] == 1.0
    assert row["dev_feedback_linked_fix_issue_count"] == 1.0
    assert row["dev_feedback_resolved_issue_count"] == 1.0
    assert row["dev_feedback_created_at"] == "2026-03-19T00:00:00+00:00"
    assert row["dev_feedback_resolved_at"] == "2026-03-19T12:00:00+00:00"
    assert row["dev_issue_to_fix_rate"] == 1.0
    assert row["feedback_loop"]["feedback_surface"] == "issue_resolution_mcp"
    assert row["feedback_loop"]["dev_feedback_issue_count"] == 1
    assert row["feedback_loop"]["dev_feedback_linked_fix_issue_count"] == 1
    assert row["feedback_loop"]["dev_feedback_resolved_issue_count"] == 1


def test_build_case_evaluation_row_derives_feedback_from_issue_report_payload() -> None:
    kwargs = _base_row_kwargs()
    case = dict(kwargs["case"])
    case.pop("dev_feedback")
    issue_report = dict(case["issue_report"])
    issue_report["attachments"] = [
        "artifact://validation.json",
        "dev-fix://devf_demo1234",
    ]
    case["issue_report"] = issue_report
    case["comparison_lane"] = "issue_report_feedback"
    case["feedback_surface"] = "issue_report_export_cli"
    kwargs["case"] = case

    row = build_case_evaluation_row(**kwargs)

    assert row["dev_feedback_issue_count"] == 1.0
    assert row["dev_feedback_linked_fix_issue_count"] == 1.0
    assert row["dev_feedback_resolved_issue_count"] == 1.0
    assert row["dev_feedback_created_at"] == "2026-03-19T00:00:00+00:00"
    assert row["dev_feedback_resolved_at"] == "2026-03-19T12:00:00+00:00"
    assert row["dev_issue_to_fix_rate"] == 1.0
