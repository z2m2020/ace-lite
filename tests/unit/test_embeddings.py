from __future__ import annotations

import json
from pathlib import Path

import pytest

from ace_lite.embeddings import (
    BGE_M3_DEFAULT_MODEL,
    BGE_RERANKER_DEFAULT_MODEL,
    BGEM3EmbeddingProvider,
    BGERerankerCrossEncoderProvider,
    HashColbertLateInteractionProvider,
    HashCrossEncoderProvider,
    HashEmbeddingProvider,
    OllamaEmbeddingProvider,
    build_or_load_embedding_index,
    rerank_candidates_with_cross_encoder,
    rerank_candidates_with_embeddings,
    rerank_rows_with_cross_encoder,
    rerank_rows_with_embeddings,
)


def _files_map() -> dict[str, dict[str, object]]:
    return {
        "src/auth.py": {
            "module": "src.auth",
            "language": "python",
            "symbols": [{"qualified_name": "validate_token"}],
            "imports": [{"module": "src.token"}],
            "references": [{"qualified_name": "token.parse"}],
        },
        "src/token.py": {
            "module": "src.token",
            "language": "python",
            "symbols": [{"qualified_name": "parse_token"}],
            "imports": [{"module": "src.auth"}],
            "references": [{"qualified_name": "auth.validate"}],
        },
    }


def test_hash_embedding_provider_is_deterministic() -> None:
    provider = HashEmbeddingProvider(model_name="hash-v1", dim=64)
    vectors = provider.encode(["auth token parser", "auth token parser"])

    assert len(vectors) == 2
    assert vectors[0] == vectors[1]
    assert len(vectors[0]) == 64


def test_hash_colbert_provider_is_deterministic_and_rewards_overlap() -> None:
    provider = HashColbertLateInteractionProvider()

    first = provider.score(
        query="validate token signature",
        texts=["validate token signature", "unrelated text"],
    )
    second = provider.score(
        query="validate token signature",
        texts=["validate token signature", "unrelated text"],
    )

    assert first == second
    assert first[0] > first[1]


def test_build_or_load_embedding_index_reuses_cache(tmp_path: Path) -> None:
    files_map = _files_map()
    provider = HashEmbeddingProvider(model_name="hash-v1", dim=64)
    index_path = tmp_path / "context-map" / "embeddings" / "index.json"

    first_vectors, first_hit = build_or_load_embedding_index(
        files_map=files_map,
        provider=provider,
        index_path=index_path,
        index_hash="index-hash-a",
    )
    second_vectors, second_hit = build_or_load_embedding_index(
        files_map=files_map,
        provider=provider,
        index_path=index_path,
        index_hash="index-hash-a",
    )

    assert first_hit is False
    assert second_hit is True
    assert first_vectors == second_vectors
    assert set(first_vectors.keys()) == {"src/auth.py", "src/token.py"}


def test_build_or_load_embedding_index_refreshes_meta_on_index_hash_change(
    tmp_path: Path,
) -> None:
    files_map = _files_map()
    provider = HashEmbeddingProvider(model_name="hash-v1", dim=64)
    index_path = tmp_path / "context-map" / "embeddings" / "index.json"

    first_vectors, first_hit = build_or_load_embedding_index(
        files_map=files_map,
        provider=provider,
        index_path=index_path,
        index_hash="index-hash-a",
    )
    second_vectors, second_hit = build_or_load_embedding_index(
        files_map=files_map,
        provider=provider,
        index_path=index_path,
        index_hash="index-hash-b",
    )

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    meta = payload.get("meta", {})
    assert first_hit is False
    assert second_hit is False
    assert first_vectors == second_vectors
    assert meta.get("index_hash") == "index-hash-b"


def test_build_or_load_embedding_index_persists_chunk_cache_contract(
    tmp_path: Path,
) -> None:
    files_map = _files_map()
    provider = HashEmbeddingProvider(model_name="hash-v1", dim=64)
    index_path = tmp_path / "context-map" / "embeddings" / "index.json"

    build_or_load_embedding_index(
        files_map=files_map,
        provider=provider,
        index_path=index_path,
        index_hash="index-hash-a",
    )

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    contract = payload.get("meta", {}).get("chunk_cache_contract", {})

    assert contract.get("schema_version") == "chunk-cache-contract-v1"
    assert contract.get("file_count") == 2
    assert contract.get("chunk_count") == 2
    assert contract.get("fingerprint")
    assert contract.get("files", {}).get("src/auth.py", {}).get("fingerprint")


