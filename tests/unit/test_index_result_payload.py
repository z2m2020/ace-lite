from __future__ import annotations

from copy import deepcopy

from ace_lite.chunking.skeleton import CHUNK_SKELETON_SCHEMA_VERSION
from ace_lite.index_stage import build_index_stage_output as exported_build_index_stage_output
from ace_lite.index_stage import build_index_stage_result as exported_build_index_stage_result
from ace_lite.index_stage.result_payload import build_index_stage_output, build_index_stage_result


def _base_inputs() -> dict:
    candidates = [
        {
            "path": "src/auth.py",
            "module": "src.auth",
            "score_breakdown": {"path": 1.0, "bm25": 0.5},
        },
        {"path": "src/session.py", "module": "src.session"},
    ]
    candidate_chunks = [
        {
            "path": "src/auth.py",
            "qualified_name": "validate_token",
            "kind": "function",
            "lineno": 10,
            "score_breakdown": {"candidate": 1.0},
            "score_embedding": 0.6,
            "robust_signature_summary": {
                "version": "v1",
                "available": True,
                "compatibility_domain": "src/auth.py::function",
                "shape_hash": "shape123",
                "entity_vocab_count": 4,
            },
        }
    ]
    return {
        "repo": "demo",
        "root": "/tmp/demo",
        "terms": ["validate", "token"],
        "targets": ["src/auth.py"],
        "index_hash": "idx",
        "index_data": {
            "file_count": 2,
            "indexed_at": "2026-03-06T00:00:00+00:00",
            "languages_covered": ["python"],
            "parser": {"name": "tree-sitter"},
        },
        "cache_info": {"hit": False},
        "requested_ranker": "rrf_hybrid",
        "selected_ranker": "rrf_hybrid",
        "ranker_fallbacks": [],
        "corpus_size": 2,
        "min_score_used": 1,
        "fusion_mode": "linear",
        "hybrid_re2_rrf_k": 60,
        "top_k_files": 1,
        "candidate_relative_threshold": 0.25,
        "chunk_top_k": 8,
        "chunk_per_file_limit": 2,
        "chunk_token_budget": 256,
        "chunk_disclosure": "snippet",
        "candidates": candidates,
        "candidate_chunks": candidate_chunks,
        "chunk_metrics": {
            "candidate_chunk_count": 1,
            "chunk_budget_used": 48,
            "robust_signature_count": 1,
            "robust_signature_coverage_ratio": 1.0,
            "topological_shield_enabled": 1.0,
            "topological_shield_report_only": 1.0,
            "topological_shield_attenuated_chunk_count": 1.0,
            "topological_shield_coverage_ratio": 1.0,
            "topological_shield_attenuation_total": 0.4,
        },
        "exact_search_payload": {"enabled": False},
        "docs_payload": {"enabled": True, "section_count": 1},
        "worktree_prior": {"enabled": False, "changed_count": 0, "seed_paths": []},
        "parallel_payload": {"enabled": False},
        "prior_payload": {
            "docs_hint_paths": 1,
            "docs_hint_modules": 0,
            "boosted_candidate_count": 0,
            "added_candidate_count": 0,
            "docs_injected_candidate_count": 0,
            "worktree_guard_enabled": False,
            "worktree_guard_applied": False,
            "worktree_guard_reason": "",
            "worktree_guard_filtered_changed_count": 0,
            "worktree_guard_filtered_seed_count": 0,
        },
        "graph_lookup_payload": {
            "enabled": False,
            "reason": "disabled",
            "guarded": False,
            "boosted_count": 0,
            "weights": {
                "scip": 0.0,
                "xref": 0.0,
                "query_xref": 0.0,
                "symbol": 0.0,
                "import": 0.0,
                "coverage": 0.0,
            },
            "candidate_count": 1,
            "pool_size": 0,
            "query_terms_count": 0,
            "normalization": "linear",
            "guard_max_candidates": 64,
            "guard_min_query_terms": 0,
            "guard_max_query_terms": 64,
            "query_hit_paths": 0,
            "scip_signal_paths": 0,
            "xref_signal_paths": 0,
            "symbol_hit_paths": 0,
            "import_hit_paths": 0,
            "coverage_hit_paths": 0,
            "max_inbound": 0.0,
            "max_xref_count": 0.0,
            "max_query_hits": 0.0,
            "max_symbol_hits": 0.0,
            "max_import_hits": 0.0,
            "max_query_coverage": 0.0,
        },
        "cochange_payload": {"neighbors_added": 0},
        "scip_payload": {"enabled": False},
        "embeddings_payload": {
            "enabled": True,
            "fallback": False,
            "reranked_count": 1,
            "runtime_provider": "hash_cross",
            "runtime_model": "hash-cross-v1",
            "runtime_dimension": 1,
            "auto_normalized": False,
            "auto_normalized_fields": [],
            "similarity_mean": 0.4,
            "time_budget_ms": 60,
            "time_budget_base_ms": 80,
            "time_budget_exceeded": False,
            "adaptive_budget_applied": True,
            "rerank_pool_effective": 2,
        },
        "feedback_payload": {
            "enabled": False,
            "reason": "disabled",
            "event_count": 0,
            "matched_event_count": 0,
            "boosted_candidate_count": 0,
            "boosted_unique_paths": 0,
        },
        "multi_channel_fusion_payload": {
            "enabled": True,
            "applied": True,
            "reason": "ok",
            "rrf_k": 60,
            "channels": {
                "granularity": {
                    "count": 2,
                    "cap": 8,
                    "top": ["src/auth.py", "src/session.py"],
                }
            },
            "fused": {
                "scored_count": 2,
                "pool_size": 4,
                "top": [],
            },
        },
        "second_pass_payload": {
            "triggered": False,
            "applied": False,
            "reason": "n/a",
            "retry_ranker": "",
        },
        "refine_pass_payload": {
            "enabled": True,
            "trigger_condition_met": False,
            "triggered": False,
            "applied": False,
            "reason": "",
            "retry_ranker": "",
            "candidate_count_before": 0,
            "candidate_count_after": 0,
            "max_passes": 1,
        },
        "chunk_semantic_rerank_payload": {
            "enabled": True,
            "reason": "ok",
            "rerank_pool_effective": 1,
            "reranked_count": 1,
            "time_budget_ms": 40,
            "time_budget_exceeded": False,
            "fallback": False,
            "similarity_mean": 0.6,
            "similarity_max": 0.9,
        },
        "topological_shield_payload": {
            "enabled": True,
            "mode": "report_only",
            "report_only": True,
            "reason": "report_only",
            "attenuated_chunk_count": 1,
            "coverage_ratio": 1.0,
            "attenuation_total": 0.4,
            "adjacency_evidence_count": 1,
            "shared_parent_evidence_count": 1,
            "graph_attested_chunk_count": 1,
            "selection_order_changed": False,
        },
        "chunk_guard_payload": {
            "enabled": True,
            "mode": "report_only",
            "reason": "report_only",
            "candidate_pool": 1,
            "signed_chunk_count": 1,
            "filtered_count": 0,
            "retained_count": 1,
            "pairwise_conflict_count": 0,
            "max_conflict_penalty": 0.0,
            "report_only": True,
            "fallback": False,
        },
        "adaptive_router_payload": {
            "enabled": True,
            "mode": "observe",
            "model_path": "context-map/router/model.json",
            "state_path": "context-map/router/state.json",
            "arm_set": "retrieval_policy_v1",
            "arm_id": "doc_intent",
            "source": "auto",
            "confidence": 0.0,
            "shadow_arm_id": "",
            "shadow_confidence": 0.0,
            "online_bandit": {
                "requested": False,
                "experiment_enabled": False,
                "eligible": False,
                "active": False,
                "reason": "disabled",
                "is_exploration": False,
                "exploration_probability": 0.0,
                "fallback_applied": False,
                "fallback_reason": "",
                "executed_mode": "heuristic",
                "fallback_mode": "heuristic",
                "state_path": "context-map/router/state.json",
                "required_task_ids": ["Y18", "Y19", "Y20", "Y21"],
                "prerequisites": [],
            },
        },
        "policy_name": "doc_intent",
        "policy_version": "v2",
        "timings_ms": {"embeddings": 1.2},
    }


