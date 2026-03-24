from __future__ import annotations

from ace_lite.benchmark.case_evaluation_metrics import (
    build_case_evaluation_metrics,
)


def test_build_case_evaluation_metrics_rich_payload_contract() -> None:
    plan_payload = {
        "skills": {
            "selected": [{"name": "skill-a"}, {"name": "skill-b"}],
            "token_budget": 600,
            "token_budget_used": 250,
            "budget_exhausted": True,
            "routing_source": "precomputed",
            "skipped_for_budget": [{"name": "skill-c"}],
        },
        "source_plan": {
            "validation_tests": ["tests.test_auth::test_token"],
            "ltm_constraint_summary": {
                "selected_count": 2,
                "constraint_count": 1,
                "graph_neighbor_count": 1,
                "handles": ["fact-1"],
            },
            "evidence_summary": {
                "direct_count": 1.0,
                "neighbor_context_count": 1.0,
                "hint_only_count": 0.0,
                "direct_ratio": 0.5,
                "neighbor_context_ratio": 0.5,
                "hint_only_ratio": 0.0,
                "symbol_count": 2.0,
                "signature_count": 1.0,
                "skeleton_count": 1.0,
                "robust_signature_count": 1.0,
                "symbol_ratio": 1.0,
                "signature_ratio": 0.5,
                "skeleton_ratio": 0.5,
                "robust_signature_ratio": 0.5,
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
            "chunk_budget_used": 5.0,
        },
        "repomap": {
            "dependency_recall": {"hit_rate": 1.0},
            "neighbor_paths": ["src/auth.py", "src/token.py"],
        },
        "memory": {
            "count": 2,
            "gate": {"skipped": True, "skip_reason": "budget"},
            "fallback_reason": "rest",
            "namespace": {"fallback": "global"},
            "profile": {"selected_count": 1},
            "capture": {"triggered": True},
            "notes": {"selected_count": 1},
            "ltm": {
                "selected_count": 2,
                "attribution_count": 1,
                "feedback_signal_counts": {
                    "helpful": 1,
                    "stale": 0,
                    "harmful": 1,
                },
                "attribution_scope_counts": {
                    "explicit_selection_only": 1,
                },
                "attribution": [
                    {
                        "handle": "fact-1",
                        "graph_neighborhood": {"triple_count": 1},
                    }
                ],
            },
        },
        "observability": {
            "agent_loop": {
                "enabled": True,
                "attempted": True,
                "actions_requested": 2,
                "actions_executed": 1,
                "stop_reason": "completed",
                "replay_safe": True,
                "last_rerun_policy": {"policy_id": "source_plan_refresh"},
                "action_type_counts": {
                    "request_more_context": 1,
                    "request_source_plan_retry": 1,
                },
            },
            "plan_replay_cache": {
                "enabled": True,
                "hit": True,
                "stale_hit_safe": True,
            },
            "stage_metrics": [
                {"stage": "repomap", "elapsed_ms": 4.5},
                {"stage": "memory", "elapsed_ms": 1.1},
                {"stage": "index", "elapsed_ms": 2.2},
                {"stage": "augment", "elapsed_ms": 3.3},
                {"stage": "skills", "elapsed_ms": 0.4},
                {"stage": "source_plan", "elapsed_ms": 5.5},
            ],
        },
    }
    index_payload = {
        "candidate_ranking": {
            "fallbacks": ["lexical_failopen"],
            "exact_search": {"requested": True},
            "second_pass": {"applied": True},
            "refine_pass": {"applied": False},
            "multi_channel_rrf_enabled": True,
            "multi_channel_rrf_applied": True,
            "multi_channel_rrf_granularity_count": 3,
            "multi_channel_rrf_pool_size": 6,
            "multi_channel_rrf_granularity_pool_ratio": 0.5,
        },
        "docs": {
            "enabled": True,
            "section_count": 2,
        },
        "embeddings": {
            "enabled": True,
            "runtime_provider": "hash_colbert",
            "cache_hit": True,
            "similarity_mean": 0.42,
            "similarity_max": 0.88,
            "rerank_pool": 4,
            "reranked_count": 2,
            "fallback": False,
            "semantic_rerank_applied": True,
        },
        "chunk_semantic_rerank": {
            "reason": "time_budget",
        },
        "chunk_guard": {
            "enabled": True,
            "mode": "strict",
            "reason": "pairwise_conflicts",
            "candidate_pool": 4,
            "filtered_count": 1,
            "retained_count": 3,
            "signed_chunk_count": 4,
            "pairwise_conflict_count": 2,
            "max_conflict_penalty": 0.3,
            "report_only": False,
            "fallback": False,
        },
        "chunk_contract": {
            "fallback_count": 2,
            "skeleton_chunk_count": 1,
        },
        "parallel": {
            "docs": {"timed_out": True},
            "worktree": {"timed_out": False},
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
        "adaptive_router": {
            "enabled": True,
            "mode": "bandit",
            "arm_set": "default",
            "arm_id": "arm-a",
            "confidence": 0.73,
            "shadow_arm_id": "arm-b",
            "shadow_source": "model",
            "shadow_confidence": 0.22,
            "online_bandit": {
                "requested": True,
                "fallback_applied": True,
                "fallback_reason": "cold_start",
                "reason": "explore",
            },
        },
        "chunk_metrics": {
            "topological_shield_enabled": 1.0,
            "topological_shield_report_only": 1.0,
            "topological_shield_attenuated_chunk_count": 1.0,
            "topological_shield_coverage_ratio": 0.5,
            "topological_shield_attenuation_total": 0.2,
            "graph_source_provider_loaded": 1.0,
            "graph_source_projection_fallback": 1.0,
            "graph_source_edge_count": 7.0,
            "graph_source_inbound_signal_chunk_count": 1.0,
            "graph_source_inbound_signal_coverage_ratio": 1.0,
            "graph_source_centrality_signal_chunk_count": 1.0,
            "graph_source_centrality_signal_coverage_ratio": 1.0,
            "graph_source_pagerank_signal_chunk_count": 1.0,
            "graph_source_pagerank_signal_coverage_ratio": 1.0,
        },
        "policy_name": "doc_intent",
        "metadata": {
            "docs_enabled": True,
            "docs_section_count": 2,
            "docs_injected_count": 1,
        },
    }
    candidate_files = [
        {"path": "src/auth.py", "module": "src.auth"},
        {"path": "src/token.py", "module": "src.token"},
    ]
    raw_candidate_chunks = [
        {
            "path": "src/auth.py",
            "qualified_name": "auth.validate_token",
            "disclosure_fallback_reason": "unsupported_language",
        },
        {
            "path": "src/token.py",
            "qualified_name": "token.issue",
        },
    ]
    candidate_chunks = [
        {
            "path": "src/auth.py",
            "qualified_name": "auth.validate_token",
        }
    ]

    metrics = build_case_evaluation_metrics(
        plan_payload=plan_payload,
        index_payload=index_payload,
        index_metadata=index_payload["metadata"],
        source_plan_payload=plan_payload["source_plan"],
        candidate_files=candidate_files,
        raw_candidate_chunks=raw_candidate_chunks,
        candidate_chunks=candidate_chunks,
        source_plan_has_candidate_chunks=True,
    )

    assert metrics.chunk_contract_fallback_count == 2
    assert metrics.unsupported_language_fallback_count == 1
    assert metrics.skills_selected_count == 2.0
    assert metrics.source_plan_granularity_preferred_count == 1
    assert metrics.multi_channel_rrf_enabled is True
    assert metrics.multi_channel_rrf_applied is True
    assert metrics.multi_channel_rrf_granularity_count == 3
    assert metrics.multi_channel_rrf_pool_size == 6
    assert metrics.multi_channel_rrf_granularity_pool_ratio == 0.5
    assert metrics.native_scip_loaded is True
    assert metrics.native_scip_document_count == 5
    assert metrics.native_scip_definition_occurrence_count == 7
    assert metrics.native_scip_reference_occurrence_count == 11
    assert metrics.native_scip_symbol_definition_count == 3
    assert metrics.skills_budget_exhausted is True
    assert metrics.plan_replay_cache_hit is True
    assert metrics.source_plan_packed_path_ratio == 1.0
    assert metrics.router_online_bandit_requested is True
    assert metrics.router_fallback_reason == "cold_start"
    assert metrics.router_shadow_source == "model"
    assert metrics.docs_enabled_flag is True
    assert metrics.docs_hit == 1.0
    assert metrics.hint_inject == 1.0
    assert metrics.embedding_runtime_provider == "hash_colbert"
    assert metrics.embedding_strategy_mode == "cross_encoder"
    assert metrics.embedding_semantic_rerank_applied is True
    assert metrics.ltm_selected_count == 2
    assert metrics.ltm_attribution_count == 1
    assert metrics.ltm_graph_neighbor_count == 1
    assert metrics.ltm_plan_constraint_count == 1
    assert metrics.ltm_feedback_signal_counts == {
        "helpful": 1,
        "stale": 0,
        "harmful": 1,
    }
    assert metrics.ltm_attribution_scope_counts == {
        "explicit_selection_only": 1,
    }
    assert metrics.chunk_guard_mode == "strict"
    assert metrics.chunk_guard_filter_ratio == 0.25
    assert metrics.graph_source_provider_loaded is True
    assert metrics.graph_source_projection_fallback is True
    assert metrics.graph_source_edge_count == 7
    assert metrics.graph_source_inbound_signal_chunk_count == 1
    assert metrics.graph_source_inbound_signal_coverage_ratio == 1.0
    assert metrics.graph_source_centrality_signal_chunk_count == 1
    assert metrics.graph_source_centrality_signal_coverage_ratio == 1.0
    assert metrics.graph_source_pagerank_signal_chunk_count == 1
    assert metrics.graph_source_pagerank_signal_coverage_ratio == 1.0
    assert metrics.agent_loop_observed is True
    assert metrics.agent_loop_enabled is True
    assert metrics.agent_loop_attempted is True
    assert metrics.agent_loop_actions_requested == 2
    assert metrics.agent_loop_actions_executed == 1
    assert metrics.agent_loop_stop_reason == "completed"
    assert metrics.agent_loop_replay_safe is True
    assert metrics.agent_loop_last_policy_id == "source_plan_refresh"
    assert metrics.agent_loop_request_more_context_count == 1
    assert metrics.agent_loop_request_source_plan_retry_count == 1
    assert metrics.agent_loop_request_validation_retry_count == 0
    assert metrics.source_plan_evidence_summary == {
        "direct_count": 1.0,
        "neighbor_context_count": 1.0,
        "hint_only_count": 0.0,
        "direct_ratio": 0.5,
        "neighbor_context_ratio": 0.5,
        "hint_only_ratio": 0.0,
        "symbol_count": 2.0,
        "signature_count": 1.0,
        "skeleton_count": 1.0,
        "robust_signature_count": 1.0,
        "symbol_ratio": 1.0,
        "signature_ratio": 0.5,
        "skeleton_ratio": 0.5,
        "robust_signature_ratio": 0.5,
    }
