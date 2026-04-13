"""Candidate refinement and fusion orchestration for the index stage."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.embeddings import CrossEncoderProvider, EmbeddingProvider
from ace_lite.index_stage.candidate_postprocess import CandidatePostprocessResult
from ace_lite.index_stage.repo_paths import normalize_repo_path
from ace_lite.rankers import fuse_rrf, normalize_rrf_scores


@dataclass(frozen=True, slots=True)
class CandidateFusionDeps:
    """Injected helper dependencies for the candidate refinement seam."""

    postprocess_candidates: Callable[..., CandidatePostprocessResult]
    apply_structural_rerank: Callable[..., Any]
    apply_semantic_candidate_rerank: Callable[..., Any]
    apply_feedback_boost: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]]
    apply_multi_channel_rrf_fusion: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]]
    merge_candidate_lists: Callable[..., list[dict[str, Any]]]
    resolve_embedding_runtime_config: Callable[..., Any]
    build_embedding_stats: Callable[..., dict[str, Any]]
    rerank_cross_encoder_with_time_budget: Callable[..., tuple[list[dict[str, Any]], Any]]
    mark_timing: Callable[[str, float], None]


@dataclass(slots=True)
class CandidateFusionResult:
    candidates: list[dict[str, Any]]
    second_pass_payload: dict[str, Any]
    refine_pass_payload: dict[str, Any]
    cochange_payload: dict[str, Any]
    scip_payload: dict[str, Any]
    graph_lookup_payload: dict[str, Any]
    embeddings_payload: dict[str, Any]
    feedback_payload: dict[str, Any]
    multi_channel_fusion_payload: dict[str, Any]
    semantic_embedding_provider_impl: EmbeddingProvider | None
    semantic_cross_encoder_provider: CrossEncoderProvider | None
    retrieval_refinement_payload: dict[str, Any] = field(default_factory=dict)


def _call_with_supported_kwargs(func: Callable[..., Any], **kwargs: Any) -> Any:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return func(**kwargs)
    supported = {
        name
        for name, parameter in signature.parameters.items()
        if parameter.kind
        in (
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    }
    filtered_kwargs = {
        key: value for key, value in kwargs.items() if key in supported
    }
    return func(**filtered_kwargs)


def _candidate_granularity_score(entry: dict[str, Any]) -> float:
    if not isinstance(entry, dict):
        return 0.0

    explicit_symbol_count = entry.get("symbol_count")
    try:
        if explicit_symbol_count is not None:
            return max(0.0, float(explicit_symbol_count or 0.0))
    except Exception:
        pass

    classes_raw = entry.get("classes")
    classes = classes_raw if isinstance(classes_raw, list) else []
    functions_raw = entry.get("functions")
    functions = functions_raw if isinstance(functions_raw, list) else []
    return float(len(classes) + len(functions))


def apply_multi_channel_rrf_fusion(
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
            "granularity": {"count": 0, "cap": int(code_cap_effective), "top": []},
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
        path = normalize_repo_path(str(row.get("path") or ""))
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
            path = normalize_repo_path(str(row.get("value") or ""))
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
        path = normalize_repo_path(str(raw_path or ""))
        if not path or path in seen_memory:
            continue
        if path not in pool_set or path not in files_map:
            continue
        seen_memory.add(path)
        memory_ranking.append(path)
        if len(memory_ranking) >= memory_cap_effective:
            break

    granularity_scored_paths: list[tuple[float, str]] = []
    for path in pool_paths:
        file_entry = files_map.get(path)
        if not isinstance(file_entry, dict):
            continue
        score = _candidate_granularity_score(file_entry)
        if score <= 0.0:
            continue
        granularity_scored_paths.append((score, path))
    granularity_scored_paths.sort(key=lambda item: (-float(item[0]), str(item[1])))
    granularity_ranking: list[str] = []
    seen_granularity: set[str] = set()
    for score, path in granularity_scored_paths:
        _ = score
        if path in seen_granularity:
            continue
        seen_granularity.add(path)
        granularity_ranking.append(path)
        if len(granularity_ranking) >= code_cap_effective:
            break

    payload["channels"]["code"]["count"] = len(code_ranking)
    payload["channels"]["docs"]["count"] = len(docs_ranking)
    payload["channels"]["memory"]["count"] = len(memory_ranking)
    payload["channels"]["granularity"]["count"] = len(granularity_ranking)
    payload["channels"]["code"]["top"] = list(code_ranking[:8])
    payload["channels"]["docs"]["top"] = list(docs_ranking[:8])
    payload["channels"]["memory"]["top"] = list(memory_ranking[:8])
    payload["channels"]["granularity"]["top"] = list(granularity_ranking[:8])

    if not docs_ranking and not memory_ranking and not granularity_ranking:
        payload["reason"] = "no_aux_rankings"
        return candidates, payload

    try:
        fused_raw = fuse_rrf(
            [code_ranking, docs_ranking, memory_ranking, granularity_ranking],
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
    granularity_pos = {
        path: rank for rank, path in enumerate(granularity_ranking, start=1)
    }

    rrf_scores: dict[str, float] = {str(k): float(v) for k, v in fused.items()}
    payload["fused"]["scored_count"] = len(rrf_scores)

    for row in pool:
        if not isinstance(row, dict):
            continue
        path = normalize_repo_path(str(row.get("path") or ""))
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
                    normalize_repo_path(str(row.get("path") or "")),
                    0.0,
                )
                or 0.0
            ),
            -float(row.get("score", 0.0) or 0.0),
            normalize_repo_path(str(row.get("path") or "")),
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
                    "granularity": int(granularity_pos.get(path, 0) or 0),
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
                    "granularity": float(
                        round(
                            1.0
                            / (
                                rrf_k_effective
                                + int(granularity_pos.get(path, 0) or 0)
                            ),
                            8,
                        )
                    )
                    if int(granularity_pos.get(path, 0) or 0) > 0
                    else 0.0,
                },
            }
        )

    payload["fused"]["top"] = fused_top
    payload["fused"]["pool_size"] = int(pool_cap_effective)
    payload["applied"] = True
    payload["reason"] = "ok"
    return pool + tail, payload


def refine_candidate_pool(
    *,
    root: str,
    repo: str,
    query: str,
    terms: list[str],
    files_map: dict[str, Any],
    candidates: list[dict[str, Any]],
    memory_paths: list[str],
    docs_payload: dict[str, Any],
    policy: dict[str, Any],
    selected_ranker: str,
    top_k_files: int,
    candidate_relative_threshold: float,
    refine_enabled: bool,
    rank_candidates: Callable[..., list[dict[str, Any]]],
    index_hash: str,
    cochange_enabled: bool,
    cochange_cache_path: str,
    cochange_lookback_commits: int,
    cochange_half_life_days: float,
    cochange_neighbor_cap: int,
    cochange_top_neighbors: int,
    cochange_boost_weight: float,
    cochange_min_neighbor_score: float,
    cochange_max_boost: float,
    scip_enabled: bool,
    scip_index_path: str,
    scip_provider: str,
    scip_generate_fallback: bool,
    scip_base_weight: float,
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
    feedback_enabled: bool,
    feedback_path: str,
    feedback_max_entries: int,
    feedback_boost_per_select: float,
    feedback_max_boost: float,
    feedback_decay_days: float,
    multi_channel_rrf_enabled: bool,
    multi_channel_rrf_k: int,
    multi_channel_rrf_pool_cap: int,
    multi_channel_rrf_code_cap: int,
    multi_channel_rrf_docs_cap: int,
    multi_channel_rrf_memory_cap: int,
    deps: CandidateFusionDeps,
    retrieval_refinement: dict[str, Any] | None = None,
) -> CandidateFusionResult:
    """Apply postprocess, rerank, feedback, and multi-channel fusion."""

    timing_started = perf_counter()
    candidate_postprocess_result = deps.postprocess_candidates(
        candidates=candidates,
        files_map=files_map,
        selected_ranker=selected_ranker,
        top_k_files=int(top_k_files),
        candidate_relative_threshold=float(candidate_relative_threshold),
        refine_enabled=bool(refine_enabled),
        retrieval_refinement=retrieval_refinement,
        rank_candidates=rank_candidates,
        merge_candidate_lists=deps.merge_candidate_lists,
    )
    refined_candidates = list(candidate_postprocess_result.candidates)
    second_pass_payload = candidate_postprocess_result.second_pass_payload
    refine_pass_payload = candidate_postprocess_result.refine_pass_payload
    retrieval_refinement_payload = (
        dict(candidate_postprocess_result.retrieval_refinement_payload)
        if bool(candidate_postprocess_result.retrieval_refinement_payload.get("enabled"))
        else {}
    )
    deps.mark_timing("candidate_postprocess", timing_started)

    structural_rerank = _call_with_supported_kwargs(
        deps.apply_structural_rerank,
        root=root,
        files_map=files_map,
        candidates=refined_candidates,
        memory_paths=memory_paths,
        terms=terms,
        policy=policy,
        cochange_enabled=bool(cochange_enabled),
        cochange_cache_path=str(cochange_cache_path),
        cochange_lookback_commits=int(cochange_lookback_commits),
        cochange_half_life_days=float(cochange_half_life_days),
        cochange_neighbor_cap=int(cochange_neighbor_cap),
        top_k_files=int(top_k_files),
        cochange_top_neighbors=int(cochange_top_neighbors),
        cochange_boost_weight=float(cochange_boost_weight),
        cochange_min_neighbor_score=float(cochange_min_neighbor_score),
        cochange_max_boost=float(cochange_max_boost),
        scip_enabled=bool(scip_enabled),
        scip_index_path=str(scip_index_path),
        scip_provider=str(scip_provider),
        scip_generate_fallback=bool(scip_generate_fallback),
        scip_base_weight=float(scip_base_weight),
        mark_timing=deps.mark_timing,
    )
    refined_candidates = list(structural_rerank.candidates)
    cochange_payload = structural_rerank.cochange_payload
    scip_payload = structural_rerank.scip_payload
    graph_lookup_payload = structural_rerank.graph_lookup_payload

    semantic_candidate_rerank = deps.apply_semantic_candidate_rerank(
        root=root,
        query=query,
        files_map=files_map,
        candidates=refined_candidates,
        terms=terms,
        index_hash=index_hash,
        embedding_index_path=embedding_index_path,
        embedding_enabled=bool(embedding_enabled),
        embedding_provider=str(embedding_provider),
        embedding_model=str(embedding_model),
        embedding_dimension=int(embedding_dimension),
        embedding_rerank_pool=int(embedding_rerank_pool),
        embedding_lexical_weight=float(embedding_lexical_weight),
        embedding_semantic_weight=float(embedding_semantic_weight),
        embedding_min_similarity=float(embedding_min_similarity),
        embedding_fail_open=bool(embedding_fail_open),
        policy=policy,
        mark_timing=deps.mark_timing,
        resolve_embedding_runtime_config=deps.resolve_embedding_runtime_config,
        build_embedding_stats=deps.build_embedding_stats,
        rerank_cross_encoder_with_time_budget=(
            deps.rerank_cross_encoder_with_time_budget
        ),
    )
    refined_candidates = list(semantic_candidate_rerank.candidates)
    embeddings_payload = semantic_candidate_rerank.embeddings_payload
    semantic_embedding_provider_impl = (
        semantic_candidate_rerank.semantic_embedding_provider_impl
    )
    semantic_cross_encoder_provider = (
        semantic_candidate_rerank.semantic_cross_encoder_provider
    )

    feedback_payload: dict[str, Any] = {
        "enabled": bool(feedback_enabled),
        "reason": "disabled",
        "path": "",
        "event_count": 0,
        "matched_event_count": 0,
        "boosted_candidate_count": 0,
        "boosted_unique_paths": 0,
    }
    timing_started = perf_counter()
    if bool(feedback_enabled) and refined_candidates:
        refined_candidates, feedback_payload = deps.apply_feedback_boost(
            candidates=refined_candidates,
            repo=repo,
            root=root,
            enabled=bool(feedback_enabled),
            configured_path=str(feedback_path),
            max_entries=int(feedback_max_entries),
            boost_per_select=float(feedback_boost_per_select),
            max_boost=float(feedback_max_boost),
            decay_days=float(feedback_decay_days),
            query_terms=terms,
            policy=policy,
        )
    deps.mark_timing("feedback_boost", timing_started)

    multi_channel_fusion_payload: dict[str, Any] = {
        "enabled": bool(multi_channel_rrf_enabled),
        "applied": False,
        "reason": "disabled",
        "rrf_k": max(1, int(multi_channel_rrf_k)),
        "caps": {
            "pool": int(multi_channel_rrf_pool_cap),
            "code": int(multi_channel_rrf_code_cap),
            "docs": int(multi_channel_rrf_docs_cap),
            "memory": int(multi_channel_rrf_memory_cap),
        },
        "channels": {
            "code": {"count": 0, "cap": 0, "top": []},
            "docs": {"count": 0, "cap": 0, "top": []},
            "memory": {"count": 0, "cap": 0, "top": []},
        },
        "fused": {"scored_count": 0, "pool_size": 0, "top": []},
        "warning": None,
    }
    timing_started = perf_counter()
    if bool(multi_channel_rrf_enabled) and refined_candidates:
        refined_candidates, multi_channel_fusion_payload = (
            deps.apply_multi_channel_rrf_fusion(
                candidates=refined_candidates,
                files_map=files_map,
                docs_payload=docs_payload,
                memory_paths=memory_paths,
                top_k_files=int(top_k_files),
                rrf_k=int(multi_channel_rrf_k),
                pool_cap=int(multi_channel_rrf_pool_cap),
                code_cap=int(multi_channel_rrf_code_cap),
                docs_cap=int(multi_channel_rrf_docs_cap),
                memory_cap=int(multi_channel_rrf_memory_cap),
            )
        )
    deps.mark_timing("multi_channel_fusion", timing_started)

    return CandidateFusionResult(
        candidates=list(refined_candidates),
        second_pass_payload=second_pass_payload,
        refine_pass_payload=refine_pass_payload,
        cochange_payload=cochange_payload,
        scip_payload=scip_payload,
        graph_lookup_payload=graph_lookup_payload,
        embeddings_payload=embeddings_payload,
        feedback_payload=feedback_payload,
        multi_channel_fusion_payload=multi_channel_fusion_payload,
        semantic_embedding_provider_impl=semantic_embedding_provider_impl,
        semantic_cross_encoder_provider=semantic_cross_encoder_provider,
        retrieval_refinement_payload=retrieval_refinement_payload,
    )


__all__ = [
    "CandidateFusionDeps",
    "CandidateFusionResult",
    "apply_multi_channel_rrf_fusion",
    "refine_candidate_pool",
]
