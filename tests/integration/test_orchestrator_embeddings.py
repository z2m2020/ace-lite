from __future__ import annotations

from pathlib import Path

import pytest

from ace_lite.memory import NullMemoryProvider
from ace_lite.orchestrator import AceOrchestrator
from ace_lite.orchestrator_config import OrchestratorConfig


def _seed_repo(root: Path) -> None:
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "auth.py").write_text(
        "def validate_token(token: str) -> bool:\n    return bool(token)\n",
        encoding="utf-8",
    )
    (src / "token.py").write_text(
        "def parse_token(raw: str) -> str:\n    return raw.strip()\n",
        encoding="utf-8",
    )


def _base_config(
    *,
    tmp_path: Path,
    fake_skill_manifest,
    **overrides,
) -> OrchestratorConfig:
    return OrchestratorConfig(
        skills={"manifest": fake_skill_manifest},
        index={
            "languages": ["python"],
            "cache_path": tmp_path / "context-map" / "index.json",
        },
        repomap={"enabled": False},
        cochange={"enabled": False},
        scip={"enabled": False},
        **overrides,
    )


def test_orchestrator_emits_embedding_payload_when_enabled(
    tmp_path: Path, fake_skill_manifest
) -> None:
    _seed_repo(tmp_path)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        embeddings={
            "enabled": True,
            "provider": "hash",
            "model": "hash-v1",
            "dimension": 64,
            "index_path": "context-map/embeddings/index.json",
            "rerank_pool": 8,
        },
    )
    orch = AceOrchestrator(memory_provider=NullMemoryProvider(), config=config)

    payload = orch.plan(query="validate auth token", repo="demo", root=str(tmp_path))
    embeddings = payload["index"]["embeddings"]

    assert embeddings["enabled"] is True
    assert embeddings["provider"] == "hash"
    assert embeddings["fallback"] is False
    assert int(embeddings.get("reranked_count", 0) or 0) >= 1
    assert (tmp_path / "context-map" / "embeddings" / "index.json").exists()


def test_orchestrator_embedding_provider_flag_off_preserves_default_candidates(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    _seed_repo(tmp_path)

    baseline = AceOrchestrator(
        memory_provider=NullMemoryProvider(),
        config=_base_config(tmp_path=tmp_path, fake_skill_manifest=fake_skill_manifest),
    ).plan(query="validate auth token", repo="demo", root=str(tmp_path))

    gated = AceOrchestrator(
        memory_provider=NullMemoryProvider(),
        config=_base_config(
            tmp_path=tmp_path,
            fake_skill_manifest=fake_skill_manifest,
            embeddings={
                "enabled": False,
                "provider": "hash_colbert",
                "model": "hash-colbert-v1",
                "rerank_pool": 8,
                "fail_open": True,
            },
        ),
    ).plan(query="validate auth token", repo="demo", root=str(tmp_path))

    assert [
        item.get("path")
        for item in baseline["index"]["candidate_files"]
        if isinstance(item, dict)
    ] == [
        item.get("path")
        for item in gated["index"]["candidate_files"]
        if isinstance(item, dict)
    ]
    assert [
        item.get("path")
        for item in baseline["index"]["candidate_chunks"]
        if isinstance(item, dict)
    ] == [
        item.get("path")
        for item in gated["index"]["candidate_chunks"]
        if isinstance(item, dict)
    ]
    assert baseline["index"]["embeddings"]["enabled"] is False
    assert gated["index"]["embeddings"]["enabled"] is False
    assert gated["index"]["embeddings"]["semantic_rerank_applied"] is False


def test_orchestrator_embedding_fail_open_on_unsupported_provider(
    tmp_path: Path, fake_skill_manifest
) -> None:
    _seed_repo(tmp_path)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        embeddings={
            "enabled": True,
            "provider": "unsupported-provider",
            "fail_open": True,
        },
    )
    orch = AceOrchestrator(memory_provider=NullMemoryProvider(), config=config)

    payload = orch.plan(query="validate auth token", repo="demo", root=str(tmp_path))
    embeddings = payload["index"]["embeddings"]

    assert embeddings["enabled"] is False
    assert embeddings["fallback"] is True
    assert "unsupported_provider" in str(embeddings.get("warning", ""))


