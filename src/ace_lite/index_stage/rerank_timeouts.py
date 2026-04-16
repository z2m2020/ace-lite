"""Time-budget wrappers for index-stage rerank helpers."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

from ace_lite.embeddings import (
    CrossEncoderProvider,
    EmbeddingIndexStats,
    EmbeddingProvider,
    rerank_candidates_with_cross_encoder,
    rerank_candidates_with_embeddings,
    rerank_rows_with_cross_encoder,
    rerank_rows_with_embeddings,
)


def rerank_embeddings_with_time_budget(
    *,
    candidates: list[dict[str, Any]],
    files_map: dict[str, dict[str, Any]],
    query: str,
    provider: EmbeddingProvider,
    index_path: str | Path,
    index_hash: str | None,
    rerank_pool: int,
    lexical_weight: float,
    semantic_weight: float,
    min_similarity: float,
    time_budget_ms: int,
    rerank_fn: Callable[..., tuple[list[dict[str, Any]], EmbeddingIndexStats]] = (
        rerank_candidates_with_embeddings
    ),
) -> tuple[list[dict[str, Any]], EmbeddingIndexStats]:
    budget_ms = max(1, int(time_budget_ms))
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        rerank_fn,
        candidates=candidates,
        files_map=files_map,
        query=query,
        provider=provider,
        index_path=index_path,
        index_hash=index_hash,
        rerank_pool=rerank_pool,
        lexical_weight=lexical_weight,
        semantic_weight=semantic_weight,
        min_similarity=min_similarity,
    )
    try:
        return future.result(timeout=float(budget_ms) / 1000.0)
    except FuturesTimeoutError as exc:
        raise TimeoutError(f"embedding_time_budget_exceeded:{budget_ms}ms") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def rerank_cross_encoder_with_time_budget(
    *,
    candidates: list[dict[str, Any]],
    files_map: dict[str, dict[str, Any]],
    query: str,
    provider: CrossEncoderProvider,
    index_path: str | Path,
    rerank_pool: int,
    lexical_weight: float,
    semantic_weight: float,
    min_similarity: float,
    time_budget_ms: int,
    rerank_fn: Callable[..., tuple[list[dict[str, Any]], EmbeddingIndexStats]] = (
        rerank_candidates_with_cross_encoder
    ),
) -> tuple[list[dict[str, Any]], EmbeddingIndexStats]:
    budget_ms = max(1, int(time_budget_ms))
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        rerank_fn,
        candidates=candidates,
        files_map=files_map,
        query=query,
        provider=provider,
        index_path=index_path,
        rerank_pool=rerank_pool,
        lexical_weight=lexical_weight,
        semantic_weight=semantic_weight,
        min_similarity=min_similarity,
    )
    try:
        return future.result(timeout=float(budget_ms) / 1000.0)
    except FuturesTimeoutError as exc:
        raise TimeoutError(f"cross_encoder_time_budget_exceeded:{budget_ms}ms") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def rerank_rows_cross_encoder_with_time_budget(
    *,
    rows: list[dict[str, Any]],
    texts: list[str],
    query: str,
    provider: CrossEncoderProvider,
    rerank_pool: int,
    lexical_weight: float,
    semantic_weight: float,
    min_similarity: float,
    time_budget_ms: int,
    rerank_fn: Callable[..., tuple[list[dict[str, Any]], EmbeddingIndexStats]] = (
        rerank_rows_with_cross_encoder
    ),
) -> tuple[list[dict[str, Any]], EmbeddingIndexStats]:
    budget_ms = max(1, int(time_budget_ms))
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        rerank_fn,
        rows=rows,
        texts=texts,
        query=query,
        provider=provider,
        rerank_pool=rerank_pool,
        lexical_weight=lexical_weight,
        semantic_weight=semantic_weight,
        min_similarity=min_similarity,
    )
    try:
        return future.result(timeout=float(budget_ms) / 1000.0)
    except FuturesTimeoutError as exc:
        raise TimeoutError(f"chunk_cross_encoder_time_budget_exceeded:{budget_ms}ms") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def rerank_rows_embeddings_with_time_budget(
    *,
    rows: list[dict[str, Any]],
    texts: list[str],
    query: str,
    provider: EmbeddingProvider,
    index_path: str | Path | None,
    index_hash: str | None,
    rerank_pool: int,
    lexical_weight: float,
    semantic_weight: float,
    min_similarity: float,
    time_budget_ms: int,
    rerank_fn: Callable[..., tuple[list[dict[str, Any]], EmbeddingIndexStats]] = (
        rerank_rows_with_embeddings
    ),
) -> tuple[list[dict[str, Any]], EmbeddingIndexStats]:
    budget_ms = max(1, int(time_budget_ms))
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        rerank_fn,
        rows=rows,
        texts=texts,
        query=query,
        provider=provider,
        index_path=index_path,
        index_hash=index_hash,
        rerank_pool=rerank_pool,
        lexical_weight=lexical_weight,
        semantic_weight=semantic_weight,
        min_similarity=min_similarity,
    )
    try:
        return future.result(timeout=float(budget_ms) / 1000.0)
    except FuturesTimeoutError as exc:
        raise TimeoutError(f"chunk_embedding_time_budget_exceeded:{budget_ms}ms") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


__all__ = [
    "rerank_cross_encoder_with_time_budget",
    "rerank_embeddings_with_time_budget",
    "rerank_rows_cross_encoder_with_time_budget",
    "rerank_rows_embeddings_with_time_budget",
]
