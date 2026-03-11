"""Reciprocal Rank Fusion (RRF) implementation.

RRF is a simple yet effective method for combining multiple ranked lists
into a single ranking. It's parameterized by a constant k that controls
the influence of individual rankings.

Reference: Cormack, Clarke, and Buettcher. "Reciprocal rank fusion outperforms
condorcet and individual rank learning methods." SIGIR 2009.
"""

from __future__ import annotations


def fuse_rrf(
    rankings: list[list[str]],
    *,
    rrf_k: int = 60,
) -> dict[str, float]:
    """Compute Reciprocal Rank Fusion scores.

    Args:
        rankings: List of ranked item lists (each list is a ranking).
        rrf_k: RRF constant (default 60, from original paper).

    Returns:
        Dict mapping items to their fused RRF scores.
    """
    scores: dict[str, float] = {}

    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            if not item:
                continue
            scores[item] = scores.get(item, 0.0) + 1.0 / (rrf_k + rank)

    return scores


def normalize_rrf_scores(
    scores: dict[str, float],
    *,
    max_score: float | None = None,
) -> dict[str, float]:
    """Normalize RRF scores to [0, 1] range.

    Args:
        scores: Raw RRF scores from fuse_rrf.
        max_score: Optional maximum score for normalization (computed if not provided).

    Returns:
        Dict with normalized scores.
    """
    if not scores:
        return {}

    computed_max = max_score if max_score is not None else max(scores.values())
    if computed_max <= 0:
        return {k: 0.0 for k in scores}

    return {k: v / computed_max for k, v in scores.items()}


__all__ = ["fuse_rrf", "normalize_rrf_scores"]