def test_build_or_load_embedding_index_only_recomputes_changed_contract_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ace_lite.embeddings_index_store as embeddings_store_mod

    files_map = _files_map()
    provider = HashEmbeddingProvider(model_name="hash-v1", dim=64)
    index_path = tmp_path / "context-map" / "embeddings" / "index.json"

    build_or_load_embedding_index(
        files_map=files_map,
        provider=provider,
        index_path=index_path,
        index_hash="index-hash-a",
    )

    changed_files_map = _files_map()
    changed_files_map["src/auth.py"]["references"] = [
        {"qualified_name": "token.rotate"}
    ]

    calls: list[str] = []
    original = embeddings_store_mod._build_file_embedding_text

    def counting_build_file_embedding_text(*, path: str, entry: dict[str, object]) -> str:
        calls.append(path)
        return original(path=path, entry=entry)

    monkeypatch.setattr(
        embeddings_store_mod,
        "_build_file_embedding_text",
        counting_build_file_embedding_text,
    )

    build_or_load_embedding_index(
        files_map=changed_files_map,
        provider=provider,
        index_path=index_path,
        index_hash="index-hash-b",
    )

    assert calls == ["src/auth.py"]


def test_build_or_load_embedding_index_mirror_fail_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ace_lite.embeddings_index_store as embeddings_store_mod

    def _raise_mirror_error(**_: object) -> object:
        raise RuntimeError("mirror down")

    monkeypatch.setattr(
        embeddings_store_mod,
        "write_embeddings_mirror",
        _raise_mirror_error,
    )

    files_map = _files_map()
    provider = HashEmbeddingProvider(model_name="hash-v1", dim=64)
    index_path = tmp_path / "context-map" / "embeddings" / "index.json"

    vectors, cache_hit = build_or_load_embedding_index(
        files_map=files_map,
        provider=provider,
        index_path=index_path,
    )

    assert cache_hit is False
    assert vectors
    assert index_path.exists()


def test_rerank_candidates_with_embeddings_is_deterministic(tmp_path: Path) -> None:
    files_map = _files_map()
    provider = HashEmbeddingProvider(model_name="hash-v1", dim=64)
    index_path = tmp_path / "context-map" / "embeddings" / "index.json"
    candidates = [
        {"path": "src/token.py", "score": 2.0},
        {"path": "src/auth.py", "score": 1.0},
    ]

    first_ranked, first_stats = rerank_candidates_with_embeddings(
        candidates=[dict(item) for item in candidates],
        files_map=files_map,
        query="validate auth token",
        provider=provider,
        index_path=index_path,
        rerank_pool=2,
        lexical_weight=0.7,
        semantic_weight=0.3,
        min_similarity=0.0,
    )
    second_ranked, second_stats = rerank_candidates_with_embeddings(
        candidates=[dict(item) for item in candidates],
        files_map=files_map,
        query="validate auth token",
        provider=provider,
        index_path=index_path,
        rerank_pool=2,
        lexical_weight=0.7,
        semantic_weight=0.3,
        min_similarity=0.0,
    )

    assert [row.get("path") for row in first_ranked] == [
        row.get("path") for row in second_ranked
    ]
    assert all("score_fused" in row for row in first_ranked[:2])
    assert first_stats.cache_hit is False
    assert second_stats.cache_hit is True
    assert second_stats.reranked_count == 2


def test_rerank_candidates_with_hash_cross_encoder_is_deterministic(
    tmp_path: Path,
) -> None:
    files_map = _files_map()
    provider = HashCrossEncoderProvider(model_name="hash-cross-v1")
    index_path = tmp_path / "context-map" / "embeddings" / "index.json"
    candidates = [
        {"path": "src/token.py", "score": 2.0},
        {"path": "src/auth.py", "score": 1.0},
    ]

    first_ranked, first_stats = rerank_candidates_with_cross_encoder(
        candidates=[dict(item) for item in candidates],
        files_map=files_map,
        query="validate auth token",
        provider=provider,
        index_path=index_path,
        rerank_pool=2,
        lexical_weight=0.4,
        semantic_weight=0.6,
        min_similarity=0.0,
    )
    second_ranked, second_stats = rerank_candidates_with_cross_encoder(
        candidates=[dict(item) for item in candidates],
        files_map=files_map,
        query="validate auth token",
        provider=provider,
        index_path=index_path,
        rerank_pool=2,
        lexical_weight=0.4,
        semantic_weight=0.6,
        min_similarity=0.0,
    )

    assert [row.get("path") for row in first_ranked] == [
        row.get("path") for row in second_ranked
    ]
    assert first_stats.cache_hit is False
    assert second_stats.cache_hit is False
    assert first_stats.provider == "hash_cross"
    assert second_stats.reranked_count == 2


