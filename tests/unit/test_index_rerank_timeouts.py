from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Any

from ace_lite.index_stage.rerank_timeouts import (
    rerank_cross_encoder_with_time_budget,
    rerank_rows_cross_encoder_with_time_budget,
    rerank_rows_embeddings_with_time_budget,
)


@dataclass(frozen=True, slots=True)
class _FakeStats:
    reranked_count: int = 1


def test_rerank_cross_encoder_with_time_budget_returns_wrapped_result() -> None:
    rows, stats = rerank_cross_encoder_with_time_budget(
        candidates=[{"path": "src/app.py"}],
        files_map={"src/app.py": {}},
        query="q",
        provider=object(),  # type: ignore[arg-type]
        index_path="context-map/index.json",
        rerank_pool=4,
        lexical_weight=0.7,
        semantic_weight=0.3,
        min_similarity=0.0,
        time_budget_ms=20,
        rerank_fn=lambda **kwargs: (kwargs["candidates"], _FakeStats()),
    )

    assert rows == [{"path": "src/app.py"}]
    assert stats == _FakeStats()


def test_rerank_rows_embeddings_with_time_budget_raises_timeout() -> None:
    def _slow(**kwargs: Any) -> tuple[list[dict[str, Any]], _FakeStats]:
        _ = kwargs
        sleep(0.03)
        return [], _FakeStats()

    try:
        rerank_rows_embeddings_with_time_budget(
            rows=[{"path": "src/app.py"}],
            texts=["snippet"],
            query="q",
            provider=object(),  # type: ignore[arg-type]
            index_path="context-map/index.json",
            index_hash="idx",
            rerank_pool=4,
            lexical_weight=0.7,
            semantic_weight=0.3,
            min_similarity=0.0,
            time_budget_ms=1,
            rerank_fn=_slow,
        )
    except TimeoutError as exc:
        assert "chunk_embedding_time_budget_exceeded" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected TimeoutError")


def test_rerank_rows_cross_encoder_with_time_budget_raises_timeout() -> None:
    def _slow(**kwargs: Any) -> tuple[list[dict[str, Any]], _FakeStats]:
        _ = kwargs
        sleep(0.03)
        return [], _FakeStats()

    try:
        rerank_rows_cross_encoder_with_time_budget(
            rows=[{"path": "src/app.py"}],
            texts=["snippet"],
            query="q",
            provider=object(),  # type: ignore[arg-type]
            rerank_pool=4,
            lexical_weight=0.7,
            semantic_weight=0.3,
            min_similarity=0.0,
            time_budget_ms=1,
            rerank_fn=_slow,
        )
    except TimeoutError as exc:
        assert "chunk_cross_encoder_time_budget_exceeded" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected TimeoutError")
