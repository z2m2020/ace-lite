from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ace_lite.embeddings import CrossEncoderProvider, EmbeddingProvider
from ace_lite.index_stage.chunk_pipeline import (
    ChunkSelectionDeps,
    ChunkSelectionRuntimeConfig,
)
from ace_lite.index_stage.chunk_selection import ChunkSelectionResult


def run_index_chunk_selection(
    *,
    root: str,
    query: str,
    files_map: dict[str, Any],
    candidates: list[dict[str, Any]],
    terms: list[str],
    policy: dict[str, Any],
    index_hash: str,
    embeddings_payload: dict[str, Any],
    semantic_embedding_provider_impl: EmbeddingProvider | None,
    semantic_cross_encoder_provider: CrossEncoderProvider | None,
    top_k_files: int,
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
    embedding_enabled: bool,
    embedding_lexical_weight: float,
    embedding_semantic_weight: float,
    embedding_min_similarity: float,
    select_index_chunks_fn: Callable[..., ChunkSelectionResult],
    apply_chunk_selection_fn: Callable[..., ChunkSelectionResult],
    mark_timing_fn: Callable[[str, float], None],
    rerank_rows_embeddings_with_time_budget_fn: Callable[
        ..., tuple[list[dict[str, Any]], Any]
    ],
    rerank_rows_cross_encoder_with_time_budget_fn: Callable[
        ..., tuple[list[dict[str, Any]], Any]
    ],
) -> ChunkSelectionResult:
    return select_index_chunks_fn(
        root=root,
        query=query,
        files_map=files_map,
        candidates=candidates,
        terms=terms,
        policy=policy,
        runtime_config=ChunkSelectionRuntimeConfig(
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
        ),
        index_hash=index_hash,
        embeddings_payload=embeddings_payload,
        semantic_embedding_provider_impl=semantic_embedding_provider_impl,
        semantic_cross_encoder_provider=semantic_cross_encoder_provider,
        deps=ChunkSelectionDeps(
            apply_chunk_selection=apply_chunk_selection_fn,
            mark_timing=mark_timing_fn,
            rerank_rows_embeddings_with_time_budget=(
                rerank_rows_embeddings_with_time_budget_fn
            ),
            rerank_rows_cross_encoder_with_time_budget=(
                rerank_rows_cross_encoder_with_time_budget_fn
            ),
        ),
    )


__all__ = ["run_index_chunk_selection"]
