from __future__ import annotations

from copy import deepcopy

from ace_lite.index_stage import build_index_stage_output as exported_build_index_stage_output
from ace_lite.index_stage import build_index_stage_result as exported_build_index_stage_result
from ace_lite.index_stage.result_payload import build_index_stage_output
from ace_lite.index_stage.result_payload import build_index_stage_result


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
        "graph_lookup_payload": {"enabled": False, "boosted_count": 0, "query_hit_paths": 0},
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
            "enabled": False,
            "applied": False,
            "reason": "disabled",
            "rrf_k": 0,
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
    assert payload["candidate_ranking"]["topological_shield"]["mode"] == "report_only"
    assert payload["chunk_guard"]["mode"] == "report_only"
    assert payload["metadata"]["selection_fingerprint"]
    assert payload["metadata"]["robust_signature_count"] == 1
    assert payload["metadata"]["robust_signature_coverage_ratio"] == 1.0
    assert payload["metadata"]["topological_shield_enabled"] is True
    assert payload["metadata"]["topological_shield_attenuation_total"] == 0.4


def test_build_index_stage_result_fingerprint_is_stable() -> None:
    payload1 = build_index_stage_result(**_base_inputs())
    payload2 = build_index_stage_result(**deepcopy(_base_inputs()))

    assert payload1["metadata"]["selection_fingerprint"] == payload2["metadata"][
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
        "boosted_count": 0,
        "query_hit_paths": 0,
    }
    assert payload["cochange"] == {"neighbors_added": 0}
    assert payload["embeddings"]["runtime_provider"] == "hash_cross"
    assert payload["feedback"]["reason"] == "disabled"
    assert payload["multi_channel_fusion"] == {
        "enabled": False,
        "applied": False,
        "reason": "disabled",
        "rrf_k": 0,
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
    inputs["adaptive_router_payload"]["shadow_confidence"] = 0.84

    payload = build_index_stage_result(**inputs)

    assert payload["adaptive_router"]["shadow_arm_id"] == "doc_intent_hybrid"
    assert payload["candidate_ranking"]["adaptive_router"]["shadow_arm_id"] == "doc_intent_hybrid"
    assert payload["metadata"]["router_shadow_arm_id"] == "doc_intent_hybrid"
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
