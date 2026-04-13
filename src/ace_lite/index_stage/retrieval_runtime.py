from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from ace_lite.scoring_config import (
    BM25_B,
    BM25_K1,
    BM25_PATH_PRIOR_FACTOR,
    BM25_SCORE_SCALE,
    BM25_SHORTLIST_FACTOR,
    BM25_SHORTLIST_MIN,
    HEUR_CONTENT_CAP,
    HEUR_CONTENT_IMPORT_FACTOR,
    HEUR_CONTENT_SYMBOL_FACTOR,
    HEUR_DEPTH_BASE,
    HEUR_DEPTH_FACTOR,
    HEUR_IMPORT_CAP,
    HEUR_IMPORT_FACTOR,
    HEUR_MODULE_CONTAINS,
    HEUR_MODULE_EXACT,
    HEUR_MODULE_TAIL,
    HEUR_PATH_CONTAINS,
    HEUR_PATH_EXACT,
    HEUR_SYMBOL_EXACT,
    HEUR_SYMBOL_PARTIAL_CAP,
    HEUR_SYMBOL_PARTIAL_FACTOR,
    HYBRID_SHORTLIST_FACTOR,
    HYBRID_SHORTLIST_MIN,
)


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
    fusion_mode = normalize_fusion_mode_fn(
        str(getattr(retrieval_cfg, "hybrid_re2_fusion_mode", "relative"))
    )
    hybrid_weights = {
        "bm25_weight": float(
            getattr(retrieval_cfg, "hybrid_re2_bm25_weight", 0.45) or 0.45
        ),
        "heuristic_weight": float(
            getattr(retrieval_cfg, "hybrid_re2_heuristic_weight", 0.45) or 0.45
        ),
        "coverage_weight": float(
            getattr(retrieval_cfg, "hybrid_re2_coverage_weight", 0.10) or 0.10
        ),
        "combined_scale": float(
            getattr(retrieval_cfg, "hybrid_re2_combined_scale", 10.0) or 10.0
        ),
    }
    bm25_config = {
        "k1": float(getattr(retrieval_cfg, "bm25_k1", BM25_K1) or BM25_K1),
        "b": float(getattr(retrieval_cfg, "bm25_b", BM25_B) or BM25_B),
        "score_scale": float(
            getattr(retrieval_cfg, "bm25_score_scale", BM25_SCORE_SCALE)
            or BM25_SCORE_SCALE
        ),
        "path_prior_factor": float(
            getattr(
                retrieval_cfg,
                "bm25_path_prior_factor",
                BM25_PATH_PRIOR_FACTOR,
            )
            or BM25_PATH_PRIOR_FACTOR
        ),
        "shortlist_min": int(
            getattr(retrieval_cfg, "bm25_shortlist_min", BM25_SHORTLIST_MIN)
            or BM25_SHORTLIST_MIN
        ),
        "shortlist_factor": int(
            getattr(
                retrieval_cfg,
                "bm25_shortlist_factor",
                BM25_SHORTLIST_FACTOR,
            )
            or BM25_SHORTLIST_FACTOR
        ),
    }
    heuristic_config = {
        "path_exact": float(
            getattr(retrieval_cfg, "heur_path_exact", HEUR_PATH_EXACT)
            or HEUR_PATH_EXACT
        ),
        "path_contains": float(
            getattr(retrieval_cfg, "heur_path_contains", HEUR_PATH_CONTAINS)
            or HEUR_PATH_CONTAINS
        ),
        "module_exact": float(
            getattr(retrieval_cfg, "heur_module_exact", HEUR_MODULE_EXACT)
            or HEUR_MODULE_EXACT
        ),
        "module_tail": float(
            getattr(retrieval_cfg, "heur_module_tail", HEUR_MODULE_TAIL)
            or HEUR_MODULE_TAIL
        ),
        "module_contains": float(
            getattr(retrieval_cfg, "heur_module_contains", HEUR_MODULE_CONTAINS)
            or HEUR_MODULE_CONTAINS
        ),
        "symbol_exact": float(
            getattr(retrieval_cfg, "heur_symbol_exact", HEUR_SYMBOL_EXACT)
            or HEUR_SYMBOL_EXACT
        ),
        "symbol_partial_factor": float(
            getattr(
                retrieval_cfg,
                "heur_symbol_partial_factor",
                HEUR_SYMBOL_PARTIAL_FACTOR,
            )
            or HEUR_SYMBOL_PARTIAL_FACTOR
        ),
        "symbol_partial_cap": float(
            getattr(retrieval_cfg, "heur_symbol_partial_cap", HEUR_SYMBOL_PARTIAL_CAP)
            or HEUR_SYMBOL_PARTIAL_CAP
        ),
        "import_factor": float(
            getattr(retrieval_cfg, "heur_import_factor", HEUR_IMPORT_FACTOR)
            or HEUR_IMPORT_FACTOR
        ),
        "import_cap": float(
            getattr(retrieval_cfg, "heur_import_cap", HEUR_IMPORT_CAP)
            or HEUR_IMPORT_CAP
        ),
        "content_symbol_factor": float(
            getattr(
                retrieval_cfg,
                "heur_content_symbol_factor",
                HEUR_CONTENT_SYMBOL_FACTOR,
            )
            or HEUR_CONTENT_SYMBOL_FACTOR
        ),
        "content_import_factor": float(
            getattr(
                retrieval_cfg,
                "heur_content_import_factor",
                HEUR_CONTENT_IMPORT_FACTOR,
            )
            or HEUR_CONTENT_IMPORT_FACTOR
        ),
        "content_cap": float(
            getattr(retrieval_cfg, "heur_content_cap", HEUR_CONTENT_CAP)
            or HEUR_CONTENT_CAP
        ),
        "depth_base": float(
            getattr(retrieval_cfg, "heur_depth_base", HEUR_DEPTH_BASE)
            or HEUR_DEPTH_BASE
        ),
        "depth_factor": float(
            getattr(retrieval_cfg, "heur_depth_factor", HEUR_DEPTH_FACTOR)
            or HEUR_DEPTH_FACTOR
        ),
    }
    hybrid_config = {
        "shortlist_min": int(
            getattr(
                retrieval_cfg,
                "hybrid_re2_shortlist_min",
                HYBRID_SHORTLIST_MIN,
            )
            or HYBRID_SHORTLIST_MIN
        ),
        "shortlist_factor": int(
            getattr(
                retrieval_cfg,
                "hybrid_re2_shortlist_factor",
                HYBRID_SHORTLIST_FACTOR,
            )
            or HYBRID_SHORTLIST_FACTOR
        ),
    }
    runtime_profile = build_retrieval_runtime_profile_fn(
        candidate_ranker=str(
            getattr(retrieval_cfg, "candidate_ranker", "hybrid_re2")
            or "hybrid_re2"
        ),
        min_candidate_score=int(
            getattr(retrieval_cfg, "min_candidate_score", 1) or 1
        ),
        top_k_files=int(getattr(retrieval_cfg, "top_k_files", 8) or 8),
        hybrid_fusion_mode=fusion_mode,
        hybrid_rrf_k=int(getattr(retrieval_cfg, "hybrid_re2_rrf_k", 60) or 60),
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
        return cast(
            list[dict[str, Any]],
            runtime_profile.rank_candidates(
                files_map=effective_files_map,
                terms=ranked_terms,
                candidate_ranker=candidate_ranker,
                min_score=min_score,
            ),
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
