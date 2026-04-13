from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ace_lite.index_stage.benchmark_candidate_runtime import (
    BenchmarkCandidateFilterResult,
)
from ace_lite.index_stage.candidate_fusion import CandidateFusionResult
from ace_lite.index_stage.chunk_selection import ChunkSelectionResult
from ace_lite.scoring_config import SCIP_BASE_WEIGHT, resolve_chunk_scoring_config


@dataclass(slots=True)
class IndexPostGenerationRuntimeResult:
    candidates: list[dict[str, Any]]
    second_pass_payload: dict[str, Any]
    refine_pass_payload: dict[str, Any]
    cochange_payload: dict[str, Any]
    scip_payload: dict[str, Any]
    graph_lookup_payload: dict[str, Any]
    embeddings_payload: dict[str, Any]
    feedback_payload: dict[str, Any]
    multi_channel_fusion_payload: dict[str, Any]
    semantic_embedding_provider_impl: Any
    semantic_cross_encoder_provider: Any
    benchmark_filter_payload: dict[str, Any]
    candidate_chunks: list[dict[str, Any]]
    chunk_metrics: dict[str, Any]
    chunk_semantic_rerank_payload: dict[str, Any]
    topological_shield_payload: dict[str, Any]
    chunk_guard_payload: dict[str, Any]
    retrieval_refinement_payload: dict[str, Any] = field(default_factory=dict)


