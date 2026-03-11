from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ace_lite.embeddings_index_store import (
    _build_file_embedding_text,
    _build_row_embedding_key,
    _load_embedding_index_payload,
    _sha256_text,
    _write_embedding_index,
    build_or_load_embedding_index,
)
from ace_lite.embeddings_providers import (
    CrossEncoderProvider,
    EmbeddingProvider,
    _coerce_vector,
)


@dataclass(frozen=True, slots=True)
class EmbeddingIndexStats:
    enabled: bool
    provider: str
    model: str
    dimension: int
    cache_hit: bool
    index_path: str
    indexed_files: int
    rerank_pool: int
    reranked_count: int
    lexical_weight: float
    semantic_weight: float
    similarity_mean: float
    similarity_max: float
    fallback: bool
    warning: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _empty_rerank_stats(
    *,
    provider: EmbeddingProvider | CrossEncoderProvider,
    lexical_weight: float,
    semantic_weight: float,
    index_path: str = "",
) -> EmbeddingIndexStats:
    lw, sw = _normalize_weights(
        lexical_weight=lexical_weight,
        semantic_weight=semantic_weight,
    )
    return EmbeddingIndexStats(
        enabled=True,
        provider=provider.provider,
        model=provider.model,
        dimension=provider.dimension,
        cache_hit=False,
        index_path=str(index_path),
        indexed_files=0,
        rerank_pool=0,
        reranked_count=0,
        lexical_weight=lw,
        semantic_weight=sw,
        similarity_mean=0.0,
        similarity_max=0.0,
        fallback=False,
        warning=None,
    )


def _rerank_core(
    *,
    items: list[dict[str, Any]],
    similarities: list[float],
    rerank_pool: int,
    lexical_weight: float,
    semantic_weight: float,
    min_similarity: float,
    provider: EmbeddingProvider | CrossEncoderProvider,
    cache_hit: bool = False,
    index_path: str = "",
    indexed_files: int = 0,
    warning: str | None = None,
) -> tuple[list[dict[str, Any]], EmbeddingIndexStats]:
    lw, sw = _normalize_weights(
        lexical_weight=lexical_weight,
        semantic_weight=semantic_weight,
    )

    pool_size = max(1, min(int(rerank_pool), len(items)))
    rerank_slice = items[:pool_size]
    tail_slice = items[pool_size:]

    lexical_scores = [float(item.get("score", 0.0) or 0.0) for item in rerank_slice]
    lexical_norm = _minmax_normalize(lexical_scores)

    threshold = float(min_similarity)
    filtered: list[float] = []
    for value in similarities[:pool_size]:
        similarity = float(value)
        if similarity < threshold:
            similarity = 0.0
        filtered.append(similarity)
    while len(filtered) < pool_size:
        filtered.append(0.0)
    similarity_norm = _minmax_normalize(filtered)

    reranked_rows: list[dict[str, Any]] = []
    for index, item in enumerate(rerank_slice):
        lexical = float(lexical_norm[index] if index < len(lexical_norm) else 0.0)
        semantic = float(similarity_norm[index] if index < len(similarity_norm) else 0.0)
        combined = lw * lexical + sw * semantic
        updated = dict(item)
        updated["score_lexical"] = float(
            lexical_scores[index] if index < len(lexical_scores) else 0.0
        )
        updated["score_embedding"] = float(
            filtered[index] if index < len(filtered) else 0.0
        )
        updated["score_fused"] = float(round(combined, 8))
        reranked_rows.append(updated)

    reranked_rows.sort(
        key=lambda row: (
            -float(row.get("score_fused", 0.0) or 0.0),
            -float(row.get("score_lexical", 0.0) or 0.0),
            str(row.get("path") or ""),
        )
    )

    merged = reranked_rows + [dict(item) for item in tail_slice]
    for row in merged:
        if "score_fused" in row:
            row["score"] = float(row.get("score_fused", row.get("score", 0.0)) or 0.0)

    sim_values = [float(value) for value in filtered if math.isfinite(value)]
    sim_mean = float(sum(sim_values) / len(sim_values)) if sim_values else 0.0
    sim_max = max(sim_values) if sim_values else 0.0

    stats = EmbeddingIndexStats(
        enabled=True,
        provider=provider.provider,
        model=provider.model,
        dimension=provider.dimension,
        cache_hit=bool(cache_hit),
        index_path=str(index_path),
        indexed_files=int(indexed_files),
        rerank_pool=pool_size,
        reranked_count=len(reranked_rows),
        lexical_weight=lw,
        semantic_weight=sw,
        similarity_mean=float(round(sim_mean, 8)),
        similarity_max=float(round(sim_max, 8)),
        fallback=False,
        warning=str(warning)[:240] if warning else None,
    )
    return merged, stats