def test_rerank_rows_with_embeddings_can_reorder_by_semantic_score() -> None:
    provider = HashEmbeddingProvider(model_name="hash-v1", dim=64)
    rows = [
        {"path": "src/irrelevant.py", "score": 2.0},
        {"path": "src/auth.py", "score": 1.0},
    ]
    texts = ["unrelated stuff", "auth token validate"]

    ranked, stats = rerank_rows_with_embeddings(
        rows=[dict(item) for item in rows],
        texts=list(texts),
        query="auth token",
        provider=provider,
        rerank_pool=2,
        lexical_weight=0.2,
        semantic_weight=0.8,
        min_similarity=0.0,
    )

    assert ranked[0]["path"] == "src/auth.py"
    assert all("score_fused" in row for row in ranked[:2])
    assert stats.indexed_files == 0
    assert stats.cache_hit is False
    assert stats.reranked_count == 2


def test_rerank_rows_with_embeddings_row_cache_hit_reuses_vectors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = HashEmbeddingProvider(model_name="hash-v1", dim=64)
    rows = [
        {
            "path": "src/auth.py",
            "qualified_name": "validate_token",
            "kind": "function",
            "lineno": 1,
            "end_lineno": 2,
            "score": 2.0,
        },
        {
            "path": "src/token.py",
            "qualified_name": "parse_token",
            "kind": "function",
            "lineno": 1,
            "end_lineno": 2,
            "score": 1.0,
        },
    ]
    texts = [
        "src/auth.py\nvalidate_token\ndef validate_token(token: str) -> bool",
        "src/token.py\nparse_token\ndef parse_token(raw: str) -> str",
    ]
    index_path = tmp_path / "context-map" / "embeddings" / "chunks.index.json"

    encode_calls: list[list[str]] = []
    original_encode = HashEmbeddingProvider.encode

    def _encode(
        self: HashEmbeddingProvider,
        texts_payload: list[str],
    ) -> list[list[float]]:
        encode_calls.append(list(texts_payload))
        return original_encode(self, texts_payload)

    monkeypatch.setattr(HashEmbeddingProvider, "encode", _encode)

    first_ranked, first_stats = rerank_rows_with_embeddings(
        rows=[dict(item) for item in rows],
        texts=list(texts),
        query="how validate token works",
        provider=provider,
        index_path=index_path,
        index_hash="idx-a",
        rerank_pool=2,
        lexical_weight=0.3,
        semantic_weight=0.7,
        min_similarity=0.0,
    )
    second_ranked, second_stats = rerank_rows_with_embeddings(
        rows=[dict(item) for item in rows],
        texts=list(texts),
        query="how validate token works",
        provider=provider,
        index_path=index_path,
        index_hash="idx-a",
        rerank_pool=2,
        lexical_weight=0.3,
        semantic_weight=0.7,
        min_similarity=0.0,
    )

    assert [row.get("path") for row in first_ranked] == [
        row.get("path") for row in second_ranked
    ]
    assert first_stats.cache_hit is False
    assert second_stats.cache_hit is True
    assert second_stats.indexed_files == 2
    assert index_path.exists()
    assert len(encode_calls) == 3
    assert len(encode_calls[0]) == 1
    assert len(encode_calls[1]) == 2
    assert len(encode_calls[2]) == 1


