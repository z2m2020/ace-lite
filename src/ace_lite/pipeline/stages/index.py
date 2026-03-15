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
    CandidateFusionDeps,
    ChunkSelectionDeps,
    ChunkSelectionRuntimeConfig,
    InitialCandidateGenerationDeps,
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
from ace_lite.index_stage.config_adapter import (
    build_index_stage_config_from_orchestrator,
)
from ace_lite.index_stage.feedback import apply_feedback_boost
from ace_lite.parsers.languages import supported_extensions
from ace_lite.pipeline.types import StageContext
from ace_lite.rankers import normalize_fusion_mode
from ace_lite.retrieval_shared import (
    build_retrieval_runtime_profile,
    extract_retrieval_terms,
    load_retrieval_index_snapshot,
)

_INDEX_CANDIDATE_CACHE_CONTENT_VERSION = "index-candidates-v1"


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
    router_cfg = retrieval_cfg.adaptive_router
    chunking_cfg = config.chunking
    topological_shield_cfg = chunking_cfg.topological_shield
    chunk_guard_cfg = chunking_cfg.guard

    def mark_timing(label: str, started_at: float) -> None:
        timings_ms[label] = round((perf_counter() - started_at) * 1000.0, 3)

    timing_started = perf_counter()
    memory_stage = ctx.state.get("memory", {}) if isinstance(ctx.state.get("memory"), dict) else {}
    terms = extract_retrieval_terms(query=ctx.query, memory_stage=memory_stage)
    memory_paths = extract_memory_paths(memory_stage=memory_stage, root=ctx.root)
    mark_timing("term_extraction", timing_started)

    timing_started = perf_counter()
    policy = resolve_retrieval_policy(
        query=ctx.query,
        retrieval_policy=retrieval_cfg.retrieval_policy,
        policy_version=retrieval_cfg.policy_version,
        cochange_enabled=config.cochange_enabled,
        embedding_enabled=config.embedding_enabled,
    )
    shadow_router = resolve_shadow_router_arm(
        enabled=router_cfg.enabled,
        mode=router_cfg.mode,
        model_path=resolve_repo_relative_path(
            root=ctx.root,
            configured_path=router_cfg.model_path,
        ),
        arm_set=router_cfg.arm_set,
        executed_policy_name=str(policy.get("name", "")).strip(),
        candidate_ranker=retrieval_cfg.candidate_ranker,
        embedding_enabled=bool(policy.get("embedding_enabled", config.embedding_enabled)),
    )
    online_bandit_gate = resolve_online_bandit_gate(
        enabled=router_cfg.online_bandit_enabled,
        experiment_enabled=router_cfg.online_bandit_experiment_enabled,
        state_path=resolve_repo_relative_path(
            root=ctx.root,
            configured_path=router_cfg.state_path,
        ),
    )
    adaptive_router_payload = build_adaptive_router_payload(
        enabled=bool(router_cfg.enabled),
        mode=str(router_cfg.mode),
        model_path=str(router_cfg.model_path),
        state_path=str(router_cfg.state_path),
        arm_set=str(router_cfg.arm_set),
        policy=policy,
        shadow=shadow_router,
        online_bandit=online_bandit_gate,
    )
    ctx.state["__policy"] = policy
    mark_timing("policy_resolution", timing_started)

    timing_started = perf_counter()
    snapshot = load_retrieval_index_snapshot(
        root_dir=ctx.root,
        cache_path=str(config.cache_path),
        languages=config.languages,
        incremental=config.incremental,
        fail_open=True,
        include_index_hash=True,
    )
    index_data = snapshot.index_payload
    cache_info = snapshot.cache_info
    mark_timing("index_cache_load", timing_started)

    files_map = snapshot.files_map
    index_hash = snapshot.index_hash
    corpus_size = snapshot.corpus_size
    benchmark_filter_payload = resolve_benchmark_candidate_filters(ctx)
    effective_files_map = files_map
    effective_corpus_size = corpus_size
    if benchmark_filter_payload["requested"]:
        filtered_files_map, removed_file_count = filter_files_map_for_benchmark(
            files_map,
            include_paths=list(benchmark_filter_payload["include_paths"]),
            include_globs=list(benchmark_filter_payload["include_globs"]),
            exclude_paths=list(benchmark_filter_payload["exclude_paths"]),
            exclude_globs=list(benchmark_filter_payload["exclude_globs"]),
        )
        benchmark_filter_payload["files_map_count_before"] = len(files_map)
        benchmark_filter_payload["files_map_count_after"] = len(filtered_files_map)
        benchmark_filter_payload["dropped_files_map_count"] = int(removed_file_count)
        if filtered_files_map:
            effective_files_map = filtered_files_map
            effective_corpus_size = len(filtered_files_map)
            benchmark_filter_payload["files_map_applied"] = True
            benchmark_filter_payload["files_map_fallback_to_unfiltered"] = False
        else:
            benchmark_filter_payload["files_map_applied"] = False
            benchmark_filter_payload["files_map_fallback_to_unfiltered"] = True
    else:
        benchmark_filter_payload["files_map_count_before"] = len(files_map)
        benchmark_filter_payload["files_map_count_after"] = len(files_map)
        benchmark_filter_payload["dropped_files_map_count"] = 0
        benchmark_filter_payload["files_map_applied"] = False
        benchmark_filter_payload["files_map_fallback_to_unfiltered"] = False
    ctx.state["__index_files"] = effective_files_map
    docs_policy_enabled, docs_policy_reason = resolve_docs_policy_for_benchmark(
        policy_docs_enabled=bool(policy.get("docs_enabled", True)),
        benchmark_filter_payload=benchmark_filter_payload,
    )
    benchmark_filter_payload["docs_policy_enabled"] = bool(docs_policy_enabled)
    benchmark_filter_payload["docs_policy_reason"] = str(docs_policy_reason)
    worktree_prior_enabled, worktree_policy_reason = resolve_worktree_policy_for_benchmark(
        worktree_prior_enabled=bool(config.cochange_enabled),
        benchmark_filter_payload=benchmark_filter_payload,
    )
    benchmark_filter_payload["worktree_policy_enabled"] = bool(worktree_prior_enabled)
    benchmark_filter_payload["worktree_policy_reason"] = str(worktree_policy_reason)
    embedding_runtime = resolve_embedding_runtime_config(
        provider=str(config.embedding_provider),
        model=str(config.embedding_model),
        dimension=int(config.embedding_dimension),
    )
    index_candidate_cache_path = default_index_candidate_cache_path(root=ctx.root)
    index_candidate_cache_ttl_seconds = max(
        0, int(policy.get("index_candidate_cache_ttl_seconds", 1800) or 1800)
    )
    index_candidate_cache_required_meta = {
        "policy_name": str(policy.get("name", "general")),
        "policy_version": str(policy.get("version", retrieval_cfg.policy_version)),
        "index_hash": str(index_hash or ""),
        "content_version": _INDEX_CANDIDATE_CACHE_CONTENT_VERSION,
    }
    index_candidate_cache_key = build_index_candidate_cache_key(
        query=ctx.query,
        terms=terms,
        memory_paths=memory_paths,
        index_hash=index_hash,
        policy=policy,
        requested_ranker=str(retrieval_cfg.candidate_ranker),
        top_k_files=int(retrieval_cfg.top_k_files),
        min_candidate_score=int(retrieval_cfg.min_candidate_score),
        candidate_relative_threshold=float(retrieval_cfg.candidate_relative_threshold),
        chunk_top_k=int(chunking_cfg.top_k),
        chunk_per_file_limit=int(chunking_cfg.per_file_limit),
        chunk_token_budget=int(chunking_cfg.token_budget),
        chunk_disclosure=str(chunking_cfg.disclosure),
        exact_search_enabled=bool(retrieval_cfg.exact_search_enabled),
        deterministic_refine_enabled=bool(retrieval_cfg.deterministic_refine_enabled),
        embedding_enabled=bool(config.embedding_enabled),
        embedding_provider=str(embedding_runtime.provider),
        embedding_model=str(embedding_runtime.model),
        embedding_dimension=int(embedding_runtime.dimension),
        feedback_enabled=bool(config.feedback_enabled),
        multi_channel_rrf_enabled=bool(retrieval_cfg.multi_channel_rrf_enabled)
        or str(policy.get("version", "")).strip().lower().startswith("v2"),
        chunk_guard_mode=str(chunk_guard_cfg.mode),
        topological_shield_mode=str(topological_shield_cfg.mode),
        settings_payload={
            "retrieval": {
                "exact_search_time_budget_ms": int(
                    retrieval_cfg.exact_search_time_budget_ms
                ),
                "exact_search_max_paths": int(retrieval_cfg.exact_search_max_paths),
                "hybrid_re2_fusion_mode": str(retrieval_cfg.hybrid_re2_fusion_mode),
                "hybrid_re2_rrf_k": int(retrieval_cfg.hybrid_re2_rrf_k),
                "hybrid_re2_bm25_weight": float(retrieval_cfg.hybrid_re2_bm25_weight),
                "hybrid_re2_heuristic_weight": float(
                    retrieval_cfg.hybrid_re2_heuristic_weight
                ),
                "hybrid_re2_coverage_weight": float(
                    retrieval_cfg.hybrid_re2_coverage_weight
                ),
                "hybrid_re2_combined_scale": float(
                    retrieval_cfg.hybrid_re2_combined_scale
                ),
                "multi_channel_rrf_k": int(retrieval_cfg.multi_channel_rrf_k),
                "multi_channel_rrf_pool_cap": int(
                    retrieval_cfg.multi_channel_rrf_pool_cap
                ),
                "multi_channel_rrf_code_cap": int(
                    retrieval_cfg.multi_channel_rrf_code_cap
                ),
                "multi_channel_rrf_docs_cap": int(
                    retrieval_cfg.multi_channel_rrf_docs_cap
                ),
                "multi_channel_rrf_memory_cap": int(
                    retrieval_cfg.multi_channel_rrf_memory_cap
                ),
            },
            "chunking": {
                "diversity_enabled": bool(chunking_cfg.diversity_enabled),
                "diversity_path_penalty": float(
                    chunking_cfg.diversity_path_penalty
                ),
                "diversity_symbol_family_penalty": float(
                    chunking_cfg.diversity_symbol_family_penalty
                ),
                "diversity_kind_penalty": float(chunking_cfg.diversity_kind_penalty),
                "diversity_locality_penalty": float(
                    chunking_cfg.diversity_locality_penalty
                ),
                "diversity_locality_window": int(
                    chunking_cfg.diversity_locality_window
                ),
                "topological_max_attenuation": float(
                    topological_shield_cfg.max_attenuation
                ),
                "topological_shared_parent_attenuation": float(
                    topological_shield_cfg.shared_parent_attenuation
                ),
                "topological_adjacency_attenuation": float(
                    topological_shield_cfg.adjacency_attenuation
                ),
                "guard_lambda_penalty": float(chunk_guard_cfg.lambda_penalty),
                "guard_min_pool": int(chunk_guard_cfg.min_pool),
                "guard_max_pool": int(chunk_guard_cfg.max_pool),
                "guard_min_marginal_utility": float(
                    chunk_guard_cfg.min_marginal_utility
                ),
                "guard_compatibility_min_overlap": float(
                    chunk_guard_cfg.compatibility_min_overlap
                ),
            },
            "embedding": {
                "rerank_pool": int(config.embedding_rerank_pool),
                "lexical_weight": float(config.embedding_lexical_weight),
                "semantic_weight": float(config.embedding_semantic_weight),
                "min_similarity": float(config.embedding_min_similarity),
                "fail_open": bool(config.embedding_fail_open),
            },
            "feedback": {
                "path": str(config.feedback_path),
                "max_entries": int(config.feedback_max_entries),
                "boost_per_select": float(config.feedback_boost_per_select),
                "max_boost": float(config.feedback_max_boost),
                "decay_days": float(config.feedback_decay_days),
            },
            "feature_flags": {
                "cochange_enabled": bool(config.cochange_enabled),
                "scip_enabled": bool(config.scip_enabled),
            },
            "adaptive_router": {
                "enabled": bool(router_cfg.enabled),
                "mode": str(router_cfg.mode),
                "model_path": str(router_cfg.model_path),
                "state_path": str(router_cfg.state_path),
                "arm_set": str(router_cfg.arm_set),
                "online_bandit_enabled": bool(router_cfg.online_bandit_enabled),
                "online_bandit_experiment_enabled": bool(
                    router_cfg.online_bandit_experiment_enabled
                ),
            },
            "benchmark_filters": resolve_benchmark_candidate_filters(ctx),
        },
        content_version=_INDEX_CANDIDATE_CACHE_CONTENT_VERSION,
    )
    index_candidate_cache = {
        "enabled": True,
        "hit": False,
        "store_written": False,
        "cache_key": str(index_candidate_cache_key),
        "path": str(index_candidate_cache_path),
        "ttl_seconds": int(index_candidate_cache_ttl_seconds),
        "content_version": _INDEX_CANDIDATE_CACHE_CONTENT_VERSION,
    }
    cached_index_payload = load_cached_index_candidates_checked(
        cache_path=index_candidate_cache_path,
        key=index_candidate_cache_key,
        max_age_seconds=index_candidate_cache_ttl_seconds,
        required_meta=index_candidate_cache_required_meta,
    )
    if cached_index_payload is not None:
        index_candidate_cache["hit"] = True
        if bool(config.cochange_enabled) and not worktree_prior_enabled:
            ctx.state["__vcs_worktree"] = build_disabled_worktree_prior(
                reason=worktree_policy_reason
            )
        else:
            ctx.state.pop("__vcs_worktree", None)
        refreshed_cached_payload = refresh_cached_index_candidate_payload(
            payload=cached_index_payload,
            index_data=index_data,
            cache_info=cache_info,
            index_hash=index_hash,
            timings_ms=timings_ms,
            benchmark_filter_payload=benchmark_filter_payload,
        )
        return attach_index_candidate_cache_info(
            payload=refreshed_cached_payload,
            cache_info=index_candidate_cache,
        )

    fusion_mode = normalize_fusion_mode(retrieval_cfg.hybrid_re2_fusion_mode)
    hybrid_weights = {
        "bm25_weight": float(retrieval_cfg.hybrid_re2_bm25_weight),
        "heuristic_weight": float(retrieval_cfg.hybrid_re2_heuristic_weight),
        "coverage_weight": float(retrieval_cfg.hybrid_re2_coverage_weight),
        "combined_scale": float(retrieval_cfg.hybrid_re2_combined_scale),
    }
    runtime_profile = build_retrieval_runtime_profile(
        candidate_ranker=retrieval_cfg.candidate_ranker,
        min_candidate_score=int(retrieval_cfg.min_candidate_score),
        top_k_files=int(retrieval_cfg.top_k_files),
        hybrid_fusion_mode=fusion_mode,
        hybrid_rrf_k=int(retrieval_cfg.hybrid_re2_rrf_k),
        hybrid_weights=hybrid_weights,
        index_hash=index_hash,
    )
    parallel_requested = bool(policy.get("index_parallel_enabled", False))
    parallel_time_budget_ms = max(
        0, int(policy.get("index_parallel_time_budget_ms", 0) or 0)
    )

    def rank_candidates(
        min_score: int,
        candidate_ranker: str,
        candidate_terms: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        ranked_terms = terms if candidate_terms is None else candidate_terms
        return runtime_profile.rank_candidates(
            files_map=effective_files_map,
            terms=ranked_terms,
            candidate_ranker=candidate_ranker,
            min_score=min_score,
        )

    initial_candidates = gather_initial_candidates(
        root=ctx.root,
        query=ctx.query,
        terms=terms,
        files_map=effective_files_map,
        corpus_size=effective_corpus_size,
        runtime_profile=runtime_profile,
        top_k_files=int(retrieval_cfg.top_k_files),
        exact_search_enabled=bool(retrieval_cfg.exact_search_enabled),
        exact_search_time_budget_ms=int(retrieval_cfg.exact_search_time_budget_ms),
        exact_search_max_paths=int(retrieval_cfg.exact_search_max_paths),
        exact_search_include_globs=[
            f"*{suffix}"
            for suffix in sorted(supported_extensions(tuple(config.languages)))
            if suffix
        ][:12],
        docs_policy_enabled=docs_policy_enabled,
        worktree_prior_enabled=worktree_prior_enabled,
        cochange_enabled=bool(config.cochange_enabled),
        docs_intent_weight=float(policy.get("docs_weight", 1.0) or 1.0),
        parallel_requested=parallel_requested,
        parallel_time_budget_ms=parallel_time_budget_ms,
        policy=policy,
        deps=InitialCandidateGenerationDeps(
            build_exact_search_payload=build_exact_search_payload,
            select_initial_candidates=select_initial_candidates,
            apply_exact_search_boost=apply_exact_search_boost,
            collect_parallel_signals=collect_parallel_signals,
            apply_candidate_priors=apply_candidate_priors,
            collect_docs=collect_docs_signals,
            collect_worktree=collect_worktree_prior,
            disabled_docs_payload=build_disabled_docs_payload,
            disabled_worktree_prior=build_disabled_worktree_prior,
            get_executor=get_index_parallel_executor,
            resolve_future=resolve_parallel_future,
            run_exact_search=run_exact_search_ripgrep,
            score_exact_hits=score_exact_search_hits,
            normalize_repo_path=normalize_repo_path,
            mark_timing=mark_timing,
        ),
    )
    requested_ranker = initial_candidates.requested_ranker
    selected_ranker = initial_candidates.selected_ranker
    ranker_fallbacks = list(initial_candidates.ranker_fallbacks)
    min_score_used = int(initial_candidates.min_score_used)
    candidates = list(initial_candidates.candidates)
    exact_search_payload = initial_candidates.exact_search_payload
    docs_payload = initial_candidates.docs_payload
    worktree_prior = initial_candidates.worktree_prior
    parallel_payload = initial_candidates.parallel_payload
    prior_payload = initial_candidates.prior_payload
    timings_ms["docs_signals"] = round(float(initial_candidates.docs_elapsed_ms), 3)
    timings_ms["worktree_prior"] = round(
        float(initial_candidates.worktree_elapsed_ms), 3
    )

    if (
        config.cochange_enabled
        and isinstance(initial_candidates.raw_worktree, dict)
    ):
        ctx.state["__vcs_worktree"] = initial_candidates.raw_worktree

    embedding_index_path = resolve_repo_relative_path(
        root=ctx.root, configured_path=config.embedding_index_path
    )
    candidate_fusion = refine_candidate_pool(
        root=ctx.root,
        repo=ctx.repo,
        query=ctx.query,
        terms=terms,
        files_map=effective_files_map,
        candidates=candidates,
        memory_paths=memory_paths,
        docs_payload=docs_payload,
        policy=policy,
        selected_ranker=selected_ranker,
        top_k_files=int(retrieval_cfg.top_k_files),
        candidate_relative_threshold=float(
            retrieval_cfg.candidate_relative_threshold
        ),
        refine_enabled=bool(retrieval_cfg.deterministic_refine_enabled),
        rank_candidates=rank_candidates,
        index_hash=index_hash,
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
        or str(policy.get("version", "")).strip().lower().startswith("v2"),
        multi_channel_rrf_k=int(retrieval_cfg.multi_channel_rrf_k),
        multi_channel_rrf_pool_cap=int(retrieval_cfg.multi_channel_rrf_pool_cap),
        multi_channel_rrf_code_cap=int(retrieval_cfg.multi_channel_rrf_code_cap),
        multi_channel_rrf_docs_cap=int(retrieval_cfg.multi_channel_rrf_docs_cap),
        multi_channel_rrf_memory_cap=int(
            retrieval_cfg.multi_channel_rrf_memory_cap
        ),
        deps=CandidateFusionDeps(
            postprocess_candidates=postprocess_candidates,
            apply_structural_rerank=apply_structural_rerank,
            apply_semantic_candidate_rerank=apply_semantic_candidate_rerank,
            apply_feedback_boost=apply_feedback_boost,
            apply_multi_channel_rrf_fusion=apply_multi_channel_rrf_fusion,
            merge_candidate_lists=merge_candidate_lists,
            resolve_embedding_runtime_config=resolve_embedding_runtime_config,
            build_embedding_stats=build_embedding_stats,
            rerank_cross_encoder_with_time_budget=(
                rerank_cross_encoder_with_time_budget
            ),
            mark_timing=mark_timing,
        ),
    )
    candidates = list(candidate_fusion.candidates)
    second_pass_payload = candidate_fusion.second_pass_payload
    refine_pass_payload = candidate_fusion.refine_pass_payload
    cochange_payload = candidate_fusion.cochange_payload
    scip_payload = candidate_fusion.scip_payload
    graph_lookup_payload = candidate_fusion.graph_lookup_payload
    embeddings_payload = candidate_fusion.embeddings_payload
    feedback_payload = candidate_fusion.feedback_payload
    multi_channel_fusion_payload = candidate_fusion.multi_channel_fusion_payload
    semantic_embedding_provider_impl = (
        candidate_fusion.semantic_embedding_provider_impl
    )
    semantic_cross_encoder_provider = (
        candidate_fusion.semantic_cross_encoder_provider
    )
    if benchmark_filter_payload["requested"]:
        filtered_candidates, removed_count = filter_candidate_rows(
            candidates,
            include_paths=list(benchmark_filter_payload["include_paths"]),
            include_globs=list(benchmark_filter_payload["include_globs"]),
            exclude_paths=list(benchmark_filter_payload["exclude_paths"]),
            exclude_globs=list(benchmark_filter_payload["exclude_globs"]),
        )
        benchmark_filter_payload["dropped_candidate_count"] = int(removed_count)
        benchmark_filter_payload["candidate_count_before"] = len(candidates)
        benchmark_filter_payload["candidate_count_after"] = len(filtered_candidates)
        if filtered_candidates:
            candidates = filtered_candidates
            benchmark_filter_payload["applied"] = True
            benchmark_filter_payload["fallback_to_unfiltered"] = False
        else:
            benchmark_filter_payload["applied"] = False
            benchmark_filter_payload["fallback_to_unfiltered"] = True
    else:
        benchmark_filter_payload["dropped_candidate_count"] = 0
        benchmark_filter_payload["candidate_count_before"] = len(candidates)
        benchmark_filter_payload["candidate_count_after"] = len(candidates)
        benchmark_filter_payload["applied"] = False
        benchmark_filter_payload["fallback_to_unfiltered"] = False

    chunk_selection = select_index_chunks(
        root=ctx.root,
        query=ctx.query,
        files_map=effective_files_map,
        candidates=candidates,
        terms=terms,
        policy=policy,
        runtime_config=ChunkSelectionRuntimeConfig(
            top_k_files=int(retrieval_cfg.top_k_files),
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
            chunk_diversity_locality_window=int(
                chunking_cfg.diversity_locality_window
            ),
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
            embedding_enabled=bool(config.embedding_enabled),
            embedding_lexical_weight=float(config.embedding_lexical_weight),
            embedding_semantic_weight=float(config.embedding_semantic_weight),
            embedding_min_similarity=float(config.embedding_min_similarity),
        ),
        index_hash=index_hash,
        embeddings_payload=embeddings_payload,
        semantic_embedding_provider_impl=semantic_embedding_provider_impl,
        semantic_cross_encoder_provider=semantic_cross_encoder_provider,
        deps=ChunkSelectionDeps(
            apply_chunk_selection=apply_chunk_selection,
            mark_timing=mark_timing,
            rerank_rows_embeddings_with_time_budget=(
                rerank_rows_embeddings_with_time_budget
            ),
            rerank_rows_cross_encoder_with_time_budget=(
                rerank_rows_cross_encoder_with_time_budget
            ),
        ),
    )
    candidate_chunks = chunk_selection.candidate_chunks
    chunk_metrics = chunk_selection.chunk_metrics
    chunk_semantic_rerank_payload = chunk_selection.chunk_semantic_rerank_payload
    topological_shield_payload = chunk_selection.topological_shield_payload
    chunk_guard_payload = chunk_selection.chunk_guard_payload

    payload = build_index_stage_output(
        repo=ctx.repo,
        root=ctx.root,
        terms=terms,
        memory_paths=memory_paths,
        index_hash=index_hash,
        index_data=index_data,
        cache_info=cache_info,
        requested_ranker=requested_ranker,
        selected_ranker=selected_ranker,
        ranker_fallbacks=ranker_fallbacks,
        corpus_size=corpus_size,
        min_score_used=min_score_used,
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
        candidates=candidates,
        candidate_chunks=candidate_chunks,
        chunk_metrics=chunk_metrics,
        exact_search_payload=exact_search_payload,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        parallel_payload=parallel_payload,
        prior_payload=prior_payload,
        graph_lookup_payload=graph_lookup_payload,
        cochange_payload=cochange_payload,
        scip_payload=scip_payload,
        embeddings_payload=embeddings_payload,
        feedback_payload=feedback_payload,
        multi_channel_fusion_payload=multi_channel_fusion_payload,
        second_pass_payload=second_pass_payload,
        refine_pass_payload=refine_pass_payload,
        chunk_semantic_rerank_payload=chunk_semantic_rerank_payload,
        topological_shield_payload=topological_shield_payload,
        chunk_guard_payload=chunk_guard_payload,
        adaptive_router_payload=adaptive_router_payload,
        policy_name=str(policy.get("name", "general")),
        policy_version=str(policy.get("version", retrieval_cfg.policy_version)),
        timings_ms=timings_ms,
    )
    if benchmark_filter_payload["requested"]:
        payload["benchmark_filters"] = benchmark_filter_payload
    index_candidate_cache["store_written"] = bool(
        store_cached_index_candidates(
            cache_path=index_candidate_cache_path,
            key=index_candidate_cache_key,
            payload=clone_index_candidate_payload(payload),
            meta={
                **index_candidate_cache_required_meta,
                "query": ctx.query,
                "ttl_seconds": int(index_candidate_cache_ttl_seconds),
                "trust_class": "exact",
            },
        )
    )
    return attach_index_candidate_cache_info(
        payload=payload,
        cache_info=index_candidate_cache,
    )


__all__ = ["IndexStageConfig", "run_index"]
