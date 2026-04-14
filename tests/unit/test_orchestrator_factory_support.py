from __future__ import annotations

import pytest

from ace_lite.cli_app.orchestrator_factory_support import (
    PAYLOAD_FAMILY_REGISTRY,
    OrchestratorGroupedConfigs,
    build_chunking_payload,
    build_orchestrator_projection_payload_map,
    build_payload_family,
    build_retrieval_payload,
    get_payload_family_descriptor,
    iter_payload_family_descriptors,
    normalize_orchestrator_group_configs,
)


def _build_projection_payload_map(
    *,
    groups: OrchestratorGroupedConfigs,
) -> dict[str, dict[str, object]]:
    return build_orchestrator_projection_payload_map(
        groups=groups,
        memory_disclosure_mode="compact",
        memory_preview_max_chars=280,
        memory_strategy="hybrid",
        memory_gate_enabled=False,
        memory_gate_mode="auto",
        memory_timeline_enabled=True,
        memory_container_tag=None,
        memory_auto_tag_mode=None,
        memory_profile_enabled=False,
        memory_profile_path="~/.ace-lite/profile.json",
        memory_profile_top_n=4,
        memory_profile_token_budget=160,
        memory_profile_expiry_enabled=True,
        memory_profile_ttl_days=90,
        memory_profile_max_age_days=365,
        memory_feedback_enabled=False,
        memory_feedback_path="~/.ace-lite/profile.json",
        memory_feedback_max_entries=512,
        memory_feedback_boost_per_select=0.15,
        memory_feedback_max_boost=0.6,
        memory_feedback_decay_days=60.0,
        memory_long_term_enabled=False,
        memory_long_term_path="context-map/long_term_memory.db",
        memory_long_term_top_n=4,
        memory_long_term_token_budget=192,
        memory_long_term_write_enabled=False,
        memory_long_term_as_of_enabled=True,
        memory_capture_enabled=False,
        memory_capture_notes_path="context-map/memory_notes.jsonl",
        memory_capture_min_query_length=24,
        memory_capture_keywords=None,
        memory_notes_enabled=False,
        memory_notes_path="context-map/memory_notes.jsonl",
        memory_notes_limit=8,
        memory_notes_mode="supplement",
        memory_notes_expiry_enabled=True,
        memory_notes_ttl_days=90,
        memory_notes_max_age_days=365,
        memory_postprocess_enabled=False,
        memory_postprocess_noise_filter_enabled=True,
        memory_postprocess_length_norm_anchor_chars=500,
        memory_postprocess_time_decay_half_life_days=0.0,
        memory_postprocess_hard_min_score=0.0,
        memory_postprocess_diversity_enabled=True,
        memory_postprocess_diversity_similarity_threshold=0.9,
        skills_dir="skills",
        precomputed_routing_enabled=True,
        top_k_files=8,
        index_languages=None,
        index_cache_path="context-map/index.json",
        index_incremental=True,
        conventions_files=None,
        min_candidate_score=2,
        candidate_relative_threshold=0.0,
        candidate_ranker="heuristic",
        exact_search_enabled=False,
        deterministic_refine_enabled=True,
        exact_search_time_budget_ms=40,
        exact_search_max_paths=24,
        hybrid_re2_fusion_mode="linear",
        hybrid_re2_rrf_k=60,
        hybrid_re2_bm25_weight=0.0,
        hybrid_re2_heuristic_weight=0.0,
        hybrid_re2_coverage_weight=0.0,
        hybrid_re2_combined_scale=0.0,
        retrieval_policy="auto",
        policy_version="v1",
        adaptive_router_enabled=False,
        adaptive_router_mode="observe",
        adaptive_router_model_path="context-map/router/model.json",
        adaptive_router_state_path="context-map/router/state.json",
        adaptive_router_arm_set="retrieval_policy_v1",
        adaptive_router_online_bandit_enabled=False,
        adaptive_router_online_bandit_experiment_enabled=False,
        embedding_enabled=False,
        embedding_provider="hash",
        embedding_model="hash-v1",
        embedding_dimension=256,
        embedding_index_path="context-map/embeddings/index.json",
        embedding_rerank_pool=24,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embedding_fail_open=True,
        cochange_enabled=True,
        cochange_cache_path="context-map/cochange.json",
        cochange_lookback_commits=400,
        cochange_half_life_days=60.0,
        cochange_top_neighbors=12,
        cochange_boost_weight=1.5,
        junit_xml=None,
        coverage_json=None,
        sbfl_json=None,
        sbfl_metric="ochiai",
        scip_enabled=False,
        scip_index_path="context-map/scip/index.json",
        scip_provider="auto",
        scip_generate_fallback=True,
        repomap_enabled=True,
        repomap_top_k=8,
        repomap_neighbor_limit=20,
        repomap_budget_tokens=800,
        repomap_ranking_profile="graph",
        repomap_signal_weights=None,
        lsp_enabled=False,
        lsp_top_n=5,
        lsp_commands=None,
        lsp_xref_enabled=False,
        lsp_xref_top_n=3,
        lsp_time_budget_ms=1500,
        lsp_xref_commands=None,
        plugins_enabled=True,
        remote_slot_policy_mode="strict",
        remote_slot_allowlist=None,
        chunk_top_k=24,
        chunk_per_file_limit=3,
        chunk_disclosure="refs",
        chunk_signature=False,
        chunk_snippet_max_lines=18,
        chunk_snippet_max_chars=1200,
        chunk_token_budget=1200,
        chunk_guard_enabled=False,
        chunk_guard_mode="off",
        chunk_guard_lambda_penalty=0.8,
        chunk_guard_min_pool=4,
        chunk_guard_max_pool=32,
        chunk_guard_min_marginal_utility=0.0,
        chunk_guard_compatibility_min_overlap=0.3,
        chunk_diversity_enabled=True,
        chunk_diversity_path_penalty=0.20,
        chunk_diversity_symbol_family_penalty=0.30,
        chunk_diversity_kind_penalty=0.10,
        chunk_diversity_locality_penalty=0.15,
        chunk_diversity_locality_window=24,
        tokenizer_model="gpt-4o-mini",
        trace_export_enabled=False,
        trace_export_path="context-map/traces/stage_spans.jsonl",
        trace_otlp_enabled=False,
        trace_otlp_endpoint="",
        trace_otlp_timeout_seconds=1.5,
        plan_replay_cache_enabled=False,
        plan_replay_cache_path="context-map/plan-replay/cache.json",
    )


