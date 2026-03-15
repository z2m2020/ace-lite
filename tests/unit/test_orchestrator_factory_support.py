from __future__ import annotations

import pytest

from ace_lite.cli_app.orchestrator_factory_support import (
    PAYLOAD_FAMILY_REGISTRY,
    build_payload_family,
    build_chunking_payload,
    build_retrieval_payload,
    get_payload_family_descriptor,
    iter_payload_family_descriptors,
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
