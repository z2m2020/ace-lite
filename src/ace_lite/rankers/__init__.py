"""Candidate ranking modules.

This package provides modular ranking algorithms for file candidate selection:

- `heuristic`: Fast hand-crafted scoring rules
- `bm25`: Okapi BM25 probabilistic ranking
- `hybrid_re2`: Combined BM25 + heuristic + coverage scoring
- `rrf`: Reciprocal Rank Fusion for combining rankings

Usage:
    from ace_lite.rankers import (
        rank_candidates_heuristic,
        rank_candidates_bm25,
        rank_candidates_hybrid_re2,
    )
"""

from __future__ import annotations

from ace_lite.rankers.bm25 import (
    rank_candidates_bm25,
    rank_candidates_bm25_two_stage,
)
from ace_lite.rankers.heuristic import rank_candidates_heuristic
from ace_lite.rankers.hybrid_re2 import (
    _compute_term_coverage,
    normalize_fusion_mode,
    rank_candidates_hybrid_re2,
)
from ace_lite.rankers.rrf import fuse_rrf, normalize_rrf_scores
from ace_lite.rankers.types import Candidate, RankerFunc, RankResult

__all__ = [
    "Candidate",
    "RankResult",
    "RankerFunc",
    "_compute_term_coverage",
    "fuse_rrf",
    "normalize_fusion_mode",
    "normalize_rrf_scores",
    "rank_candidates_bm25",
    "rank_candidates_bm25_two_stage",
    "rank_candidates_heuristic",
    "rank_candidates_hybrid_re2",
]
