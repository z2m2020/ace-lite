"""Chunk diversity penalty algorithms.

Diversity penalties encourage selecting chunks from different files,
symbol families, and code regions to avoid redundant context.
"""

from __future__ import annotations

from typing import Any

from ace_lite.scoring_config import (
    CHUNK_DIVERSITY_KIND_PENALTY,
    CHUNK_DIVERSITY_LOCALITY_PENALTY,
    CHUNK_DIVERSITY_LOCALITY_WINDOW,
    CHUNK_DIVERSITY_PATH_PENALTY,
    CHUNK_DIVERSITY_SYMBOL_FAMILY_PENALTY,
)


def chunk_symbol_family(qualified_name: str) -> str:
    """Extract the symbol family from a qualified name.

    The family is the final identifier after the last dot or ::.

    Args:
        qualified_name: Fully qualified symbol name.

    Returns:
        Lowercase symbol family string.
    """
    normalized = str(qualified_name or "").strip().replace("::", ".").replace("/", ".")
    if not normalized:
        return ""
    parts = [part.strip().lower() for part in normalized.split(".") if part.strip()]
    if not parts:
        return ""
    tail = parts[-1]
    if "(" in tail:
        tail = tail.split("(", 1)[0].strip()
    return tail


def calculate_diversity_penalty(
    *,
    candidate: dict[str, Any],
    selected: list[dict[str, Any]],
    diversity_enabled: bool = True,
    path_penalty: float = CHUNK_DIVERSITY_PATH_PENALTY,
    symbol_family_penalty: float = CHUNK_DIVERSITY_SYMBOL_FAMILY_PENALTY,
    kind_penalty: float = CHUNK_DIVERSITY_KIND_PENALTY,
    locality_penalty: float = CHUNK_DIVERSITY_LOCALITY_PENALTY,
    locality_window: int = CHUNK_DIVERSITY_LOCALITY_WINDOW,
) -> float:
    """Calculate diversity penalty for a candidate chunk.

    Higher penalties are applied when the candidate is similar to
    already-selected chunks (same file, symbol family, kind, or region).

    Args:
        candidate: Candidate chunk dict.
        selected: List of already-selected chunk dicts.
        diversity_enabled: Whether diversity penalties are enabled.
        path_penalty: Penalty for same file.
        symbol_family_penalty: Penalty for same symbol family.
        kind_penalty: Penalty for same kind (function/class).
        locality_penalty: Penalty for nearby lines in same file.
        locality_window: Line window for locality penalty.

    Returns:
        Total diversity penalty (non-negative).
    """
    if not diversity_enabled or not selected:
        return 0.0

    candidate_path = str(candidate.get("path") or "").strip()
    candidate_kind = str(candidate.get("kind") or "").strip().lower()
    candidate_lineno = int(candidate.get("lineno") or 0)
    candidate_family = chunk_symbol_family(
        str(candidate.get("qualified_name") or "")
    )

    penalty = 0.0
    for item in selected:
        path = str(item.get("path") or "").strip()

        # Same file penalty
        if candidate_path and path == candidate_path:
            penalty += path_penalty

            # Locality penalty for nearby lines
            item_lineno = int(item.get("lineno") or 0)
            if (
                candidate_lineno > 0
                and item_lineno > 0
                and abs(candidate_lineno - item_lineno) <= locality_window
            ):
                penalty += locality_penalty

        # Same kind penalty
        kind = str(item.get("kind") or "").strip().lower()
        if candidate_kind and kind == candidate_kind:
            penalty += kind_penalty

        # Same symbol family penalty
        family = chunk_symbol_family(str(item.get("qualified_name") or ""))
        if candidate_family and family == candidate_family:
            penalty += symbol_family_penalty

    return max(0.0, float(penalty))


__all__ = [
    "calculate_diversity_penalty",
    "chunk_symbol_family",
]
