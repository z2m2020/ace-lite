"""Retrieval and chunking payload builders for orchestrator factory wiring."""

from __future__ import annotations

from typing import Any

from ace_lite.cli_app.orchestrator_factory_payload_core import (
    CanonicalFieldSpec,
    build_canonical_payload,
)


def build_retrieval_payload(
    *,
    retrieval_group: dict[str, Any],
    adaptive_router_group: dict[str, Any],
    top_k_files: int,
    min_candidate_score: int,
    candidate_relative_threshold: float,
    candidate_ranker: str,
    exact_search_enabled: bool,
    deterministic_refine_enabled: bool,
    exact_search_time_budget_ms: int,
    exact_search_max_paths: int,
    hybrid_re2_fusion_mode: str,
    hybrid_re2_rrf_k: int,
    hybrid_re2_bm25_weight: float,
    hybrid_re2_heuristic_weight: float,
    hybrid_re2_coverage_weight: float,
    hybrid_re2_combined_scale: float,
    retrieval_policy: str,
    policy_version: str,
    adaptive_router_enabled: bool,
    adaptive_router_mode: str,
    adaptive_router_model_path: str,
    adaptive_router_state_path: str,
    adaptive_router_arm_set: str,
    adaptive_router_online_bandit_enabled: bool,
    adaptive_router_online_bandit_experiment_enabled: bool,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(
                ("top_k_files",),
                top_k_files,
                8,
                ((retrieval_group, (("top_k_files",),)),),
            ),
            CanonicalFieldSpec(
                ("min_candidate_score",),
                min_candidate_score,
                2,
                ((retrieval_group, (("min_candidate_score",),)),),
            ),
            CanonicalFieldSpec(
                ("candidate_relative_threshold",),
                candidate_relative_threshold,
                0.0,
                ((retrieval_group, (("candidate_relative_threshold",),)),),
            ),
            CanonicalFieldSpec(
                ("candidate_ranker",),
                candidate_ranker,
                "heuristic",
                ((retrieval_group, (("candidate_ranker",),)),),
            ),
            CanonicalFieldSpec(
                ("exact_search_enabled",),
                exact_search_enabled,
                False,
                ((retrieval_group, (("exact_search_enabled",),)),),
            ),
            CanonicalFieldSpec(
                ("deterministic_refine_enabled",),
                deterministic_refine_enabled,
                True,
                ((retrieval_group, (("deterministic_refine_enabled",),)),),
            ),
            CanonicalFieldSpec(
                ("exact_search_time_budget_ms",),
                exact_search_time_budget_ms,
                40,
                ((retrieval_group, (("exact_search_time_budget_ms",),)),),
            ),
            CanonicalFieldSpec(
                ("exact_search_max_paths",),
                exact_search_max_paths,
                24,
                ((retrieval_group, (("exact_search_max_paths",),)),),
            ),
            CanonicalFieldSpec(
                ("hybrid_re2_fusion_mode",),
                hybrid_re2_fusion_mode,
                "linear",
                ((retrieval_group, (("hybrid_re2_fusion_mode",),)),),
            ),
            CanonicalFieldSpec(
                ("hybrid_re2_rrf_k",),
                hybrid_re2_rrf_k,
                60,
                ((retrieval_group, (("hybrid_re2_rrf_k",),)),),
            ),
            CanonicalFieldSpec(
                ("hybrid_re2_bm25_weight",),
                hybrid_re2_bm25_weight,
                0.0,
                ((retrieval_group, (("hybrid_re2_bm25_weight",),)),),
            ),
            CanonicalFieldSpec(
                ("hybrid_re2_heuristic_weight",),
                hybrid_re2_heuristic_weight,
                0.0,
                ((retrieval_group, (("hybrid_re2_heuristic_weight",),)),),
            ),
            CanonicalFieldSpec(
                ("hybrid_re2_coverage_weight",),
                hybrid_re2_coverage_weight,
                0.0,
                ((retrieval_group, (("hybrid_re2_coverage_weight",),)),),
            ),
            CanonicalFieldSpec(
                ("hybrid_re2_combined_scale",),
                hybrid_re2_combined_scale,
                0.0,
                ((retrieval_group, (("hybrid_re2_combined_scale",),)),),
            ),
            CanonicalFieldSpec(
                ("retrieval_policy",),
                retrieval_policy,
                "auto",
                ((retrieval_group, (("retrieval_policy",),)),),
            ),
            CanonicalFieldSpec(
                ("policy_version",),
                policy_version,
                "v1",
                ((retrieval_group, (("policy_version",),)),),
            ),
            CanonicalFieldSpec(
                ("adaptive_router_enabled",),
                adaptive_router_enabled,
                False,
                (
                    (adaptive_router_group, (("enabled",),)),
                    (
                        retrieval_group,
                        (("adaptive_router_enabled",), ("adaptive_router", "enabled")),
                    ),
                ),
            ),
            CanonicalFieldSpec(
                ("adaptive_router_mode",),
                adaptive_router_mode,
                "observe",
                (
                    (adaptive_router_group, (("mode",),)),
                    (
                        retrieval_group,
                        (("adaptive_router_mode",), ("adaptive_router", "mode")),
                    ),
                ),
            ),
            CanonicalFieldSpec(
                ("adaptive_router_model_path",),
                adaptive_router_model_path,
                "context-map/router/model.json",
                (
                    (adaptive_router_group, (("model_path",),)),
                    (
                        retrieval_group,
                        (
                            ("adaptive_router_model_path",),
                            ("adaptive_router", "model_path"),
                        ),
                    ),
                ),
            ),
            CanonicalFieldSpec(
                ("adaptive_router_state_path",),
                adaptive_router_state_path,
                "context-map/router/state.json",
                (
                    (adaptive_router_group, (("state_path",),)),
                    (
                        retrieval_group,
                        (
                            ("adaptive_router_state_path",),
                            ("adaptive_router", "state_path"),
                        ),
                    ),
                ),
            ),
            CanonicalFieldSpec(
                ("adaptive_router_arm_set",),
                adaptive_router_arm_set,
                "retrieval_policy_v1",
                (
                    (adaptive_router_group, (("arm_set",),)),
                    (
                        retrieval_group,
                        (
                            ("adaptive_router_arm_set",),
                            ("adaptive_router", "arm_set"),
                        ),
                    ),
                ),
            ),
            CanonicalFieldSpec(
                ("adaptive_router_online_bandit_enabled",),
                adaptive_router_online_bandit_enabled,
                False,
                (
                    (adaptive_router_group, (("online_bandit", "enabled"),)),
                    (
                        retrieval_group,
                        (
                            ("adaptive_router_online_bandit_enabled",),
                            ("adaptive_router", "online_bandit", "enabled"),
                        ),
                    ),
                ),
            ),
            CanonicalFieldSpec(
                ("adaptive_router_online_bandit_experiment_enabled",),
                adaptive_router_online_bandit_experiment_enabled,
                False,
                (
                    (
                        adaptive_router_group,
                        (("online_bandit", "experiment_enabled"),),
                    ),
                    (
                        retrieval_group,
                        (
                            ("adaptive_router_online_bandit_experiment_enabled",),
                            ("adaptive_router", "online_bandit", "experiment_enabled"),
                        ),
                    ),
                ),
            ),
        ),
    )