def test_orchestrator_emits_hash_cross_embedding_payload(
    tmp_path: Path, fake_skill_manifest
) -> None:
    _seed_repo(tmp_path)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        embeddings={
            "enabled": True,
            "provider": "hash_cross",
            "model": "hash-cross-v1",
            "rerank_pool": 8,
        },
    )
    orch = AceOrchestrator(memory_provider=NullMemoryProvider(), config=config)

    payload = orch.plan(query="validate auth token", repo="demo", root=str(tmp_path))
    embeddings = payload["index"]["embeddings"]

    assert embeddings["enabled"] is True
    assert embeddings["provider"] == "hash_cross"
    assert embeddings["fallback"] is False
    assert int(embeddings.get("reranked_count", 0) or 0) >= 1


def test_orchestrator_bge_provider_fail_open_on_missing_dependency(
    tmp_path: Path,
    fake_skill_manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)

    def _raise_backend_error() -> tuple[type[object], type[object]]:
        raise RuntimeError("sentence-transformers missing")

    monkeypatch.setattr(
        "ace_lite.embeddings_providers._load_sentence_transformer_backend",
        _raise_backend_error,
    )

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        embeddings={
            "enabled": True,
            "provider": "bge_m3",
            "model": "BAAI/bge-m3",
            "fail_open": True,
        },
    )
    orch = AceOrchestrator(memory_provider=NullMemoryProvider(), config=config)

    payload = orch.plan(query="validate auth token", repo="demo", root=str(tmp_path))
    embeddings = payload["index"]["embeddings"]

    assert embeddings["enabled"] is True
    assert embeddings["provider"] == "bge_m3"
    assert embeddings["fallback"] is True
    assert embeddings["model"] == "BAAI/bge-m3"
    assert int(embeddings.get("dimension", 0) or 0) == 1024
    assert embeddings["auto_normalized"] is True
    assert "dimension" in list(embeddings.get("auto_normalized_fields", []))
    assert "sentence-transformers" in str(embeddings.get("warning", ""))


def test_orchestrator_bge_reranker_normalizes_runtime_defaults_on_fail_open(
    tmp_path: Path,
    fake_skill_manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)

    def _raise_backend_error() -> tuple[type[object], type[object]]:
        raise RuntimeError("sentence-transformers missing")

    monkeypatch.setattr(
        "ace_lite.embeddings_providers._load_sentence_transformer_backend",
        _raise_backend_error,
    )

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        embeddings={
            "enabled": True,
            "provider": "bge_reranker",
            "model": "hash-v1",
            "dimension": 256,
            "fail_open": True,
        },
    )
    orch = AceOrchestrator(memory_provider=NullMemoryProvider(), config=config)

    payload = orch.plan(query="validate auth token", repo="demo", root=str(tmp_path))
    embeddings = payload["index"]["embeddings"]

    assert embeddings["enabled"] is True
    assert embeddings["provider"] == "bge_reranker"
    assert embeddings["fallback"] is True
    assert embeddings["model"] == "BAAI/bge-reranker-base"
    assert int(embeddings.get("dimension", 0) or 0) == 1
    assert embeddings["auto_normalized"] is True
    normalized_fields = list(embeddings.get("auto_normalized_fields", []))
    assert "model" in normalized_fields
    assert "dimension" in normalized_fields
    assert "sentence-transformers" in str(embeddings.get("warning", ""))