def test_build_index_stage_result_limits_files_and_attaches_why() -> None:
    payload = build_index_stage_result(**_base_inputs())

    assert payload["module_hint"] == "src.auth"
    assert len(payload["candidate_files"]) == 1
    assert payload["candidate_files"][0]["path"] == "src/auth.py"
    assert payload["candidate_files"][0]["why"].startswith("signals:")
    assert payload["candidate_chunks"][0]["why"].startswith("signals:")
    assert payload["context_budget"]["chunk_budget_used"] == 48
    assert payload["candidate_ranking"]["chunk_semantic_rerank_reason"] == "ok"
    assert payload["candidate_ranking"]["multi_channel_rrf_granularity_count"] == 2
    assert payload["candidate_ranking"]["multi_channel_rrf_pool_size"] == 4
    assert payload["candidate_ranking"]["multi_channel_rrf_granularity_pool_ratio"] == 0.5
    assert payload["candidate_ranking"]["graph_lookup_pool_size"] == 0
    assert payload["candidate_ranking"]["graph_lookup_query_terms_count"] == 0
    assert payload["candidate_ranking"]["graph_lookup_scip_signal_paths"] == 0
    assert payload["candidate_ranking"]["graph_lookup_reason"] == "disabled"
    assert payload["candidate_ranking"]["graph_lookup_guarded"] is False
    assert payload["candidate_ranking"]["graph_lookup_weight_scip"] == 0.0
    assert payload["candidate_ranking"]["graph_lookup_candidate_count"] == 1
    assert payload["candidate_ranking"]["graph_lookup_guard_max_candidates"] == 64
    assert payload["candidate_ranking"]["graph_lookup_normalization"] == "linear"
    assert payload["candidate_ranking"]["graph_lookup_max_inbound"] == 0.0
    assert payload["candidate_ranking"]["graph_lookup_max_query_coverage"] == 0.0
    assert payload["candidate_ranking"]["topological_shield"]["mode"] == "report_only"
    assert payload["chunk_guard"]["mode"] == "report_only"
    assert payload["metadata"]["selection_fingerprint"]
    assert payload["metadata"]["chunk_cache_contract_schema_version"] == ""
    assert payload["metadata"]["chunk_cache_contract_fingerprint"] == ""
    assert payload["metadata"]["chunk_cache_contract_file_count"] == 0
    assert payload["metadata"]["chunk_cache_contract_chunk_count"] == 0
    assert payload["metadata"]["multi_channel_rrf_granularity_count"] == 2
    assert payload["metadata"]["multi_channel_rrf_pool_size"] == 4
    assert payload["metadata"]["multi_channel_rrf_granularity_pool_ratio"] == 0.5
    assert payload["metadata"]["graph_lookup_pool_size"] == 0
    assert payload["metadata"]["graph_lookup_query_terms_count"] == 0
    assert payload["metadata"]["graph_lookup_scip_signal_paths"] == 0
    assert payload["metadata"]["graph_lookup_reason"] == "disabled"
    assert payload["metadata"]["graph_lookup_guarded"] is False
    assert payload["metadata"]["graph_lookup_weight_scip"] == 0.0
    assert payload["metadata"]["graph_lookup_candidate_count"] == 1
    assert payload["metadata"]["graph_lookup_guard_max_candidates"] == 64
    assert payload["metadata"]["graph_lookup_normalization"] == "linear"
    assert payload["metadata"]["graph_lookup_max_inbound"] == 0.0
    assert payload["metadata"]["graph_lookup_max_query_coverage"] == 0.0
    assert payload["metadata"]["robust_signature_count"] == 1
    assert payload["metadata"]["robust_signature_coverage_ratio"] == 1.0
    assert payload["metadata"]["topological_shield_enabled"] is True
    assert payload["metadata"]["topological_shield_attenuation_total"] == 0.4
    assert payload["chunk_contract"] == {
        "schema_version": CHUNK_SKELETON_SCHEMA_VERSION,
        "requested_disclosure": "snippet",
        "observed_disclosures": ["snippet"],
        "fallback_count": 0,
        "chunk_count": 1,
        "skeleton_chunk_count": 0,
        "skeleton_modes": [],
        "skeleton_schema_versions": [],
    }
    assert payload["metadata"]["chunk_contract_schema_version"] == CHUNK_SKELETON_SCHEMA_VERSION
    assert payload["metadata"]["chunk_contract_requested_disclosure"] == "snippet"
    assert payload["metadata"]["chunk_contract_observed_disclosures"] == ["snippet"]
    assert payload["metadata"]["chunk_contract_fallback_count"] == 0
    assert payload["metadata"]["chunk_contract_skeleton_chunk_count"] == 0
    assert payload["subgraph_payload"] == {
        "payload_version": "subgraph_payload_v1",
        "taxonomy_version": "subgraph_edge_taxonomy_v1",
        "enabled": False,
        "reason": "disabled",
        "seed_paths": [],
        "edge_counts": {},
    }
    assert payload["metadata"]["subgraph_payload_version"] == "subgraph_payload_v1"
    assert payload["metadata"]["subgraph_taxonomy_version"] == "subgraph_edge_taxonomy_v1"
    assert payload["metadata"]["subgraph_enabled"] is False
    assert payload["metadata"]["subgraph_seed_path_count"] == 0


