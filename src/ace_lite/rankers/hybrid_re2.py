"""Hybrid RE2 candidate ranker.

This ranker combines BM25 and heuristic scores using either linear
combination or Reciprocal Rank Fusion (RRF), plus term coverage scoring.
"""

from __future__ import annotations

from typing import Any

from ace_lite.rankers.bm25 import rank_candidates_bm25
from ace_lite.rankers.heuristic import rank_candidates_heuristic
from ace_lite.rankers.rrf import fuse_rrf
from ace_lite.scoring_config import (
    HYBRID_BM25_WEIGHT,
    HYBRID_COMBINED_SCALE,
    HYBRID_COVERAGE_WEIGHT,
    HYBRID_HEURISTIC_WEIGHT,
    HYBRID_RRF_K_DEFAULT,
    HYBRID_SHORTLIST_FACTOR,
    HYBRID_SHORTLIST_MIN,
)
from ace_lite.text_tokens import code_token_set


def _compute_term_coverage(
    *,
    path: str,
    entry: dict[str, Any],
    terms: list[str],
) -> float:
    """Compute fraction of query terms found in file metadata.

    Args:
        path: File path.
        entry: Index entry for the file.
        terms: Normalized query terms.

    Returns:
        Coverage score in [0, 1].
    """
    if not terms:
        return 0.0

    fragments: list[str] = [path.lower(), str(entry.get("module", "")).lower()]

    symbols = entry.get("symbols", [])
    if isinstance(symbols, list):
        for item in symbols:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", ""))
            qualified = str(item.get("qualified_name", ""))
            if name:
                fragments.append(name.lower())
            if qualified:
                fragments.append(qualified.lower())

    imports = entry.get("imports", [])
    if isinstance(imports, list):
        for item in imports:
            if not isinstance(item, dict):
                continue
            module_name = str(item.get("module", ""))
            import_name = str(item.get("name", ""))
            if module_name:
                fragments.append(module_name.lower())
            if import_name:
                fragments.append(import_name.lower())

    haystack = " ".join(fragment for fragment in fragments if fragment)
    if not haystack:
        return 0.0

    token_set = code_token_set(haystack, min_len=2, max_tokens=512)

    covered = 0.0
    for term in terms:
        if not term:
            continue
        if term in token_set:
            covered += 1.0
        elif term in haystack:
            covered += 0.5

    return max(0.0, min(1.0, covered / max(1, len(terms))))


def normalize_fusion_mode(fusion_mode: str) -> str:
    """Normalize fusion mode string.

    Args:
        fusion_mode: Input fusion mode string.

    Returns:
        Normalized fusion mode ("linear" or "rrf").
    """
    normalized = str(fusion_mode or "linear").strip().lower()
    if normalized not in ("linear", "rrf"):
        return "linear"
    return normalized


