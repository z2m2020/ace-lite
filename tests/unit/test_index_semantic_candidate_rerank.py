from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from ace_lite.index_stage.semantic_candidate_rerank import (
    apply_semantic_candidate_rerank,
)


@dataclass(frozen=True, slots=True)
class _FakeStats:
    enabled: bool = True
    fallback: bool = False
    reranked_count: int = 0
    similarity_mean: float = 0.0
    similarity_max: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "fallback": self.fallback,
            "reranked_count": self.reranked_count,
            "similarity_mean": self.similarity_mean,
            "similarity_max": self.similarity_max,
        }


def _build_embedding_stats(**kwargs: Any) -> dict[str, Any]:
    return dict(kwargs)


def _resolve_runtime(*, provider: str, model: str, dimension: int) -> Any:
    return SimpleNamespace(
        provider=provider,
        model=model or f"{provider}-model",
        dimension=dimension,
        normalized_fields=("model",),
        notes=("normalized",),
    )


def test_apply_semantic_candidate_rerank_marks_policy_disabled() -> None:
    timings: list[str] = []

    result = apply_semantic_candidate_rerank(
        root=".",
        query="explain the architecture",
        files_map={"src/app.py": {"path": "src/app.py"}},
        candidates=[{"path": "src/app.py", "score": 1.0}],
        terms=["explain", "architecture"],
        index_hash="idx",
        embedding_index_path="context-map/embeddings/index.json",
        embedding_enabled=True,
        embedding_provider="hash",
        embedding_model="hash-v1",
        embedding_dimension=16,
        embedding_rerank_pool=24,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embedding_fail_open=True,
        policy={"embedding_enabled": False, "semantic_rerank_time_budget_ms": 80},
        mark_timing=lambda name, started: timings.append(name),
        resolve_embedding_runtime_config=_resolve_runtime,
        build_embedding_stats=_build_embedding_stats,
        rerank_cross_encoder_with_time_budget=lambda **kwargs: ([], _FakeStats()),
    )

    assert result.candidates == [{"path": "src/app.py", "score": 1.0}]
    assert result.embeddings_payload["enabled"] is False
    assert result.embeddings_payload["warning"] == "policy_disabled"
    assert result.embeddings_payload["runtime_provider"] == "hash"
    assert result.embeddings_payload["runtime_model"] == "hash-v1"
    assert result.embeddings_payload["adaptive_budget_applied"] is True
    assert result.embeddings_payload["time_budget_ms"] == 52
    assert timings == ["embeddings"]


def test_apply_semantic_candidate_rerank_applies_adaptive_budget_to_embedding_path() -> None:
    captured: dict[str, Any] = {}

    def _rerank_embeddings(**kwargs: Any) -> tuple[list[dict[str, Any]], _FakeStats]:
        captured["rerank_pool"] = kwargs["rerank_pool"]
        return list(reversed(kwargs["candidates"])), _FakeStats(
            reranked_count=4,
            similarity_mean=0.42,
            similarity_max=0.84,
        )

    candidates = [
        {"path": f"src/file_{index}.py", "score": float(index)}
        for index in range(10)
    ]
    result = apply_semantic_candidate_rerank(
        root=".",
        query="rank candidates",
        files_map={item["path"]: {"path": item["path"]} for item in candidates},
        candidates=candidates,
        terms=["rank", "candidates"],
        index_hash="idx",
        embedding_index_path="context-map/embeddings/index.json",
        embedding_enabled=True,
        embedding_provider="hash",
        embedding_model="hash-v1",
        embedding_dimension=16,
        embedding_rerank_pool=24,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embedding_fail_open=True,
        policy={
            "embedding_enabled": True,
            "semantic_rerank_time_budget_ms": 100,
            "semantic_rerank_pool_cap": 24,
        },
        mark_timing=lambda name, started: None,
        resolve_embedding_runtime_config=_resolve_runtime,
        build_embedding_stats=_build_embedding_stats,
        rerank_cross_encoder_with_time_budget=lambda **kwargs: ([], _FakeStats()),
        rerank_embeddings_fn=_rerank_embeddings,
    )

    assert captured["rerank_pool"] == 10
    assert result.candidates[0]["path"] == "src/file_9.py"
    assert result.embeddings_payload["time_budget_ms"] == 75
    assert result.embeddings_payload["rerank_pool_effective"] == 10
    assert result.embeddings_payload["runtime_provider"] == "hash"
    assert result.embeddings_payload["semantic_rerank_applied"] is False


def test_apply_semantic_candidate_rerank_marks_cross_encoder_timeout_fail_open() -> None:
    def _timeout_cross_encoder(**kwargs: Any) -> tuple[list[dict[str, Any]], _FakeStats]:
        raise TimeoutError("cross_encoder_time_budget_exceeded:60ms")

    result = apply_semantic_candidate_rerank(
        root=".",
        query="explain the retrieval path",
        files_map={"src/app.py": {"path": "src/app.py"}},
        candidates=[{"path": "src/app.py", "score": 1.0}],
        terms=["explain", "retrieval", "path"],
        index_hash="idx",
        embedding_index_path="context-map/embeddings/index.json",
        embedding_enabled=True,
        embedding_provider="hash_cross",
        embedding_model="hash-cross-v1",
        embedding_dimension=1,
        embedding_rerank_pool=24,
        embedding_lexical_weight=0.7,
        embedding_semantic_weight=0.3,
        embedding_min_similarity=0.0,
        embedding_fail_open=True,
        policy={"embedding_enabled": True, "semantic_rerank_time_budget_ms": 60},
        mark_timing=lambda name, started: None,
        resolve_embedding_runtime_config=_resolve_runtime,
        build_embedding_stats=_build_embedding_stats,
        rerank_cross_encoder_with_time_budget=_timeout_cross_encoder,
    )

    assert result.candidates == [{"path": "src/app.py", "score": 1.0}]
    assert result.embeddings_payload["fallback"] is True
    assert result.embeddings_payload["time_budget_exceeded"] is True
    assert result.embeddings_payload["semantic_rerank_applied"] is False
    assert "time_budget_exceeded" in result.embeddings_payload["warning"]
    assert result.semantic_cross_encoder_provider is not None