def test_build_index_stage_result_fingerprint_is_stable() -> None:
    payload1 = build_index_stage_result(**_base_inputs())
    payload2 = build_index_stage_result(**deepcopy(_base_inputs()))

    assert payload1["metadata"]["selection_fingerprint"] == payload2["metadata"][
        "selection_fingerprint"
    ]


def test_build_index_stage_result_fingerprint_changes_when_chunk_contract_changes() -> None:
    baseline_inputs = _base_inputs()
    baseline = build_index_stage_result(**baseline_inputs)

    changed_inputs = deepcopy(_base_inputs())
    changed_inputs["chunk_disclosure"] = "skeleton_light"
    changed_inputs["candidate_chunks"][0]["disclosure"] = "skeleton_light"
    changed_inputs["candidate_chunks"][0]["skeleton"] = {
        "schema_version": CHUNK_SKELETON_SCHEMA_VERSION,
        "mode": "skeleton_light",
        "language": "python",
        "module": "src.auth",
        "symbol": {
            "name": "validate_token",
            "qualified_name": "validate_token",
            "kind": "function",
        },
        "span": {"start_line": 10, "end_line": 12, "line_count": 3},
        "anchors": {
            "path": "src/auth.py",
            "signature": "def validate_token(raw: str) -> bool:",
            "robust_signature_available": True,
        },
    }
    changed = build_index_stage_result(**changed_inputs)

    assert baseline["metadata"]["selection_fingerprint"] != changed["metadata"][
        "selection_fingerprint"
    ]


