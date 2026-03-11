from __future__ import annotations

import importlib

from ace_lite.embeddings import (
    BGEM3EmbeddingProvider,
    EmbeddingIndexStats,
    HashEmbeddingProvider,
    build_or_load_embedding_index,
    rerank_rows_with_embeddings,
)


def test_embeddings_facade_exports_match_split_modules() -> None:
    providers_module = importlib.import_module("ace_lite.embeddings_providers")
    index_store_module = importlib.import_module("ace_lite.embeddings_index_store")
    rerank_module = importlib.import_module("ace_lite.embeddings_rerank")

    assert HashEmbeddingProvider is providers_module.HashEmbeddingProvider
    assert BGEM3EmbeddingProvider is providers_module.BGEM3EmbeddingProvider
    assert build_or_load_embedding_index is index_store_module.build_or_load_embedding_index
    assert EmbeddingIndexStats is rerank_module.EmbeddingIndexStats
    assert rerank_rows_with_embeddings is rerank_module.rerank_rows_with_embeddings
