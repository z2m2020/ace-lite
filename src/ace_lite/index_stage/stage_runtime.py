from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, cast

from ace_lite.scoring_config import SCIP_BASE_WEIGHT, resolve_chunk_scoring_config


@dataclass(frozen=True, slots=True)
class IndexStageRuntimeDeps:
    content_version: str
    bootstrap_index_runtime_fn: Callable[..., Any]
    build_index_stage_execution_state_fn: Callable[..., Any]
    build_index_retrieval_runtime_fn: Callable[..., Any]
    run_index_candidate_generation_fn: Callable[..., Any]
    apply_candidate_generation_runtime_to_state_fn: Callable[..., None]
    resolve_repo_relative_path_fn: Callable[..., str]
    run_index_post_generation_runtime_fn: Callable[..., Any]
    apply_post_generation_runtime_to_state_fn: Callable[..., None]
    finalize_index_stage_output_from_state_fn: Callable[..., dict[str, Any]]
    normalize_fusion_mode_fn: Callable[..., str]
    build_retrieval_runtime_profile_fn: Callable[..., Any]
    bootstrap_helpers: dict[str, Any]
    candidate_generation_helpers: dict[str, Any]
    post_generation_helpers: dict[str, Any]
    finalize_helpers: dict[str, Any]


def execute_index_stage_runtime(
    *,
    ctx: Any,
    config: Any,
    deps: IndexStageRuntimeDeps,
) -> dict[str, Any]:
    timings_ms: dict[str, float] = {}
    retrieval_cfg = config.retrieval
    chunking_cfg = config.chunking
    topological_shield_cfg = chunking_cfg.topological_shield
    chunk_guard_cfg = chunking_cfg.guard
    chunk_scoring_config = resolve_chunk_scoring_config(
        {
            key: value
            for key, value in {
                "file_prior_weight": getattr(
                    chunking_cfg, "file_prior_weight", None
                ),
                "path_match": getattr(chunking_cfg, "path_match", None),
                "module_match": getattr(chunking_cfg, "module_match", None),
                "symbol_exact": getattr(chunking_cfg, "symbol_exact", None),
                "symbol_partial": getattr(chunking_cfg, "symbol_partial", None),
                "signature_match": getattr(chunking_cfg, "signature_match", None),
                "reference_factor": getattr(
                    chunking_cfg, "reference_factor", None
                ),
                "reference_cap": getattr(chunking_cfg, "reference_cap", None),
            }.items()
            if value is not None
        }
    )

    def mark_timing(label: str, started_at: float) -> None:
        timings_ms[label] = round((perf_counter() - started_at) * 1000.0, 3)

    bootstrap = deps.bootstrap_index_runtime_fn(
        ctx=ctx,
        config=config,
        content_version=deps.content_version,
        timings_ms=timings_ms,
        mark_timing=mark_timing,
        **deps.bootstrap_helpers,
    )
    if bootstrap.cache_hit_payload is not None:
        return cast(dict[str, Any], bootstrap.cache_hit_payload)

    state = deps.build_index_stage_execution_state_fn(bootstrap=bootstrap)
    retrieval_refinement = ctx.state.get("_agent_loop_retrieval_refinement")
    if isinstance(retrieval_refinement, dict) and retrieval_refinement:
        setattr(state, "retrieval_refinement_payload", dict(retrieval_refinement))

    retrieval_runtime = deps.build_index_retrieval_runtime_fn(
        retrieval_cfg=retrieval_cfg,
        policy=state.policy,
        index_hash=state.index_hash,
        terms=state.terms,
        effective_files_map=state.effective_files_map,
        normalize_fusion_mode_fn=deps.normalize_fusion_mode_fn,
        build_retrieval_runtime_profile_fn=deps.build_retrieval_runtime_profile_fn,
    )
    fusion_mode = retrieval_runtime.fusion_mode
    rank_candidates = retrieval_runtime.rank_candidates

    candidate_generation_runtime = deps.run_index_candidate_generation_fn(
        root=ctx.root,
        query=ctx.query,
        terms=state.terms,
        files_map=state.effective_files_map,
        corpus_size=state.effective_corpus_size,
        runtime_profile=retrieval_runtime.runtime_profile,
        top_k_files=int(retrieval_cfg.top_k_files),
        exact_search_enabled=bool(retrieval_cfg.exact_search_enabled),
        exact_search_time_budget_ms=int(retrieval_cfg.exact_search_time_budget_ms),
        exact_search_max_paths=int(retrieval_cfg.exact_search_max_paths),
        languages=list(config.languages),
        docs_policy_enabled=state.docs_policy_enabled,
        worktree_prior_enabled=state.worktree_prior_enabled,
        cochange_enabled=bool(config.cochange_enabled),
        docs_intent_weight=float(state.policy.get("docs_weight", 1.0) or 1.0),
        parallel_requested=retrieval_runtime.parallel_requested,
        parallel_time_budget_ms=retrieval_runtime.parallel_time_budget_ms,
        policy=state.policy,
        mark_timing_fn=mark_timing,
        **deps.candidate_generation_helpers,
    )
    deps.apply_candidate_generation_runtime_to_state_fn(
        state=state,
        candidate_generation_runtime=candidate_generation_runtime,
        timings_ms=timings_ms,
        cochange_enabled=bool(config.cochange_enabled),
        ctx_state=ctx.state,
    )

    embedding_index_path = deps.resolve_repo_relative_path_fn(
        root=ctx.root,
        configured_path=config.embedding_index_path,
    )
    post_generation_runtime = deps.run_index_post_generation_runtime_fn(
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
        scip_base_weight=float(
            getattr(config, "scip_base_weight", SCIP_BASE_WEIGHT)
            or SCIP_BASE_WEIGHT
        ),
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
        chunk_scoring_config=chunk_scoring_config,
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
        mark_timing_fn=mark_timing,
        retrieval_refinement=getattr(state, "retrieval_refinement_payload", {}),
        **deps.post_generation_helpers,
    )
    deps.apply_post_generation_runtime_to_state_fn(
        state=state,
        post_generation_runtime=post_generation_runtime,
    )

    return deps.finalize_index_stage_output_from_state_fn(
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
        **deps.finalize_helpers,
    )


__all__ = ["IndexStageRuntimeDeps", "execute_index_stage_runtime"]
