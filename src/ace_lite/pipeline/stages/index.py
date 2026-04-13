"""Index stage for the orchestrator pipeline.

This module builds (or refreshes) the repo index and selects file/chunk
candidates for downstream stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ace_lite.exact_search import run_exact_search_ripgrep, score_exact_search_hits
from ace_lite.index_stage import (
    apply_candidate_priors,
    apply_chunk_selection,
    apply_exact_search_boost,
    apply_multi_channel_rrf_fusion,
    apply_semantic_candidate_rerank,
    apply_structural_rerank,
    build_adaptive_router_payload,
    build_disabled_docs_payload,
    build_disabled_worktree_prior,
    build_embedding_stats,
    build_exact_search_payload,
    build_index_stage_output,
    collect_docs_signals,
    collect_parallel_signals,
    collect_worktree_prior,
    extract_memory_paths,
    filter_candidate_rows,
    filter_files_map_for_benchmark,
    gather_initial_candidates,
    get_index_parallel_executor,
    merge_candidate_lists,
    normalize_repo_path,
    postprocess_candidates,
    refine_candidate_pool,
    rerank_cross_encoder_with_time_budget,
    rerank_rows_cross_encoder_with_time_budget,
    rerank_rows_embeddings_with_time_budget,
    resolve_benchmark_candidate_filters,
    resolve_docs_policy_for_benchmark,
    resolve_embedding_runtime_config,
    resolve_online_bandit_gate,
    resolve_parallel_future,
    resolve_repo_relative_path,
    resolve_retrieval_policy,
    resolve_shadow_router_arm,
    resolve_worktree_policy_for_benchmark,
    select_index_chunks,
    select_initial_candidates,
)
from ace_lite.index_stage.benchmark_candidate_runtime import (
    apply_benchmark_candidate_filters,
)
from ace_lite.index_stage.cache import (
    attach_index_candidate_cache_info,
    build_index_candidate_cache_key,
    clone_index_candidate_payload,
    default_index_candidate_cache_path,
    load_cached_index_candidates_checked,
    refresh_cached_index_candidate_payload,
    store_cached_index_candidates,
)
from ace_lite.index_stage.candidate_fusion_runtime import run_index_candidate_fusion
from ace_lite.index_stage.candidate_generation_runtime import (
    run_index_candidate_generation,
)
from ace_lite.index_stage.chunk_runtime import run_index_chunk_selection
from ace_lite.index_stage.config_adapter import (
    build_index_stage_config_from_orchestrator,
)
from ace_lite.index_stage.execution_state import (
    apply_candidate_generation_runtime_to_state,
    apply_post_generation_runtime_to_state,
    build_index_stage_execution_state,
)
from ace_lite.index_stage.feedback import apply_feedback_boost
from ace_lite.index_stage.output_finalize import finalize_index_stage_output_from_state
from ace_lite.index_stage.post_generation_runtime import (
    run_index_post_generation_runtime,
)
from ace_lite.index_stage.retrieval_runtime import build_index_retrieval_runtime
from ace_lite.index_stage.runtime_bootstrap import bootstrap_index_runtime
from ace_lite.index_stage.stage_runtime import (
    IndexStageRuntimeDeps,
    execute_index_stage_runtime,
)
from ace_lite.parsers.languages import supported_extensions
from ace_lite.pipeline.types import StageContext
from ace_lite.rankers import normalize_fusion_mode
from ace_lite.retrieval_shared import (
    build_retrieval_runtime_profile,
    extract_retrieval_terms,
    load_retrieval_index_snapshot,
)

_INDEX_CANDIDATE_CACHE_CONTENT_VERSION = "index-candidates-v1"
_disabled_docs_payload = build_disabled_docs_payload
_disabled_worktree_prior = build_disabled_worktree_prior
_rerank_cross_encoder_with_time_budget = rerank_cross_encoder_with_time_budget
_rerank_rows_cross_encoder_with_time_budget = (
    rerank_rows_cross_encoder_with_time_budget
)
_rerank_rows_embeddings_with_time_budget = rerank_rows_embeddings_with_time_budget


@dataclass(frozen=True, slots=True)
class IndexAdaptiveRouterConfig:
    """Adaptive-router controls for the index stage."""

    enabled: bool
    mode: str
    model_path: str
    state_path: str
    arm_set: str
    online_bandit_enabled: bool
    online_bandit_experiment_enabled: bool


@dataclass(frozen=True, slots=True)
class IndexRetrievalConfig:
    """Retrieval and routing controls for the index stage."""

    retrieval_policy: str
    policy_version: str
    adaptive_router: IndexAdaptiveRouterConfig
    candidate_ranker: str
    top_k_files: int
    min_candidate_score: int
    candidate_relative_threshold: float
    deterministic_refine_enabled: bool
    hybrid_re2_fusion_mode: str
    hybrid_re2_rrf_k: int
    hybrid_re2_shortlist_min: int
    hybrid_re2_shortlist_factor: int
    hybrid_re2_bm25_weight: float
    hybrid_re2_heuristic_weight: float
    hybrid_re2_coverage_weight: float
    hybrid_re2_combined_scale: float
    bm25_k1: float
    bm25_b: float
    bm25_score_scale: float
    bm25_path_prior_factor: float
    bm25_shortlist_min: int
    bm25_shortlist_factor: int
    heur_path_exact: float
    heur_path_contains: float
    heur_module_exact: float
    heur_module_tail: float
    heur_module_contains: float
    heur_symbol_exact: float
    heur_symbol_partial_factor: float
    heur_symbol_partial_cap: float
    heur_import_factor: float
    heur_import_cap: float
    heur_content_symbol_factor: float
    heur_content_import_factor: float
    heur_content_cap: float
    heur_depth_base: float
    heur_depth_factor: float
    exact_search_enabled: bool
    exact_search_time_budget_ms: int
    exact_search_max_paths: int
    multi_channel_rrf_enabled: bool
    multi_channel_rrf_k: int
    multi_channel_rrf_pool_cap: int
    multi_channel_rrf_code_cap: int
    multi_channel_rrf_docs_cap: int
    multi_channel_rrf_memory_cap: int

 
@dataclass(frozen=True, slots=True)
class IndexChunkGuardConfig:
    """Chunk-guard controls for the index stage."""

    enabled: bool
    mode: str
    lambda_penalty: float
    min_pool: int
    max_pool: int
    min_marginal_utility: float
    compatibility_min_overlap: float


@dataclass(frozen=True, slots=True)
class IndexTopologicalShieldConfig:
    """Report-only topological shield controls for the index stage."""

    enabled: bool
    mode: str
    max_attenuation: float
    shared_parent_attenuation: float
    adjacency_attenuation: float


@dataclass(frozen=True, slots=True)
class IndexChunkingConfig:
    """Chunk-selection controls for the index stage."""

    top_k: int
    per_file_limit: int
    token_budget: int
    disclosure: str
    snippet_max_lines: int
    snippet_max_chars: int
    tokenizer_model: str
    diversity_enabled: bool
    diversity_path_penalty: float
    diversity_symbol_family_penalty: float
    diversity_kind_penalty: float
    diversity_locality_penalty: float
    diversity_locality_window: int
    file_prior_weight: float
    path_match: float
    module_match: float
    symbol_exact: float
    symbol_partial: float
    signature_match: float
    reference_factor: float
    reference_cap: float
    topological_shield: IndexTopologicalShieldConfig
    guard: IndexChunkGuardConfig


@dataclass(frozen=True, slots=True)
class IndexStageConfig:
    """Configuration options for the index stage."""

    cache_path: Path
    languages: list[str]
    incremental: bool
    retrieval: IndexRetrievalConfig

    embedding_enabled: bool
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embedding_index_path: str
    embedding_rerank_pool: int
    embedding_lexical_weight: float
    embedding_semantic_weight: float
    embedding_min_similarity: float
    embedding_fail_open: bool

    chunking: IndexChunkingConfig

    # Co-change (temporal coupling)
    cochange_enabled: bool
    cochange_cache_path: str
    cochange_lookback_commits: int
    cochange_half_life_days: float
    cochange_neighbor_cap: int
    cochange_top_neighbors: int
    cochange_boost_weight: float
    cochange_min_neighbor_score: float
    cochange_max_boost: float

    # Selection feedback rerank
    feedback_enabled: bool
    feedback_path: str
    feedback_max_entries: int
    feedback_boost_per_select: float
    feedback_max_boost: float
    feedback_decay_days: float

    # SCIP boosting
    scip_enabled: bool
    scip_index_path: str
    scip_provider: str
    scip_generate_fallback: bool
    scip_base_weight: float

    @classmethod
    def from_orchestrator_config(
        cls,
        *,
        config: Any,
        tokenizer_model: str,
        cochange_neighbor_cap: int,
        cochange_min_neighbor_score: float,
        cochange_max_boost: float,
    ) -> IndexStageConfig:
        """Create an index-stage config from the orchestrator runtime config."""
        return build_index_stage_config_from_orchestrator(
            config=config,
            tokenizer_model=tokenizer_model,
            cochange_neighbor_cap=cochange_neighbor_cap,
            cochange_min_neighbor_score=cochange_min_neighbor_score,
            cochange_max_boost=cochange_max_boost,
            stage_config_cls=cls,
            retrieval_config_cls=IndexRetrievalConfig,
            adaptive_router_config_cls=IndexAdaptiveRouterConfig,
            chunking_config_cls=IndexChunkingConfig,
            topological_shield_config_cls=IndexTopologicalShieldConfig,
            chunk_guard_config_cls=IndexChunkGuardConfig,
        )


def run_index(*, ctx: StageContext, config: IndexStageConfig) -> dict[str, Any]:
    """Run the index stage."""
    deps = IndexStageRuntimeDeps(
        content_version=_INDEX_CANDIDATE_CACHE_CONTENT_VERSION,
        bootstrap_index_runtime_fn=bootstrap_index_runtime,
        build_index_stage_execution_state_fn=build_index_stage_execution_state,
        build_index_retrieval_runtime_fn=build_index_retrieval_runtime,
        run_index_candidate_generation_fn=run_index_candidate_generation,
        apply_candidate_generation_runtime_to_state_fn=(
            apply_candidate_generation_runtime_to_state
        ),
        resolve_repo_relative_path_fn=resolve_repo_relative_path,
        run_index_post_generation_runtime_fn=run_index_post_generation_runtime,
        apply_post_generation_runtime_to_state_fn=(
            apply_post_generation_runtime_to_state
        ),
        finalize_index_stage_output_from_state_fn=(
            finalize_index_stage_output_from_state
        ),
        normalize_fusion_mode_fn=normalize_fusion_mode,
        build_retrieval_runtime_profile_fn=build_retrieval_runtime_profile,
        bootstrap_helpers={
            "extract_retrieval_terms_fn": extract_retrieval_terms,
            "extract_memory_paths_fn": extract_memory_paths,
            "resolve_retrieval_policy_fn": resolve_retrieval_policy,
            "resolve_shadow_router_arm_fn": resolve_shadow_router_arm,
            "resolve_online_bandit_gate_fn": resolve_online_bandit_gate,
            "build_adaptive_router_payload_fn": build_adaptive_router_payload,
            "load_retrieval_index_snapshot_fn": load_retrieval_index_snapshot,
            "resolve_benchmark_candidate_filters_fn": (
                resolve_benchmark_candidate_filters
            ),
            "filter_files_map_for_benchmark_fn": filter_files_map_for_benchmark,
            "resolve_docs_policy_for_benchmark_fn": (
                resolve_docs_policy_for_benchmark
            ),
            "resolve_worktree_policy_for_benchmark_fn": (
                resolve_worktree_policy_for_benchmark
            ),
            "resolve_embedding_runtime_config_fn": (
                resolve_embedding_runtime_config
            ),
            "resolve_repo_relative_path_fn": resolve_repo_relative_path,
            "default_index_candidate_cache_path_fn": (
                default_index_candidate_cache_path
            ),
            "build_index_candidate_cache_key_fn": build_index_candidate_cache_key,
            "load_cached_index_candidates_checked_fn": (
                load_cached_index_candidates_checked
            ),
            "build_disabled_worktree_prior_fn": _disabled_worktree_prior,
            "refresh_cached_index_candidate_payload_fn": (
                refresh_cached_index_candidate_payload
            ),
            "attach_index_candidate_cache_info_fn": (
                attach_index_candidate_cache_info
            ),
        },
        candidate_generation_helpers={
            "gather_initial_candidates_fn": gather_initial_candidates,
            "build_exact_search_payload_fn": build_exact_search_payload,
            "select_initial_candidates_fn": select_initial_candidates,
            "apply_exact_search_boost_fn": apply_exact_search_boost,
            "collect_parallel_signals_fn": collect_parallel_signals,
            "apply_candidate_priors_fn": apply_candidate_priors,
            "collect_docs_fn": collect_docs_signals,
            "collect_worktree_fn": collect_worktree_prior,
            "disabled_docs_payload_fn": _disabled_docs_payload,
            "disabled_worktree_prior_fn": _disabled_worktree_prior,
            "get_executor_fn": get_index_parallel_executor,
            "resolve_future_fn": resolve_parallel_future,
            "run_exact_search_fn": run_exact_search_ripgrep,
            "score_exact_hits_fn": score_exact_search_hits,
            "normalize_repo_path_fn": normalize_repo_path,
            "supported_extensions_fn": supported_extensions,
        },
        post_generation_helpers={
            "run_index_candidate_fusion_fn": run_index_candidate_fusion,
            "apply_benchmark_candidate_filters_fn": (
                apply_benchmark_candidate_filters
            ),
            "run_index_chunk_selection_fn": run_index_chunk_selection,
            "refine_candidate_pool_fn": refine_candidate_pool,
            "postprocess_candidates_fn": postprocess_candidates,
            "apply_structural_rerank_fn": apply_structural_rerank,
            "apply_semantic_candidate_rerank_fn": (
                apply_semantic_candidate_rerank
            ),
            "apply_feedback_boost_fn": apply_feedback_boost,
            "apply_multi_channel_rrf_fusion_fn": apply_multi_channel_rrf_fusion,
            "merge_candidate_lists_fn": merge_candidate_lists,
            "resolve_embedding_runtime_config_fn": (
                resolve_embedding_runtime_config
            ),
            "build_embedding_stats_fn": build_embedding_stats,
            "rerank_cross_encoder_with_time_budget_fn": (
                _rerank_cross_encoder_with_time_budget
            ),
            "filter_candidate_rows_fn": filter_candidate_rows,
            "select_index_chunks_fn": select_index_chunks,
            "apply_chunk_selection_fn": apply_chunk_selection,
            "rerank_rows_embeddings_with_time_budget_fn": (
                _rerank_rows_embeddings_with_time_budget
            ),
            "rerank_rows_cross_encoder_with_time_budget_fn": (
                _rerank_rows_cross_encoder_with_time_budget
            ),
        },
        finalize_helpers={
            "build_index_stage_output_fn": build_index_stage_output,
            "clone_index_candidate_payload_fn": clone_index_candidate_payload,
            "store_cached_index_candidates_fn": store_cached_index_candidates,
            "attach_index_candidate_cache_info_fn": (
                attach_index_candidate_cache_info
            ),
        },
    )
    return execute_index_stage_runtime(ctx=ctx, config=config, deps=deps)


__all__ = ["IndexStageConfig", "run_index"]
