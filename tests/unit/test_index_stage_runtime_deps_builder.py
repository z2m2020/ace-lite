from __future__ import annotations

import pytest

from ace_lite.index_stage.stage_runtime_deps_builder import (
    build_index_stage_runtime_deps,
)


def test_build_index_stage_runtime_deps_reads_namespace_contract() -> None:
    namespace = {name: object() for name in _all_dependency_attr_names()}

    deps = build_index_stage_runtime_deps(
        namespace=namespace,
        content_version="index-candidates-v-test",
    )

    assert deps.content_version == "index-candidates-v-test"
    assert deps.bootstrap_index_runtime_fn is namespace["bootstrap_index_runtime"]
    assert deps.build_index_retrieval_runtime_fn is namespace[
        "build_index_retrieval_runtime"
    ]
    assert deps.bootstrap_helpers["extract_retrieval_terms_fn"] is namespace[
        "extract_retrieval_terms"
    ]
    assert deps.bootstrap_helpers["build_disabled_worktree_prior_fn"] is namespace[
        "_disabled_worktree_prior"
    ]
    assert deps.candidate_generation_helpers["disabled_docs_payload_fn"] is namespace[
        "_disabled_docs_payload"
    ]
    assert deps.post_generation_helpers[
        "rerank_rows_cross_encoder_with_time_budget_fn"
    ] is namespace["_rerank_rows_cross_encoder_with_time_budget"]
    assert deps.finalize_helpers["store_cached_index_candidates_fn"] is namespace[
        "store_cached_index_candidates"
    ]


def test_build_index_stage_runtime_deps_raises_for_missing_namespace_symbol() -> None:
    namespace = {name: object() for name in _all_dependency_attr_names()}
    namespace.pop("run_index_post_generation_runtime")

    with pytest.raises(KeyError, match="run_index_post_generation_runtime"):
        build_index_stage_runtime_deps(
            namespace=namespace,
            content_version="index-candidates-v-test",
        )


def _all_dependency_attr_names() -> list[str]:
    return [
        "bootstrap_index_runtime",
        "build_index_stage_execution_state",
        "build_index_retrieval_runtime",
        "run_index_candidate_generation",
        "apply_candidate_generation_runtime_to_state",
        "resolve_repo_relative_path",
        "run_index_post_generation_runtime",
        "apply_post_generation_runtime_to_state",
        "finalize_index_stage_output_from_state",
        "normalize_fusion_mode",
        "build_retrieval_runtime_profile",
        "extract_retrieval_terms",
        "extract_memory_paths",
        "resolve_retrieval_policy",
        "resolve_shadow_router_arm",
        "resolve_online_bandit_gate",
        "build_adaptive_router_payload",
        "load_retrieval_index_snapshot",
        "resolve_benchmark_candidate_filters",
        "filter_files_map_for_benchmark",
        "resolve_docs_policy_for_benchmark",
        "resolve_worktree_policy_for_benchmark",
        "resolve_embedding_runtime_config",
        "default_index_candidate_cache_path",
        "build_index_candidate_cache_key",
        "load_cached_index_candidates_checked",
        "_disabled_worktree_prior",
        "refresh_cached_index_candidate_payload",
        "attach_index_candidate_cache_info",
        "gather_initial_candidates",
        "build_exact_search_payload",
        "select_initial_candidates",
        "apply_exact_search_boost",
        "collect_parallel_signals",
        "apply_candidate_priors",
        "collect_docs_signals",
        "collect_worktree_prior",
        "_disabled_docs_payload",
        "get_index_parallel_executor",
        "resolve_parallel_future",
        "run_exact_search_ripgrep",
        "score_exact_search_hits",
        "normalize_repo_path",
        "supported_extensions",
        "run_index_candidate_fusion",
        "apply_benchmark_candidate_filters",
        "run_index_chunk_selection",
        "refine_candidate_pool",
        "postprocess_candidates",
        "apply_structural_rerank",
        "apply_semantic_candidate_rerank",
        "apply_feedback_boost",
        "apply_multi_channel_rrf_fusion",
        "merge_candidate_lists",
        "build_embedding_stats",
        "_rerank_cross_encoder_with_time_budget",
        "filter_candidate_rows",
        "select_index_chunks",
        "apply_chunk_selection",
        "_rerank_rows_embeddings_with_time_budget",
        "_rerank_rows_cross_encoder_with_time_budget",
        "build_index_stage_output",
        "clone_index_candidate_payload",
        "store_cached_index_candidates",
    ]
