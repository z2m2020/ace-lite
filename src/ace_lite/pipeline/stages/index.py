"""Index stage for the orchestrator pipeline.

This module builds (or refreshes) the repo index and selects file/chunk
candidates for downstream stages.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.embeddings import (
    CrossEncoderProvider,
    EmbeddingIndexStats,
    EmbeddingProvider,
)
from ace_lite.exact_search import run_exact_search_ripgrep, score_exact_search_hits
from ace_lite.index_stage import (
    apply_candidate_priors,
    apply_chunk_selection,
    apply_multi_channel_rrf_fusion,
    apply_exact_search_boost,
    apply_semantic_candidate_rerank,
    apply_structural_rerank,
    build_adaptive_router_payload,
    build_disabled_docs_payload,
    build_disabled_worktree_prior,
    build_embedding_stats,
    build_index_stage_output,
    build_exact_search_payload,
    collect_docs_signals,
    collect_parallel_signals,
    collect_worktree_prior,
    EmbeddingRuntimeConfig,
    extract_memory_paths,
    filter_candidate_rows,
    filter_files_map_for_benchmark,
    gather_initial_candidates,
    merge_candidate_lists,
    get_index_parallel_executor,
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
from ace_lite.index_stage.benchmark_candidate_runtime import (
    apply_benchmark_candidate_filters,
)
from ace_lite.index_stage.candidate_generation_runtime import (
    run_index_candidate_generation,
)
from ace_lite.index_stage.chunk_runtime import run_index_chunk_selection
from ace_lite.index_stage.config_adapter import (
    build_index_stage_config_from_orchestrator,
)
from ace_lite.index_stage.feedback import apply_feedback_boost
from ace_lite.index_stage.execution_state import (
    apply_candidate_generation_runtime_to_state,
    apply_post_generation_runtime_to_state,
    build_index_stage_execution_state,
)
from ace_lite.index_stage.output_finalize import finalize_index_stage_output
from ace_lite.index_stage.output_finalize import finalize_index_stage_output_from_state
from ace_lite.index_stage.post_generation_runtime import (
    run_index_post_generation_runtime,
)
from ace_lite.index_stage.retrieval_runtime import build_index_retrieval_runtime
from ace_lite.index_stage.runtime_bootstrap import bootstrap_index_runtime
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
    hybrid_re2_bm25_weight: float
    hybrid_re2_heuristic_weight: float
    hybrid_re2_coverage_weight: float
    hybrid_re2_combined_scale: float
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
    timings_ms: dict[str, float] = {}
    retrieval_cfg = config.retrieval
    chunking_cfg = config.chunking
    topological_shield_cfg = chunking_cfg.topological_shield
    chunk_guard_cfg = chunking_cfg.guard

    def mark_timing(label: str, started_at: float) -> None:
        timings_ms[label] = round((perf_counter() - started_at) * 1000.0, 3)

    bootstrap = bootstrap_index_runtime(
        ctx=ctx,
        config=config,
        content_version=_INDEX_CANDIDATE_CACHE_CONTENT_VERSION,
        timings_ms=timings_ms,
        mark_timing=mark_timing,
        extract_retrieval_terms_fn=extract_retrieval_terms,
        extract_memory_paths_fn=extract_memory_paths,
        resolve_retrieval_policy_fn=resolve_retrieval_policy,
        resolve_shadow_router_arm_fn=resolve_shadow_router_arm,
        resolve_online_bandit_gate_fn=resolve_online_bandit_gate,
        build_adaptive_router_payload_fn=build_adaptive_router_payload,
        load_retrieval_index_snapshot_fn=load_retrieval_index_snapshot,
        resolve_benchmark_candidate_filters_fn=resolve_benchmark_candidate_filters,
        filter_files_map_for_benchmark_fn=filter_files_map_for_benchmark,
        resolve_docs_policy_for_benchmark_fn=resolve_docs_policy_for_benchmark,
        resolve_worktree_policy_for_benchmark_fn=resolve_worktree_policy_for_benchmark,
        resolve_embedding_runtime_config_fn=resolve_embedding_runtime_config,
        resolve_repo_relative_path_fn=resolve_repo_relative_path,
        default_index_candidate_cache_path_fn=default_index_candidate_cache_path,
        build_index_candidate_cache_key_fn=build_index_candidate_cache_key,
        load_cached_index_candidates_checked_fn=load_cached_index_candidates_checked,
        build_disabled_worktree_prior_fn=_disabled_worktree_prior,
        refresh_cached_index_candidate_payload_fn=refresh_cached_index_candidate_payload,
        attach_index_candidate_cache_info_fn=attach_index_candidate_cache_info,
    )
    if bootstrap.cache_hit_payload is not None:
        return bootstrap.cache_hit_payload

    state = build_index_stage_execution_state(bootstrap=bootstrap)

    retrieval_runtime = build_index_retrieval_runtime(
        retrieval_cfg=retrieval_cfg,
        policy=state.policy,
        index_hash=state.index_hash,
        terms=state.terms,
        effective_files_map=state.effective_files_map,
        normalize_fusion_mode_fn=normalize_fusion_mode,
        build_retrieval_runtime_profile_fn=build_retrieval_runtime_profile,
    )
    fusion_mode = retrieval_runtime.fusion_mode
    hybrid_weights = retrieval_runtime.hybrid_weights
    runtime_profile = retrieval_runtime.runtime_profile
    parallel_requested = retrieval_runtime.parallel_requested
    parallel_time_budget_ms = retrieval_runtime.parallel_time_budget_ms
    rank_candidates = retrieval_runtime.rank_candidates

    candidate_generation_runtime = run_index_candidate_generation(
        root=ctx.root,
        query=ctx.query,
        terms=state.terms,
        files_map=state.effective_files_map,
        corpus_size=state.effective_corpus_size,
        runtime_profile=runtime_profile,
        top_k_files=int(retrieval_cfg.top_k_files),
        exact_search_enabled=bool(retrieval_cfg.exact_search_enabled),
        exact_search_time_budget_ms=int(retrieval_cfg.exact_search_time_budget_ms),
        exact_search_max_paths=int(retrieval_cfg.exact_search_max_paths),
        languages=list(config.languages),
        docs_policy_enabled=state.docs_policy_enabled,
        worktree_prior_enabled=state.worktree_prior_enabled,
        cochange_enabled=bool(config.cochange_enabled),
        docs_intent_weight=float(state.policy.get("docs_weight", 1.0) or 1.0),
        parallel_requested=parallel_requested,
        parallel_time_budget_ms=parallel_time_budget_ms,
        policy=state.policy,
        gather_initial_candidates_fn=gather_initial_candidates,
        build_exact_search_payload_fn=build_exact_search_payload,
        select_initial_candidates_fn=select_initial_candidates,
        apply_exact_search_boost_fn=apply_exact_search_boost,
        collect_parallel_signals_fn=collect_parallel_signals,
        apply_candidate_priors_fn=apply_candidate_priors,
        collect_docs_fn=collect_docs_signals,
        collect_worktree_fn=collect_worktree_prior,
        disabled_docs_payload_fn=_disabled_docs_payload,
        disabled_worktree_prior_fn=_disabled_worktree_prior,
        get_executor_fn=get_index_parallel_executor,
        resolve_future_fn=resolve_parallel_future,
        run_exact_search_fn=run_exact_search_ripgrep,
        score_exact_hits_fn=score_exact_search_hits,
        normalize_repo_path_fn=normalize_repo_path,
        supported_extensions_fn=supported_extensions,
        mark_timing_fn=mark_timing,
    )
    apply_candidate_generation_runtime_to_state(
        state=state,
        candidate_generation_runtime=candidate_generation_runtime,
        timings_ms=timings_ms,
        cochange_enabled=bool(config.cochange_enabled),
        ctx_state=ctx.state,
    )

    embedding_index_path = resolve_repo_relative_path(
        root=ctx.root, configured_path=config.embedding_index_path
    )
    post_generation_runtime = run_index_post_generation_runtime(
        root=ctx.root,
        repo=ctx.repo,
        query=ctx.query,
        terms=state.terms,
        files_map=state.effective_files_map,
        candidates=state.candidates,
        memory_paths=state.memory_paths,
        docs_payload=state.docs_payload,
        policy=state.policy,
        selected_ranker=state.selected_ranker,
        top_k_files=int(retrieval_cfg.top_k_files),
        candidate_relative_threshold=float(
            retrieval_cfg.candidate_relative_threshold
        ),
        refine_enabled=bool(retrieval_cfg.deterministic_refine_enabled),
        rank_candidates=rank_candidates,
        index_hash=state.index_hash,
        cochange_enabled=bool(config.cochange_enabled),
        cochange_cache_path=str(config.cochange_cache_path),
        cochange_lookback_commits=int(config.cochange_lookback_commits),
        cochange_half_life_days=float(config.cochange_half_life_days),
        cochange_neighbor_cap=int(config.cochange_neighbor_cap),
        cochange_top_neighbors=int(config.cochange_top_neighbors),
        cochange_boost_weight=float(config.cochange_boost_weight),
        cochange_min_neighbor_score=float(config.cochange_min_neighbor_score),
        cochange_max_boost=float(config.cochange_max_boost),
        scip_enabled=bool(config.scip_enabled),
        scip_index_path=str(config.scip_index_path),
        scip_provider=str(config.scip_provider),
        scip_generate_fallback=bool(config.scip_generate_fallback),
        embedding_index_path=embedding_index_path,
        embedding_enabled=bool(config.embedding_enabled),
        embedding_provider=str(config.embedding_provider),
        embedding_model=str(config.embedding_model),
        embedding_dimension=int(config.embedding_dimension),
        embedding_rerank_pool=int(config.embedding_rerank_pool),
        embedding_lexical_weight=float(config.embedding_lexical_weight),
        embedding_semantic_weight=float(config.embedding_semantic_weight),
        embedding_min_similarity=float(config.embedding_min_similarity),
        embedding_fail_open=bool(config.embedding_fail_open),
        feedback_enabled=bool(config.feedback_enabled),
        feedback_path=str(config.feedback_path),
        feedback_max_entries=int(config.feedback_max_entries),
        feedback_boost_per_select=float(config.feedback_boost_per_select),
        feedback_max_boost=float(config.feedback_max_boost),
        feedback_decay_days=float(config.feedback_decay_days),
        multi_channel_rrf_enabled=bool(retrieval_cfg.multi_channel_rrf_enabled)
        or str(state.policy.get("version", "")).strip().lower().startswith("v2"),
        multi_channel_rrf_k=int(retrieval_cfg.multi_channel_rrf_k),
        multi_channel_rrf_pool_cap=int(retrieval_cfg.multi_channel_rrf_pool_cap),
        multi_channel_rrf_code_cap=int(retrieval_cfg.multi_channel_rrf_code_cap),
        multi_channel_rrf_docs_cap=int(retrieval_cfg.multi_channel_rrf_docs_cap),
        multi_channel_rrf_memory_cap=int(
            retrieval_cfg.multi_channel_rrf_memory_cap
        ),
        benchmark_filter_payload=state.benchmark_filter_payload,
        chunk_top_k=int(chunking_cfg.top_k),
        chunk_per_file_limit=int(chunking_cfg.per_file_limit),
        chunk_token_budget=int(chunking_cfg.token_budget),
        chunk_disclosure=str(chunking_cfg.disclosure),
        chunk_snippet_max_lines=int(chunking_cfg.snippet_max_lines),
        chunk_snippet_max_chars=int(chunking_cfg.snippet_max_chars),
        tokenizer_model=str(chunking_cfg.tokenizer_model),
        chunk_diversity_enabled=bool(chunking_cfg.diversity_enabled),
        chunk_diversity_path_penalty=float(chunking_cfg.diversity_path_penalty),
        chunk_diversity_symbol_family_penalty=float(
            chunking_cfg.diversity_symbol_family_penalty
        ),
        chunk_diversity_kind_penalty=float(chunking_cfg.diversity_kind_penalty),
        chunk_diversity_locality_penalty=float(
            chunking_cfg.diversity_locality_penalty
        ),
        chunk_diversity_locality_window=int(chunking_cfg.diversity_locality_window),
        chunk_topological_shield_enabled=bool(topological_shield_cfg.enabled),
        chunk_topological_shield_mode=str(topological_shield_cfg.mode),
        chunk_topological_shield_max_attenuation=float(
            topological_shield_cfg.max_attenuation
        ),
        chunk_topological_shield_shared_parent_attenuation=float(
            topological_shield_cfg.shared_parent_attenuation
        ),
        chunk_topological_shield_adjacency_attenuation=float(
            topological_shield_cfg.adjacency_attenuation
        ),
        chunk_guard_enabled=bool(chunk_guard_cfg.enabled),
        chunk_guard_mode=str(chunk_guard_cfg.mode),
        chunk_guard_lambda_penalty=float(chunk_guard_cfg.lambda_penalty),
        chunk_guard_min_pool=int(chunk_guard_cfg.min_pool),
        chunk_guard_max_pool=int(chunk_guard_cfg.max_pool),
        chunk_guard_min_marginal_utility=float(
            chunk_guard_cfg.min_marginal_utility
        ),
        chunk_guard_compatibility_min_overlap=float(
            chunk_guard_cfg.compatibility_min_overlap
        ),
        run_index_candidate_fusion_fn=run_index_candidate_fusion,
        apply_benchmark_candidate_filters_fn=apply_benchmark_candidate_filters,
        run_index_chunk_selection_fn=run_index_chunk_selection,
        refine_candidate_pool_fn=refine_candidate_pool,
        postprocess_candidates_fn=postprocess_candidates,
        apply_structural_rerank_fn=apply_structural_rerank,
        apply_semantic_candidate_rerank_fn=apply_semantic_candidate_rerank,
        apply_feedback_boost_fn=apply_feedback_boost,
        apply_multi_channel_rrf_fusion_fn=apply_multi_channel_rrf_fusion,
        merge_candidate_lists_fn=merge_candidate_lists,
        resolve_embedding_runtime_config_fn=resolve_embedding_runtime_config,
        build_embedding_stats_fn=build_embedding_stats,
        rerank_cross_encoder_with_time_budget_fn=(
            _rerank_cross_encoder_with_time_budget
        ),
        filter_candidate_rows_fn=filter_candidate_rows,
        select_index_chunks_fn=select_index_chunks,
        apply_chunk_selection_fn=apply_chunk_selection,
        mark_timing_fn=mark_timing,
        rerank_rows_embeddings_with_time_budget_fn=(
            _rerank_rows_embeddings_with_time_budget
        ),
        rerank_rows_cross_encoder_with_time_budget_fn=(
            _rerank_rows_cross_encoder_with_time_budget
        ),
    )
    apply_post_generation_runtime_to_state(
        state=state,
        post_generation_runtime=post_generation_runtime,
    )

    return finalize_index_stage_output_from_state(
        state=state,
        repo=ctx.repo,
        root=ctx.root,
        fusion_mode=fusion_mode,
        hybrid_re2_rrf_k=int(retrieval_cfg.hybrid_re2_rrf_k),
        top_k_files=int(retrieval_cfg.top_k_files),
        candidate_relative_threshold=float(
            retrieval_cfg.candidate_relative_threshold
        ),
        chunk_top_k=int(chunking_cfg.top_k),
        chunk_per_file_limit=int(chunking_cfg.per_file_limit),
        chunk_token_budget=int(chunking_cfg.token_budget),
        chunk_disclosure=str(chunking_cfg.disclosure),
        policy_version=str(state.policy.get("version", retrieval_cfg.policy_version)),
        timings_ms=timings_ms,
        query=ctx.query,
        build_index_stage_output_fn=build_index_stage_output,
        clone_index_candidate_payload_fn=clone_index_candidate_payload,
        store_cached_index_candidates_fn=store_cached_index_candidates,
        attach_index_candidate_cache_info_fn=attach_index_candidate_cache_info,
    )


__all__ = ["IndexStageConfig", "run_index"]