def test_build_index_stage_result_attaches_chunk_cache_contract_summary() -> None:
    payload = build_index_stage_result(
        **{
            **_base_inputs(),
            "index_data": {
                **_base_inputs()["index_data"],
                "chunk_cache_contract": {
                    "schema_version": "chunk-cache-contract-v1",
                    "fingerprint": "chunk-contract-fp",
                    "file_count": 2,
                    "chunk_count": 5,
                    "files": {
                        "src/auth.py": {
                            "fingerprint": "auth-fp",
                            "chunk_count": 3,
                        }
                    },
                },
            },
        }
    )

    assert payload["chunk_cache_contract"] == {
        "schema_version": "chunk-cache-contract-v1",
        "fingerprint": "chunk-contract-fp",
        "file_count": 2,
        "chunk_count": 5,
    }
    assert payload["metadata"]["chunk_cache_contract_schema_version"] == (
        "chunk-cache-contract-v1"
    )
    assert payload["metadata"]["chunk_cache_contract_fingerprint"] == "chunk-contract-fp"
    assert payload["metadata"]["chunk_cache_contract_file_count"] == 2
    assert payload["metadata"]["chunk_cache_contract_chunk_count"] == 5


def test_build_index_stage_result_fingerprint_changes_when_subgraph_contract_changes() -> None:
    baseline_inputs = _base_inputs()
    baseline = build_index_stage_result(**baseline_inputs)

    changed_inputs = deepcopy(_base_inputs())
    changed_inputs["graph_lookup_payload"] = {
        "enabled": True,
        "reason": "ok",
        "boosted_count": 1,
        "query_hit_paths": 1,
    }
    changed_inputs["candidates"][0]["score_breakdown"]["graph_lookup"] = 0.3
    changed = build_index_stage_result(**changed_inputs)

    assert baseline["metadata"]["selection_fingerprint"] != changed["metadata"][
        "selection_fingerprint"
    ]


