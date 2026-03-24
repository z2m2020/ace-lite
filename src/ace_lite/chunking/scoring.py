"""Chunk scoring algorithms."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ace_lite.explainability import build_selection_reason
from ace_lite.scoring_config import (
    resolve_chunk_scoring_config,
)


def score_chunk_candidate(
    *,
    path: str,
    module: str,
    qualified_name: str,
    name: str,
    signature: str,
    terms: list[str],
    file_score: float,
    reference_hits: dict[str, int],
    scoring_config: Mapping[str, Any] | None = None,
) -> tuple[float, dict[str, float]]:
    """Score a candidate chunk based on term matching and references.

    Args:
        path: File path.
        module: Module name.
        qualified_name: Fully qualified symbol name.
        name: Simple symbol name.
        signature: Function/method signature line.
        terms: Query terms to match.
        file_score: Parent file's candidate score.
        reference_hits: Dict of symbol names to reference counts.

    Returns:
        Tuple of (score, breakdown_dict).
    """
    scoring = resolve_chunk_scoring_config(scoring_config)
    file_prior_weight = float(scoring["file_prior_weight"])
    path_match = float(scoring["path_match"])
    module_match = float(scoring["module_match"])
    symbol_exact = float(scoring["symbol_exact"])
    symbol_partial = float(scoring["symbol_partial"])
    signature_match = float(scoring["signature_match"])
    reference_factor = float(scoring["reference_factor"])
    reference_cap = float(scoring["reference_cap"])

    score = max(0.0, float(file_score) * file_prior_weight)
    breakdown = {
        "file_prior": round(score, 6),
        "path": 0.0,
        "module": 0.0,
        "symbol": 0.0,
        "signature": 0.0,
        "reference": 0.0,
    }

    path_lower = path.lower()
    module_lower = module.lower()
    qualified_lower = qualified_name.lower()
    name_lower = name.lower()
    signature_lower = signature.lower()

    for term in [str(item).strip().lower() for item in terms if str(item).strip()]:
        # Path matching
        if term in path_lower:
            score += path_match
            breakdown["path"] += path_match

        # Module matching
        if term and term in module_lower:
            score += module_match
            breakdown["module"] += module_match

        # Symbol matching
        if term in (qualified_lower, name_lower):
            score += symbol_exact
            breakdown["symbol"] += symbol_exact
        elif term in qualified_lower or term in name_lower:
            score += symbol_partial
            breakdown["symbol"] += symbol_partial

        # Signature matching
        if signature_lower and term and term in signature_lower:
            score += signature_match
            breakdown["signature"] += signature_match

    # Reference-based scoring
    reference_score = max(
        float(reference_hits.get(qualified_name, 0)),
        float(reference_hits.get(name, 0)),
    )
    if reference_score > 0:
        weight = min(reference_cap, reference_factor * reference_score)
        score += weight
        breakdown["reference"] = round(weight, 6)

    return score, {key: round(value, 6) for key, value in breakdown.items()}


def build_chunk_step_reason(item: dict[str, Any]) -> str:
    """Build a human-readable reason string for chunk selection.

    Args:
        item: Chunk candidate dict with score_breakdown.

    Returns:
        String describing why this chunk was selected.
    """
    return build_selection_reason(item, default_reason="ranked_chunk_candidate")


__all__ = ["build_chunk_step_reason", "score_chunk_candidate"]
