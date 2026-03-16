from __future__ import annotations

from ace_lite.orchestrator_config import OrchestratorConfig


def test_orchestrator_config_accepts_embedding_section_payload() -> None:
    config = OrchestratorConfig(
        embeddings={
            "enabled": True,
            "provider": "hash",
            "model": "hash-v2",
            "dimension": 384,
            "index_path": "context-map/embeddings/custom.json",
            "rerank_pool": 16,
            "lexical_weight": 0.65,
            "semantic_weight": 0.35,
            "min_similarity": 0.05,
            "fail_open": False,
        }
    )

    assert config.embeddings.enabled is True
    assert config.embeddings.provider == "hash"
    assert config.embeddings.model == "hash-v2"
    assert config.embeddings.dimension == 384
    assert str(config.embeddings.index_path) == "context-map/embeddings/custom.json"
    assert config.embeddings.rerank_pool == 16
    assert config.embeddings.lexical_weight == 0.65
    assert config.embeddings.semantic_weight == 0.35
    assert config.embeddings.min_similarity == 0.05
    assert config.embeddings.fail_open is False


def test_orchestrator_config_preserves_unknown_embedding_provider_for_fail_open() -> None:
    config = OrchestratorConfig(
        embeddings={
            "enabled": True,
            "provider": " unsupported-provider ",
        }
    )

    assert config.embeddings.provider == "unsupported-provider"
