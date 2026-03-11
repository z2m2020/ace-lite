"""Candidate refinement and fusion orchestration for the index stage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.embeddings import CrossEncoderProvider
from ace_lite.embeddings import EmbeddingProvider
from ace_lite.index_stage.candidate_postprocess import CandidatePostprocessResult


@dataclass(frozen=True, slots=True)
class CandidateFusionDeps:
    """Injected helper dependencies for the candidate refinement seam."""

    postprocess_candidates: Callable[..., CandidatePostprocessResult]
    apply_structural_rerank: Callable[..., Any]
    apply_semantic_candidate_rerank: Callable[..., Any]
    apply_feedback_boost: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]]
    apply_multi_channel_rrf_fusion: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]]
    merge_candidate_lists: Callable[..., list[dict[str, Any]]]
    resolve_embedding_runtime_config: Callable[..., Any]
    build_embedding_stats: Callable[..., dict[str, Any]]
    rerank_cross_encoder_with_time_budget: Callable[..., tuple[list[dict[str, Any]], Any]]
    mark_timing: Callable[[str, float], None]


@dataclass(slots=True)
class CandidateFusionResult:
    candidates: list[dict[str, Any]]
    second_pass_payload: dict[str, Any]
    refine_pass_payload: dict[str, Any]
    cochange_payload: dict[str, Any]
    scip_payload: dict[str, Any]
    graph_lookup_payload: dict[str, Any]
    embeddings_payload: dict[str, Any]
    feedback_payload: dict[str, Any]
    multi_channel_fusion_payload: dict[str, Any]
    semantic_embedding_provider_impl: EmbeddingProvider | None
    semantic_cross_encoder_provider: CrossEncoderProvider | None


def refine_candidate_pool(
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
    embedding_index_path: str | Path,
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
    deps: CandidateFusionDeps,
) -> CandidateFusionResult:
    """Apply postprocess, rerank, feedback, and multi-channel fusion."""

    timing_started = perf_counter()
    candidate_postprocess_result = deps.postprocess_candidates(
        candidates=candidates,
        files_map=files_map,
        selected_ranker=selected_ranker,
        top_k_files=int(top_k_files),
        candidate_relative_threshold=float(candidate_relative_threshold),
        refine_enabled=bool(refine_enabled),
        rank_candidates=rank_candidates,
        merge_candidate_lists=deps.merge_candidate_lists,
    )
    refined_candidates = list(candidate_postprocess_result.candidates)
    second_pass_payload = candidate_postprocess_result.second_pass_payload
    refine_pass_payload = candidate_postprocess_result.refine_pass_payload
    deps.mark_timing("candidate_postprocess", timing_started)

    structural_rerank = deps.apply_structural_rerank(
        root=root,
        files_map=files_map,
        candidates=refined_candidates,
        memory_paths=memory_paths,
        terms=terms,
        policy=policy,
        cochange_enabled=bool(cochange_enabled),
        cochange_cache_path=str(cochange_cache_path),
        cochange_lookback_commits=int(cochange_lookback_commits),
        cochange_half_life_days=float(cochange_half_life_days),
        cochange_neighbor_cap=int(cochange_neighbor_cap),
        top_k_files=int(top_k_files),
        cochange_top_neighbors=int(cochange_top_neighbors),
        cochange_boost_weight=float(cochange_boost_weight),
        cochange_min_neighbor_score=float(cochange_min_neighbor_score),
        cochange_max_boost=float(cochange_max_boost),
        scip_enabled=bool(scip_enabled),
        scip_index_path=str(scip_index_path),
        scip_provider=str(scip_provider),
        scip_generate_fallback=bool(scip_generate_fallback),
        mark_timing=deps.mark_timing,
    )
    refined_candidates = list(structural_rerank.candidates)
    cochange_payload = structural_rerank.cochange_payload
    scip_payload = structural_rerank.scip_payload
    graph_lookup_payload = structural_rerank.graph_lookup_payload

    semantic_candidate_rerank = deps.apply_semantic_candidate_rerank(
        root=root,
        query=query,
        files_map=files_map,
        candidates=refined_candidates,
        terms=terms,
        index_hash=index_hash,
        embedding_index_path=embedding_index_path,
        embedding_enabled=bool(embedding_enabled),
        embedding_provider=str(embedding_provider),
        embedding_model=str(embedding_model),
        embedding_dimension=int(embedding_dimension),
        embedding_rerank_pool=int(embedding_rerank_pool),
        embedding_lexical_weight=float(embedding_lexical_weight),
        embedding_semantic_weight=float(embedding_semantic_weight),
        embedding_min_similarity=float(embedding_min_similarity),
        embedding_fail_open=bool(embedding_fail_open),
        policy=policy,
        mark_timing=deps.mark_timing,
        resolve_embedding_runtime_config=deps.resolve_embedding_runtime_config,
        build_embedding_stats=deps.build_embedding_stats,
        rerank_cross_encoder_with_time_budget=(
            deps.rerank_cross_encoder_with_time_budget
        ),
    )
    refined_candidates = list(semantic_candidate_rerank.candidates)
    embeddings_payload = semantic_candidate_rerank.embeddings_payload
    semantic_embedding_provider_impl = (
        semantic_candidate_rerank.semantic_embedding_provider_impl
    )
    semantic_cross_encoder_provider = (
        semantic_candidate_rerank.semantic_cross_encoder_provider
    )

    feedback_payload: dict[str, Any] = {
        "enabled": bool(feedback_enabled),
        "reason": "disabled",
        "path": "",
        "event_count": 0,
        "matched_event_count": 0,
        "boosted_candidate_count": 0,
        "boosted_unique_paths": 0,
    }
    timing_started = perf_counter()
    if bool(feedback_enabled) and refined_candidates:
        refined_candidates, feedback_payload = deps.apply_feedback_boost(
            candidates=refined_candidates,
            repo=repo,
            root=root,
            enabled=bool(feedback_enabled),
            configured_path=str(feedback_path),
            max_entries=int(feedback_max_entries),
            boost_per_select=float(feedback_boost_per_select),
            max_boost=float(feedback_max_boost),
            decay_days=float(feedback_decay_days),
            query_terms=terms,
            policy=policy,
        )
    deps.mark_timing("feedback_boost", timing_started)

    multi_channel_fusion_payload: dict[str, Any] = {
        "enabled": bool(multi_channel_rrf_enabled),
        "applied": False,
        "reason": "disabled",
        "rrf_k": max(1, int(multi_channel_rrf_k)),
        "caps": {
            "pool": int(multi_channel_rrf_pool_cap),
            "code": int(multi_channel_rrf_code_cap),
            "docs": int(multi_channel_rrf_docs_cap),
            "memory": int(multi_channel_rrf_memory_cap),
        },
        "channels": {
            "code": {"count": 0, "cap": 0, "top": []},
            "docs": {"count": 0, "cap": 0, "top": []},
            "memory": {"count": 0, "cap": 0, "top": []},
        },
        "fused": {"scored_count": 0, "pool_size": 0, "top": []},
        "warning": None,
    }
    timing_started = perf_counter()
    if bool(multi_channel_rrf_enabled) and refined_candidates:
        refined_candidates, multi_channel_fusion_payload = (
            deps.apply_multi_channel_rrf_fusion(
                candidates=refined_candidates,
                files_map=files_map,
                docs_payload=docs_payload,
                memory_paths=memory_paths,
                top_k_files=int(top_k_files),
                rrf_k=int(multi_channel_rrf_k),
                pool_cap=int(multi_channel_rrf_pool_cap),
                code_cap=int(multi_channel_rrf_code_cap),
                docs_cap=int(multi_channel_rrf_docs_cap),
                memory_cap=int(multi_channel_rrf_memory_cap),
            )
        )
    deps.mark_timing("multi_channel_fusion", timing_started)

    return CandidateFusionResult(
        candidates=list(refined_candidates),
        second_pass_payload=second_pass_payload,
        refine_pass_payload=refine_pass_payload,
        cochange_payload=cochange_payload,
        scip_payload=scip_payload,
        graph_lookup_payload=graph_lookup_payload,
        embeddings_payload=embeddings_payload,
        feedback_payload=feedback_payload,
        multi_channel_fusion_payload=multi_channel_fusion_payload,
        semantic_embedding_provider_impl=semantic_embedding_provider_impl,
        semantic_cross_encoder_provider=semantic_cross_encoder_provider,
    )


__all__ = [
    "CandidateFusionDeps",
    "CandidateFusionResult",
    "refine_candidate_pool",
]
