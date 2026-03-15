from __future__ import annotations

from ace_lite.embeddings import (
    BGE_M3_DEFAULT_MODEL,
    OLLAMA_DEFAULT_DIMENSION,
    OLLAMA_DEFAULT_MODEL,
)
from ace_lite.index_stage import (
    build_embedding_stats,
    resolve_embedding_runtime_config,
)


def test_resolve_embedding_runtime_config_normalizes_provider_defaults() -> None:
    ollama = resolve_embedding_runtime_config(
        provider="ollama",
        model="hash-v1",
        dimension=256,
    )
    bge = resolve_embedding_runtime_config(
        provider="bge_m3",
        model="",
        dimension=256,
    )
    cross = resolve_embedding_runtime_config(
        provider="hash_cross",
        model="",
        dimension=128,
    )

    assert ollama.provider == "ollama"
    assert ollama.model == OLLAMA_DEFAULT_MODEL
    assert ollama.dimension == OLLAMA_DEFAULT_DIMENSION
    assert "model" in ollama.normalized_fields
    assert "dimension" in ollama.normalized_fields

    assert bge.model == BGE_M3_DEFAULT_MODEL
    assert bge.dimension == 1024
    assert "bge_m3_default_model" in bge.notes
    assert "bge_m3_default_dimension" in bge.notes

    assert cross.model == "hash-cross-v1"
    assert cross.dimension == 1
    assert "hash_cross_dimension_forced" in cross.notes


def test_build_embedding_stats_coerces_ranges() -> None:
    payload = build_embedding_stats(
        enabled=True,
        provider="ollama",
        model="demo",
        dimension=0,
        index_path="context-map/embeddings/index.json",
        rerank_pool=-1,
        lexical_weight=-0.5,
        semantic_weight=0.7,
        fallback=True,
        warning="fallback",
    )

    assert payload["enabled"] is True
    assert payload["provider"] == "ollama"
    assert payload["model"] == "demo"
    assert payload["dimension"] == 1
    assert payload["rerank_pool"] == 0
    assert payload["lexical_weight"] == 0.0
    assert payload["semantic_weight"] == 0.7
    assert payload["fallback"] is True
    assert payload["warning"] == "fallback"
