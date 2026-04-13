"""Compatibility facade for embedding providers, index storage, and rerank helpers."""

from __future__ import annotations

from ace_lite.embeddings_index_store import build_or_load_embedding_index
from ace_lite.embeddings_providers import (
    BGE_M3_DEFAULT_MODEL,
    BGE_RERANKER_DEFAULT_MODEL,
    OLLAMA_DEFAULT_BASE_URL,
    OLLAMA_DEFAULT_DIMENSION,
    OLLAMA_DEFAULT_MODEL,
    BGEM3EmbeddingProvider,
    BGERerankerCrossEncoderProvider,
    CrossEncoderProvider,
    EmbeddingProvider,
    HashColbertLateInteractionProvider,
    HashCrossEncoderProvider,
    HashEmbeddingProvider,
    OllamaEmbeddingProvider,
    SentenceTransformersEmbeddingProvider,
)
from ace_lite.embeddings_rerank import (
    EmbeddingIndexStats,
    rerank_candidates_with_cross_encoder,
    rerank_candidates_with_embeddings,
    rerank_rows_with_cross_encoder,
    rerank_rows_with_embeddings,
)

__all__ = [
    "BGE_M3_DEFAULT_MODEL",
    "BGE_RERANKER_DEFAULT_MODEL",
    "OLLAMA_DEFAULT_BASE_URL",
    "OLLAMA_DEFAULT_DIMENSION",
    "OLLAMA_DEFAULT_MODEL",
    "BGEM3EmbeddingProvider",
    "BGERerankerCrossEncoderProvider",
    "CrossEncoderProvider",
    "EmbeddingIndexStats",
    "EmbeddingProvider",
    "HashColbertLateInteractionProvider",
    "HashCrossEncoderProvider",
    "HashEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "SentenceTransformersEmbeddingProvider",
    "build_or_load_embedding_index",
    "rerank_candidates_with_cross_encoder",
    "rerank_candidates_with_embeddings",
    "rerank_rows_with_cross_encoder",
    "rerank_rows_with_embeddings",
]