def rerank_candidates_with_embeddings(
    *,
    candidates: list[dict[str, Any]],
    files_map: dict[str, dict[str, Any]],
    query: str,
    provider: EmbeddingProvider,
    index_path: str | Path,
    index_hash: str | None = None,
    rerank_pool: int,
    lexical_weight: float,
    semantic_weight: float,
    min_similarity: float,
) -> tuple[list[dict[str, Any]], EmbeddingIndexStats]:
    if not candidates:
        return candidates, _empty_rerank_stats(
            provider=provider,
            lexical_weight=lexical_weight,
            semantic_weight=semantic_weight,
            index_path=str(Path(index_path)),
        )

    vectors, cache_hit = build_or_load_embedding_index(
        files_map=files_map,
        provider=provider,
        index_path=index_path,
        index_hash=index_hash,
    )
    query_vector = provider.encode([str(query or "")])[0]
    query_vector = _coerce_vector(query_vector, dimension=provider.dimension)

    pool_size = max(1, min(int(rerank_pool), len(candidates)))
    similarities: list[float] = []
    for item in candidates[:pool_size]:
        path = str(item.get("path") or "").strip()
        vector = vectors.get(path)
        if vector is None:
            similarities.append(0.0)
        else:
            similarities.append(_cosine_similarity(query_vector, vector))

    return _rerank_core(
        items=candidates,
        similarities=similarities,
        rerank_pool=rerank_pool,
        lexical_weight=lexical_weight,
        semantic_weight=semantic_weight,
        min_similarity=min_similarity,
        provider=provider,
        cache_hit=cache_hit,
        index_path=str(Path(index_path)),
        indexed_files=len(vectors),
    )


def rerank_candidates_with_cross_encoder(
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
) -> tuple[list[dict[str, Any]], EmbeddingIndexStats]:
    if not candidates:
        return candidates, _empty_rerank_stats(
            provider=provider,
            lexical_weight=lexical_weight,
            semantic_weight=semantic_weight,
            index_path=str(Path(index_path)),
        )

    pool_size = max(1, min(int(rerank_pool), len(candidates)))
    rerank_texts: list[str] = []
    for item in candidates[:pool_size]:
        path = str(item.get("path") or "").strip()
        entry = files_map.get(path, {}) if path else {}
        rerank_texts.append(
            _build_file_embedding_text(
                path=path,
                entry=entry if isinstance(entry, dict) else {},
            )
        )

    similarities = provider.score(query=str(query or ""), texts=rerank_texts)

    return _rerank_core(
        items=candidates,
        similarities=list(similarities),
        rerank_pool=rerank_pool,
        lexical_weight=lexical_weight,
        semantic_weight=semantic_weight,
        min_similarity=min_similarity,
        provider=provider,
        index_path=str(Path(index_path)),
        indexed_files=len(files_map),
    )