def test_orchestrator_cross_encoder_time_budget_fail_open(
    tmp_path: Path,
    fake_skill_manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)

    def _raise_timeout(**kwargs):
        _ = kwargs
        raise TimeoutError("cross_encoder_time_budget_exceeded:90ms")

    monkeypatch.setattr(
        "ace_lite.pipeline.stages.index._rerank_cross_encoder_with_time_budget",
        _raise_timeout,
    )

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        embeddings={
            "enabled": True,
            "provider": "hash_cross",
            "model": "hash-cross-v1",
            "rerank_pool": 8,
            "fail_open": True,
        },
    )
    orch = AceOrchestrator(memory_provider=NullMemoryProvider(), config=config)

    payload = orch.plan(query="validate auth token", repo="demo", root=str(tmp_path))
    embeddings = payload["index"]["embeddings"]

    assert embeddings["enabled"] is True
    assert embeddings["provider"] == "hash_cross"
    assert embeddings["fallback"] is True
    assert int(embeddings.get("time_budget_base_ms", 0) or 0) >= int(
        embeddings.get("time_budget_ms", 0) or 0
    )
    assert int(embeddings.get("time_budget_ms", 0) or 0) > 0
    assert embeddings["adaptive_budget_applied"] is True
    assert int(embeddings.get("rerank_pool_effective", 0) or 0) <= 8
    assert embeddings["time_budget_exceeded"] is True
    assert embeddings["semantic_rerank_applied"] is False
    assert "time_budget_exceeded" in str(embeddings.get("warning", ""))


def test_orchestrator_chunk_semantic_rerank_applies_for_doc_intent(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    _seed_repo(tmp_path)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        retrieval={"retrieval_policy": "doc_intent"},
        chunking={
            "top_k": 12,
            "per_file_limit": 2,
            "token_budget": 256,
        },
        embeddings={
            "enabled": True,
            "provider": "hash",
            "model": "hash-v1",
            "dimension": 64,
            "index_path": "context-map/embeddings/index.json",
            "rerank_pool": 8,
            "fail_open": True,
        },
    )
    orch = AceOrchestrator(memory_provider=NullMemoryProvider(), config=config)

    payload = orch.plan(
        query="how does validate_token work and where is it implemented",
        repo="demo",
        root=str(tmp_path),
    )

    index_payload = payload["index"]
    assert index_payload["policy_name"] == "doc_intent"

    chunk_semantic = index_payload["chunk_semantic_rerank"]
    assert chunk_semantic["enabled"] is True
    assert chunk_semantic["reason"] == "ok"
    assert str(Path(str(chunk_semantic.get("index_path", ""))).as_posix()).endswith(
        "context-map/embeddings/chunks.index.json"
    )
    assert int(chunk_semantic.get("time_budget_ms", 0) or 0) > 0
    assert chunk_semantic["fallback"] is False
    assert chunk_semantic["time_budget_exceeded"] is False
    assert int(chunk_semantic.get("reranked_count", 0) or 0) >= 1

    chunks = index_payload["candidate_chunks"]
    assert chunks
    assert isinstance(chunks[0], dict)
    assert "score_fused" in chunks[0]
    assert "score_embedding" in chunks[0]

    stage_metrics = payload["observability"]["stage_metrics"]
    index_metric = next(item for item in stage_metrics if item["stage"] == "index")
    tags = index_metric["tags"]
    assert tags["chunk_semantic_rerank_enabled"] is True
    assert tags["chunk_semantic_rerank_reason"] == "ok"
    assert float(tags["chunk_semantic_rerank_ratio"]) > 0.0
    assert int(tags["chunk_semantic_time_budget_ms"]) > 0
    assert tags["chunk_semantic_time_budget_exceeded"] is False