def test_build_index_stage_result_preserves_payload_contract() -> None:
    payload = build_index_stage_result(**_base_inputs())

    assert payload["candidate_ranking"]["requested"] == "rrf_hybrid"
    assert payload["candidate_ranking"]["selected"] == "rrf_hybrid"
    assert payload["candidate_ranking"]["fusion_mode"] == "rrf"
    assert payload["candidate_ranking"]["exact_search"] == {"enabled": False}
    assert payload["candidate_ranking"]["embedding_auto_normalized"] is False
    assert payload["candidate_ranking"]["topological_shield"]["report_only"] is True
    assert payload["candidate_ranking"]["adaptive_router"]["enabled"] is True
    assert payload["candidate_ranking"]["adaptive_router"]["arm_id"] == "doc_intent"
    assert payload["candidate_ranking"]["second_pass"] == {
        "triggered": False,
        "applied": False,
        "reason": "n/a",
        "retry_ranker": "",
    }
    assert payload["candidate_ranking"]["refine_pass"] == {
        "enabled": True,
        "trigger_condition_met": False,
        "triggered": False,
        "applied": False,
        "reason": "",
        "retry_ranker": "",
        "candidate_count_before": 0,
        "candidate_count_after": 0,
        "max_passes": 1,
    }
    assert payload["metadata"]["candidate_fusion_mode"] == "rrf"
    assert payload["metadata"]["router_enabled"] is True
    assert payload["metadata"]["router_mode"] == "observe"
    assert payload["metadata"]["router_arm_id"] == "doc_intent"
    assert payload["metadata"]["router_source"] == "auto"
    assert payload["metadata"]["embedding_auto_normalized_fields"] == []
    assert payload["metadata"]["timings_ms"] == {"embeddings": 1.2}
    assert payload["metadata"]["refine_pass_enabled"] is True
    assert payload["metadata"]["refine_pass_trigger_condition_met"] is False
    assert payload["metadata"]["refine_pass_reason"] == ""
    assert payload["metadata"]["second_pass_triggered"] is False
    assert payload["metadata"]["second_pass_reason"] == "n/a"
    assert payload["docs"] == {"enabled": True, "section_count": 1}
    assert payload["parallel"] == {"enabled": False}
    assert payload["prior_applied"]["docs_hint_paths"] == 1
    assert payload["graph_lookup"] == {
        "enabled": False,
        "reason": "disabled",
        "guarded": False,
        "boosted_count": 0,
        "weights": {
            "scip": 0.0,
            "xref": 0.0,
            "query_xref": 0.0,
            "symbol": 0.0,
            "import": 0.0,
            "coverage": 0.0,
        },
        "candidate_count": 1,
        "pool_size": 0,
        "query_terms_count": 0,
        "normalization": "linear",
        "guard_max_candidates": 64,
        "guard_min_query_terms": 0,
        "guard_max_query_terms": 64,
        "query_hit_paths": 0,
        "scip_signal_paths": 0,
        "xref_signal_paths": 0,
        "symbol_hit_paths": 0,
        "import_hit_paths": 0,
        "coverage_hit_paths": 0,
        "max_inbound": 0.0,
        "max_xref_count": 0.0,
        "max_query_hits": 0.0,
        "max_symbol_hits": 0.0,
        "max_import_hits": 0.0,
        "max_query_coverage": 0.0,
    }
    assert payload["subgraph_payload"]["payload_version"] == "subgraph_payload_v1"
    assert payload["cochange"] == {"neighbors_added": 0}
    assert payload["embeddings"]["runtime_provider"] == "hash_cross"
    assert payload["feedback"]["reason"] == "disabled"
    assert payload["multi_channel_fusion"] == {
        "enabled": True,
        "applied": True,
        "reason": "ok",
        "rrf_k": 60,
        "channels": {
            "granularity": {
                "count": 2,
                "cap": 8,
                "top": ["src/auth.py", "src/session.py"],
            }
        },
        "fused": {
            "scored_count": 2,
            "pool_size": 4,
            "top": [],
        },
    }
    assert payload["topological_shield"]["selection_order_changed"] is False
    assert payload["chunk_guard"]["reason"] == "report_only"
    assert payload["metadata"]["chunk_guard_report_only"] is True
    assert payload["adaptive_router"]["arm_set"] == "retrieval_policy_v1"


def test_build_index_stage_result_normalizes_fusion_modes() -> None:
    rrf_payload = build_index_stage_result(**_base_inputs())

    hybrid_inputs = _base_inputs()
    hybrid_inputs["selected_ranker"] = "hybrid_re2"
    hybrid_inputs["fusion_mode"] = "combined"
    hybrid_payload = build_index_stage_result(**hybrid_inputs)

    lexical_inputs = _base_inputs()
    lexical_inputs["selected_ranker"] = "bm25"
    lexical_inputs["fusion_mode"] = "combined"
    lexical_payload = build_index_stage_result(**lexical_inputs)

    assert rrf_payload["candidate_ranking"]["fusion_mode"] == "rrf"
    assert hybrid_payload["candidate_ranking"]["fusion_mode"] == "combined"
    assert hybrid_payload["metadata"]["candidate_fusion_mode"] == "combined"
    assert lexical_payload["candidate_ranking"]["fusion_mode"] == "linear"
    assert lexical_payload["metadata"]["candidate_fusion_mode"] == "linear"


