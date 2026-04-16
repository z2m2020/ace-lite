"""Index-stage helper modules.

This package contains pure helpers used by the `index` pipeline stage:
- term extraction
- memory-path extraction
- retrieval policy resolution
- optional boost signals (exact-search, co-change, SCIP)

Exports are resolved lazily so packages that only need a narrow helper
(`ace_lite.index_stage.terms`, for example) do not pay the import cost or
trigger unrelated dependency cycles during package initialization.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "apply_candidate_priors": ("ace_lite.index_stage.priors", "apply_candidate_priors"),
    "apply_cochange_neighbors": ("ace_lite.index_stage.cochange", "apply_cochange_neighbors"),
    "apply_exact_search_boost": (
        "ace_lite.index_stage.exact_search_boost",
        "apply_exact_search_boost",
    ),
    "apply_chunk_selection": (
        "ace_lite.index_stage.chunk_selection",
        "apply_chunk_selection",
    ),
    "filter_candidate_rows": (
        "ace_lite.index_stage.benchmark_filters",
        "filter_candidate_rows",
    ),
    "filter_files_map_for_benchmark": (
        "ace_lite.index_stage.benchmark_filters",
        "filter_files_map_for_benchmark",
    ),
    "apply_graph_lookup_rerank": (
        "ace_lite.index_stage.graph_lookup",
        "apply_graph_lookup_rerank",
    ),
    "apply_scip_boost": ("ace_lite.index_stage.scip_boost", "apply_scip_boost"),
    "build_exact_search_payload": (
        "ace_lite.index_stage.exact_search_boost",
        "build_exact_search_payload",
    ),
    "build_adaptive_router_payload": (
        "ace_lite.index_stage.adaptive_router",
        "build_adaptive_router_payload",
    ),
    "build_embedding_stats": (
        "ace_lite.index_stage.embedding_runtime",
        "build_embedding_stats",
    ),
    "collect_docs_signals": ("ace_lite.index_stage.docs_channel", "collect_docs_signals"),
    "collect_parallel_signals": (
        "ace_lite.index_stage.parallel_signals",
        "collect_parallel_signals",
    ),
    "build_disabled_docs_payload": (
        "ace_lite.index_stage.parallel_runtime",
        "build_disabled_docs_payload",
    ),
    "build_disabled_worktree_prior": (
        "ace_lite.index_stage.parallel_runtime",
        "build_disabled_worktree_prior",
    ),
    "collect_worktree_prior": ("ace_lite.index_stage.priors", "collect_worktree_prior"),
    "extract_memory_paths": ("ace_lite.index_stage.memory_paths", "extract_memory_paths"),
    "extract_terms": ("ace_lite.index_stage.terms", "extract_terms"),
    "EmbeddingRuntimeConfig": (
        "ace_lite.index_stage.embedding_runtime",
        "EmbeddingRuntimeConfig",
    ),
    "postprocess_candidates": (
        "ace_lite.index_stage.candidate_postprocess",
        "postprocess_candidates",
    ),
    "merge_candidate_lists": (
        "ace_lite.index_stage.candidate_postprocess",
        "merge_candidate_lists",
    ),
    "get_index_parallel_executor": (
        "ace_lite.index_stage.parallel_runtime",
        "get_index_parallel_executor",
    ),
    "apply_semantic_candidate_rerank": (
        "ace_lite.index_stage.semantic_candidate_rerank",
        "apply_semantic_candidate_rerank",
    ),
    "resolve_online_bandit_gate": (
        "ace_lite.index_stage.policy",
        "resolve_online_bandit_gate",
    ),
    "resolve_embedding_runtime_config": (
        "ace_lite.index_stage.embedding_runtime",
        "resolve_embedding_runtime_config",
    ),
    "rerank_cross_encoder_with_time_budget": (
        "ace_lite.index_stage.rerank_timeouts",
        "rerank_cross_encoder_with_time_budget",
    ),
    "rerank_embeddings_with_time_budget": (
        "ace_lite.index_stage.rerank_timeouts",
        "rerank_embeddings_with_time_budget",
    ),
    "rerank_rows_cross_encoder_with_time_budget": (
        "ace_lite.index_stage.rerank_timeouts",
        "rerank_rows_cross_encoder_with_time_budget",
    ),
    "rerank_rows_embeddings_with_time_budget": (
        "ace_lite.index_stage.rerank_timeouts",
        "rerank_rows_embeddings_with_time_budget",
    ),
    "normalize_repo_path": (
        "ace_lite.index_stage.repo_paths",
        "normalize_repo_path",
    ),
    "resolve_repo_relative_path": (
        "ace_lite.index_stage.repo_paths",
        "resolve_repo_relative_path",
    ),
    "resolve_parallel_future": (
        "ace_lite.index_stage.parallel_runtime",
        "resolve_parallel_future",
    ),
    "resolve_benchmark_candidate_filters": (
        "ace_lite.index_stage.benchmark_filters",
        "resolve_benchmark_candidate_filters",
    ),
    "resolve_docs_policy_for_benchmark": (
        "ace_lite.index_stage.benchmark_filters",
        "resolve_docs_policy_for_benchmark",
    ),
    "resolve_retrieval_policy": ("ace_lite.index_stage.policy", "resolve_retrieval_policy"),
    "resolve_worktree_policy_for_benchmark": (
        "ace_lite.index_stage.benchmark_filters",
        "resolve_worktree_policy_for_benchmark",
    ),
    "resolve_shadow_router_arm": ("ace_lite.index_stage.policy", "resolve_shadow_router_arm"),
    "select_initial_candidates": (
        "ace_lite.index_stage.candidate_selection",
        "select_initial_candidates",
    ),
    "apply_structural_rerank": (
        "ace_lite.index_stage.structural_rerank",
        "apply_structural_rerank",
    ),
    "build_index_stage_result": (
        "ace_lite.index_stage.result_payload",
        "build_index_stage_result",
    ),
    "build_index_stage_output": (
        "ace_lite.index_stage.result_payload",
        "build_index_stage_output",
    ),
    "apply_multi_channel_rrf_fusion": (
        "ace_lite.index_stage.candidate_fusion",
        "apply_multi_channel_rrf_fusion",
    ),
    "CandidateFusionDeps": (
        "ace_lite.index_stage.candidate_fusion",
        "CandidateFusionDeps",
    ),
    "ChunkSelectionDeps": (
        "ace_lite.index_stage.chunk_pipeline",
        "ChunkSelectionDeps",
    ),
    "ChunkSelectionRuntimeConfig": (
        "ace_lite.index_stage.chunk_pipeline",
        "ChunkSelectionRuntimeConfig",
    ),
    "gather_initial_candidates": (
        "ace_lite.index_stage.candidate_generation",
        "gather_initial_candidates",
    ),
    "InitialCandidateGenerationDeps": (
        "ace_lite.index_stage.candidate_generation",
        "InitialCandidateGenerationDeps",
    ),
    "refine_candidate_pool": (
        "ace_lite.index_stage.candidate_fusion",
        "refine_candidate_pool",
    ),
    "select_index_chunks": (
        "ace_lite.index_stage.chunk_pipeline",
        "select_index_chunks",
    ),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_EXPORTS.keys()))
