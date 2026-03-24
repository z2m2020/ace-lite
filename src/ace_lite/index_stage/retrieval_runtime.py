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
    bm25_config = {
        "k1": float(retrieval_cfg.bm25_k1),
        "b": float(retrieval_cfg.bm25_b),
        "score_scale": float(retrieval_cfg.bm25_score_scale),
        "path_prior_factor": float(retrieval_cfg.bm25_path_prior_factor),
        "shortlist_min": int(retrieval_cfg.bm25_shortlist_min),
        "shortlist_factor": int(retrieval_cfg.bm25_shortlist_factor),
    }
    heuristic_config = {
        "path_exact": float(retrieval_cfg.heur_path_exact),
        "path_contains": float(retrieval_cfg.heur_path_contains),
        "module_exact": float(retrieval_cfg.heur_module_exact),
        "module_tail": float(retrieval_cfg.heur_module_tail),
        "module_contains": float(retrieval_cfg.heur_module_contains),
        "symbol_exact": float(retrieval_cfg.heur_symbol_exact),
        "symbol_partial_factor": float(retrieval_cfg.heur_symbol_partial_factor),
        "symbol_partial_cap": float(retrieval_cfg.heur_symbol_partial_cap),
        "import_factor": float(retrieval_cfg.heur_import_factor),
        "import_cap": float(retrieval_cfg.heur_import_cap),
        "content_symbol_factor": float(retrieval_cfg.heur_content_symbol_factor),
        "content_import_factor": float(retrieval_cfg.heur_content_import_factor),
        "content_cap": float(retrieval_cfg.heur_content_cap),
        "depth_base": float(retrieval_cfg.heur_depth_base),
        "depth_factor": float(retrieval_cfg.heur_depth_factor),
    }
    hybrid_config = {
        "shortlist_min": int(retrieval_cfg.hybrid_re2_shortlist_min),
        "shortlist_factor": int(retrieval_cfg.hybrid_re2_shortlist_factor),
    }
    runtime_profile = build_retrieval_runtime_profile_fn(
        candidate_ranker=retrieval_cfg.candidate_ranker,
        min_candidate_score=int(retrieval_cfg.min_candidate_score),
        top_k_files=int(retrieval_cfg.top_k_files),
        hybrid_fusion_mode=fusion_mode,
        hybrid_rrf_k=int(retrieval_cfg.hybrid_re2_rrf_k),
        hybrid_weights=hybrid_weights,
        bm25_config=bm25_config,
        heuristic_config=heuristic_config,
        hybrid_config=hybrid_config,
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