def test_build_index_stage_result_preserves_shadow_router_metadata() -> None:
    inputs = _base_inputs()
    inputs["adaptive_router_payload"]["shadow_arm_id"] = "doc_intent_hybrid"
    inputs["adaptive_router_payload"]["shadow_source"] = "model"
    inputs["adaptive_router_payload"]["shadow_confidence"] = 0.84

    payload = build_index_stage_result(**inputs)

    assert payload["adaptive_router"]["shadow_arm_id"] == "doc_intent_hybrid"
    assert payload["adaptive_router"]["shadow_source"] == "model"
    assert payload["candidate_ranking"]["adaptive_router"]["shadow_arm_id"] == "doc_intent_hybrid"
    assert payload["candidate_ranking"]["adaptive_router"]["shadow_source"] == "model"
    assert payload["metadata"]["router_shadow_arm_id"] == "doc_intent_hybrid"
    assert payload["metadata"]["router_shadow_source"] == "model"
    assert payload["metadata"]["router_shadow_confidence"] == 0.84


def test_build_index_stage_result_preserves_online_bandit_gate_metadata() -> None:
    inputs = _base_inputs()
    inputs["adaptive_router_payload"]["online_bandit"] = {
        "requested": True,
        "experiment_enabled": True,
        "eligible": True,
        "active": False,
        "reason": "eligible_pending_runtime",
        "is_exploration": False,
        "exploration_probability": 0.0,
        "fallback_applied": True,
        "fallback_reason": "heuristic_default",
        "executed_mode": "heuristic",
        "fallback_mode": "heuristic",
        "state_path": "context-map/router/online-bandit-state.json",
        "required_task_ids": ["Y18", "Y19", "Y20", "Y21"],
        "prerequisites": [
            {"task_id": "Y18", "capability": "shadow_mode_ready", "ready": True}
        ],
    }

    payload = build_index_stage_result(**inputs)

    assert payload["adaptive_router"]["online_bandit"]["requested"] is True
    assert payload["adaptive_router"]["online_bandit"]["experiment_enabled"] is True
    assert payload["candidate_ranking"]["adaptive_router"]["online_bandit"]["eligible"] is True
    assert payload["metadata"]["router_online_bandit_requested"] is True
    assert payload["metadata"]["router_experiment_enabled"] is True
    assert payload["metadata"]["router_online_bandit_eligible"] is True
    assert payload["metadata"]["router_online_bandit_active"] is False
    assert payload["metadata"]["router_is_exploration"] is False
    assert payload["metadata"]["router_exploration_probability"] == 0.0
    assert payload["metadata"]["router_fallback_applied"] is True
    assert payload["metadata"]["router_fallback_reason"] == "heuristic_default"
    assert payload["metadata"]["router_online_bandit_reason"] == "eligible_pending_runtime"


def test_build_index_stage_result_zero_chunk_semantic_pool_has_zero_ratio() -> None:
    inputs = _base_inputs()
    inputs["chunk_semantic_rerank_payload"] = {
        "enabled": True,
        "reason": "empty_pool",
        "rerank_pool_effective": 0,
        "reranked_count": 3,
        "time_budget_ms": 40,
        "time_budget_exceeded": False,
        "fallback": False,
        "similarity_mean": 0.0,
        "similarity_max": 0.0,
    }

    payload = build_index_stage_result(**inputs)

    assert payload["candidate_ranking"]["chunk_semantic_rerank_pool_effective"] == 0
    assert payload["candidate_ranking"]["chunk_semantic_rerank_reranked_count"] == 3
    assert payload["candidate_ranking"]["chunk_semantic_rerank_ratio"] == 0.0
    assert payload["metadata"]["chunk_semantic_rerank_ratio"] == 0.0