def test_build_retrieval_payload_prefers_adaptive_router_group_over_nested_retrieval() -> None:
    payload = build_retrieval_payload(
        retrieval_group={
            "top_k_files": 5,
            "candidate_ranker": "bm25_lite",
            "adaptive_router": {
                "enabled": False,
                "mode": "observe",
                "model_path": "context-map/router/nested-model.json",
                "state_path": "context-map/router/nested-state.json",
                "arm_set": "retrieval_policy_nested",
                "online_bandit": {
                    "enabled": False,
                    "experiment_enabled": False,
                },
            },
        },
        adaptive_router_group={
            "enabled": True,
            "mode": "shadow",
            "model_path": "context-map/router/group-model.json",
            "state_path": "context-map/router/group-state.json",
            "arm_set": "retrieval_policy_group",
            "online_bandit": {
                "enabled": True,
                "experiment_enabled": True,
            },
        },
        top_k_files=8,
        min_candidate_score=2,
        candidate_relative_threshold=0.0,
        candidate_ranker="heuristic",
        exact_search_enabled=False,
        deterministic_refine_enabled=True,
        exact_search_time_budget_ms=40,
        exact_search_max_paths=24,
        hybrid_re2_fusion_mode="linear",
        hybrid_re2_rrf_k=60,
        hybrid_re2_bm25_weight=0.0,
        hybrid_re2_heuristic_weight=0.0,
        hybrid_re2_coverage_weight=0.0,
        hybrid_re2_combined_scale=0.0,
        retrieval_policy="auto",
        policy_version="v1",
        adaptive_router_enabled=False,
        adaptive_router_mode="observe",
        adaptive_router_model_path="context-map/router/model.json",
        adaptive_router_state_path="context-map/router/state.json",
        adaptive_router_arm_set="retrieval_policy_v1",
        adaptive_router_online_bandit_enabled=False,
        adaptive_router_online_bandit_experiment_enabled=False,
    )

    assert payload["top_k_files"] == 5
    assert payload["candidate_ranker"] == "bm25_lite"
    assert payload["adaptive_router_enabled"] is True
    assert payload["adaptive_router_mode"] == "shadow"
    assert payload["adaptive_router_model_path"] == "context-map/router/group-model.json"
    assert payload["adaptive_router_state_path"] == "context-map/router/group-state.json"
    assert payload["adaptive_router_arm_set"] == "retrieval_policy_group"
    assert payload["adaptive_router_online_bandit_enabled"] is True
    assert payload["adaptive_router_online_bandit_experiment_enabled"] is True


