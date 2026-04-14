from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ace_lite.index_stage.stage_runtime import IndexStageRuntimeDeps

_BOOTSTRAP_HELPER_ATTRS: dict[str, str] = {
    "extract_retrieval_terms_fn": "extract_retrieval_terms",
    "extract_memory_paths_fn": "extract_memory_paths",
    "resolve_retrieval_policy_fn": "resolve_retrieval_policy",
    "resolve_shadow_router_arm_fn": "resolve_shadow_router_arm",
    "resolve_online_bandit_gate_fn": "resolve_online_bandit_gate",
    "build_adaptive_router_payload_fn": "build_adaptive_router_payload",
    "load_retrieval_index_snapshot_fn": "load_retrieval_index_snapshot",
    "resolve_benchmark_candidate_filters_fn": (
        "resolve_benchmark_candidate_filters"
    ),
    "filter_files_map_for_benchmark_fn": "filter_files_map_for_benchmark",
    "resolve_docs_policy_for_benchmark_fn": (
        "resolve_docs_policy_for_benchmark"
    ),
    "resolve_worktree_policy_for_benchmark_fn": (
        "resolve_worktree_policy_for_benchmark"
    ),
    "resolve_embedding_runtime_config_fn": (
        "resolve_embedding_runtime_config"
    ),
    "resolve_repo_relative_path_fn": "resolve_repo_relative_path",
    "default_index_candidate_cache_path_fn": (
        "default_index_candidate_cache_path"
    ),
    "build_index_candidate_cache_key_fn": "build_index_candidate_cache_key",
    "load_cached_index_candidates_checked_fn": (
        "load_cached_index_candidates_checked"
    ),
    "build_disabled_worktree_prior_fn": "_disabled_worktree_prior",
    "refresh_cached_index_candidate_payload_fn": (
        "refresh_cached_index_candidate_payload"
    ),
    "attach_index_candidate_cache_info_fn": (
        "attach_index_candidate_cache_info"
    ),
}

_CANDIDATE_GENERATION_HELPER_ATTRS: dict[str, str] = {
    "gather_initial_candidates_fn": "gather_initial_candidates",
    "build_exact_search_payload_fn": "build_exact_search_payload",
    "select_initial_candidates_fn": "select_initial_candidates",
    "apply_exact_search_boost_fn": "apply_exact_search_boost",
    "collect_parallel_signals_fn": "collect_parallel_signals",
    "apply_candidate_priors_fn": "apply_candidate_priors",
    "collect_docs_fn": "collect_docs_signals",
    "collect_worktree_fn": "collect_worktree_prior",
    "disabled_docs_payload_fn": "_disabled_docs_payload",
    "disabled_worktree_prior_fn": "_disabled_worktree_prior",
    "get_executor_fn": "get_index_parallel_executor",
    "resolve_future_fn": "resolve_parallel_future",
    "run_exact_search_fn": "run_exact_search_ripgrep",
    "score_exact_hits_fn": "score_exact_search_hits",
    "normalize_repo_path_fn": "normalize_repo_path",
    "supported_extensions_fn": "supported_extensions",
}

_POST_GENERATION_HELPER_ATTRS: dict[str, str] = {
    "run_index_candidate_fusion_fn": "run_index_candidate_fusion",
    "apply_benchmark_candidate_filters_fn": (
        "apply_benchmark_candidate_filters"
    ),
    "run_index_chunk_selection_fn": "run_index_chunk_selection",
    "refine_candidate_pool_fn": "refine_candidate_pool",
    "postprocess_candidates_fn": "postprocess_candidates",
    "apply_structural_rerank_fn": "apply_structural_rerank",
    "apply_semantic_candidate_rerank_fn": (
        "apply_semantic_candidate_rerank"
    ),
    "apply_feedback_boost_fn": "apply_feedback_boost",
    "apply_multi_channel_rrf_fusion_fn": "apply_multi_channel_rrf_fusion",
    "merge_candidate_lists_fn": "merge_candidate_lists",
    "resolve_embedding_runtime_config_fn": (
        "resolve_embedding_runtime_config"
    ),
    "build_embedding_stats_fn": "build_embedding_stats",
    "rerank_cross_encoder_with_time_budget_fn": (
        "_rerank_cross_encoder_with_time_budget"
    ),
    "filter_candidate_rows_fn": "filter_candidate_rows",
    "select_index_chunks_fn": "select_index_chunks",
    "apply_chunk_selection_fn": "apply_chunk_selection",
    "rerank_rows_embeddings_with_time_budget_fn": (
        "_rerank_rows_embeddings_with_time_budget"
    ),
    "rerank_rows_cross_encoder_with_time_budget_fn": (
        "_rerank_rows_cross_encoder_with_time_budget"
    ),
}