def test_rerank_rows_with_embeddings_row_cache_reencodes_only_changed_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = HashEmbeddingProvider(model_name="hash-v1", dim=64)
    rows = [
        {
            "path": "src/auth.py",
            "qualified_name": "validate_token",
            "kind": "function",
            "lineno": 1,
            "end_lineno": 2,
            "score": 2.0,
        },
        {
            "path": "src/token.py",
            "qualified_name": "parse_token",
            "kind": "function",
            "lineno": 1,
            "end_lineno": 2,
            "score": 1.0,
        },
    ]
    texts = [
        "src/auth.py\nvalidate_token\ndef validate_token(token: str) -> bool",
        "src/token.py\nparse_token\ndef parse_token(raw: str) -> str",
    ]
    index_path = tmp_path / "context-map" / "embeddings" / "chunks.index.json"

    encode_calls: list[list[str]] = []
    original_encode = HashEmbeddingProvider.encode

    def _encode(
        self: HashEmbeddingProvider,
        texts_payload: list[str],
    ) -> list[list[float]]:
        encode_calls.append(list(texts_payload))
        return original_encode(self, texts_payload)

    monkeypatch.setattr(HashEmbeddingProvider, "encode", _encode)

    rerank_rows_with_embeddings(
        rows=[dict(item) for item in rows],
        texts=list(texts),
        query="how validate token works",
        provider=provider,
        index_path=index_path,
        index_hash="idx-a",
        rerank_pool=2,
        lexical_weight=0.3,
        semantic_weight=0.7,
        min_similarity=0.0,
    )
    encode_calls.clear()

    changed_texts = list(texts)
    changed_texts[1] = "src/token.py\nparse_token\ndef parse_token(raw: str) -> str\n# changed"
    _, second_stats = rerank_rows_with_embeddings(
        rows=[dict(item) for item in rows],
        texts=changed_texts,
        query="how validate token works",
        provider=provider,
        index_path=index_path,
        index_hash="idx-a",
        rerank_pool=2,
        lexical_weight=0.3,
        semantic_weight=0.7,
        min_similarity=0.0,
    )

    assert second_stats.cache_hit is False
    assert len(encode_calls) == 2
    assert len(encode_calls[0]) == 1
    assert len(encode_calls[1]) == 1


def test_rerank_rows_with_embeddings_row_cache_refreshes_index_hash_meta(
    tmp_path: Path,
) -> None:
    provider = HashEmbeddingProvider(model_name="hash-v1", dim=64)
    rows = [
        {"path": "src/auth.py", "qualified_name": "validate_token", "score": 2.0},
        {"path": "src/token.py", "qualified_name": "parse_token", "score": 1.0},
    ]
    texts = [
        "src/auth.py\nvalidate_token\ndef validate_token(token: str) -> bool",
        "src/token.py\nparse_token\ndef parse_token(raw: str) -> str",
    ]
    index_path = tmp_path / "context-map" / "embeddings" / "chunks.index.json"

    _, first_stats = rerank_rows_with_embeddings(
        rows=[dict(item) for item in rows],
        texts=list(texts),
        query="how validate token works",
        provider=provider,
        index_path=index_path,
        index_hash="idx-a",
        rerank_pool=2,
        lexical_weight=0.3,
        semantic_weight=0.7,
        min_similarity=0.0,
    )
    _, second_stats = rerank_rows_with_embeddings(
        rows=[dict(item) for item in rows],
        texts=list(texts),
        query="how validate token works",
        provider=provider,
        index_path=index_path,
        index_hash="idx-b",
        rerank_pool=2,
        lexical_weight=0.3,
        semantic_weight=0.7,
        min_similarity=0.0,
    )

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    meta = payload.get("meta", {})
    assert first_stats.cache_hit is False
    assert second_stats.cache_hit is False
    assert str(meta.get("index_hash")) == "idx-b"


def test_rerank_rows_with_cross_encoder_can_reorder_by_semantic_score() -> None:
    provider = HashCrossEncoderProvider(model_name="hash-cross-v1")
    rows = [
        {"path": "src/irrelevant.py", "score": 2.0},
        {"path": "src/auth.py", "score": 1.0},
    ]
    texts = ["unrelated stuff", "auth token validate"]

    ranked, stats = rerank_rows_with_cross_encoder(
        rows=[dict(item) for item in rows],
        texts=list(texts),
        query="auth token",
        provider=provider,
        rerank_pool=2,
        lexical_weight=0.1,
        semantic_weight=0.9,
        min_similarity=0.0,
    )

    assert ranked[0]["path"] == "src/auth.py"
    assert all("score_fused" in row for row in ranked[:2])
    assert stats.provider == "hash_cross"
    assert stats.indexed_files == 0
    assert stats.cache_hit is False
    assert stats.reranked_count == 2


