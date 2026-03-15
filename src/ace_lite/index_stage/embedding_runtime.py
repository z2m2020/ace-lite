from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ace_lite.embeddings import (
    BGE_M3_DEFAULT_MODEL,
    BGE_RERANKER_DEFAULT_MODEL,
    OLLAMA_DEFAULT_DIMENSION,
    OLLAMA_DEFAULT_MODEL,
    EmbeddingIndexStats,
)


@dataclass(frozen=True, slots=True)
class EmbeddingRuntimeConfig:
    provider: str
    model: str
    dimension: int
    normalized_fields: tuple[str, ...]
    notes: tuple[str, ...]


def build_embedding_stats(
    *,
    enabled: bool,
    provider: str,
    model: str,
    dimension: int,
    index_path: str | Path,
    rerank_pool: int,
    lexical_weight: float,
    semantic_weight: float,
    fallback: bool,
    warning: str | None,
) -> dict[str, object]:
    return EmbeddingIndexStats(
        enabled=bool(enabled),
        provider=str(provider),
        model=str(model),
        dimension=max(1, int(dimension)),
        cache_hit=False,
        index_path=str(index_path),
        indexed_files=0,
        rerank_pool=max(0, int(rerank_pool)),
        reranked_count=0,
        lexical_weight=max(0.0, float(lexical_weight)),
        semantic_weight=max(0.0, float(semantic_weight)),
        similarity_mean=0.0,
        similarity_max=0.0,
        fallback=bool(fallback),
        warning=warning,
    ).to_dict()


def resolve_embedding_runtime_config(
    *,
    provider: str,
    model: str,
    dimension: int,
) -> EmbeddingRuntimeConfig:
    provider_name = str(provider or "hash").strip().lower() or "hash"
    configured_model = str(model or "").strip()
    configured_dimension = max(8, int(dimension))

    runtime_model = configured_model
    runtime_dimension = configured_dimension
    normalized_fields: list[str] = []
    notes: list[str] = []

    if provider_name == "hash":
        if not runtime_model:
            runtime_model = "hash-v1"
            normalized_fields.append("model")
            notes.append("hash_default_model")
    elif provider_name == "hash_cross":
        if not runtime_model:
            runtime_model = "hash-cross-v1"
            normalized_fields.append("model")
            notes.append("hash_cross_default_model")
        if configured_dimension != 1:
            runtime_dimension = 1
            normalized_fields.append("dimension")
            notes.append("hash_cross_dimension_forced")
    elif provider_name == "hash_colbert":
        if not runtime_model:
            runtime_model = "hash-colbert-v1"
            normalized_fields.append("model")
            notes.append("hash_colbert_default_model")
        if configured_dimension != 1:
            runtime_dimension = 1
            normalized_fields.append("dimension")
            notes.append("hash_colbert_dimension_forced")
    elif provider_name == "bge_m3":
        if not runtime_model or runtime_model in {"hash-v1", "hash-cross-v1"}:
            runtime_model = BGE_M3_DEFAULT_MODEL
            normalized_fields.append("model")
            notes.append("bge_m3_default_model")
        if configured_dimension == 256:
            runtime_dimension = 1024
            normalized_fields.append("dimension")
            notes.append("bge_m3_default_dimension")
    elif provider_name == "bge_reranker":
        if not runtime_model or runtime_model in {"hash-v1", "hash-cross-v1"}:
            runtime_model = BGE_RERANKER_DEFAULT_MODEL
            normalized_fields.append("model")
            notes.append("bge_reranker_default_model")
        if configured_dimension != 1:
            runtime_dimension = 1
            normalized_fields.append("dimension")
            notes.append("bge_reranker_dimension_forced")
    elif provider_name == "ollama":
        if not runtime_model or runtime_model in {"hash-v1", "hash-cross-v1"}:
            runtime_model = OLLAMA_DEFAULT_MODEL
            normalized_fields.append("model")
            notes.append("ollama_default_model")
        if configured_dimension == 256:
            runtime_dimension = OLLAMA_DEFAULT_DIMENSION
            normalized_fields.append("dimension")
            notes.append("ollama_default_dimension")

    return EmbeddingRuntimeConfig(
        provider=provider_name,
        model=runtime_model,
        dimension=max(1, int(runtime_dimension)),
        normalized_fields=tuple(dict.fromkeys(normalized_fields)),
        notes=tuple(dict.fromkeys(notes)),
    )


__all__ = [
    "EmbeddingRuntimeConfig",
    "build_embedding_stats",
    "resolve_embedding_runtime_config",
]