def build_chunking_payload(
    *,
    chunking_group: dict[str, Any],
    chunk_top_k: int,
    chunk_per_file_limit: int,
    chunk_disclosure: str,
    chunk_signature: bool,
    chunk_snippet_max_lines: int,
    chunk_snippet_max_chars: int,
    chunk_token_budget: int,
    chunk_guard_enabled: bool,
    chunk_guard_mode: str,
    chunk_guard_lambda_penalty: float,
    chunk_guard_min_pool: int,
    chunk_guard_max_pool: int,
    chunk_guard_min_marginal_utility: float,
    chunk_guard_compatibility_min_overlap: float,
    chunk_diversity_enabled: bool,
    chunk_diversity_path_penalty: float,
    chunk_diversity_symbol_family_penalty: float,
    chunk_diversity_kind_penalty: float,
    chunk_diversity_locality_penalty: float,
    chunk_diversity_locality_window: int,
) -> dict[str, Any]:
    return build_canonical_payload(
        field_specs=(
            CanonicalFieldSpec(("top_k",), chunk_top_k, 24, ((chunking_group, (("top_k",),)),)),
            CanonicalFieldSpec(("per_file_limit",), chunk_per_file_limit, 3, ((chunking_group, (("per_file_limit",),)),)),
            CanonicalFieldSpec(("disclosure",), chunk_disclosure, "refs", ((chunking_group, (("disclosure",),)),)),
            CanonicalFieldSpec(("signature",), chunk_signature, False, ((chunking_group, (("signature",),)),)),
            CanonicalFieldSpec(("snippet_max_lines",), chunk_snippet_max_lines, 18, ((chunking_group, (("snippet", "max_lines"), ("snippet_max_lines",))),)),
            CanonicalFieldSpec(("snippet_max_chars",), chunk_snippet_max_chars, 1200, ((chunking_group, (("snippet", "max_chars"), ("snippet_max_chars",))),)),
            CanonicalFieldSpec(("token_budget",), chunk_token_budget, 1200, ((chunking_group, (("token_budget",),)),)),
            CanonicalFieldSpec(
                ("topological_shield", "enabled"),
                False,
                False,
                ((chunking_group, (("topological_shield", "enabled"),)),),
            ),
            CanonicalFieldSpec(
                ("topological_shield", "mode"),
                "off",
                "off",
                ((chunking_group, (("topological_shield", "mode"),)),),
            ),
            CanonicalFieldSpec(
                ("topological_shield", "max_attenuation"),
                0.6,
                0.6,
                ((chunking_group, (("topological_shield", "max_attenuation"),)),),
            ),
            CanonicalFieldSpec(
                ("topological_shield", "shared_parent_attenuation"),
                0.2,
                0.2,
                (
                    (
                        chunking_group,
                        (("topological_shield", "shared_parent_attenuation"),),
                    ),
                ),
            ),
            CanonicalFieldSpec(
                ("topological_shield", "adjacency_attenuation"),
                0.5,
                0.5,
                (
                    (
                        chunking_group,
                        (("topological_shield", "adjacency_attenuation"),),
                    ),
                ),
            ),
            CanonicalFieldSpec(("guard", "enabled"), chunk_guard_enabled, False, ((chunking_group, (("guard", "enabled"), ("guard_enabled",))),)),
            CanonicalFieldSpec(("guard", "mode"), chunk_guard_mode, "off", ((chunking_group, (("guard", "mode"), ("guard_mode",))),)),
            CanonicalFieldSpec(("guard", "lambda_penalty"), chunk_guard_lambda_penalty, 0.8, ((chunking_group, (("guard", "lambda_penalty"), ("guard_lambda_penalty",))),)),
            CanonicalFieldSpec(("guard", "min_pool"), chunk_guard_min_pool, 4, ((chunking_group, (("guard", "min_pool"), ("guard_min_pool",))),)),
            CanonicalFieldSpec(("guard", "max_pool"), chunk_guard_max_pool, 32, ((chunking_group, (("guard", "max_pool"), ("guard_max_pool",))),)),
            CanonicalFieldSpec(("guard", "min_marginal_utility"), chunk_guard_min_marginal_utility, 0.0, ((chunking_group, (("guard", "min_marginal_utility"), ("guard_min_marginal_utility",))),)),
            CanonicalFieldSpec(("guard", "compatibility_min_overlap"), chunk_guard_compatibility_min_overlap, 0.3, ((chunking_group, (("guard", "compatibility_min_overlap"), ("guard_compatibility_min_overlap",))),)),
            CanonicalFieldSpec(("diversity_enabled",), chunk_diversity_enabled, True, ((chunking_group, (("diversity_enabled",),)),)),
            CanonicalFieldSpec(("diversity_path_penalty",), chunk_diversity_path_penalty, 0.20, ((chunking_group, (("diversity_path_penalty",),)),)),
            CanonicalFieldSpec(("diversity_symbol_family_penalty",), chunk_diversity_symbol_family_penalty, 0.30, ((chunking_group, (("diversity_symbol_family_penalty",),)),)),
            CanonicalFieldSpec(("diversity_kind_penalty",), chunk_diversity_kind_penalty, 0.10, ((chunking_group, (("diversity_kind_penalty",),)),)),
            CanonicalFieldSpec(("diversity_locality_penalty",), chunk_diversity_locality_penalty, 0.15, ((chunking_group, (("diversity_locality_penalty",),)),)),
            CanonicalFieldSpec(("diversity_locality_window",), chunk_diversity_locality_window, 24, ((chunking_group, (("diversity_locality_window",),)),)),
        ),
    )


__all__ = [
    "build_chunking_payload",
    "build_retrieval_payload",
]
