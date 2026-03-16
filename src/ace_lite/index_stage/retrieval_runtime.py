from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class IndexRetrievalRuntime:
    fusion_mode: str
    hybrid_weights: dict[str, float]
    runtime_profile: Any
    parallel_requested: bool
    parallel_time_budget_ms: int
    rank_candidates: Callable[..., list[dict[str, Any]]]


def build_index_retrieval_runtime(
    *,
    retrieval_cfg: Any,
    policy: dict[str, Any],
    index_hash: str,
    terms: list[str],
    effective_files_map: dict[str, Any],
    normalize_fusion_mode_fn: Callable[[str], str],
    build_retrieval_runtime_profile_fn: Callable[..., Any],
) -> IndexRetrievalRuntime:
    fusion_mode = normalize_fusion_mode_fn(retrieval_cfg.hybrid_re2_fusion_mode)
    hybrid_weights = {
        "bm25_weight": float(retrieval_cfg.hybrid_re2_bm25_weight),
        "heuristic_weight": float(retrieval_cfg.hybrid_re2_heuristic_weight),
        "coverage_weight": float(retrieval_cfg.hybrid_re2_coverage_weight),
        "combined_scale": float(retrieval_cfg.hybrid_re2_combined_scale),
    }
    runtime_profile = build_retrieval_runtime_profile_fn(
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

    def rank_candidates(
        min_score: int,
        candidate_ranker: str,
        candidate_terms: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        ranked_terms = terms if candidate_terms is None else candidate_terms
        return runtime_profile.rank_candidates(
            files_map=effective_files_map,
            terms=ranked_terms,
            candidate_ranker=candidate_ranker,
            min_score=min_score,
        )

    return IndexRetrievalRuntime(
        fusion_mode=fusion_mode,
        hybrid_weights=hybrid_weights,
        runtime_profile=runtime_profile,
        parallel_requested=parallel_requested,
        parallel_time_budget_ms=parallel_time_budget_ms,
        rank_candidates=rank_candidates,
    )


__all__ = ["IndexRetrievalRuntime", "build_index_retrieval_runtime"]
