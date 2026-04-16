from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.embeddings import (
    BGE_M3_DEFAULT_MODEL,
    BGE_RERANKER_DEFAULT_MODEL,
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
    rerank_candidates_with_cross_encoder,
    rerank_candidates_with_embeddings,
)
from ace_lite.index_stage.rerank_timeouts import rerank_embeddings_with_time_budget

_EMBEDDING_PROVIDERS = frozenset({"hash", "bge_m3", "ollama", "sentence_transformers"})
_CROSS_ENCODER_PROVIDERS = frozenset({"hash_cross", "hash_colbert", "bge_reranker"})


@dataclass(frozen=True, slots=True)
class SemanticCandidateRerankResult:
    candidates: list[dict[str, Any]]
    embeddings_payload: dict[str, Any]
    semantic_embedding_provider_impl: EmbeddingProvider | None
    semantic_cross_encoder_provider: CrossEncoderProvider | None


def apply_semantic_candidate_rerank(
    *,
    root: str,
    query: str,
    files_map: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    terms: list[str],
    index_hash: str,
    embedding_index_path: str | Path,
    embedding_enabled: bool,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
    embedding_rerank_pool: int,
    embedding_lexical_weight: float,
    embedding_semantic_weight: float,
    embedding_min_similarity: float,
    embedding_fail_open: bool,
    policy: dict[str, Any],
    mark_timing: Callable[[str, float], None],
    resolve_embedding_runtime_config: Callable[..., Any],
    build_embedding_stats: Callable[..., dict[str, Any]],
    rerank_cross_encoder_with_time_budget: Callable[..., tuple[list[dict[str, Any]], Any]],
    perf_counter_fn: Callable[[], float] = perf_counter,
    rerank_embeddings_fn: Callable[
        ..., tuple[list[dict[str, Any]], Any]
    ] = rerank_candidates_with_embeddings,
    rerank_cross_encoder_fn: Callable[
        ..., tuple[list[dict[str, Any]], Any]
    ] = rerank_candidates_with_cross_encoder,
    rerank_embeddings_with_time_budget_fn: Callable[..., tuple[list[dict[str, Any]], Any]] = (
        rerank_embeddings_with_time_budget
    ),
) -> SemanticCandidateRerankResult:
    _ = root
    embedding_runtime = resolve_embedding_runtime_config(
        provider=embedding_provider,
        model=embedding_model,
        dimension=embedding_dimension,
    )
    runtime_provider = str(getattr(embedding_runtime, "provider", "") or "")
    runtime_model = str(getattr(embedding_runtime, "model", "") or "")
    runtime_dimension = int(getattr(embedding_runtime, "dimension", 0) or 0)
    normalized_fields = tuple(
        str(item)
        for item in getattr(embedding_runtime, "normalized_fields", ())
        if str(item).strip()
    )
    normalization_notes = tuple(
        str(item) for item in getattr(embedding_runtime, "notes", ()) if str(item).strip()
    )

    semantic_rerank_base_budget_ms = max(
        0, int(policy.get("semantic_rerank_time_budget_ms", 0) or 0)
    )
    semantic_rerank_budget_ms = semantic_rerank_base_budget_ms
    semantic_rerank_pool_base = max(1, int(embedding_rerank_pool))
    semantic_rerank_pool = semantic_rerank_pool_base
    if candidates:
        semantic_rerank_pool = min(semantic_rerank_pool, len(candidates))

    adaptive_semantic_budget_applied = bool(policy.get("semantic_rerank_adaptive", True))
    if adaptive_semantic_budget_applied:
        pool_cap = max(
            1,
            int(
                policy.get("semantic_rerank_pool_cap", semantic_rerank_pool_base)
                or semantic_rerank_pool_base
            ),
        )
        semantic_rerank_pool = min(semantic_rerank_pool, pool_cap)

        candidate_count = len(candidates)
        if candidate_count > 0:
            if candidate_count <= 6:
                semantic_rerank_pool = min(semantic_rerank_pool, 8)
            elif candidate_count <= 12:
                semantic_rerank_pool = min(semantic_rerank_pool, 12)
            elif candidate_count <= 24:
                semantic_rerank_pool = min(semantic_rerank_pool, 16)
            else:
                semantic_rerank_pool = min(semantic_rerank_pool, 20)

        if semantic_rerank_base_budget_ms > 0:
            if candidate_count <= 6:
                candidate_factor = 0.65
            elif candidate_count <= 12:
                candidate_factor = 0.75
            elif candidate_count <= 24:
                candidate_factor = 0.85
            else:
                candidate_factor = 0.95
            query_factor = 1.0 + (0.05 if len(terms) >= 8 else 0.0)
            adapted = round(
                float(semantic_rerank_base_budget_ms)
                * float(candidate_factor)
                * float(query_factor)
            )
            semantic_rerank_budget_ms = min(
                semantic_rerank_base_budget_ms,
                max(20, adapted),
            )

    timing_started = perf_counter_fn()
    embeddings_payload: dict[str, Any] = build_embedding_stats(
        enabled=embedding_enabled,
        provider=runtime_provider,
        model=runtime_model,
        dimension=runtime_dimension,
        index_path=embedding_index_path,
        rerank_pool=semantic_rerank_pool,
        lexical_weight=embedding_lexical_weight,
        semantic_weight=embedding_semantic_weight,
        fallback=False,
        warning=None if embedding_enabled else "disabled",
    )
    embeddings_payload["time_budget_base_ms"] = semantic_rerank_base_budget_ms
    embeddings_payload["time_budget_ms"] = semantic_rerank_budget_ms
    embeddings_payload["time_budget_exceeded"] = False
    embeddings_payload["semantic_rerank_applied"] = False
    embeddings_payload["adaptive_budget_applied"] = adaptive_semantic_budget_applied
    embeddings_payload["rerank_pool_effective"] = semantic_rerank_pool

    semantic_embedding_provider_impl: EmbeddingProvider | None = None
    semantic_cross_encoder_provider: CrossEncoderProvider | None = None
    if embedding_enabled and not bool(policy.get("embedding_enabled", True)):
        embeddings_payload = build_embedding_stats(
            enabled=False,
            provider=runtime_provider,
            model=runtime_model,
            dimension=runtime_dimension,
            index_path=embedding_index_path,
            rerank_pool=semantic_rerank_pool,
            lexical_weight=embedding_lexical_weight,
            semantic_weight=embedding_semantic_weight,
            fallback=False,
            warning="policy_disabled",
        )
    elif embedding_enabled and runtime_provider not in (
        _EMBEDDING_PROVIDERS | _CROSS_ENCODER_PROVIDERS
    ):
        embeddings_payload = build_embedding_stats(
            enabled=False,
            provider=runtime_provider,
            model=runtime_model,
            dimension=runtime_dimension,
            index_path=embedding_index_path,
            rerank_pool=semantic_rerank_pool,
            lexical_weight=embedding_lexical_weight,
            semantic_weight=embedding_semantic_weight,
            fallback=True,
            warning=f"unsupported_provider:{runtime_provider}",
        )
    elif embedding_enabled and files_map and candidates:
        provider_name = runtime_provider
        if provider_name in _EMBEDDING_PROVIDERS:
            embedding_provider_impl: EmbeddingProvider
            if provider_name == "hash":
                embedding_provider_impl = HashEmbeddingProvider(
                    model_name=str(runtime_model or "hash-v1"),
                    dim=max(8, int(runtime_dimension)),
                )
            elif provider_name == "bge_m3":
                embedding_provider_impl = BGEM3EmbeddingProvider(
                    model_name=str(runtime_model or BGE_M3_DEFAULT_MODEL),
                    dim=max(8, int(runtime_dimension)),
                )
            elif provider_name == "sentence_transformers":
                embedding_provider_impl = SentenceTransformersEmbeddingProvider(
                    model_name=str(runtime_model or "nomic-ai/CodeRankEmbed"),
                    dim=int(runtime_dimension) if runtime_dimension else None,
                )
            else:
                embedding_provider_impl = OllamaEmbeddingProvider(
                    model_name=str(runtime_model or OLLAMA_DEFAULT_MODEL),
                    dim=max(8, int(runtime_dimension)),
                )
            semantic_embedding_provider_impl = embedding_provider_impl
            try:
                if semantic_rerank_budget_ms > 0:
                    candidates, embedding_stats = rerank_embeddings_with_time_budget_fn(
                        candidates=candidates,
                        files_map=files_map,
                        query=query,
                        provider=embedding_provider_impl,
                        index_path=embedding_index_path,
                        index_hash=index_hash,
                        rerank_pool=max(1, int(semantic_rerank_pool)),
                        lexical_weight=float(embedding_lexical_weight),
                        semantic_weight=float(embedding_semantic_weight),
                        min_similarity=float(embedding_min_similarity),
                        time_budget_ms=semantic_rerank_budget_ms,
                        rerank_fn=rerank_embeddings_fn,
                    )
                else:
                    candidates, embedding_stats = rerank_embeddings_fn(
                        candidates=candidates,
                        files_map=files_map,
                        query=query,
                        provider=embedding_provider_impl,
                        index_path=embedding_index_path,
                        index_hash=index_hash,
                        rerank_pool=max(1, int(semantic_rerank_pool)),
                        lexical_weight=float(embedding_lexical_weight),
                        semantic_weight=float(embedding_semantic_weight),
                        min_similarity=float(embedding_min_similarity),
                    )
                embeddings_payload = embedding_stats.to_dict()
                embeddings_payload["semantic_rerank_applied"] = bool(
                    int(getattr(embedding_stats, "reranked_count", 0) or 0) > 0
                )
                embeddings_payload["time_budget_exceeded"] = False
            except Exception as exc:
                if not bool(embedding_fail_open):
                    raise
                embeddings_payload = build_embedding_stats(
                    enabled=True,
                    provider=provider_name,
                    model=runtime_model,
                    dimension=runtime_dimension,
                    index_path=embedding_index_path,
                    rerank_pool=semantic_rerank_pool,
                    lexical_weight=embedding_lexical_weight,
                    semantic_weight=embedding_semantic_weight,
                    fallback=True,
                    warning=str(exc)[:240],
                )
                embeddings_payload["semantic_rerank_applied"] = False
                embeddings_payload["time_budget_exceeded"] = "time_budget_exceeded" in str(exc)
        elif provider_name in _CROSS_ENCODER_PROVIDERS:
            cross_encoder_provider: CrossEncoderProvider
            if provider_name == "hash_cross":
                cross_encoder_provider = HashCrossEncoderProvider(
                    model_name=str(runtime_model or "hash-cross-v1")
                )
            elif provider_name == "hash_colbert":
                cross_encoder_provider = HashColbertLateInteractionProvider(
                    model_name=str(runtime_model or "hash-colbert-v1")
                )
            else:
                cross_encoder_provider = BGERerankerCrossEncoderProvider(
                    model_name=str(runtime_model or BGE_RERANKER_DEFAULT_MODEL)
                )
            semantic_cross_encoder_provider = cross_encoder_provider
            try:
                if semantic_rerank_budget_ms > 0:
                    candidates, embedding_stats = rerank_cross_encoder_with_time_budget(
                        candidates=candidates,
                        files_map=files_map,
                        query=query,
                        provider=cross_encoder_provider,
                        index_path=embedding_index_path,
                        rerank_pool=max(1, int(semantic_rerank_pool)),
                        lexical_weight=float(embedding_lexical_weight),
                        semantic_weight=float(embedding_semantic_weight),
                        min_similarity=float(embedding_min_similarity),
                        time_budget_ms=semantic_rerank_budget_ms,
                    )
                else:
                    candidates, embedding_stats = rerank_cross_encoder_fn(
                        candidates=candidates,
                        files_map=files_map,
                        query=query,
                        provider=cross_encoder_provider,
                        index_path=embedding_index_path,
                        rerank_pool=max(1, int(semantic_rerank_pool)),
                        lexical_weight=float(embedding_lexical_weight),
                        semantic_weight=float(embedding_semantic_weight),
                        min_similarity=float(embedding_min_similarity),
                    )
                embeddings_payload = embedding_stats.to_dict()
                embeddings_payload["semantic_rerank_applied"] = bool(
                    int(embedding_stats.reranked_count) > 0
                )
                embeddings_payload["time_budget_exceeded"] = False
            except Exception as exc:
                if not bool(embedding_fail_open):
                    raise
                embeddings_payload = build_embedding_stats(
                    enabled=True,
                    provider=provider_name,
                    model=runtime_model,
                    dimension=runtime_dimension,
                    index_path=embedding_index_path,
                    rerank_pool=semantic_rerank_pool,
                    lexical_weight=embedding_lexical_weight,
                    semantic_weight=embedding_semantic_weight,
                    fallback=True,
                    warning=str(exc)[:240],
                )
                embeddings_payload["semantic_rerank_applied"] = False
                embeddings_payload["time_budget_exceeded"] = "time_budget_exceeded" in str(exc)
    mark_timing("embeddings", timing_started)

    embeddings_payload.setdefault("time_budget_ms", semantic_rerank_budget_ms)
    embeddings_payload.setdefault("time_budget_base_ms", semantic_rerank_base_budget_ms)
    embeddings_payload.setdefault("time_budget_exceeded", False)
    embeddings_payload.setdefault("adaptive_budget_applied", adaptive_semantic_budget_applied)
    embeddings_payload.setdefault("rerank_pool_effective", semantic_rerank_pool)
    if "semantic_rerank_applied" not in embeddings_payload:
        embeddings_payload["semantic_rerank_applied"] = bool(
            runtime_provider in {"hash_cross", "bge_reranker"}
            and int(embeddings_payload.get("reranked_count", 0) or 0) > 0
        )

    embeddings_payload["runtime_provider"] = runtime_provider
    embeddings_payload["runtime_model"] = runtime_model
    embeddings_payload["runtime_dimension"] = runtime_dimension
    embeddings_payload["auto_normalized"] = bool(normalized_fields)
    embeddings_payload["auto_normalized_fields"] = list(normalized_fields)
    embeddings_payload["normalization_notes"] = list(normalization_notes)

    return SemanticCandidateRerankResult(
        candidates=list(candidates),
        embeddings_payload=embeddings_payload,
        semantic_embedding_provider_impl=semantic_embedding_provider_impl,
        semantic_cross_encoder_provider=semantic_cross_encoder_provider,
    )


__all__ = [
    "SemanticCandidateRerankResult",
    "apply_semantic_candidate_rerank",
]