def test_build_index_stage_result_fingerprint_ignores_candidates_beyond_top_k() -> None:
    baseline = build_index_stage_result(**_base_inputs())

    ignored_change_inputs = _base_inputs()
    ignored_change_inputs["candidates"][1]["path"] = "src/renamed_session.py"
    ignored_change_inputs["candidates"][1]["module"] = "src.renamed_session"
    ignored_payload = build_index_stage_result(**ignored_change_inputs)

    included_change_inputs = _base_inputs()
    included_change_inputs["candidates"][0]["path"] = "src/auth_v2.py"
    included_change_inputs["candidates"][0]["module"] = "src.auth_v2"
    included_payload = build_index_stage_result(**included_change_inputs)

    chunk_change_inputs = _base_inputs()
    chunk_change_inputs["candidate_chunks"][0]["qualified_name"] = "refresh_token"
    chunk_payload = build_index_stage_result(**chunk_change_inputs)

    assert (
        baseline["metadata"]["selection_fingerprint"]
        == ignored_payload["metadata"]["selection_fingerprint"]
    )
    assert (
        baseline["metadata"]["selection_fingerprint"]
        != included_payload["metadata"]["selection_fingerprint"]
    )
    assert (
        baseline["metadata"]["selection_fingerprint"]
        != chunk_payload["metadata"]["selection_fingerprint"]
    )


def test_build_index_stage_result_fingerprint_ignores_chunk_guard_counters() -> None:
    baseline = build_index_stage_result(**_base_inputs())

    changed_inputs = _base_inputs()
    changed_inputs["chunk_guard_payload"] = {
        **changed_inputs["chunk_guard_payload"],
        "filtered_count": 3,
        "retained_count": 5,
        "pairwise_conflict_count": 4,
    }
    changed_inputs["topological_shield_payload"] = {
        **changed_inputs["topological_shield_payload"],
        "attenuated_chunk_count": 3,
        "attenuation_total": 0.9,
    }
    changed_payload = build_index_stage_result(**changed_inputs)

    assert (
        baseline["metadata"]["selection_fingerprint"]
        == changed_payload["metadata"]["selection_fingerprint"]
    )


def test_build_index_stage_result_surfaces_refine_metadata() -> None:
    inputs = _base_inputs()
    inputs["refine_pass_payload"] = {
        "enabled": False,
        "trigger_condition_met": True,
        "triggered": False,
        "applied": False,
        "reason": "disabled",
        "retry_ranker": "hybrid_re2",
        "candidate_count_before": 1,
        "candidate_count_after": 1,
        "max_passes": 1,
    }

    payload = build_index_stage_result(**inputs)

    assert payload["candidate_ranking"]["refine_pass"]["trigger_condition_met"] is True
    assert payload["candidate_ranking"]["refine_pass"]["reason"] == "disabled"
    assert payload["metadata"]["refine_pass_enabled"] is False
    assert payload["metadata"]["refine_pass_trigger_condition_met"] is True
    assert payload["metadata"]["refine_pass_retry_ranker"] == "hybrid_re2"