def run_index_post_generation_runtime(
    *,
    root: str,
    repo: str,
    query: str,
    terms: list[str],
    files_map: dict[str, Any],
    candidates: list[dict[str, Any]],
    memory_paths: list[str],
    docs_payload: dict[str, Any],
    policy: dict[str, Any],
    selected_ranker: str,
    top_k_files: int,
    candidate_relative_threshold: float,
    refine_enabled: bool,
    rank_candidates: Callable[..., list[dict[str, Any]]],
    index_hash: str,
    cochange_enabled: bool,
    cochange_cache_path: str,
    cochange_lookback_commits: int,
    cochange_half_life_days: float,
    cochange_neighbor_cap: int,
    cochange_top_neighbors: int,
    cochange_boost_weight: float,
    cochange_min_neighbor_score: float,
    cochange_max_boost: float,
    scip_enabled: bool,
    scip_index_path: str,
    scip_provider: str,
    scip_generate_fallback: bool,
    embedding_index_path: str,
    embedding_enabled: bool,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
    embedding_rerank_pool: int,
    embedding_lexical_weight: float,
    embedding_semantic_weight: float,
    embedding_min_similarity: float,
    embedding_fail_open: bool,
    feedback_enabled: bool,
    feedback_path: str,
    feedback_max_entries: int,
    feedback_boost_per_select: float,
    feedback_max_boost: float,
    feedback_decay_days: float,
    multi_channel_rrf_enabled: bool,
    multi_channel_rrf_k: int,
    multi_channel_rrf_pool_cap: int,
    multi_channel_rrf_code_cap: int,
    multi_channel_rrf_docs_cap: int,
    multi_channel_rrf_memory_cap: int,
    benchmark_filter_payload: dict[str, Any],
    chunk_top_k: int,
    chunk_per_file_limit: int,
    chunk_token_budget: int,
    chunk_disclosure: str,
    chunk_snippet_max_lines: int,
    chunk_snippet_max_chars: int,
    tokenizer_model: str,
    chunk_diversity_enabled: bool,
    chunk_diversity_path_penalty: float,
    chunk_diversity_symbol_family_penalty: float,
    chunk_diversity_kind_penalty: float,
    chunk_diversity_locality_penalty: float,
    chunk_diversity_locality_window: int,
    chunk_topological_shield_enabled: bool,
    chunk_topological_shield_mode: str,
    chunk_topological_shield_max_attenuation: float,
    chunk_topological_shield_shared_parent_attenuation: float,
    chunk_topological_shield_adjacency_attenuation: float,
    chunk_guard_enabled: bool,
    chunk_guard_mode: str,
    chunk_guard_lambda_penalty: float,
    chunk_guard_min_pool: int,
    chunk_guard_max_pool: int,
    chunk_guard_min_marginal_utility: float,
    chunk_guard_compatibility_min_overlap: float,
    run_index_candidate_fusion_fn: Callable[..., CandidateFusionResult],
    apply_benchmark_candidate_filters_fn: Callable[
        ..., BenchmarkCandidateFilterResult
    ],
    run_index_chunk_selection_fn: Callable[..., ChunkSelectionResult],
    refine_candidate_pool_fn: Callable[..., CandidateFusionResult],
    postprocess_candidates_fn: Callable[..., Any],
    apply_structural_rerank_fn: Callable[..., Any],
    apply_semantic_candidate_rerank_fn: Callable[..., Any],
    apply_feedback_boost_fn: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]],
    apply_multi_channel_rrf_fusion_fn: Callable[
        ..., tuple[list[dict[str, Any]], dict[str, Any]]
    ],
    merge_candidate_lists_fn: Callable[..., list[dict[str, Any]]],
    resolve_embedding_runtime_config_fn: Callable[..., Any],
    build_embedding_stats_fn: Callable[..., dict[str, Any]],
    rerank_cross_encoder_with_time_budget_fn: Callable[
        ..., tuple[list[dict[str, Any]], Any]
    ],
    filter_candidate_rows_fn: Callable[..., tuple[list[dict[str, Any]], int]],
    select_index_chunks_fn: Callable[..., ChunkSelectionResult],
    apply_chunk_selection_fn: Callable[..., ChunkSelectionResult],
    mark_timing_fn: Callable[[str, float], None],
    rerank_rows_embeddings_with_time_budget_fn: Callable[
        ..., tuple[list[dict[str, Any]], Any]
    ],
    rerank_rows_cross_encoder_with_time_budget_fn: Callable[
        ..., tuple[list[dict[str, Any]], Any]
    ],
    scip_base_weight: float = SCIP_BASE_WEIGHT,
    chunk_scoring_config: dict[str, Any] | None = None,
    retrieval_refinement: dict[str, Any] | None = None,
) -> IndexPostGenerationRuntimeResult:
    resolved_chunk_scoring_config = resolve_chunk_scoring_config(
        chunk_scoring_config
    )
    candidate_fusion = run_index_candidate_fusion_fn(
        root=root,
        repo=repo,
        query=query,
        terms=terms,
        files_map=files_map,
        candidates=candidates,
        memory_paths=memory_paths,
        docs_payload=docs_payload,
        policy=policy,
        selected_ranker=selected_ranker,
        top_k_files=int(top_k_files),
        candidate_relative_threshold=float(candidate_relative_threshold),
        refine_enabled=bool(refine_enabled),
        rank_candidates=rank_candidates,
        index_hash=index_hash,
        cochange_enabled=bool(cochange_enabled),
        cochange_cache_path=str(cochange_cache_path),
        cochange_lookback_commits=int(cochange_lookback_commits),
        cochange_half_life_days=float(cochange_half_life_days),
        cochange_neighbor_cap=int(cochange_neighbor_cap),
        cochange_top_neighbors=int(cochange_top_neighbors),
        cochange_boost_weight=float(cochange_boost_weight),
        cochange_min_neighbor_score=float(cochange_min_neighbor_score),
        cochange_max_boost=float(cochange_max_boost),
        scip_enabled=bool(scip_enabled),
        scip_index_path=str(scip_index_path),
        scip_provider=str(scip_provider),
        scip_generate_fallback=bool(scip_generate_fallback),
        scip_base_weight=float(scip_base_weight or SCIP_BASE_WEIGHT),
        embedding_index_path=str(embedding_index_path),
        embedding_enabled=bool(embedding_enabled),
        embedding_provider=str(embedding_provider),
        embedding_model=str(embedding_model),
        embedding_dimension=int(embedding_dimension),
        embedding_rerank_pool=int(embedding_rerank_pool),
        embedding_lexical_weight=float(embedding_lexical_weight),
        embedding_semantic_weight=float(embedding_semantic_weight),
        embedding_min_similarity=float(embedding_min_similarity),
        embedding_fail_open=bool(embedding_fail_open),
        feedback_enabled=bool(feedback_enabled),
        feedback_path=str(feedback_path),
        feedback_max_entries=int(feedback_max_entries),
        feedback_boost_per_select=float(feedback_boost_per_select),
        feedback_max_boost=float(feedback_max_boost),
        feedback_decay_days=float(feedback_decay_days),
        multi_channel_rrf_enabled=bool(multi_channel_rrf_enabled),
        multi_channel_rrf_k=int(multi_channel_rrf_k),
        multi_channel_rrf_pool_cap=int(multi_channel_rrf_pool_cap),
        multi_channel_rrf_code_cap=int(multi_channel_rrf_code_cap),
        multi_channel_rrf_docs_cap=int(multi_channel_rrf_docs_cap),
        multi_channel_rrf_memory_cap=int(multi_channel_rrf_memory_cap),
        retrieval_refinement=retrieval_refinement,
        refine_candidate_pool_fn=refine_candidate_pool_fn,
        postprocess_candidates_fn=postprocess_candidates_fn,
        apply_structural_rerank_fn=apply_structural_rerank_fn,
        apply_semantic_candidate_rerank_fn=apply_semantic_candidate_rerank_fn,
        apply_feedback_boost_fn=apply_feedback_boost_fn,
        apply_multi_channel_rrf_fusion_fn=apply_multi_channel_rrf_fusion_fn,
        merge_candidate_lists_fn=merge_candidate_lists_fn,
        resolve_embedding_runtime_config_fn=resolve_embedding_runtime_config_fn,
        build_embedding_stats_fn=build_embedding_stats_fn,
        rerank_cross_encoder_with_time_budget_fn=(
            rerank_cross_encoder_with_time_budget_fn
        ),
        mark_timing_fn=mark_timing_fn,
    )
    filtered = apply_benchmark_candidate_filters_fn(
        candidates=list(candidate_fusion.candidates),
        benchmark_filter_payload=benchmark_filter_payload,
        filter_candidate_rows_fn=filter_candidate_rows_fn,
    )
    chunk_selection = run_index_chunk_selection_fn(
        root=root,
        query=query,
        files_map=files_map,
        candidates=list(filtered.candidates),
        terms=terms,
        policy=policy,
        top_k_files=int(top_k_files),
        chunk_top_k=int(chunk_top_k),
        chunk_per_file_limit=int(chunk_per_file_limit),
        chunk_token_budget=int(chunk_token_budget),
        chunk_disclosure=str(chunk_disclosure),
        chunk_snippet_max_lines=int(chunk_snippet_max_lines),
        chunk_snippet_max_chars=int(chunk_snippet_max_chars),
        tokenizer_model=str(tokenizer_model),
        chunk_diversity_enabled=bool(chunk_diversity_enabled),
        chunk_diversity_path_penalty=float(chunk_diversity_path_penalty),
        chunk_diversity_symbol_family_penalty=float(
            chunk_diversity_symbol_family_penalty
        ),
        chunk_diversity_kind_penalty=float(chunk_diversity_kind_penalty),
        chunk_diversity_locality_penalty=float(chunk_diversity_locality_penalty),
        chunk_diversity_locality_window=int(chunk_diversity_locality_window),
        chunk_topological_shield_enabled=bool(chunk_topological_shield_enabled),
        chunk_topological_shield_mode=str(chunk_topological_shield_mode),
        chunk_topological_shield_max_attenuation=float(
            chunk_topological_shield_max_attenuation
        ),
        chunk_topological_shield_shared_parent_attenuation=float(
            chunk_topological_shield_shared_parent_attenuation
        ),
        chunk_topological_shield_adjacency_attenuation=float(
            chunk_topological_shield_adjacency_attenuation
        ),
        chunk_scoring_config=dict(resolved_chunk_scoring_config),
        chunk_guard_enabled=bool(chunk_guard_enabled),
        chunk_guard_mode=str(chunk_guard_mode),
        chunk_guard_lambda_penalty=float(chunk_guard_lambda_penalty),
        chunk_guard_min_pool=int(chunk_guard_min_pool),
        chunk_guard_max_pool=int(chunk_guard_max_pool),
        chunk_guard_min_marginal_utility=float(chunk_guard_min_marginal_utility),
        chunk_guard_compatibility_min_overlap=float(
            chunk_guard_compatibility_min_overlap
        ),
        embedding_enabled=bool(embedding_enabled),
        embedding_lexical_weight=float(embedding_lexical_weight),
        embedding_semantic_weight=float(embedding_semantic_weight),
        embedding_min_similarity=float(embedding_min_similarity),
        select_index_chunks_fn=select_index_chunks_fn,
        index_hash=index_hash,
        embeddings_payload=candidate_fusion.embeddings_payload,
        semantic_embedding_provider_impl=(
            candidate_fusion.semantic_embedding_provider_impl
        ),
        semantic_cross_encoder_provider=(
            candidate_fusion.semantic_cross_encoder_provider
        ),
        apply_chunk_selection_fn=apply_chunk_selection_fn,
        mark_timing_fn=mark_timing_fn,
        rerank_rows_embeddings_with_time_budget_fn=(
            rerank_rows_embeddings_with_time_budget_fn
        ),
        rerank_rows_cross_encoder_with_time_budget_fn=(
            rerank_rows_cross_encoder_with_time_budget_fn
        ),
    )
    return IndexPostGenerationRuntimeResult(
        candidates=list(filtered.candidates),
        second_pass_payload=candidate_fusion.second_pass_payload,
        refine_pass_payload=candidate_fusion.refine_pass_payload,
        cochange_payload=candidate_fusion.cochange_payload,
        scip_payload=candidate_fusion.scip_payload,
        graph_lookup_payload=candidate_fusion.graph_lookup_payload,
        embeddings_payload=candidate_fusion.embeddings_payload,
        feedback_payload=candidate_fusion.feedback_payload,
        multi_channel_fusion_payload=candidate_fusion.multi_channel_fusion_payload,
        semantic_embedding_provider_impl=(
            candidate_fusion.semantic_embedding_provider_impl
        ),
        semantic_cross_encoder_provider=(
            candidate_fusion.semantic_cross_encoder_provider
        ),
        benchmark_filter_payload=filtered.benchmark_filter_payload,
        candidate_chunks=chunk_selection.candidate_chunks,
        chunk_metrics=chunk_selection.chunk_metrics,
        chunk_semantic_rerank_payload=chunk_selection.chunk_semantic_rerank_payload,
        topological_shield_payload=chunk_selection.topological_shield_payload,
        chunk_guard_payload=chunk_selection.chunk_guard_payload,
        retrieval_refinement_payload=candidate_fusion.retrieval_refinement_payload,
    )


__all__ = ["IndexPostGenerationRuntimeResult", "run_index_post_generation_runtime"]