def test_build_retrieval_payload_explicit_values_override_grouped_defaults() -> None:
    payload = build_retrieval_payload(
        retrieval_group={
            "top_k_files": 5,
            "candidate_ranker": "bm25_lite",
            "retrieval_policy": "feature",
            "policy_version": "v2",
        },
        adaptive_router_group={
            "enabled": False,
            "mode": "shadow",
            "arm_set": "retrieval_policy_shadow",
        },
        top_k_files=7,
        min_candidate_score=2,
        candidate_relative_threshold=0.0,
        candidate_ranker="hybrid_re2",
        exact_search_enabled=False,
        deterministic_refine_enabled=True,
        exact_search_time_budget_ms=40,
        exact_search_max_paths=24,
        hybrid_re2_fusion_mode="linear",
        hybrid_re2_rrf_k=60,
        hybrid_re2_bm25_weight=0.0,
        hybrid_re2_heuristic_weight=0.0,
        hybrid_re2_coverage_weight=0.0,
        hybrid_re2_combined_scale=0.0,
        retrieval_policy="general",
        policy_version="v9",
        adaptive_router_enabled=True,
        adaptive_router_mode="enforce",
        adaptive_router_model_path="context-map/router/override-model.json",
        adaptive_router_state_path="context-map/router/override-state.json",
        adaptive_router_arm_set="retrieval_policy_enforce",
        adaptive_router_online_bandit_enabled=False,
        adaptive_router_online_bandit_experiment_enabled=False,
    )

    assert payload["top_k_files"] == 7
    assert payload["candidate_ranker"] == "hybrid_re2"
    assert payload["retrieval_policy"] == "general"
    assert payload["policy_version"] == "v9"
    assert payload["adaptive_router_enabled"] is True
    assert payload["adaptive_router_mode"] == "enforce"
    assert payload["adaptive_router_model_path"] == "context-map/router/override-model.json"
    assert payload["adaptive_router_state_path"] == "context-map/router/override-state.json"
    assert payload["adaptive_router_arm_set"] == "retrieval_policy_enforce"


def test_build_retrieval_payload_reads_nested_online_bandit_from_retrieval_group() -> None:
    payload = build_retrieval_payload(
        retrieval_group={
            "adaptive_router": {
                "online_bandit": {
                    "enabled": True,
                    "experiment_enabled": True,
                },
            },
        },
        adaptive_router_group={},
        top_k_files=8,
        min_candidate_score=2,
        candidate_relative_threshold=0.0,
        candidate_ranker="heuristic",
        exact_search_enabled=False,
        deterministic_refine_enabled=True,
        exact_search_time_budget_ms=40,
        exact_search_max_paths=24,
        hybrid_re2_fusion_mode="linear",
        hybrid_re2_rrf_k=60,
        hybrid_re2_bm25_weight=0.0,
        hybrid_re2_heuristic_weight=0.0,
        hybrid_re2_coverage_weight=0.0,
        hybrid_re2_combined_scale=0.0,
        retrieval_policy="auto",
        policy_version="v1",
        adaptive_router_enabled=False,
        adaptive_router_mode="observe",
        adaptive_router_model_path="context-map/router/model.json",
        adaptive_router_state_path="context-map/router/state.json",
        adaptive_router_arm_set="retrieval_policy_v1",
        adaptive_router_online_bandit_enabled=False,
        adaptive_router_online_bandit_experiment_enabled=False,
    )

    assert payload["adaptive_router_online_bandit_enabled"] is True
    assert payload["adaptive_router_online_bandit_experiment_enabled"] is True


