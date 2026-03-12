"""Index stage for the orchestrator pipeline.

This module builds (or refreshes) the repo index and selects file/chunk
candidates for downstream stages.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any

from ace_lite.embeddings import (
    BGE_M3_DEFAULT_MODEL,
    BGE_RERANKER_DEFAULT_MODEL,
    OLLAMA_DEFAULT_DIMENSION,
    OLLAMA_DEFAULT_MODEL,
    CrossEncoderProvider,
    EmbeddingIndexStats,
    EmbeddingProvider,
    rerank_candidates_with_cross_encoder,
    rerank_rows_with_cross_encoder,
    rerank_rows_with_embeddings,
)
from ace_lite.exact_search import run_exact_search_ripgrep, score_exact_search_hits
from ace_lite.index_stage import (
    CandidateFusionDeps,
    ChunkSelectionDeps,
    ChunkSelectionRuntimeConfig,
    InitialCandidateGenerationDeps,
    apply_candidate_priors,
    apply_chunk_selection,
    apply_exact_search_boost,
    apply_semantic_candidate_rerank,
    apply_structural_rerank,
    build_index_stage_output,
    build_exact_search_payload,
    collect_docs_signals,
    collect_parallel_signals,
    collect_worktree_prior,
    extract_memory_paths,
    gather_initial_candidates,
    postprocess_candidates,
    refine_candidate_pool,
    resolve_online_bandit_gate,
    resolve_retrieval_policy,
    resolve_shadow_router_arm,
    select_index_chunks,
    select_initial_candidates,
)
from ace_lite.index_stage.cache import (
    build_index_candidate_cache_key,
    default_index_candidate_cache_path,
    load_cached_index_candidates_checked,
    store_cached_index_candidates,
)
from ace_lite.index_stage.config_adapter import (
    build_index_stage_config_from_orchestrator,
)
from ace_lite.index_stage.feedback import apply_feedback_boost
from ace_lite.parsers.languages import supported_extensions
from ace_lite.pipeline.types import StageContext
from ace_lite.rankers import (
    fuse_rrf,
    normalize_fusion_mode,
    normalize_rrf_scores,
)
from ace_lite.retrieval_shared import (
    build_retrieval_runtime_profile,
    extract_retrieval_terms,
    load_retrieval_index_snapshot,
)

_INDEX_CANDIDATE_CACHE_CONTENT_VERSION = "index-candidates-v1"


@dataclass(frozen=True, slots=True)
class IndexAdaptiveRouterConfig:
    """Adaptive-router controls for the index stage."""

    enabled: bool
    mode: str
    model_path: str
    state_path: str
    arm_set: str
    online_bandit_enabled: bool
    online_bandit_experiment_enabled: bool


@dataclass(frozen=True, slots=True)
class IndexRetrievalConfig:
    """Retrieval and routing controls for the index stage."""

    retrieval_policy: str
    policy_version: str
    adaptive_router: IndexAdaptiveRouterConfig
    candidate_ranker: str
    top_k_files: int
    min_candidate_score: int
    candidate_relative_threshold: float
    deterministic_refine_enabled: bool
    hybrid_re2_fusion_mode: str
    hybrid_re2_rrf_k: int
    hybrid_re2_bm25_weight: float
    hybrid_re2_heuristic_weight: float
    hybrid_re2_coverage_weight: float
    hybrid_re2_combined_scale: float
    exact_search_enabled: bool
    exact_search_time_budget_ms: int
    exact_search_max_paths: int
    multi_channel_rrf_enabled: bool
    multi_channel_rrf_k: int
    multi_channel_rrf_pool_cap: int
    multi_channel_rrf_code_cap: int
    multi_channel_rrf_docs_cap: int
    multi_channel_rrf_memory_cap: int

 
@dataclass(frozen=True, slots=True)
class IndexChunkGuardConfig:
    """Chunk-guard controls for the index stage."""

    enabled: bool
    mode: str
    lambda_penalty: float
    min_pool: int
    max_pool: int
    min_marginal_utility: float
    compatibility_min_overlap: float


@dataclass(frozen=True, slots=True)
class IndexTopologicalShieldConfig:
    """Report-only topological shield controls for the index stage."""

    enabled: bool
    mode: str
    max_attenuation: float
    shared_parent_attenuation: float
    adjacency_attenuation: float


@dataclass(frozen=True, slots=True)
class IndexChunkingConfig:
    """Chunk-selection controls for the index stage."""

    top_k: int
    per_file_limit: int
    token_budget: int
    disclosure: str
    snippet_max_lines: int
    snippet_max_chars: int
    tokenizer_model: str
    diversity_enabled: bool
    diversity_path_penalty: float
    diversity_symbol_family_penalty: float
    diversity_kind_penalty: float
    diversity_locality_penalty: float
    diversity_locality_window: int
    topological_shield: IndexTopologicalShieldConfig
    guard: IndexChunkGuardConfig


@dataclass(frozen=True, slots=True)
class IndexStageConfig:
    """Configuration options for the index stage."""

    cache_path: Path
    languages: list[str]
    incremental: bool
    retrieval: IndexRetrievalConfig

    embedding_enabled: bool
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embedding_index_path: str
    embedding_rerank_pool: int
    embedding_lexical_weight: float
    embedding_semantic_weight: float
    embedding_min_similarity: float
    embedding_fail_open: bool

    chunking: IndexChunkingConfig

    # Co-change (temporal coupling)
    cochange_enabled: bool
    cochange_cache_path: str
    cochange_lookback_commits: int
    cochange_half_life_days: float
    cochange_neighbor_cap: int
    cochange_top_neighbors: int
    cochange_boost_weight: float
    cochange_min_neighbor_score: float
    cochange_max_boost: float

    # Selection feedback rerank
    feedback_enabled: bool
    feedback_path: str
    feedback_max_entries: int
    feedback_boost_per_select: float
    feedback_max_boost: float
    feedback_decay_days: float

    # SCIP boosting
    scip_enabled: bool
    scip_index_path: str
    scip_provider: str
    scip_generate_fallback: bool

    @classmethod
    def from_orchestrator_config(
        cls,
        *,
        config: Any,
        tokenizer_model: str,
        cochange_neighbor_cap: int,
        cochange_min_neighbor_score: float,
        cochange_max_boost: float,
    ) -> IndexStageConfig:
        """Create an index-stage config from the orchestrator runtime config."""
        return build_index_stage_config_from_orchestrator(
            config=config,
            tokenizer_model=tokenizer_model,
            cochange_neighbor_cap=cochange_neighbor_cap,
            cochange_min_neighbor_score=cochange_min_neighbor_score,
            cochange_max_boost=cochange_max_boost,
            stage_config_cls=cls,
            retrieval_config_cls=IndexRetrievalConfig,
            adaptive_router_config_cls=IndexAdaptiveRouterConfig,
            chunking_config_cls=IndexChunkingConfig,
            topological_shield_config_cls=IndexTopologicalShieldConfig,
            chunk_guard_config_cls=IndexChunkGuardConfig,
        )


def _build_adaptive_router_payload(
    *,
    config: IndexAdaptiveRouterConfig,
    policy: dict[str, Any],
    shadow: dict[str, Any] | None = None,
    online_bandit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enabled = bool(config.enabled)
    source = str(policy.get("source", "")).strip() if enabled else "disabled"
    confidence = 1.0 if enabled and source == "configured" else 0.0
    shadow_payload = shadow if isinstance(shadow, dict) else {}
    online_bandit_payload = online_bandit if isinstance(online_bandit, dict) else {}
    return {
        "enabled": enabled,
        "mode": str(config.mode).strip() or "observe",
        "model_path": str(config.model_path).strip(),
        "state_path": str(config.state_path).strip(),
        "arm_set": str(config.arm_set).strip() or "retrieval_policy_v1",
        "arm_id": str(policy.get("name", "")).strip() if enabled else "",
        "source": source,
        "confidence": float(confidence),
        "shadow_arm_id": str(shadow_payload.get("arm_id", "")).strip() if enabled else "",
        "shadow_confidence": float(shadow_payload.get("confidence", 0.0) or 0.0)
        if enabled
        else 0.0,
        "online_bandit": dict(online_bandit_payload),
    }


@dataclass(frozen=True, slots=True)
class EmbeddingRuntimeConfig:
    provider: str
    model: str
    dimension: int
    normalized_fields: tuple[str, ...]
    notes: tuple[str, ...]


def _resolve_repo_relative_path(*, root: str, configured_path: str) -> Path:
    path = Path(str(configured_path or "").strip() or "context-map/index.json")
    if path.is_absolute():
        return path
    return Path(root) / path


def _normalize_repo_path(value: str) -> str:
    path = str(value or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def _build_embedding_stats(
    *,
    enabled: bool,
    provider: str,
    model: str,
    dimension: int,
    index_path: str | Path,
    rerank_pool: int,
    lexical_weight: float,
    semantic_weight: float,
    fallback: bool,
    warning: str | None,
) -> dict[str, Any]:
    return EmbeddingIndexStats(
        enabled=bool(enabled),
        provider=str(provider),
        model=str(model),
        dimension=max(1, int(dimension)),
        cache_hit=False,
        index_path=str(index_path),
        indexed_files=0,
        rerank_pool=max(0, int(rerank_pool)),
        reranked_count=0,
        lexical_weight=max(0.0, float(lexical_weight)),
        semantic_weight=max(0.0, float(semantic_weight)),
        similarity_mean=0.0,
        similarity_max=0.0,
        fallback=bool(fallback),
        warning=warning,
    ).to_dict()


def _resolve_embedding_runtime_config(
    *,
    provider: str,
    model: str,
    dimension: int,
) -> EmbeddingRuntimeConfig:
    provider_name = str(provider or "hash").strip().lower() or "hash"
    configured_model = str(model or "").strip()
    configured_dimension = max(8, int(dimension))

    runtime_model = configured_model
    runtime_dimension = configured_dimension
    normalized_fields: list[str] = []
    notes: list[str] = []

    if provider_name == "hash":
        if not runtime_model:
            runtime_model = "hash-v1"
            normalized_fields.append("model")
            notes.append("hash_default_model")
    elif provider_name == "hash_cross":
        if not runtime_model:
            runtime_model = "hash-cross-v1"
            normalized_fields.append("model")
            notes.append("hash_cross_default_model")
        if configured_dimension != 1:
            runtime_dimension = 1
            normalized_fields.append("dimension")
            notes.append("hash_cross_dimension_forced")
    elif provider_name == "hash_colbert":
        if not runtime_model:
            runtime_model = "hash-colbert-v1"
            normalized_fields.append("model")
            notes.append("hash_colbert_default_model")
        if configured_dimension != 1:
            runtime_dimension = 1
            normalized_fields.append("dimension")
            notes.append("hash_colbert_dimension_forced")
    elif provider_name == "bge_m3":
        if not runtime_model or runtime_model in {"hash-v1", "hash-cross-v1"}:
            runtime_model = BGE_M3_DEFAULT_MODEL
            normalized_fields.append("model")
            notes.append("bge_m3_default_model")
        # Avoid silent quality regression when inheriting the global hash default.
        if configured_dimension == 256:
            runtime_dimension = 1024
            normalized_fields.append("dimension")
            notes.append("bge_m3_default_dimension")
    elif provider_name == "bge_reranker":
        if not runtime_model or runtime_model in {"hash-v1", "hash-cross-v1"}:
            runtime_model = BGE_RERANKER_DEFAULT_MODEL
            normalized_fields.append("model")
            notes.append("bge_reranker_default_model")
        if configured_dimension != 1:
            runtime_dimension = 1
            normalized_fields.append("dimension")
            notes.append("bge_reranker_dimension_forced")
    elif provider_name == "ollama":
        if not runtime_model or runtime_model in {"hash-v1", "hash-cross-v1"}:
            runtime_model = OLLAMA_DEFAULT_MODEL
            normalized_fields.append("model")
            notes.append("ollama_default_model")
        # Avoid silent quality regression when inheriting the global hash default.
        if configured_dimension == 256:
            runtime_dimension = OLLAMA_DEFAULT_DIMENSION
            normalized_fields.append("dimension")
            notes.append("ollama_default_dimension")

    return EmbeddingRuntimeConfig(
        provider=provider_name,
        model=runtime_model,
        dimension=max(1, int(runtime_dimension)),
        normalized_fields=tuple(dict.fromkeys(normalized_fields)),
        notes=tuple(dict.fromkeys(notes)),
    )


def _clone_index_candidate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cloned = dict(payload)
    cloned.pop("candidate_cache", None)
    return cloned


def _attach_index_candidate_cache_info(
    *,
    payload: dict[str, Any],
    cache_info: dict[str, Any],
) -> dict[str, Any]:
    materialized = _clone_index_candidate_payload(payload)
    materialized["candidate_cache"] = dict(cache_info)
    return materialized


def _rerank_cross_encoder_with_time_budget(
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
) -> tuple[list[dict[str, Any]], EmbeddingIndexStats]:
    budget_ms = max(1, int(time_budget_ms))
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        rerank_candidates_with_cross_encoder,
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


def _rerank_rows_cross_encoder_with_time_budget(
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
) -> tuple[list[dict[str, Any]], EmbeddingIndexStats]:
    budget_ms = max(1, int(time_budget_ms))
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        rerank_rows_with_cross_encoder,
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
        raise TimeoutError(
            f"chunk_cross_encoder_time_budget_exceeded:{budget_ms}ms"
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _rerank_rows_embeddings_with_time_budget(
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
) -> tuple[list[dict[str, Any]], EmbeddingIndexStats]:
    budget_ms = max(1, int(time_budget_ms))
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        rerank_rows_with_embeddings,
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
        raise TimeoutError(
            f"chunk_embedding_time_budget_exceeded:{budget_ms}ms"
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _merge_candidate_lists(
    *,
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    merged_by_path: dict[str, dict[str, Any]] = {}
    for source_name, rows in (("primary", primary), ("secondary", secondary)):
        for row in rows:
            if not isinstance(row, dict):
                continue
            path = str(row.get("path") or "").strip()
            if not path:
                continue
            score = float(row.get("score") or 0.0)
            existing = merged_by_path.get(path)
            if existing is None or float(existing.get("score") or 0.0) < score:
                payload = dict(row)
                payload["retrieval_pass"] = source_name
                merged_by_path[path] = payload

    merged = list(merged_by_path.values())
    merged.sort(
        key=lambda item: (
            -float(item.get("score") or 0.0),
            str(item.get("path") or ""),
        )
    )
    return merged[:limit]


def _apply_multi_channel_rrf_fusion(
    *,
    candidates: list[dict[str, Any]],
    files_map: dict[str, dict[str, Any]],
    docs_payload: dict[str, Any],
    memory_paths: list[str],
    top_k_files: int,
    rrf_k: int,
    pool_cap: int,
    code_cap: int,
    docs_cap: int,
    memory_cap: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized_top_k_files = max(1, int(top_k_files))
    rrf_k_effective = max(1, int(rrf_k))
    pool_cap_effective = int(pool_cap)
    if pool_cap_effective <= 0:
        pool_cap_effective = max(32, normalized_top_k_files * 12)
    pool_cap_effective = min(pool_cap_effective, len(candidates))

    code_cap_effective = int(code_cap)
    if code_cap_effective <= 0:
        code_cap_effective = max(16, normalized_top_k_files * 8)
    code_cap_effective = min(code_cap_effective, pool_cap_effective)

    docs_cap_effective = int(docs_cap)
    if docs_cap_effective <= 0:
        docs_cap_effective = max(8, normalized_top_k_files * 4)
    docs_cap_effective = min(docs_cap_effective, pool_cap_effective)

    memory_cap_effective = int(memory_cap)
    if memory_cap_effective <= 0:
        memory_cap_effective = max(8, normalized_top_k_files * 4)
    memory_cap_effective = min(memory_cap_effective, pool_cap_effective)

    payload: dict[str, Any] = {
        "enabled": True,
        "applied": False,
        "reason": "disabled",
        "rrf_k": rrf_k_effective,
        "caps": {
            "pool": int(pool_cap_effective),
            "code": int(code_cap_effective),
            "docs": int(docs_cap_effective),
            "memory": int(memory_cap_effective),
        },
        "channels": {
            "code": {"count": 0, "cap": int(code_cap_effective), "top": []},
            "docs": {"count": 0, "cap": int(docs_cap_effective), "top": []},
            "memory": {"count": 0, "cap": int(memory_cap_effective), "top": []},
        },
        "fused": {
            "scored_count": 0,
            "pool_size": int(pool_cap_effective),
            "top": [],
        },
        "warning": None,
    }

    if not candidates:
        payload["reason"] = "empty_candidates"
        return candidates, payload
    if pool_cap_effective <= 0:
        payload["reason"] = "empty_pool"
        return candidates, payload

    pool = list(candidates[:pool_cap_effective])
    tail = list(candidates[pool_cap_effective:])

    pool_paths: list[str] = []
    pool_set: set[str] = set()
    for row in pool:
        if not isinstance(row, dict):
            continue
        path = _normalize_repo_path(str(row.get("path") or ""))
        if not path or path in pool_set:
            continue
        pool_set.add(path)
        pool_paths.append(path)

    code_ranking = pool_paths[:code_cap_effective]

    docs_ranking: list[str] = []
    docs_hints = (
        docs_payload.get("hints", {})
        if isinstance(docs_payload.get("hints"), dict)
        else {}
    )
    docs_path_scores = docs_hints.get("path_scores", [])
    scored_docs_paths: list[tuple[float, str]] = []
    if isinstance(docs_path_scores, list):
        for row in docs_path_scores:
            if not isinstance(row, dict):
                continue
            path = _normalize_repo_path(str(row.get("value") or ""))
            if not path or path not in pool_set or path not in files_map:
                continue
            try:
                score = float(row.get("score") or 0.0)
            except Exception:
                score = 0.0
            if score <= 0.0:
                continue
            scored_docs_paths.append((score, path))
    scored_docs_paths.sort(key=lambda item: (-float(item[0]), str(item[1])))
    seen_docs: set[str] = set()
    for score, path in scored_docs_paths:
        _ = score
        if path in seen_docs:
            continue
        seen_docs.add(path)
        docs_ranking.append(path)
        if len(docs_ranking) >= docs_cap_effective:
            break

    memory_ranking: list[str] = []
    seen_memory: set[str] = set()
    for raw_path in memory_paths:
        path = _normalize_repo_path(str(raw_path or ""))
        if not path or path in seen_memory:
            continue
        if path not in pool_set or path not in files_map:
            continue
        seen_memory.add(path)
        memory_ranking.append(path)
        if len(memory_ranking) >= memory_cap_effective:
            break

    payload["channels"]["code"]["count"] = len(code_ranking)
    payload["channels"]["docs"]["count"] = len(docs_ranking)
    payload["channels"]["memory"]["count"] = len(memory_ranking)
    payload["channels"]["code"]["top"] = list(code_ranking[:8])
    payload["channels"]["docs"]["top"] = list(docs_ranking[:8])
    payload["channels"]["memory"]["top"] = list(memory_ranking[:8])

    if not docs_ranking and not memory_ranking:
        payload["reason"] = "no_aux_rankings"
        return candidates, payload

    try:
        fused_raw = fuse_rrf(
            [code_ranking, docs_ranking, memory_ranking],
            rrf_k=rrf_k_effective,
        )
        fused = normalize_rrf_scores(fused_raw)
    except Exception as exc:  # pragma: no cover - fail-open
        payload["reason"] = f"error:{exc.__class__.__name__}"
        payload["warning"] = str(exc)[:240]
        return candidates, payload

    code_pos = {path: rank for rank, path in enumerate(code_ranking, start=1)}
    docs_pos = {path: rank for rank, path in enumerate(docs_ranking, start=1)}
    memory_pos = {path: rank for rank, path in enumerate(memory_ranking, start=1)}

    rrf_scores: dict[str, float] = {str(k): float(v) for k, v in fused.items()}
    payload["fused"]["scored_count"] = len(rrf_scores)

    for row in pool:
        if not isinstance(row, dict):
            continue
        path = _normalize_repo_path(str(row.get("path") or ""))
        if not path:
            continue
        rrf_score = float(rrf_scores.get(path, 0.0) or 0.0)
        if rrf_score <= 0.0:
            continue
        row["score_rrf_multi"] = round(rrf_score, 8)
        breakdown = row.get("score_breakdown")
        if not isinstance(breakdown, dict):
            breakdown = {}
            row["score_breakdown"] = breakdown
        breakdown["rrf_multi_channel"] = round(rrf_score, 8)

    pool.sort(
        key=lambda row: (
            -float(
                rrf_scores.get(
                    _normalize_repo_path(str(row.get("path") or "")),
                    0.0,
                )
                or 0.0
            ),
            -float(row.get("score", 0.0) or 0.0),
            _normalize_repo_path(str(row.get("path") or "")),
        )
    )

    fused_top: list[dict[str, Any]] = []
    for path, score in sorted(
        rrf_scores.items(),
        key=lambda item: (-float(item[1]), str(item[0])),
    )[:12]:
        code_rank = int(code_pos.get(path, 0) or 0)
        docs_rank = int(docs_pos.get(path, 0) or 0)
        memory_rank = int(memory_pos.get(path, 0) or 0)
        fused_top.append(
            {
                "path": str(path),
                "score": float(round(float(score), 8)),
                "ranks": {
                    "code": code_rank,
                    "docs": docs_rank,
                    "memory": memory_rank,
                },
                "contrib": {
                    "code": float(round(1.0 / (rrf_k_effective + code_rank), 8))
                    if code_rank > 0
                    else 0.0,
                    "docs": float(round(1.0 / (rrf_k_effective + docs_rank), 8))
                    if docs_rank > 0
                    else 0.0,
                    "memory": float(
                        round(1.0 / (rrf_k_effective + memory_rank), 8)
                    )
                    if memory_rank > 0
                    else 0.0,
                },
            }
        )

    payload["fused"]["top"] = fused_top
    payload["fused"]["pool_size"] = int(pool_cap_effective)
    payload["applied"] = True
    payload["reason"] = "ok"
    return pool + tail, payload


def _disabled_docs_payload(*, reason: str, elapsed_ms: float) -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": str(reason),
        "backend": "disabled",
        "backend_fallback_reason": "",
        "cache_hit": False,
        "cache_layer": "none",
        "cache_store_written": False,
        "cache_path": "",
        "docs_fingerprint": "",
        "section_pool_size": 0,
        "section_count": 0,
        "query_token_count": 0,
        "evidence": [],
        "hints": {
            "paths": [],
            "modules": [],
            "symbols": [],
            "path_scores": [],
            "module_scores": [],
            "symbol_scores": [],
        },
        "elapsed_ms": round(float(elapsed_ms), 3),
    }


def _disabled_worktree_prior(*, reason: str) -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": str(reason),
        "changed_count": 0,
        "changed_paths": [],
        "seed_paths": [],
        "reverse_added_count": 0,
        "state_hash": "",
        "raw": {
            "enabled": False,
            "reason": str(reason),
            "changed_count": 0,
            "entries": [],
            "truncated": False,
            "error": "",
        },
    }


def _resolve_parallel_future(
    *,
    future: Future[Any] | None,
    timeout_seconds: float | None,
    fallback: Any,
) -> tuple[Any, bool, str]:
    if future is None:
        return fallback, False, ""

    try:
        if timeout_seconds is None:
            return future.result(), False, ""
        return future.result(timeout=float(timeout_seconds)), False, ""
    except FuturesTimeoutError:
        future.cancel()
        return fallback, True, "timeout"
    except Exception as exc:  # pragma: no cover - defensive
        return fallback, False, exc.__class__.__name__


_INDEX_PARALLEL_EXECUTOR: ThreadPoolExecutor | None = None
_INDEX_PARALLEL_EXECUTOR_LOCK = Lock()


def _get_index_parallel_executor() -> ThreadPoolExecutor:
    global _INDEX_PARALLEL_EXECUTOR
    with _INDEX_PARALLEL_EXECUTOR_LOCK:
        if _INDEX_PARALLEL_EXECUTOR is None:
            _INDEX_PARALLEL_EXECUTOR = ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="ace-lite-index-parallel",
            )
        return _INDEX_PARALLEL_EXECUTOR


def run_index(*, ctx: StageContext, config: IndexStageConfig) -> dict[str, Any]:
    """Run the index stage."""
    timings_ms: dict[str, float] = {}
    retrieval_cfg = config.retrieval
    router_cfg = retrieval_cfg.adaptive_router
    chunking_cfg = config.chunking
    topological_shield_cfg = chunking_cfg.topological_shield
    chunk_guard_cfg = chunking_cfg.guard

    def mark_timing(label: str, started_at: float) -> None:
        timings_ms[label] = round((perf_counter() - started_at) * 1000.0, 3)

    timing_started = perf_counter()
    memory_stage = ctx.state.get("memory", {}) if isinstance(ctx.state.get("memory"), dict) else {}
    terms = extract_retrieval_terms(query=ctx.query, memory_stage=memory_stage)
    memory_paths = extract_memory_paths(memory_stage=memory_stage, root=ctx.root)
    mark_timing("term_extraction", timing_started)

    timing_started = perf_counter()
    policy = resolve_retrieval_policy(
        query=ctx.query,
        retrieval_policy=retrieval_cfg.retrieval_policy,
        policy_version=retrieval_cfg.policy_version,
        cochange_enabled=config.cochange_enabled,
        embedding_enabled=config.embedding_enabled,
    )
    shadow_router = resolve_shadow_router_arm(
        enabled=router_cfg.enabled,
        mode=router_cfg.mode,
        model_path=_resolve_repo_relative_path(
            root=ctx.root,
            configured_path=router_cfg.model_path,
        ),
        arm_set=router_cfg.arm_set,
        executed_policy_name=str(policy.get("name", "")).strip(),
        candidate_ranker=retrieval_cfg.candidate_ranker,
        embedding_enabled=bool(policy.get("embedding_enabled", config.embedding_enabled)),
    )
    online_bandit_gate = resolve_online_bandit_gate(
        enabled=router_cfg.online_bandit_enabled,
        experiment_enabled=router_cfg.online_bandit_experiment_enabled,
        state_path=_resolve_repo_relative_path(
            root=ctx.root,
            configured_path=router_cfg.state_path,
        ),
    )
    adaptive_router_payload = _build_adaptive_router_payload(
        config=router_cfg,
        policy=policy,
        shadow=shadow_router,
        online_bandit=online_bandit_gate,
    )
    ctx.state["__policy"] = policy
    mark_timing("policy_resolution", timing_started)

    timing_started = perf_counter()
    snapshot = load_retrieval_index_snapshot(
        root_dir=ctx.root,
        cache_path=str(config.cache_path),
        languages=config.languages,
        incremental=config.incremental,
        fail_open=True,
        include_index_hash=True,
    )
    index_data = snapshot.index_payload
    cache_info = snapshot.cache_info
    mark_timing("index_cache_load", timing_started)

    files_map = snapshot.files_map
    ctx.state["__index_files"] = files_map
    index_hash = snapshot.index_hash
    corpus_size = snapshot.corpus_size
    embedding_runtime = _resolve_embedding_runtime_config(
        provider=str(config.embedding_provider),
        model=str(config.embedding_model),
        dimension=int(config.embedding_dimension),
    )
    index_candidate_cache_path = default_index_candidate_cache_path(root=ctx.root)
    index_candidate_cache_ttl_seconds = max(
        0, int(policy.get("index_candidate_cache_ttl_seconds", 1800) or 1800)
    )
    index_candidate_cache_required_meta = {
        "policy_name": str(policy.get("name", "general")),
        "policy_version": str(policy.get("version", retrieval_cfg.policy_version)),
        "index_hash": str(index_hash or ""),
        "content_version": _INDEX_CANDIDATE_CACHE_CONTENT_VERSION,
    }
    index_candidate_cache_key = build_index_candidate_cache_key(
        query=ctx.query,
        terms=terms,
        memory_paths=memory_paths,
        index_hash=index_hash,
        policy=policy,
        requested_ranker=str(retrieval_cfg.candidate_ranker),
        top_k_files=int(retrieval_cfg.top_k_files),
        min_candidate_score=int(retrieval_cfg.min_candidate_score),
        candidate_relative_threshold=float(retrieval_cfg.candidate_relative_threshold),
        chunk_top_k=int(chunking_cfg.top_k),
        chunk_per_file_limit=int(chunking_cfg.per_file_limit),
        chunk_token_budget=int(chunking_cfg.token_budget),
        chunk_disclosure=str(chunking_cfg.disclosure),
        exact_search_enabled=bool(retrieval_cfg.exact_search_enabled),
        deterministic_refine_enabled=bool(retrieval_cfg.deterministic_refine_enabled),
        embedding_enabled=bool(config.embedding_enabled),
        embedding_provider=str(embedding_runtime.provider),
        embedding_model=str(embedding_runtime.model),
        embedding_dimension=int(embedding_runtime.dimension),
        feedback_enabled=bool(config.feedback_enabled),
        multi_channel_rrf_enabled=bool(retrieval_cfg.multi_channel_rrf_enabled)
        or str(policy.get("version", "")).strip().lower().startswith("v2"),
        chunk_guard_mode=str(chunk_guard_cfg.mode),
        topological_shield_mode=str(topological_shield_cfg.mode),
        settings_payload={
            "retrieval": {
                "exact_search_time_budget_ms": int(
                    retrieval_cfg.exact_search_time_budget_ms
                ),
                "exact_search_max_paths": int(retrieval_cfg.exact_search_max_paths),
                "hybrid_re2_fusion_mode": str(retrieval_cfg.hybrid_re2_fusion_mode),
                "hybrid_re2_rrf_k": int(retrieval_cfg.hybrid_re2_rrf_k),
                "hybrid_re2_bm25_weight": float(retrieval_cfg.hybrid_re2_bm25_weight),
                "hybrid_re2_heuristic_weight": float(
                    retrieval_cfg.hybrid_re2_heuristic_weight
                ),
                "hybrid_re2_coverage_weight": float(
                    retrieval_cfg.hybrid_re2_coverage_weight
                ),
                "hybrid_re2_combined_scale": float(
                    retrieval_cfg.hybrid_re2_combined_scale
                ),
                "multi_channel_rrf_k": int(retrieval_cfg.multi_channel_rrf_k),
                "multi_channel_rrf_pool_cap": int(
                    retrieval_cfg.multi_channel_rrf_pool_cap
                ),
                "multi_channel_rrf_code_cap": int(
                    retrieval_cfg.multi_channel_rrf_code_cap
                ),
                "multi_channel_rrf_docs_cap": int(
                    retrieval_cfg.multi_channel_rrf_docs_cap
                ),
                "multi_channel_rrf_memory_cap": int(
                    retrieval_cfg.multi_channel_rrf_memory_cap
                ),
            },
            "chunking": {
                "diversity_enabled": bool(chunking_cfg.diversity_enabled),
                "diversity_path_penalty": float(
                    chunking_cfg.diversity_path_penalty
                ),
                "diversity_symbol_family_penalty": float(
                    chunking_cfg.diversity_symbol_family_penalty
                ),
                "diversity_kind_penalty": float(chunking_cfg.diversity_kind_penalty),
                "diversity_locality_penalty": float(
                    chunking_cfg.diversity_locality_penalty
                ),
                "diversity_locality_window": int(
                    chunking_cfg.diversity_locality_window
                ),
                "topological_max_attenuation": float(
                    topological_shield_cfg.max_attenuation
                ),
                "topological_shared_parent_attenuation": float(
                    topological_shield_cfg.shared_parent_attenuation
                ),
                "topological_adjacency_attenuation": float(
                    topological_shield_cfg.adjacency_attenuation
                ),
                "guard_lambda_penalty": float(chunk_guard_cfg.lambda_penalty),
                "guard_min_pool": int(chunk_guard_cfg.min_pool),
                "guard_max_pool": int(chunk_guard_cfg.max_pool),
                "guard_min_marginal_utility": float(
                    chunk_guard_cfg.min_marginal_utility
                ),
                "guard_compatibility_min_overlap": float(
                    chunk_guard_cfg.compatibility_min_overlap
                ),
            },
            "embedding": {
                "rerank_pool": int(config.embedding_rerank_pool),
                "lexical_weight": float(config.embedding_lexical_weight),
                "semantic_weight": float(config.embedding_semantic_weight),
                "min_similarity": float(config.embedding_min_similarity),
                "fail_open": bool(config.embedding_fail_open),
            },
            "feedback": {
                "path": str(config.feedback_path),
                "max_entries": int(config.feedback_max_entries),
                "boost_per_select": float(config.feedback_boost_per_select),
                "max_boost": float(config.feedback_max_boost),
                "decay_days": float(config.feedback_decay_days),
            },
            "feature_flags": {
                "cochange_enabled": bool(config.cochange_enabled),
                "scip_enabled": bool(config.scip_enabled),
            },
            "adaptive_router": {
                "enabled": bool(router_cfg.enabled),
                "mode": str(router_cfg.mode),
                "model_path": str(router_cfg.model_path),
                "state_path": str(router_cfg.state_path),
                "arm_set": str(router_cfg.arm_set),
                "online_bandit_enabled": bool(router_cfg.online_bandit_enabled),
                "online_bandit_experiment_enabled": bool(
                    router_cfg.online_bandit_experiment_enabled
                ),
            },
        },
        content_version=_INDEX_CANDIDATE_CACHE_CONTENT_VERSION,
    )
    index_candidate_cache = {
        "enabled": True,
        "hit": False,
        "store_written": False,
        "cache_key": str(index_candidate_cache_key),
        "path": str(index_candidate_cache_path),
        "ttl_seconds": int(index_candidate_cache_ttl_seconds),
        "content_version": _INDEX_CANDIDATE_CACHE_CONTENT_VERSION,
    }
    cached_index_payload = load_cached_index_candidates_checked(
        cache_path=index_candidate_cache_path,
        key=index_candidate_cache_key,
        max_age_seconds=index_candidate_cache_ttl_seconds,
        required_meta=index_candidate_cache_required_meta,
    )
    if cached_index_payload is not None:
        index_candidate_cache["hit"] = True
        return _attach_index_candidate_cache_info(
            payload=cached_index_payload,
            cache_info=index_candidate_cache,
        )

    fusion_mode = normalize_fusion_mode(retrieval_cfg.hybrid_re2_fusion_mode)
    hybrid_weights = {
        "bm25_weight": float(retrieval_cfg.hybrid_re2_bm25_weight),
        "heuristic_weight": float(retrieval_cfg.hybrid_re2_heuristic_weight),
        "coverage_weight": float(retrieval_cfg.hybrid_re2_coverage_weight),
        "combined_scale": float(retrieval_cfg.hybrid_re2_combined_scale),
    }
    runtime_profile = build_retrieval_runtime_profile(
        candidate_ranker=retrieval_cfg.candidate_ranker,
        min_candidate_score=int(retrieval_cfg.min_candidate_score),
        top_k_files=int(retrieval_cfg.top_k_files),
        hybrid_fusion_mode=fusion_mode,
        hybrid_rrf_k=int(retrieval_cfg.hybrid_re2_rrf_k),
        hybrid_weights=hybrid_weights,
        index_hash=index_hash,
    )
    parallel_requested = bool(policy.get("index_parallel_enabled", False))
    parallel_time_budget_ms = max(
        0, int(policy.get("index_parallel_time_budget_ms", 0) or 0)
    )
    docs_policy_enabled = bool(policy.get("docs_enabled", True))
    worktree_prior_enabled = bool(config.cochange_enabled)

    def rank_candidates(
        min_score: int,
        candidate_ranker: str,
        candidate_terms: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        ranked_terms = terms if candidate_terms is None else candidate_terms
        return runtime_profile.rank_candidates(
            files_map=files_map,
            terms=ranked_terms,
            candidate_ranker=candidate_ranker,
            min_score=min_score,
        )

    initial_candidates = gather_initial_candidates(
        root=ctx.root,
        query=ctx.query,
        terms=terms,
        files_map=files_map,
        corpus_size=corpus_size,
        runtime_profile=runtime_profile,
        top_k_files=int(retrieval_cfg.top_k_files),
        exact_search_enabled=bool(retrieval_cfg.exact_search_enabled),
        exact_search_time_budget_ms=int(retrieval_cfg.exact_search_time_budget_ms),
        exact_search_max_paths=int(retrieval_cfg.exact_search_max_paths),
        exact_search_include_globs=[
            f"*{suffix}"
            for suffix in sorted(supported_extensions(tuple(config.languages)))
            if suffix
        ][:12],
        docs_policy_enabled=docs_policy_enabled,
        worktree_prior_enabled=worktree_prior_enabled,
        cochange_enabled=bool(config.cochange_enabled),
        docs_intent_weight=float(policy.get("docs_weight", 1.0) or 1.0),
        parallel_requested=parallel_requested,
        parallel_time_budget_ms=parallel_time_budget_ms,
        policy=policy,
        deps=InitialCandidateGenerationDeps(
            build_exact_search_payload=build_exact_search_payload,
            select_initial_candidates=select_initial_candidates,
            apply_exact_search_boost=apply_exact_search_boost,
            collect_parallel_signals=collect_parallel_signals,
            apply_candidate_priors=apply_candidate_priors,
            collect_docs=collect_docs_signals,
            collect_worktree=collect_worktree_prior,
            disabled_docs_payload=_disabled_docs_payload,
            disabled_worktree_prior=_disabled_worktree_prior,
            get_executor=_get_index_parallel_executor,
            resolve_future=_resolve_parallel_future,
            run_exact_search=run_exact_search_ripgrep,
            score_exact_hits=score_exact_search_hits,
            normalize_repo_path=_normalize_repo_path,
            mark_timing=mark_timing,
        ),
    )
    requested_ranker = initial_candidates.requested_ranker
    selected_ranker = initial_candidates.selected_ranker
    ranker_fallbacks = list(initial_candidates.ranker_fallbacks)
    min_score_used = int(initial_candidates.min_score_used)
    candidates = list(initial_candidates.candidates)
    exact_search_payload = initial_candidates.exact_search_payload
    docs_payload = initial_candidates.docs_payload
    worktree_prior = initial_candidates.worktree_prior
    parallel_payload = initial_candidates.parallel_payload
    prior_payload = initial_candidates.prior_payload
    timings_ms["docs_signals"] = round(float(initial_candidates.docs_elapsed_ms), 3)
    timings_ms["worktree_prior"] = round(
        float(initial_candidates.worktree_elapsed_ms), 3
    )

    if (
        config.cochange_enabled
        and isinstance(initial_candidates.raw_worktree, dict)
    ):
        ctx.state["__vcs_worktree"] = initial_candidates.raw_worktree

    embedding_index_path = _resolve_repo_relative_path(
        root=ctx.root, configured_path=config.embedding_index_path
    )
    candidate_fusion = refine_candidate_pool(
        root=ctx.root,
        repo=ctx.repo,
        query=ctx.query,
        terms=terms,
        files_map=files_map,
        candidates=candidates,
        memory_paths=memory_paths,
        docs_payload=docs_payload,
        policy=policy,
        selected_ranker=selected_ranker,
        top_k_files=int(retrieval_cfg.top_k_files),
        candidate_relative_threshold=float(
            retrieval_cfg.candidate_relative_threshold
        ),
        refine_enabled=bool(retrieval_cfg.deterministic_refine_enabled),
        rank_candidates=rank_candidates,
        index_hash=index_hash,
        cochange_enabled=bool(config.cochange_enabled),
        cochange_cache_path=str(config.cochange_cache_path),
        cochange_lookback_commits=int(config.cochange_lookback_commits),
        cochange_half_life_days=float(config.cochange_half_life_days),
        cochange_neighbor_cap=int(config.cochange_neighbor_cap),
        cochange_top_neighbors=int(config.cochange_top_neighbors),
        cochange_boost_weight=float(config.cochange_boost_weight),
        cochange_min_neighbor_score=float(config.cochange_min_neighbor_score),
        cochange_max_boost=float(config.cochange_max_boost),
        scip_enabled=bool(config.scip_enabled),
        scip_index_path=str(config.scip_index_path),
        scip_provider=str(config.scip_provider),
        scip_generate_fallback=bool(config.scip_generate_fallback),
        embedding_index_path=embedding_index_path,
        embedding_enabled=bool(config.embedding_enabled),
        embedding_provider=str(config.embedding_provider),
        embedding_model=str(config.embedding_model),
        embedding_dimension=int(config.embedding_dimension),
        embedding_rerank_pool=int(config.embedding_rerank_pool),
        embedding_lexical_weight=float(config.embedding_lexical_weight),
        embedding_semantic_weight=float(config.embedding_semantic_weight),
        embedding_min_similarity=float(config.embedding_min_similarity),
        embedding_fail_open=bool(config.embedding_fail_open),
        feedback_enabled=bool(config.feedback_enabled),
        feedback_path=str(config.feedback_path),
        feedback_max_entries=int(config.feedback_max_entries),
        feedback_boost_per_select=float(config.feedback_boost_per_select),
        feedback_max_boost=float(config.feedback_max_boost),
        feedback_decay_days=float(config.feedback_decay_days),
        multi_channel_rrf_enabled=bool(retrieval_cfg.multi_channel_rrf_enabled)
        or str(policy.get("version", "")).strip().lower().startswith("v2"),
        multi_channel_rrf_k=int(retrieval_cfg.multi_channel_rrf_k),
        multi_channel_rrf_pool_cap=int(retrieval_cfg.multi_channel_rrf_pool_cap),
        multi_channel_rrf_code_cap=int(retrieval_cfg.multi_channel_rrf_code_cap),
        multi_channel_rrf_docs_cap=int(retrieval_cfg.multi_channel_rrf_docs_cap),
        multi_channel_rrf_memory_cap=int(
            retrieval_cfg.multi_channel_rrf_memory_cap
        ),
        deps=CandidateFusionDeps(
            postprocess_candidates=postprocess_candidates,
            apply_structural_rerank=apply_structural_rerank,
            apply_semantic_candidate_rerank=apply_semantic_candidate_rerank,
            apply_feedback_boost=apply_feedback_boost,
            apply_multi_channel_rrf_fusion=_apply_multi_channel_rrf_fusion,
            merge_candidate_lists=_merge_candidate_lists,
            resolve_embedding_runtime_config=_resolve_embedding_runtime_config,
            build_embedding_stats=_build_embedding_stats,
            rerank_cross_encoder_with_time_budget=(
                _rerank_cross_encoder_with_time_budget
            ),
            mark_timing=mark_timing,
        ),
    )
    candidates = list(candidate_fusion.candidates)
    second_pass_payload = candidate_fusion.second_pass_payload
    refine_pass_payload = candidate_fusion.refine_pass_payload
    cochange_payload = candidate_fusion.cochange_payload
    scip_payload = candidate_fusion.scip_payload
    graph_lookup_payload = candidate_fusion.graph_lookup_payload
    embeddings_payload = candidate_fusion.embeddings_payload
    feedback_payload = candidate_fusion.feedback_payload
    multi_channel_fusion_payload = candidate_fusion.multi_channel_fusion_payload
    semantic_embedding_provider_impl = (
        candidate_fusion.semantic_embedding_provider_impl
    )
    semantic_cross_encoder_provider = (
        candidate_fusion.semantic_cross_encoder_provider
    )

    chunk_selection = select_index_chunks(
        root=ctx.root,
        query=ctx.query,
        files_map=files_map,
        candidates=candidates,
        terms=terms,
        policy=policy,
        runtime_config=ChunkSelectionRuntimeConfig(
            top_k_files=int(retrieval_cfg.top_k_files),
            chunk_top_k=int(chunking_cfg.top_k),
            chunk_per_file_limit=int(chunking_cfg.per_file_limit),
            chunk_token_budget=int(chunking_cfg.token_budget),
            chunk_disclosure=str(chunking_cfg.disclosure),
            chunk_snippet_max_lines=int(chunking_cfg.snippet_max_lines),
            chunk_snippet_max_chars=int(chunking_cfg.snippet_max_chars),
            tokenizer_model=str(chunking_cfg.tokenizer_model),
            chunk_diversity_enabled=bool(chunking_cfg.diversity_enabled),
            chunk_diversity_path_penalty=float(chunking_cfg.diversity_path_penalty),
            chunk_diversity_symbol_family_penalty=float(
                chunking_cfg.diversity_symbol_family_penalty
            ),
            chunk_diversity_kind_penalty=float(chunking_cfg.diversity_kind_penalty),
            chunk_diversity_locality_penalty=float(
                chunking_cfg.diversity_locality_penalty
            ),
            chunk_diversity_locality_window=int(
                chunking_cfg.diversity_locality_window
            ),
            chunk_topological_shield_enabled=bool(topological_shield_cfg.enabled),
            chunk_topological_shield_mode=str(topological_shield_cfg.mode),
            chunk_topological_shield_max_attenuation=float(
                topological_shield_cfg.max_attenuation
            ),
            chunk_topological_shield_shared_parent_attenuation=float(
                topological_shield_cfg.shared_parent_attenuation
            ),
            chunk_topological_shield_adjacency_attenuation=float(
                topological_shield_cfg.adjacency_attenuation
            ),
            chunk_guard_enabled=bool(chunk_guard_cfg.enabled),
            chunk_guard_mode=str(chunk_guard_cfg.mode),
            chunk_guard_lambda_penalty=float(chunk_guard_cfg.lambda_penalty),
            chunk_guard_min_pool=int(chunk_guard_cfg.min_pool),
            chunk_guard_max_pool=int(chunk_guard_cfg.max_pool),
            chunk_guard_min_marginal_utility=float(
                chunk_guard_cfg.min_marginal_utility
            ),
            chunk_guard_compatibility_min_overlap=float(
                chunk_guard_cfg.compatibility_min_overlap
            ),
            embedding_enabled=bool(config.embedding_enabled),
            embedding_lexical_weight=float(config.embedding_lexical_weight),
            embedding_semantic_weight=float(config.embedding_semantic_weight),
            embedding_min_similarity=float(config.embedding_min_similarity),
        ),
        index_hash=index_hash,
        embeddings_payload=embeddings_payload,
        semantic_embedding_provider_impl=semantic_embedding_provider_impl,
        semantic_cross_encoder_provider=semantic_cross_encoder_provider,
        deps=ChunkSelectionDeps(
            apply_chunk_selection=apply_chunk_selection,
            mark_timing=mark_timing,
            rerank_rows_embeddings_with_time_budget=(
                _rerank_rows_embeddings_with_time_budget
            ),
            rerank_rows_cross_encoder_with_time_budget=(
                _rerank_rows_cross_encoder_with_time_budget
            ),
        ),
    )
    candidate_chunks = chunk_selection.candidate_chunks
    chunk_metrics = chunk_selection.chunk_metrics
    chunk_semantic_rerank_payload = chunk_selection.chunk_semantic_rerank_payload
    topological_shield_payload = chunk_selection.topological_shield_payload
    chunk_guard_payload = chunk_selection.chunk_guard_payload

    payload = build_index_stage_output(
        repo=ctx.repo,
        root=ctx.root,
        terms=terms,
        memory_paths=memory_paths,
        index_hash=index_hash,
        index_data=index_data,
        cache_info=cache_info,
        requested_ranker=requested_ranker,
        selected_ranker=selected_ranker,
        ranker_fallbacks=ranker_fallbacks,
        corpus_size=corpus_size,
        min_score_used=min_score_used,
        fusion_mode=fusion_mode,
        hybrid_re2_rrf_k=int(retrieval_cfg.hybrid_re2_rrf_k),
        top_k_files=int(retrieval_cfg.top_k_files),
        candidate_relative_threshold=float(
            retrieval_cfg.candidate_relative_threshold
        ),
        chunk_top_k=int(chunking_cfg.top_k),
        chunk_per_file_limit=int(chunking_cfg.per_file_limit),
        chunk_token_budget=int(chunking_cfg.token_budget),
        chunk_disclosure=str(chunking_cfg.disclosure),
        candidates=candidates,
        candidate_chunks=candidate_chunks,
        chunk_metrics=chunk_metrics,
        exact_search_payload=exact_search_payload,
        docs_payload=docs_payload,
        worktree_prior=worktree_prior,
        parallel_payload=parallel_payload,
        prior_payload=prior_payload,
        graph_lookup_payload=graph_lookup_payload,
        cochange_payload=cochange_payload,
        scip_payload=scip_payload,
        embeddings_payload=embeddings_payload,
        feedback_payload=feedback_payload,
        multi_channel_fusion_payload=multi_channel_fusion_payload,
        second_pass_payload=second_pass_payload,
        refine_pass_payload=refine_pass_payload,
        chunk_semantic_rerank_payload=chunk_semantic_rerank_payload,
        topological_shield_payload=topological_shield_payload,
        chunk_guard_payload=chunk_guard_payload,
        adaptive_router_payload=adaptive_router_payload,
        policy_name=str(policy.get("name", "general")),
        policy_version=str(policy.get("version", retrieval_cfg.policy_version)),
        timings_ms=timings_ms,
    )
    index_candidate_cache["store_written"] = bool(
        store_cached_index_candidates(
            cache_path=index_candidate_cache_path,
            key=index_candidate_cache_key,
            payload=_clone_index_candidate_payload(payload),
            meta={
                **index_candidate_cache_required_meta,
                "query": ctx.query,
                "ttl_seconds": int(index_candidate_cache_ttl_seconds),
                "trust_class": "exact",
            },
        )
    )
    return _attach_index_candidate_cache_info(
        payload=payload,
        cache_info=index_candidate_cache,
    )


__all__ = ["IndexStageConfig", "run_index"]