def test_build_index_stage_result_builds_consumer_facing_subgraph_payload() -> None:
    inputs = _base_inputs()
    inputs["graph_lookup_payload"] = {
        "enabled": True,
        "reason": "ok",
        "guarded": False,
        "boosted_count": 2,
        "weights": {
            "scip": 0.3,
            "xref": 0.2,
            "query_xref": 0.2,
            "symbol": 0.1,
            "import": 0.1,
            "coverage": 0.1,
        },
        "candidate_count": 4,
        "pool_size": 4,
        "query_terms_count": 3,
        "normalization": "log1p",
        "guard_max_candidates": 8,
        "guard_min_query_terms": 1,
        "guard_max_query_terms": 6,
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
    }
    inputs["candidates"][0]["score_breakdown"]["graph_lookup"] = 0.3
    inputs["candidate_chunks"][0]["score_breakdown"]["graph_lookup"] = 0.25
    inputs["candidate_chunks"][0]["score_breakdown"]["graph_prior"] = 0.15
    inputs["candidate_chunks"][0]["score_breakdown"]["graph_closure_bonus"] = 0.1

    payload = build_index_stage_result(**inputs)

    assert payload["subgraph_payload"]["enabled"] is True
    assert payload["subgraph_payload"]["reason"] == "ok"
    assert payload["subgraph_payload"]["seed_paths"] == ["src/auth.py"]
    assert payload["subgraph_payload"]["edge_counts"] == {
        "graph_lookup": 1,
        "graph_prior": 1,
        "graph_closure_bonus": 1,
    }
    assert payload["candidate_ranking"]["graph_lookup_pool_size"] == 4
    assert payload["candidate_ranking"]["graph_lookup_query_terms_count"] == 3
    assert payload["candidate_ranking"]["graph_lookup_reason"] == "ok"
    assert payload["candidate_ranking"]["graph_lookup_guarded"] is False
    assert payload["candidate_ranking"]["graph_lookup_weight_scip"] == 0.3
    assert payload["candidate_ranking"]["graph_lookup_weight_xref"] == 0.2
    assert payload["candidate_ranking"]["graph_lookup_weight_query_xref"] == 0.2
    assert payload["candidate_ranking"]["graph_lookup_candidate_count"] == 4
    assert payload["candidate_ranking"]["graph_lookup_guard_max_candidates"] == 8
    assert payload["candidate_ranking"]["graph_lookup_guard_min_query_terms"] == 1
    assert payload["candidate_ranking"]["graph_lookup_guard_max_query_terms"] == 6
    assert payload["candidate_ranking"]["graph_lookup_normalization"] == "log1p"
    assert payload["candidate_ranking"]["graph_lookup_scip_signal_paths"] == 2
    assert payload["candidate_ranking"]["graph_lookup_xref_signal_paths"] == 3
    assert payload["candidate_ranking"]["graph_lookup_symbol_hit_paths"] == 1
    assert payload["candidate_ranking"]["graph_lookup_import_hit_paths"] == 1
    assert payload["candidate_ranking"]["graph_lookup_coverage_hit_paths"] == 2
    assert payload["candidate_ranking"]["graph_lookup_max_inbound"] == 4.0
    assert payload["candidate_ranking"]["graph_lookup_max_xref_count"] == 3.0
    assert payload["candidate_ranking"]["graph_lookup_max_query_hits"] == 2.0
    assert payload["candidate_ranking"]["graph_lookup_max_symbol_hits"] == 1.0
    assert payload["candidate_ranking"]["graph_lookup_max_import_hits"] == 1.0
    assert payload["candidate_ranking"]["graph_lookup_max_query_coverage"] == 0.666667
    assert payload["metadata"]["graph_lookup_pool_size"] == 4
    assert payload["metadata"]["graph_lookup_query_terms_count"] == 3
    assert payload["metadata"]["graph_lookup_reason"] == "ok"
    assert payload["metadata"]["graph_lookup_guarded"] is False
    assert payload["metadata"]["graph_lookup_weight_scip"] == 0.3
    assert payload["metadata"]["graph_lookup_weight_xref"] == 0.2
    assert payload["metadata"]["graph_lookup_weight_query_xref"] == 0.2
    assert payload["metadata"]["graph_lookup_candidate_count"] == 4
    assert payload["metadata"]["graph_lookup_guard_max_candidates"] == 8
    assert payload["metadata"]["graph_lookup_guard_min_query_terms"] == 1
    assert payload["metadata"]["graph_lookup_guard_max_query_terms"] == 6
    assert payload["metadata"]["graph_lookup_normalization"] == "log1p"
    assert payload["metadata"]["graph_lookup_scip_signal_paths"] == 2
    assert payload["metadata"]["graph_lookup_xref_signal_paths"] == 3
    assert payload["metadata"]["graph_lookup_symbol_hit_paths"] == 1
    assert payload["metadata"]["graph_lookup_import_hit_paths"] == 1
    assert payload["metadata"]["graph_lookup_coverage_hit_paths"] == 2
    assert payload["metadata"]["graph_lookup_max_inbound"] == 4.0
    assert payload["metadata"]["graph_lookup_max_xref_count"] == 3.0
    assert payload["metadata"]["graph_lookup_max_query_hits"] == 2.0
    assert payload["metadata"]["graph_lookup_max_symbol_hits"] == 1.0
    assert payload["metadata"]["graph_lookup_max_import_hits"] == 1.0
    assert payload["metadata"]["graph_lookup_max_query_coverage"] == 0.666667


def test_index_stage_package_exports_result_builder() -> None:
    assert exported_build_index_stage_result is build_index_stage_result


def test_build_index_stage_output_derives_targets_with_memory_paths_first() -> None:
    inputs = _base_inputs()
    inputs.pop("targets")
    inputs["memory_paths"] = ["docs/guide.md", "src/auth.py", "docs/guide.md"]

    payload = build_index_stage_output(**inputs)

    assert payload["targets"] == ["docs/guide.md", "src/auth.py"]
    assert payload["candidate_files"][0]["path"] == "src/auth.py"


def test_index_stage_package_exports_output_builder() -> None:
    assert exported_build_index_stage_output is build_index_stage_output
