"""Chunk-selection orchestration wrapper for the index stage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ace_lite.embeddings import CrossEncoderProvider, EmbeddingProvider
from ace_lite.index_stage.chunk_selection import ChunkSelectionResult


@dataclass(frozen=True, slots=True)
class ChunkSelectionRuntimeConfig:
    top_k_files: int
    chunk_top_k: int
    chunk_per_file_limit: int
    chunk_token_budget: int
    chunk_disclosure: str
    chunk_snippet_max_lines: int
    chunk_snippet_max_chars: int
    tokenizer_model: str
    chunk_diversity_enabled: bool
    chunk_diversity_path_penalty: float
    chunk_diversity_symbol_family_penalty: float
    chunk_diversity_kind_penalty: float
    chunk_diversity_locality_penalty: float
    chunk_diversity_locality_window: int
    chunk_topological_shield_enabled: bool
    chunk_topological_shield_mode: str
    chunk_topological_shield_max_attenuation: float
    chunk_topological_shield_shared_parent_attenuation: float
    chunk_topological_shield_adjacency_attenuation: float
    chunk_scoring_config: dict[str, Any]
    chunk_guard_enabled: bool
    chunk_guard_mode: str
    chunk_guard_lambda_penalty: float
    chunk_guard_min_pool: int
    chunk_guard_max_pool: int
    chunk_guard_min_marginal_utility: float
    chunk_guard_compatibility_min_overlap: float
    embedding_enabled: bool
    embedding_lexical_weight: float
    embedding_semantic_weight: float
    embedding_min_similarity: float


@dataclass(frozen=True, slots=True)
class ChunkSelectionDeps:
    apply_chunk_selection: Callable[..., ChunkSelectionResult]
    mark_timing: Callable[[str, float], None]
    rerank_rows_embeddings_with_time_budget: Callable[..., tuple[list[dict[str, Any]], Any]]
    rerank_rows_cross_encoder_with_time_budget: Callable[
        ..., tuple[list[dict[str, Any]], Any]
    ]


def select_index_chunks(
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
    runtime_config: ChunkSelectionRuntimeConfig,
    deps: ChunkSelectionDeps,
) -> ChunkSelectionResult:
    """Run chunk selection using a narrowed runtime config contract."""

    return deps.apply_chunk_selection(
        root=root,
        query=query,
        files_map=files_map,
        candidates=candidates,
        terms=terms,
        top_k_files=int(runtime_config.top_k_files),
        chunk_top_k=int(runtime_config.chunk_top_k),
        chunk_per_file_limit=int(runtime_config.chunk_per_file_limit),
        chunk_token_budget=int(runtime_config.chunk_token_budget),
        chunk_disclosure=str(runtime_config.chunk_disclosure),
        chunk_snippet_max_lines=int(runtime_config.chunk_snippet_max_lines),
        chunk_snippet_max_chars=int(runtime_config.chunk_snippet_max_chars),
        policy=policy,
        tokenizer_model=str(runtime_config.tokenizer_model),
        chunk_diversity_enabled=bool(runtime_config.chunk_diversity_enabled),
        chunk_diversity_path_penalty=float(
            runtime_config.chunk_diversity_path_penalty
        ),
        chunk_diversity_symbol_family_penalty=float(
            runtime_config.chunk_diversity_symbol_family_penalty
        ),
        chunk_diversity_kind_penalty=float(runtime_config.chunk_diversity_kind_penalty),
        chunk_diversity_locality_penalty=float(
            runtime_config.chunk_diversity_locality_penalty
        ),
        chunk_diversity_locality_window=int(
            runtime_config.chunk_diversity_locality_window
        ),
        chunk_topological_shield_enabled=bool(
            runtime_config.chunk_topological_shield_enabled
        ),
        chunk_topological_shield_mode=str(
            runtime_config.chunk_topological_shield_mode
        ),
        chunk_topological_shield_max_attenuation=float(
            runtime_config.chunk_topological_shield_max_attenuation
        ),
        chunk_topological_shield_shared_parent_attenuation=float(
            runtime_config.chunk_topological_shield_shared_parent_attenuation
        ),
        chunk_topological_shield_adjacency_attenuation=float(
            runtime_config.chunk_topological_shield_adjacency_attenuation
        ),
        chunk_scoring_config=dict(runtime_config.chunk_scoring_config),
        chunk_guard_enabled=bool(runtime_config.chunk_guard_enabled),
        chunk_guard_mode=str(runtime_config.chunk_guard_mode),
        chunk_guard_lambda_penalty=float(runtime_config.chunk_guard_lambda_penalty),
        chunk_guard_min_pool=int(runtime_config.chunk_guard_min_pool),
        chunk_guard_max_pool=int(runtime_config.chunk_guard_max_pool),
        chunk_guard_min_marginal_utility=float(
            runtime_config.chunk_guard_min_marginal_utility
        ),
        chunk_guard_compatibility_min_overlap=float(
            runtime_config.chunk_guard_compatibility_min_overlap
        ),
        index_hash=index_hash,
        embedding_enabled=bool(runtime_config.embedding_enabled),
        embedding_lexical_weight=float(runtime_config.embedding_lexical_weight),
        embedding_semantic_weight=float(runtime_config.embedding_semantic_weight),
        embedding_min_similarity=float(runtime_config.embedding_min_similarity),
        embeddings_payload=embeddings_payload,
        semantic_embedding_provider_impl=semantic_embedding_provider_impl,
        semantic_cross_encoder_provider=semantic_cross_encoder_provider,
        mark_timing=deps.mark_timing,
        rerank_rows_embeddings_with_time_budget=(
            deps.rerank_rows_embeddings_with_time_budget
        ),
        rerank_rows_cross_encoder_with_time_budget=(
            deps.rerank_rows_cross_encoder_with_time_budget
        ),
    )


__all__ = ["ChunkSelectionDeps", "ChunkSelectionRuntimeConfig", "select_index_chunks"]