def test_bge_m3_embedding_provider_uses_lazy_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def encode(
            self,
            texts: list[str],
            *,
            normalize_embeddings: bool,
            batch_size: int,
        ) -> list[list[float]]:
            assert normalize_embeddings is True
            assert batch_size == 8
            return [[float(index + 1), float(len(text))] for index, text in enumerate(texts)]

    class _FakeCrossEncoder:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

    monkeypatch.setattr(
        "ace_lite.embeddings_providers._load_sentence_transformer_backend",
        lambda: (_FakeSentenceTransformer, _FakeCrossEncoder),
    )

    provider = BGEM3EmbeddingProvider(
        model_name=BGE_M3_DEFAULT_MODEL,
        dim=4,
        batch_size=8,
    )
    vectors = provider.encode(["auth", "token"])

    assert len(vectors) == 2
    assert len(vectors[0]) == provider.dimension
    assert vectors[0][0] == 1.0
    assert vectors[1][0] == 2.0


def test_bge_reranker_provider_uses_lazy_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

    class _FakeCrossEncoder:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def predict(self, pairs: list[list[str]]) -> list[object]:
            assert len(pairs) == 3
            return [0.91, [0.42], "bad"]

    monkeypatch.setattr(
        "ace_lite.embeddings_providers._load_sentence_transformer_backend",
        lambda: (_FakeSentenceTransformer, _FakeCrossEncoder),
    )

    provider = BGERerankerCrossEncoderProvider(model_name=BGE_RERANKER_DEFAULT_MODEL)
    scores = provider.score(query="validate auth token", texts=["a", "b", "c"])

    assert scores == [0.91, 0.42, 0.0]


def test_ollama_embedding_provider_can_encode_via_embed_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeResponse:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def _fake_safe_urlopen(request, *, timeout: float):
        assert request.full_url.endswith("/api/embed")
        body = json.loads((request.data or b"{}").decode("utf-8"))
        assert body["model"] == "nomic-embed-text"
        assert body["input"] == ["hello", "world"]
        payload = {
            "model": "nomic-embed-text",
            "embeddings": [
                [3.0, 4.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            ],
        }
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(
        "ace_lite.embeddings_providers.safe_urlopen",
        _fake_safe_urlopen,
    )

    provider = OllamaEmbeddingProvider(
        model_name="nomic-embed-text",
        dim=8,
        base_url="http://ollama.local",
        normalize_embeddings=True,
        batch_size=32,
        timeout_seconds=2.0,
    )
    vectors = provider.encode(["hello", "world"])

    assert len(vectors) == 2
    assert len(vectors[0]) == provider.dimension
    assert vectors[0][0] == pytest.approx(0.6)
    assert vectors[0][1] == pytest.approx(0.8)
    assert sum(abs(value) for value in vectors[1]) == pytest.approx(0.0)


def test_ollama_embedding_provider_falls_back_to_legacy_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeResponse:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    seen: list[str] = []

    def _fake_safe_urlopen(request, *, timeout: float):
        seen.append(request.full_url)
        if request.full_url.endswith("/api/embed"):
            raise RuntimeError("embed endpoint unavailable")
        assert request.full_url.endswith("/api/embeddings")
        body = json.loads((request.data or b"{}").decode("utf-8"))
        prompt = str(body.get("prompt") or "")
        if prompt == "hello":
            payload = {"embedding": [1.0, 0.0]}
        else:
            payload = {"embedding": [0.0, 2.0]}
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(
        "ace_lite.embeddings_providers.safe_urlopen",
        _fake_safe_urlopen,
    )

    provider = OllamaEmbeddingProvider(
        model_name="nomic-embed-text",
        dim=8,
        base_url="http://ollama.local",
        normalize_embeddings=False,
        batch_size=8,
        timeout_seconds=2.0,
    )
    vectors = provider.encode(["hello", "world"])

    assert seen[0].endswith("/api/embed")
    assert any(item.endswith("/api/embeddings") for item in seen[1:])
    assert len(vectors) == 2
    assert len(vectors[0]) == provider.dimension
    assert vectors[0][0] == pytest.approx(1.0)
    assert vectors[1][1] == pytest.approx(2.0)