def test_build_chunking_payload_normalizes_nested_and_flat_compat_paths() -> None:
    payload = build_chunking_payload(
        chunking_group={
            "top_k": 5,
            "per_file_limit": 2,
            "disclosure": "signature",
            "signature": True,
            "snippet": {
                "max_lines": 9,
                "max_chars": 420,
            },
            "topological_shield": {
                "enabled": True,
                "mode": "report_only",
                "max_attenuation": 0.4,
                "shared_parent_attenuation": 0.1,
                "adjacency_attenuation": 0.3,
            },
            "guard_mode": "report_only",
            "guard_compatibility_min_overlap": 0.45,
        },
        chunk_top_k=24,
        chunk_per_file_limit=3,
        chunk_disclosure="refs",
        chunk_signature=False,
        chunk_snippet_max_lines=18,
        chunk_snippet_max_chars=1200,
        chunk_token_budget=1200,
        chunk_guard_enabled=False,
        chunk_guard_mode="off",
        chunk_guard_lambda_penalty=0.8,
        chunk_guard_min_pool=4,
        chunk_guard_max_pool=32,
        chunk_guard_min_marginal_utility=0.0,
        chunk_guard_compatibility_min_overlap=0.3,
        chunk_diversity_enabled=True,
        chunk_diversity_path_penalty=0.20,
        chunk_diversity_symbol_family_penalty=0.30,
        chunk_diversity_kind_penalty=0.10,
        chunk_diversity_locality_penalty=0.15,
        chunk_diversity_locality_window=24,
    )

    assert payload["top_k"] == 5
    assert payload["per_file_limit"] == 2
    assert payload["disclosure"] == "signature"
    assert payload["signature"] is True
    assert payload["snippet_max_lines"] == 9
    assert payload["snippet_max_chars"] == 420
    assert payload["topological_shield"] == {
        "enabled": True,
        "mode": "report_only",
        "max_attenuation": 0.4,
        "shared_parent_attenuation": 0.1,
        "adjacency_attenuation": 0.3,
    }
    assert payload["guard"]["mode"] == "report_only"
    assert payload["guard"]["compatibility_min_overlap"] == 0.45
    assert "guard_mode" not in payload
    assert "guard_compatibility_min_overlap" not in payload
    assert "topological_shield_mode" not in payload


def test_build_chunking_payload_reads_legacy_flat_snippet_aliases() -> None:
    payload = build_chunking_payload(
        chunking_group={
            "snippet_max_lines": 11,
            "snippet_max_chars": 500,
        },
        chunk_top_k=24,
        chunk_per_file_limit=3,
        chunk_disclosure="refs",
        chunk_signature=False,
        chunk_snippet_max_lines=18,
        chunk_snippet_max_chars=1200,
        chunk_token_budget=1200,
        chunk_guard_enabled=False,
        chunk_guard_mode="off",
        chunk_guard_lambda_penalty=0.8,
        chunk_guard_min_pool=4,
        chunk_guard_max_pool=32,
        chunk_guard_min_marginal_utility=0.0,
        chunk_guard_compatibility_min_overlap=0.3,
        chunk_diversity_enabled=True,
        chunk_diversity_path_penalty=0.20,
        chunk_diversity_symbol_family_penalty=0.30,
        chunk_diversity_kind_penalty=0.10,
        chunk_diversity_locality_penalty=0.15,
        chunk_diversity_locality_window=24,
    )

    assert payload["snippet_max_lines"] == 11
    assert payload["snippet_max_chars"] == 500