def rank_candidates_hybrid_re2(
    files_map: Any,
    terms: list[str],
    *,
    min_score: int = 1,
    top_n: int = 8,
    fusion_mode: str = "linear",
    rrf_k: int = HYBRID_RRF_K_DEFAULT,
    weights: dict[str, float] | None = None,
    index_hash: str | None = None,
) -> list[dict[str, Any]]:
    """Rank candidates using hybrid RE2 scoring.

    Hybrid RE2 combines:
    1. BM25 scores (from coarse ranking)
    2. Heuristic scores (on shortlist)
    3. Term coverage scores

    Fusion can be linear combination or RRF.

    Args:
        files_map: Dict mapping file paths to their index entries.
        terms: List of query terms to match.
        min_score: Minimum score threshold (default 1).
        top_n: Number of top candidates to return.
        fusion_mode: "linear" or "rrf" (default "linear").
        rrf_k: RRF k parameter (default 60).

    Returns:
        List of candidate dicts sorted by score (descending).
    """
    if not isinstance(files_map, dict):
        return []

    normalized_terms = [
        str(term).strip().lower() for term in terms if str(term).strip()
    ]
    if not normalized_terms:
        return []

    # Coarse BM25 ranking
    try:
        coarse = rank_candidates_bm25(
            files_map,
            normalized_terms,
            min_score=0,
            index_hash=index_hash,
        )
    except TypeError:
        coarse = rank_candidates_bm25(files_map, normalized_terms, min_score=0)
    if not coarse:
        return []

    # Create shortlist
    shortlist_limit = max(
        max(1, int(top_n)) * HYBRID_SHORTLIST_FACTOR, HYBRID_SHORTLIST_MIN
    )
    shortlist = coarse[:shortlist_limit]

    shortlist_files = {
        str(item.get("path", "")): files_map.get(str(item.get("path", "")))
        for item in shortlist
        if isinstance(item, dict)
        and isinstance(files_map.get(str(item.get("path", ""))), dict)
    }

    # Fine-grained heuristic ranking on shortlist
    heuristic_ranked = rank_candidates_heuristic(
        shortlist_files, normalized_terms, min_score=0
    )
    heuristic_scores = {
        str(item.get("path", "")): float(item.get("score") or 0.0)
        for item in heuristic_ranked
    }

    # BM25 scores for shortlist
    bm25_scores = {
        str(item.get("path", "")): float(item.get("score") or 0.0)
        for item in shortlist
    }

    # Normalize scores
    bm25_max = max((float(score) for score in bm25_scores.values()), default=0.0)
    heuristic_max = max(
        (float(score) for score in heuristic_scores.values()), default=0.0
    )

    normalized_fusion_mode = normalize_fusion_mode(fusion_mode)

    bm25_weight = float(HYBRID_BM25_WEIGHT)
    heuristic_weight = float(HYBRID_HEURISTIC_WEIGHT)
    coverage_weight = float(HYBRID_COVERAGE_WEIGHT)
    combined_scale = float(HYBRID_COMBINED_SCALE)
    if isinstance(weights, dict):
        bm25_weight = max(0.0, float(weights.get("bm25_weight", bm25_weight) or 0.0))
        heuristic_weight = max(
            0.0, float(weights.get("heuristic_weight", heuristic_weight) or 0.0)
        )
        coverage_weight = max(
            0.0, float(weights.get("coverage_weight", coverage_weight) or 0.0)
        )
        combined_scale = max(
            0.0, float(weights.get("combined_scale", combined_scale) or 0.0)
        )
        if bm25_weight <= 0.0 and heuristic_weight <= 0.0 and coverage_weight <= 0.0:
            bm25_weight = float(HYBRID_BM25_WEIGHT)
            heuristic_weight = float(HYBRID_HEURISTIC_WEIGHT)
            coverage_weight = float(HYBRID_COVERAGE_WEIGHT)
        if combined_scale <= 0.0:
            combined_scale = float(HYBRID_COMBINED_SCALE)

    # RRF fusion
    rrf_scores = fuse_rrf(
        rankings=[
            [str(item.get("path", "")).strip() for item in shortlist],
            [str(item.get("path", "")).strip() for item in heuristic_ranked],
        ],
        rrf_k=max(1, int(rrf_k)),
    )
    rrf_max = max((float(score) for score in rrf_scores.values()), default=0.0)

    threshold = max(0.0, float(min_score))
    ranked: list[dict[str, Any]] = []

    for item in shortlist:
        path = str(item.get("path", ""))
        if not path:
            continue
        entry = files_map.get(path)
        if not isinstance(entry, dict):
            continue

        bm25_score = float(bm25_scores.get(path, 0.0))
        heuristic_score = float(heuristic_scores.get(path, 0.0))
        bm25_norm = bm25_score / bm25_max if bm25_max > 0 else 0.0
        heuristic_norm = heuristic_score / heuristic_max if heuristic_max > 0 else 0.0
        coverage = _compute_term_coverage(
            path=path, entry=entry, terms=normalized_terms
        )

        rrf_norm = float(rrf_scores.get(path, 0.0)) / rrf_max if rrf_max > 0 else 0.0

        # Compute combined score
        if normalized_fusion_mode == "rrf":
            combined_score = (
                (rrf_norm * (bm25_weight + heuristic_weight))
                + (coverage * coverage_weight)
            ) * combined_scale
        else:
            combined_score = (
                (bm25_norm * bm25_weight)
                + (heuristic_norm * heuristic_weight)
                + (coverage * coverage_weight)
            ) * combined_scale

        if combined_score < threshold:
            continue

        symbols = entry.get("symbols", [])
        imports = entry.get("imports", [])
        ranked.append(
            {
                "path": path,
                "module": str(entry.get("module", "")),
                "language": entry.get("language", ""),
                "score": round(float(combined_score), 6),
                "symbol_count": len(symbols) if isinstance(symbols, list) else 0,
                "import_count": len(imports) if isinstance(imports, list) else 0,
                "score_breakdown": {
                    "bm25_norm": round(bm25_norm, 6),
                    "heuristic_norm": round(heuristic_norm, 6),
                    "rrf_norm": round(rrf_norm, 6),
                    "re2_coverage": round(coverage, 6),
                    "fusion_mode": normalized_fusion_mode,
                    "rrf_k": max(1, int(rrf_k)),
                    "ranker": "hybrid_re2",
                },
            }
        )

    ranked.sort(
        key=lambda candidate: (
            -float(candidate.get("score") or 0.0),
            str(candidate.get("path") or ""),
        )
    )
    return ranked


__all__ = [
    "_compute_term_coverage",
    "normalize_fusion_mode",
    "rank_candidates_hybrid_re2",
]
