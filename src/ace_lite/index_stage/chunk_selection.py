from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.chunking.builder import build_candidate_chunks
from ace_lite.chunking.robust_signature import (
    build_chunk_robust_signature_sidecar,
    count_available_robust_signatures,
)
from ace_lite.chunking.types import (
    CONTEXTUAL_CHUNKING_SIDECAR_KEY,
    RETRIEVAL_CONTEXT_SIDECAR_KEY,
    resolve_retrieval_context_text,
    strip_internal_chunk_sidecars,
)
from ace_lite.embeddings import CrossEncoderProvider, EmbeddingProvider
from ace_lite.index_stage.chunk_guard import apply_chunk_guard
from ace_lite.scoring_config import resolve_chunk_scoring_config


@dataclass(frozen=True, slots=True)
class ChunkSelectionResult:
    candidate_chunks: list[dict[str, Any]]
    chunk_metrics: dict[str, Any]
    chunk_semantic_rerank_payload: dict[str, Any]
    topological_shield_payload: dict[str, Any]
    chunk_guard_payload: dict[str, Any]


def apply_chunk_selection(
    *,
    root: str,
    query: str,
    files_map: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    terms: list[str],
    top_k_files: int,
    chunk_top_k: int,
    chunk_per_file_limit: int,
    chunk_token_budget: int,
    chunk_disclosure: str,
    chunk_snippet_max_lines: int,
    chunk_snippet_max_chars: int,
    policy: dict[str, Any],
    tokenizer_model: str,
    chunk_diversity_enabled: bool,
    chunk_diversity_path_penalty: float,
    chunk_diversity_symbol_family_penalty: float,
    chunk_diversity_kind_penalty: float,
    chunk_diversity_locality_penalty: float,
    chunk_diversity_locality_window: int,
    chunk_topological_shield_enabled: bool,
    chunk_topological_shield_mode: str,
    chunk_topological_shield_max_attenuation: float,
    chunk_topological_shield_shared_parent_attenuation: float,
    chunk_topological_shield_adjacency_attenuation: float,
    chunk_guard_enabled: bool,
    chunk_guard_mode: str,
    chunk_guard_lambda_penalty: float,
    chunk_guard_min_pool: int,
    chunk_guard_max_pool: int,
    chunk_guard_min_marginal_utility: float,
    chunk_guard_compatibility_min_overlap: float,
    index_hash: str,
    embedding_enabled: bool,
    embedding_lexical_weight: float,
    embedding_semantic_weight: float,
    embedding_min_similarity: float,
    embeddings_payload: dict[str, Any],
    semantic_embedding_provider_impl: EmbeddingProvider | None,
    semantic_cross_encoder_provider: CrossEncoderProvider | None,
    mark_timing: Callable[[str, float], None],
    rerank_rows_embeddings_with_time_budget: Callable[..., tuple[list[dict[str, Any]], Any]],
    rerank_rows_cross_encoder_with_time_budget: Callable[..., tuple[list[dict[str, Any]], Any]],
    chunk_scoring_config: Mapping[str, Any] | None = None,
    perf_counter_fn: Callable[[], float] = perf_counter,
    build_candidate_chunks_fn: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]] = build_candidate_chunks,
) -> ChunkSelectionResult:
    timing_started = perf_counter_fn()
    resolved_chunk_scoring_config = resolve_chunk_scoring_config(
        chunk_scoring_config
    )
    candidate_chunks, chunk_metrics = build_candidate_chunks_fn(
        root=root,
        files_map=files_map,
        candidates=candidates,
        terms=terms,
        top_k_files=int(top_k_files),
        top_k_chunks=int(chunk_top_k),
        per_file_limit=int(chunk_per_file_limit),
        token_budget=int(chunk_token_budget),
        disclosure_mode=str(chunk_disclosure),
        snippet_max_lines=int(chunk_snippet_max_lines),
        snippet_max_chars=int(chunk_snippet_max_chars),
        policy=policy,
        tokenizer_model=str(tokenizer_model),
        diversity_enabled=bool(chunk_diversity_enabled),
        diversity_path_penalty=float(chunk_diversity_path_penalty),
        diversity_symbol_family_penalty=float(chunk_diversity_symbol_family_penalty),
        diversity_kind_penalty=float(chunk_diversity_kind_penalty),
        diversity_locality_penalty=float(chunk_diversity_locality_penalty),
        diversity_locality_window=int(chunk_diversity_locality_window),
        topological_shield_enabled=bool(chunk_topological_shield_enabled),
        topological_shield_mode=str(chunk_topological_shield_mode),
        topological_shield_max_attenuation=float(
            chunk_topological_shield_max_attenuation
        ),
        topological_shield_shared_parent_attenuation=float(
            chunk_topological_shield_shared_parent_attenuation
        ),
        topological_shield_adjacency_attenuation=float(
            chunk_topological_shield_adjacency_attenuation
        ),
        chunk_scoring_config=resolved_chunk_scoring_config,
        reference_hits_cache_key=index_hash,
    )
    mark_timing("chunk_build", timing_started)

    chunk_semantic_pool_cap = max(
        1, int(policy.get("chunk_semantic_rerank_pool_cap", 16) or 16)
    )
    chunk_semantic_time_budget_ms = max(
        0, int(policy.get("chunk_semantic_rerank_time_budget_ms", 0) or 0)
    )
    chunk_semantic_rerank_payload: dict[str, Any] = {
        "enabled": bool(policy.get("chunk_semantic_rerank_enabled", False)),
        "reason": "disabled",
        "provider": str(embeddings_payload.get("runtime_provider", "")),
        "model": str(embeddings_payload.get("runtime_model", "")),
        "dimension": int(embeddings_payload.get("runtime_dimension", 0) or 0),
        "rerank_pool_cap": chunk_semantic_pool_cap,
        "rerank_pool_effective": min(len(candidate_chunks), chunk_semantic_pool_cap)
        if isinstance(candidate_chunks, list)
        else 0,
        "reranked_count": 0,
        "lexical_weight": float(embedding_lexical_weight),
        "semantic_weight": float(embedding_semantic_weight),
        "min_similarity": float(embedding_min_similarity),
        "time_budget_ms": chunk_semantic_time_budget_ms,
        "time_budget_exceeded": False,
        "fallback": False,
        "warning": "",
        "similarity_mean": 0.0,
        "similarity_max": 0.0,
        "retrieval_context_chunk_count": 0,
        "retrieval_context_coverage_ratio": 0.0,
        "retrieval_context_pool_chunk_count": 0,
        "retrieval_context_pool_coverage_ratio": 0.0,
    }

    if isinstance(candidate_chunks, list) and candidate_chunks:
        total_chunk_count = len(candidate_chunks)
        pool_size = int(chunk_semantic_rerank_payload.get("rerank_pool_effective", 0) or 0)
        retrieval_context_chunk_count = 0
        retrieval_context_pool_chunk_count = 0
        for index, item in enumerate(candidate_chunks):
            if not isinstance(item, dict):
                continue
            retrieval_context = resolve_retrieval_context_text(item)
            if not retrieval_context:
                continue
            retrieval_context_chunk_count += 1
            if index < pool_size:
                retrieval_context_pool_chunk_count += 1
        chunk_semantic_rerank_payload["retrieval_context_chunk_count"] = int(
            retrieval_context_chunk_count
        )
        chunk_semantic_rerank_payload["retrieval_context_coverage_ratio"] = (
            float(retrieval_context_chunk_count) / float(total_chunk_count)
            if total_chunk_count > 0
            else 0.0
        )
        chunk_semantic_rerank_payload["retrieval_context_pool_chunk_count"] = int(
            retrieval_context_pool_chunk_count
        )
        chunk_semantic_rerank_payload["retrieval_context_pool_coverage_ratio"] = (
            float(retrieval_context_pool_chunk_count) / float(pool_size)
            if pool_size > 0
            else 0.0
        )

    timing_started = perf_counter_fn()
    if not bool(chunk_semantic_rerank_payload.get("enabled", False)):
        chunk_semantic_rerank_payload["reason"] = "policy_disabled"
    elif not candidate_chunks:
        chunk_semantic_rerank_payload["reason"] = "no_chunks"
    elif not (
        bool(embedding_enabled) and bool(policy.get("embedding_enabled", True))
    ):
        chunk_semantic_rerank_payload["reason"] = "embedding_disabled"
    elif chunk_semantic_time_budget_ms <= 0:
        chunk_semantic_rerank_payload["reason"] = "no_time_budget"
    else:
        pool_size = int(chunk_semantic_rerank_payload.get("rerank_pool_effective", 0) or 0)
        chunk_texts: list[str] = []
        if pool_size > 0:
            for item in candidate_chunks[:pool_size]:
                if not isinstance(item, dict):
                    chunk_texts.append("")
                    continue
                path = str(item.get("path") or "").strip()
                qualified = str(item.get("qualified_name") or "").strip()
                signature = str(item.get("signature") or "").strip()[:240]
                snippet = str(item.get("snippet") or "").strip()[:600]
                retrieval_context = resolve_retrieval_context_text(item)[:600]
                sidecar_value = item.get(CONTEXTUAL_CHUNKING_SIDECAR_KEY)
                sidecar_dict = (
                    dict(sidecar_value) if isinstance(sidecar_value, dict) else {}
                )
                parent_symbol = str(sidecar_dict.get("parent_symbol") or "").strip()
                reference_values = (
                    [
                        str(value).strip()
                        for value in sidecar_dict.get("references", [])
                        if str(value).strip()
                    ]
                    if isinstance(sidecar_dict.get("references"), list)
                    else []
                )
                parts = [
                    retrieval_context,
                    f"parent_symbol={parent_symbol}" if parent_symbol else "",
                    (
                        "references=" + ", ".join(reference_values[:3])
                        if reference_values
                        else ""
                    ),
                    path,
                    qualified,
                    signature,
                    snippet,
                ]
                chunk_texts.append("\n".join(part for part in parts if part))

        try:
            chunk_stats: Any | None = None
            chunk_embedding_index_path = (
                Path(root) / "context-map" / "embeddings" / "chunks.index.json"
            )
            chunk_semantic_rerank_payload["index_path"] = str(
                chunk_embedding_index_path
            )
            if semantic_embedding_provider_impl is not None:
                candidate_chunks, chunk_stats = rerank_rows_embeddings_with_time_budget(
                    rows=candidate_chunks,
                    texts=chunk_texts,
                    query=query,
                    provider=semantic_embedding_provider_impl,
                    index_path=chunk_embedding_index_path,
                    index_hash=index_hash,
                    rerank_pool=max(1, pool_size),
                    lexical_weight=float(embedding_lexical_weight),
                    semantic_weight=float(embedding_semantic_weight),
                    min_similarity=float(embedding_min_similarity),
                    time_budget_ms=chunk_semantic_time_budget_ms,
                )
            elif semantic_cross_encoder_provider is not None:
                candidate_chunks, chunk_stats = rerank_rows_cross_encoder_with_time_budget(
                    rows=candidate_chunks,
                    texts=chunk_texts,
                    query=query,
                    provider=semantic_cross_encoder_provider,
                    rerank_pool=max(1, pool_size),
                    lexical_weight=float(embedding_lexical_weight),
                    semantic_weight=float(embedding_semantic_weight),
                    min_similarity=float(embedding_min_similarity),
                    time_budget_ms=chunk_semantic_time_budget_ms,
                )
            else:
                chunk_semantic_rerank_payload["reason"] = "provider_unavailable"

            if chunk_stats is not None:
                chunk_semantic_rerank_payload["reason"] = "ok"
                chunk_semantic_rerank_payload["reranked_count"] = int(
                    chunk_stats.reranked_count
                )
                chunk_semantic_rerank_payload["similarity_mean"] = float(
                    chunk_stats.similarity_mean
                )
                chunk_semantic_rerank_payload["similarity_max"] = float(
                    chunk_stats.similarity_max
                )
        except Exception as exc:
            chunk_semantic_rerank_payload["reason"] = "fail_open"
            chunk_semantic_rerank_payload["fallback"] = True
            chunk_semantic_rerank_payload["warning"] = str(exc)[:240]
            chunk_semantic_rerank_payload["time_budget_exceeded"] = isinstance(
                exc, TimeoutError
            ) or "time_budget" in str(exc).lower()
    mark_timing("chunk_semantic_rerank", timing_started)

    robust_signature_sidecar = build_chunk_robust_signature_sidecar(
        candidate_chunks=list(candidate_chunks),
        files_map=files_map,
    )
    chunk_metrics = (
        dict(chunk_metrics) if isinstance(chunk_metrics, dict) else {}
    )
    robust_signature_count = count_available_robust_signatures(
        candidate_chunks=list(candidate_chunks),
        sidecar=robust_signature_sidecar,
    )
    chunk_count = len([item for item in candidate_chunks if isinstance(item, dict)])
    chunk_metrics["robust_signature_count"] = float(robust_signature_count)
    chunk_metrics["robust_signature_coverage_ratio"] = (
        float(robust_signature_count) / float(chunk_count) if chunk_count > 0 else 0.0
    )
    normalized_topological_mode = (
        str(chunk_topological_shield_mode or "off").strip().lower() or "off"
    )
    topological_shield_payload: dict[str, Any] = {
        "enabled": bool(chunk_topological_shield_enabled),
        "mode": normalized_topological_mode,
        "report_only": normalized_topological_mode == "report_only",
        "reason": "disabled" if not chunk_topological_shield_enabled else normalized_topological_mode,
        "max_attenuation": float(chunk_topological_shield_max_attenuation),
        "shared_parent_attenuation": float(
            chunk_topological_shield_shared_parent_attenuation
        ),
        "adjacency_attenuation": float(
            chunk_topological_shield_adjacency_attenuation
        ),
        "attenuated_chunk_count": int(
            chunk_metrics.get("topological_shield_attenuated_chunk_count", 0) or 0
        ),
        "coverage_ratio": float(
            chunk_metrics.get("topological_shield_coverage_ratio", 0.0) or 0.0
        ),
        "attenuation_total": float(
            chunk_metrics.get("topological_shield_attenuation_total", 0.0) or 0.0
        ),
        "adjacency_evidence_count": int(
            chunk_metrics.get("topological_shield_adjacency_evidence_count", 0) or 0
        ),
        "shared_parent_evidence_count": int(
            chunk_metrics.get(
                "topological_shield_shared_parent_evidence_count", 0
            )
            or 0
        ),
        "graph_attested_chunk_count": int(
            chunk_metrics.get(
                "topological_shield_graph_attested_chunk_count", 0
            )
            or 0
        ),
        "selection_order_changed": False,
    }

    timing_started = perf_counter_fn()
    chunk_guard_result = apply_chunk_guard(
        candidate_chunks=list(candidate_chunks),
        robust_signature_sidecar=robust_signature_sidecar,
        enabled=bool(chunk_guard_enabled),
        mode=str(chunk_guard_mode),
        lambda_penalty=float(chunk_guard_lambda_penalty),
        min_pool=int(chunk_guard_min_pool),
        max_pool=int(chunk_guard_max_pool),
        min_marginal_utility=float(chunk_guard_min_marginal_utility),
        compatibility_min_overlap=float(chunk_guard_compatibility_min_overlap),
    )
    candidate_chunks = strip_internal_chunk_sidecars(
        chunk_guard_result.candidate_chunks
    )
    chunk_guard_payload = chunk_guard_result.chunk_guard_payload
    mark_timing("chunk_guard", timing_started)

    return ChunkSelectionResult(
        candidate_chunks=list(candidate_chunks),
        chunk_metrics=chunk_metrics,
        chunk_semantic_rerank_payload=chunk_semantic_rerank_payload,
        topological_shield_payload=topological_shield_payload,
        chunk_guard_payload=chunk_guard_payload,
    )


__all__ = ["ChunkSelectionResult", "apply_chunk_selection"]