def test_build_chunking_payload_explicit_values_override_grouped_defaults() -> None:
    payload = build_chunking_payload(
        chunking_group={
            "top_k": 5,
            "snippet": {
                "max_lines": 9,
                "max_chars": 420,
            },
            "guard": {
                "mode": "report_only",
            },
        },
        chunk_top_k=7,
        chunk_per_file_limit=3,
        chunk_disclosure="refs",
        chunk_signature=False,
        chunk_snippet_max_lines=11,
        chunk_snippet_max_chars=333,
        chunk_token_budget=1200,
        chunk_guard_enabled=False,
        chunk_guard_mode="enforce",
        chunk_guard_lambda_penalty=0.8,
        chunk_guard_min_pool=4,
        chunk_guard_max_pool=32,
        chunk_guard_min_marginal_utility=0.0,
        chunk_guard_compatibility_min_overlap=0.3,
        chunk_diversity_enabled=True,
        chunk_diversity_path_penalty=0.20,
        chunk_diversity_symbol_family_penalty=0.30,
        chunk_diversity_kind_penalty=0.10,
        chunk_diversity_locality_penalty=0.15,
        chunk_diversity_locality_window=24,
    )

    assert payload["top_k"] == 7
    assert payload["snippet_max_lines"] == 11
    assert payload["snippet_max_chars"] == 333
    assert payload["guard"]["mode"] == "enforce"


def test_payload_family_registry_exposes_supported_builder_families() -> None:
    families = {descriptor.family for descriptor in iter_payload_family_descriptors()}

    assert families == {
        "chunking",
        "cochange",
        "embeddings",
        "index",
        "lsp",
        "memory",
        "plan_replay_cache",
        "plugins",
        "repomap",
        "retrieval",
        "scip",
        "skills",
        "tests",
        "tokenizer",
        "trace",
    }
    assert get_payload_family_descriptor("retrieval").grouped_inputs == (
        "retrieval_group",
        "adaptive_router_group",
    )
    assert set(PAYLOAD_FAMILY_REGISTRY) == families


def test_build_orchestrator_projection_payload_map_uses_normalized_groups() -> None:
    groups = normalize_orchestrator_group_configs(
        skills_config={"dir": "custom-skills", "precomputed_routing_enabled": False},
        index_config={"languages": ["python", "go"], "incremental": False},
        retrieval_config={"top_k_files": 5, "candidate_ranker": "bm25_lite"},
        adaptive_router_config={"enabled": True, "mode": "shadow"},
    )

    payload_map = _build_projection_payload_map(groups=groups)

    assert payload_map["skills"]["dir"] == "custom-skills"
    assert payload_map["skills"]["precomputed_routing_enabled"] is False
    assert payload_map["index"]["languages"] == ["python", "go"]
    assert payload_map["index"]["incremental"] is False
    assert payload_map["retrieval"]["top_k_files"] == 5
    assert payload_map["retrieval"]["candidate_ranker"] == "bm25_lite"
    assert payload_map["retrieval"]["adaptive_router_enabled"] is True
    assert payload_map["retrieval"]["adaptive_router_mode"] == "shadow"


def test_build_payload_family_dispatches_to_registered_builder() -> None:
    payload = build_payload_family(
        "retrieval",
        retrieval_group={"top_k_files": 5, "candidate_ranker": "bm25_lite"},
        adaptive_router_group={},
        top_k_files=8,
        min_candidate_score=2,
        candidate_relative_threshold=0.0,
        candidate_ranker="heuristic",
        exact_search_enabled=False,
        deterministic_refine_enabled=True,
        exact_search_time_budget_ms=40,
        exact_search_max_paths=24,
        hybrid_re2_fusion_mode="linear",
        hybrid_re2_rrf_k=60,
        hybrid_re2_bm25_weight=0.0,
        hybrid_re2_heuristic_weight=0.0,
        hybrid_re2_coverage_weight=0.0,
        hybrid_re2_combined_scale=0.0,
        retrieval_policy="auto",
        policy_version="v1",
        adaptive_router_enabled=False,
        adaptive_router_mode="observe",
        adaptive_router_model_path="context-map/router/model.json",
        adaptive_router_state_path="context-map/router/state.json",
        adaptive_router_arm_set="retrieval_policy_v1",
        adaptive_router_online_bandit_enabled=False,
        adaptive_router_online_bandit_experiment_enabled=False,
    )

    assert payload["top_k_files"] == 5
    assert payload["candidate_ranker"] == "bm25_lite"


def test_get_payload_family_descriptor_rejects_unknown_family() -> None:
    with pytest.raises(KeyError, match="Unknown payload family: unknown"):
        get_payload_family_descriptor("unknown")