_FINALIZE_HELPER_ATTRS: dict[str, str] = {
    "build_index_stage_output_fn": "build_index_stage_output",
    "clone_index_candidate_payload_fn": "clone_index_candidate_payload",
    "store_cached_index_candidates_fn": "store_cached_index_candidates",
    "attach_index_candidate_cache_info_fn": (
        "attach_index_candidate_cache_info"
    ),
}


def build_index_stage_runtime_deps(
    *,
    namespace: Mapping[str, Any],
    content_version: str,
) -> IndexStageRuntimeDeps:
    return IndexStageRuntimeDeps(
        content_version=content_version,
        bootstrap_index_runtime_fn=_lookup(namespace, "bootstrap_index_runtime"),
        build_index_stage_execution_state_fn=_lookup(
            namespace, "build_index_stage_execution_state"
        ),
        build_index_retrieval_runtime_fn=_lookup(
            namespace, "build_index_retrieval_runtime"
        ),
        run_index_candidate_generation_fn=_lookup(
            namespace, "run_index_candidate_generation"
        ),
        apply_candidate_generation_runtime_to_state_fn=_lookup(
            namespace, "apply_candidate_generation_runtime_to_state"
        ),
        resolve_repo_relative_path_fn=_lookup(
            namespace, "resolve_repo_relative_path"
        ),
        run_index_post_generation_runtime_fn=_lookup(
            namespace, "run_index_post_generation_runtime"
        ),
        apply_post_generation_runtime_to_state_fn=_lookup(
            namespace, "apply_post_generation_runtime_to_state"
        ),
        finalize_index_stage_output_from_state_fn=_lookup(
            namespace, "finalize_index_stage_output_from_state"
        ),
        normalize_fusion_mode_fn=_lookup(namespace, "normalize_fusion_mode"),
        build_retrieval_runtime_profile_fn=_lookup(
            namespace, "build_retrieval_runtime_profile"
        ),
        bootstrap_helpers=_resolve_helpers(
            namespace=namespace,
            helper_attrs=_BOOTSTRAP_HELPER_ATTRS,
        ),
        candidate_generation_helpers=_resolve_helpers(
            namespace=namespace,
            helper_attrs=_CANDIDATE_GENERATION_HELPER_ATTRS,
        ),
        post_generation_helpers=_resolve_helpers(
            namespace=namespace,
            helper_attrs=_POST_GENERATION_HELPER_ATTRS,
        ),
        finalize_helpers=_resolve_helpers(
            namespace=namespace,
            helper_attrs=_FINALIZE_HELPER_ATTRS,
        ),
    )


def _resolve_helpers(
    *,
    namespace: Mapping[str, Any],
    helper_attrs: Mapping[str, str],
) -> dict[str, Any]:
    return {
        helper_name: _lookup(namespace, attr_name)
        for helper_name, attr_name in helper_attrs.items()
    }


def _lookup(namespace: Mapping[str, Any], attr_name: str) -> Any:
    try:
        return namespace[attr_name]
    except KeyError as exc:
        raise KeyError(
            f"missing index-stage runtime dependency: {attr_name}"
        ) from exc


__all__ = ["build_index_stage_runtime_deps"]