def rerank_rows_with_embeddings(
    *,
    rows: list[dict[str, Any]],
    texts: list[str],
    query: str,
    provider: EmbeddingProvider,
    index_path: str | Path | None = None,
    index_hash: str | None = None,
    rerank_pool: int,
    lexical_weight: float,
    semantic_weight: float,
    min_similarity: float,
) -> tuple[list[dict[str, Any]], EmbeddingIndexStats]:
    if not rows:
        return rows, _empty_rerank_stats(
            provider=provider,
            lexical_weight=lexical_weight,
            semantic_weight=semantic_weight,
        )

    pool_size = max(1, min(int(rerank_pool), len(rows)))
    rerank_slice = rows[:pool_size]

    query_vector = provider.encode([str(query or "")])[0]
    query_vector = _coerce_vector(query_vector, dimension=provider.dimension)

    rerank_texts = [str(text or "") for text in texts[:pool_size]]
    while len(rerank_texts) < pool_size:
        rerank_texts.append("")

    normalized_index_hash = str(index_hash or "").strip().lower()
    cache_hit = False
    cache_warning: str | None = None
    indexed_files = 0
    index_path_value = ""
    vectors: list[list[float]] = []

    if index_path is not None and str(index_path).strip():
        target = Path(index_path)
        index_path_value = str(target)
        try:
            row_keys: list[str] = []
            row_hashes: dict[str, str] = {}
            key_counts: dict[str, int] = {}
            for idx, item in enumerate(rerank_slice):
                base_key = _build_row_embedding_key(row=item, index=idx)
                count = key_counts.get(base_key, 0) + 1
                key_counts[base_key] = count
                key = base_key if count == 1 else f"{base_key}#{count}"
                row_keys.append(key)
                row_hashes[key] = _sha256_text(
                    rerank_texts[idx] if idx < len(rerank_texts) else ""
                )

            cached_payload = _load_embedding_index_payload(path=target, provider=provider)
            cached_vectors = (
                dict(cached_payload.get("vectors") or {})
                if isinstance(cached_payload, dict)
                else {}
            )
            cached_hashes = (
                dict(cached_payload.get("file_hashes") or {})
                if isinstance(cached_payload, dict)
                else {}
            )
            cached_index_hash = (
                str(cached_payload.get("index_hash") or "").strip().lower()
                if isinstance(cached_payload, dict)
                else ""
            )

            vectors_by_key: dict[str, list[float]] = {}
            changed_indices: list[int] = []
            for idx, key in enumerate(row_keys):
                expected_hash = row_hashes.get(key, "")
                cached_vector = cached_vectors.get(key)
                if cached_hashes.get(key) == expected_hash and isinstance(cached_vector, list):
                    vectors_by_key[key] = _coerce_vector(
                        cached_vector,
                        dimension=provider.dimension,
                    )
                else:
                    changed_indices.append(idx)

            removed_keys = [key for key in list(cached_vectors) if key not in row_hashes]
            if changed_indices:
                changed_texts = [
                    rerank_texts[idx] if idx < len(rerank_texts) else ""
                    for idx in changed_indices
                ]
                encoded_changed = provider.encode(changed_texts)
                for local_idx, vector in enumerate(encoded_changed):
                    row_idx = changed_indices[local_idx]
                    key = row_keys[row_idx]
                    vectors_by_key[key] = _coerce_vector(vector, dimension=provider.dimension)

            for key in row_keys:
                if key not in vectors_by_key:
                    vectors_by_key[key] = [0.0] * int(provider.dimension)

            index_hash_match = (
                not normalized_index_hash
                or not cached_index_hash
                or cached_index_hash == normalized_index_hash
            )
            cache_hit = (
                bool(cached_payload is not None)
                and not changed_indices
                and not removed_keys
                and bool(index_hash_match)
            )

            if not cache_hit:
                _write_embedding_index(
                    path=target,
                    provider=provider,
                    file_hashes=row_hashes,
                    vectors=vectors_by_key,
                    index_hash=normalized_index_hash,
                )

            vectors = [
                _coerce_vector(vectors_by_key.get(key, []), dimension=provider.dimension)
                for key in row_keys
            ]
            indexed_files = len(vectors_by_key)
        except Exception as exc:
            cache_warning = f"row_cache_error:{exc.__class__.__name__}"

    if not vectors:
        encoded = provider.encode(rerank_texts)
        vectors = [
            _coerce_vector(vector, dimension=provider.dimension)
            for vector in encoded[:pool_size]
        ]
        while len(vectors) < pool_size:
            vectors.append([0.0] * int(provider.dimension))

    similarities: list[float] = [
        _cosine_similarity(query_vector, vector) for vector in vectors
    ]

    return _rerank_core(
        items=rows,
        similarities=similarities,
        rerank_pool=rerank_pool,
        lexical_weight=lexical_weight,
        semantic_weight=semantic_weight,
        min_similarity=min_similarity,
        provider=provider,
        cache_hit=cache_hit,
        index_path=index_path_value,
        indexed_files=indexed_files,
        warning=cache_warning,
    )


def rerank_rows_with_cross_encoder(
    *,
    rows: list[dict[str, Any]],
    texts: list[str],
    query: str,
    provider: CrossEncoderProvider,
    rerank_pool: int,
    lexical_weight: float,
    semantic_weight: float,
    min_similarity: float,
) -> tuple[list[dict[str, Any]], EmbeddingIndexStats]:
    if not rows:
        return rows, _empty_rerank_stats(
            provider=provider,
            lexical_weight=lexical_weight,
            semantic_weight=semantic_weight,
        )

    pool_size = max(1, min(int(rerank_pool), len(rows)))
    rerank_texts = [str(text or "") for text in texts[:pool_size]]
    while len(rerank_texts) < pool_size:
        rerank_texts.append("")

    similarities = provider.score(query=str(query or ""), texts=rerank_texts)

    return _rerank_core(
        items=rows,
        similarities=list(similarities),
        rerank_pool=rerank_pool,
        lexical_weight=lexical_weight,
        semantic_weight=semantic_weight,
        min_similarity=min_similarity,
        provider=provider,
    )


def _normalize_weights(
    *,
    lexical_weight: float,
    semantic_weight: float,
) -> tuple[float, float]:
    lexical = max(0.0, float(lexical_weight))
    semantic = max(0.0, float(semantic_weight))
    total = lexical + semantic
    if total <= 0.0:
        return 1.0, 0.0
    return lexical / total, semantic / total


def _minmax_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if math.isclose(low, high):
        return [1.0 if high > 0.0 else 0.0 for _ in values]
    scale = high - low
    return [(value - low) / scale for value in values]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    size = min(len(a), len(b))
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for idx in range(size):
        value_a = float(a[idx])
        value_b = float(b[idx])
        dot += value_a * value_b
        norm_a += value_a * value_a
        norm_b += value_b * value_b
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / math.sqrt(norm_a * norm_b)


__all__ = [
    "EmbeddingIndexStats",
    "rerank_candidates_with_cross_encoder",
    "rerank_candidates_with_embeddings",
    "rerank_rows_with_cross_encoder",
    "rerank_rows_with_embeddings",
]