def test_orchestrator_chunk_semantic_rerank_fail_open_on_timeout(
    tmp_path: Path,
    fake_skill_manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)

    def _raise_timeout(**kwargs):
        _ = kwargs
        raise TimeoutError("chunk_embedding_time_budget_exceeded:1ms")

    monkeypatch.setattr(
        "ace_lite.pipeline.stages.index._rerank_rows_embeddings_with_time_budget",
        _raise_timeout,
    )

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        retrieval={"retrieval_policy": "doc_intent"},
        chunking={
            "top_k": 12,
            "per_file_limit": 2,
            "token_budget": 256,
        },
        embeddings={
            "enabled": True,
            "provider": "hash",
            "model": "hash-v1",
            "dimension": 64,
            "index_path": "context-map/embeddings/index.json",
            "rerank_pool": 8,
            "fail_open": True,
        },
    )
    orch = AceOrchestrator(memory_provider=NullMemoryProvider(), config=config)

    payload = orch.plan(
        query="how does validate_token work and where is it implemented",
        repo="demo",
        root=str(tmp_path),
    )

    chunk_semantic = payload["index"]["chunk_semantic_rerank"]
    assert chunk_semantic["enabled"] is True
    assert chunk_semantic["fallback"] is True
    assert chunk_semantic["reason"] == "fail_open"
    assert chunk_semantic["time_budget_exceeded"] is True
    assert "time_budget" in str(chunk_semantic.get("warning", "")).lower()

    stage_metrics = payload["observability"]["stage_metrics"]
    index_metric = next(item for item in stage_metrics if item["stage"] == "index")
    tags = index_metric["tags"]
    assert tags["chunk_semantic_time_budget_exceeded"] is True
    assert float(tags["chunk_semantic_rerank_ratio"]) == 0.0


def test_orchestrator_chunk_semantic_rerank_uses_cross_encoder_provider_when_configured(
    tmp_path: Path,
    fake_skill_manifest,
) -> None:
    _seed_repo(tmp_path)

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        retrieval={"retrieval_policy": "doc_intent"},
        chunking={
            "top_k": 12,
            "per_file_limit": 2,
            "token_budget": 256,
        },
        embeddings={
            "enabled": True,
            "provider": "hash_cross",
            "model": "hash-cross-v1",
            "rerank_pool": 8,
            "fail_open": True,
        },
    )
    orch = AceOrchestrator(memory_provider=NullMemoryProvider(), config=config)

    payload = orch.plan(
        query="how does validate_token work and where is it implemented",
        repo="demo",
        root=str(tmp_path),
    )

    chunk_semantic = payload["index"]["chunk_semantic_rerank"]
    assert chunk_semantic["enabled"] is True
    assert chunk_semantic["provider"] == "hash_cross"
    assert chunk_semantic["reason"] == "ok"
    assert int(chunk_semantic.get("reranked_count", 0) or 0) >= 1

    chunks = payload["index"]["candidate_chunks"]
    assert chunks
    assert isinstance(chunks[0], dict)
    assert "score_fused" in chunks[0]


def test_orchestrator_chunk_semantic_rerank_cross_encoder_fail_open_on_timeout(
    tmp_path: Path,
    fake_skill_manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_repo(tmp_path)

    def _raise_timeout(**kwargs):
        _ = kwargs
        raise TimeoutError("chunk_cross_encoder_time_budget_exceeded:40ms")

    monkeypatch.setattr(
        "ace_lite.pipeline.stages.index._rerank_rows_cross_encoder_with_time_budget",
        _raise_timeout,
    )

    config = _base_config(
        tmp_path=tmp_path,
        fake_skill_manifest=fake_skill_manifest,
        retrieval={"retrieval_policy": "doc_intent"},
        chunking={
            "top_k": 12,
            "per_file_limit": 2,
            "token_budget": 256,
        },
        embeddings={
            "enabled": True,
            "provider": "hash_cross",
            "model": "hash-cross-v1",
            "rerank_pool": 8,
            "fail_open": True,
        },
    )
    orch = AceOrchestrator(memory_provider=NullMemoryProvider(), config=config)

    payload = orch.plan(
        query="how does validate_token work and where is it implemented",
        repo="demo",
        root=str(tmp_path),
    )

    chunk_semantic = payload["index"]["chunk_semantic_rerank"]
    assert chunk_semantic["enabled"] is True
    assert chunk_semantic["provider"] == "hash_cross"
    assert chunk_semantic["fallback"] is True
    assert chunk_semantic["reason"] == "fail_open"
    assert chunk_semantic["time_budget_exceeded"] is True

    stage_metrics = payload["observability"]["stage_metrics"]
    index_metric = next(item for item in stage_metrics if item["stage"] == "index")
    tags = index_metric["tags"]
    assert tags["chunk_semantic_time_budget_exceeded"] is True
