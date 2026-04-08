"""Additive evidence confidence taxonomy for source_plan candidate chunks.

This module adds report-only confidence metadata to candidate chunks:
- ``evidence_confidence``: EXTRACTED | INFERRED | AMBIGUOUS | UNKNOWN
- ``confidence_score``: float in [0.0, 1.0]
- ``confidence_reason``: human-readable explanation

And computes a ``confidence_summary`` dict for the source_plan payload.

IMPORTANT: These fields are strictly additive / report-only. They must NOT
change the ranking or packing of chunks. The ranking logic in
``rank_source_plan_chunks`` and ``pack_source_plan_chunks`` must remain
unchanged.

Taxonomy (PRD R8503):
- EXTRACTED / 1.0: direct symbol hit, direct import/reference, exact rg hit,
  SCIP reference, test path evidence
- INFERRED / 0.6–0.9: cochange, graph_lookup, semantic rerank, skills route,
  memory hint, neighbor context, graph_prior
- AMBIGUOUS / 0.1–0.5: hint-only, stale memory, fallback ranker, budget
  truncation, missing direct evidence
- UNKNOWN / 0.0: cannot identify evidence source
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "annotate_chunk_confidence",
    "build_confidence_summary",
]

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _str(value: Any, default: str = "") -> str:
    return str(value) if value is not None else default


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


# ----------------------------------------------------------------------
# Core classifier
# ----------------------------------------------------------------------


def _classify_chunk_confidence(chunk: dict[str, Any]) -> tuple[str, float, str]:
    """Classify a single chunk's evidence confidence.

    Returns (tier, score, reason).
    """
    evidence = _dict(chunk.get("evidence", {}))

    role = str(evidence.get("role", "")).strip().lower()
    sources = _list(evidence.get("sources", []))
    has_direct_candidate = "direct_candidate" in sources
    has_test_hint = "test_hint" in sources
    has_reference_sidecar = bool(evidence.get("reference_sidecar", False))
    score_breakdown = _dict(chunk.get("score_breakdown", {}))

    # ---- EXTRACTED (1.0) ----
    # Direct retrieval with candidate support
    if role == "direct" and has_direct_candidate:
        if has_reference_sidecar:
            return "EXTRACTED", 1.0, "direct retrieval with reference sidecar"
        return "EXTRACTED", 1.0, "direct retrieval candidate"

    # Test path evidence with direct retrieval
    if role == "direct" and has_test_hint and has_direct_candidate:
        return "EXTRACTED", 1.0, "direct retrieval with test signal"

    # Direct retrieval without test support (still strong)
    if role == "direct":
        return "EXTRACTED", 0.95, "direct retrieval without test hint"

    # ---- INFERRED (0.6–0.9) ----
    # Neighbor context (focused file context)
    if role == "neighbor_context":
        # Check for additional graph signals
        gc_bonus = _float(score_breakdown.get("graph_closure_bonus", 0.0))
        if gc_bonus > 0:
            return "INFERRED", 0.85, "neighbor context with graph closure bonus"
        return "INFERRED", 0.72, "neighbor context from focused files"

    # Graph closure bonus without direct retrieval
    if _float(score_breakdown.get("graph_closure_bonus", 0.0)) > 0:
        return "INFERRED", 0.78, "boosted by graph closure"

    # cochange boost
    if _float(score_breakdown.get("cochange_boost", 0.0)) > 0:
        return "INFERRED", 0.75, "boosted by cochange history"

    # graph_lookup boost
    if _float(score_breakdown.get("graph_lookup_boost", 0.0)) > 0:
        return "INFERRED", 0.75, "boosted by graph lookup"

    # SCIP reference boost
    if _float(score_breakdown.get("scip_reference_boost", 0.0)) > 0:
        return "INFERRED", 0.82, "boosted by SCIP reference"

    # xref boost
    if _float(score_breakdown.get("xref_boost", 0.0)) > 0:
        return "INFERRED", 0.72, "boosted by cross-reference"

    # coverage boost
    if _float(score_breakdown.get("coverage_boost", 0.0)) > 0:
        return "INFERRED", 0.70, "boosted by coverage signal"

    # ---- AMBIGUOUS (0.1–0.5) ----
    # Hint-only: role is hint_only with test hint signal (check BEFORE test_hint INFERRED)
    if role == "hint_only" and has_test_hint:
        return "AMBIGUOUS", 0.35, "hint-only with test signal"

    # Pure hint-only (no supporting signals)
    if role == "hint_only":
        return "AMBIGUOUS", 0.28, "hint-only evidence"

    # Skills route / memory hint (inferred if has some signal but no direct candidate)
    if has_test_hint and not has_direct_candidate:
        return "INFERRED", 0.65, "test hint without direct candidate"

    # Budget truncation signal
    if _float(score_breakdown.get("budget_truncation_penalty", 0.0)) > 0:
        return "AMBIGUOUS", 0.25, "budget truncation reduced confidence"

    # fallback ranker
    if "fallback_ranker" in sources:
        return "AMBIGUOUS", 0.20, "fallback ranker used"

    # Stale memory signal
    if "stale_memory" in sources:
        return "AMBIGUOUS", 0.18, "stale memory hint"

    # ---- UNKNOWN (0.0) ----
    return "UNKNOWN", 0.0, "unable to determine evidence source"


# ----------------------------------------------------------------------
# Main annotation
# ----------------------------------------------------------------------


def annotate_chunk_confidence(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate a list of chunks with additive confidence metadata.

    This function does NOT modify the input list; it returns a new list
    of shallow copies with the confidence fields added.

    Args:
        chunks: List of grounded candidate chunk dicts (with ``evidence`` field).

    Returns:
        New list of chunks with added ``evidence_confidence``,
        ``confidence_score``, and ``confidence_reason`` fields.
    """
    annotated: list[dict[str, Any]] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            annotated.append(dict(chunk) if isinstance(chunk, dict) else chunk)
            continue

        tier, score, reason = _classify_chunk_confidence(chunk)
        annotated_chunk = dict(chunk)
        annotated_chunk["evidence_confidence"] = tier
        annotated_chunk["confidence_score"] = score
        annotated_chunk["confidence_reason"] = reason
        annotated.append(annotated_chunk)

    return annotated


# ----------------------------------------------------------------------
# Summary aggregation
# ----------------------------------------------------------------------


def build_confidence_summary(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a confidence_summary dict from annotated chunks.

    Args:
        chunks: List of candidate chunks (with or without confidence fields).
                If confidence fields are missing, falls back to ``_classify_chunk_confidence``.

    Returns:
        Dict with extracted_count, inferred_count, ambiguous_count,
        unknown_count, total_count.
    """
    if not chunks:
        return {
            "extracted_count": 0,
            "inferred_count": 0,
            "ambiguous_count": 0,
            "unknown_count": 0,
            "total_count": 0,
        }

    extracted_count = 0
    inferred_count = 0
    ambiguous_count = 0
    unknown_count = 0

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue

        # Prefer explicit field (from P1 annotation)
        explicit = str(chunk.get("evidence_confidence", "")).upper().strip()
        if explicit in ("EXTRACTED", "INFERRED", "AMBIGUOUS", "UNKNOWN"):
            if explicit == "EXTRACTED":
                extracted_count += 1
            elif explicit == "INFERRED":
                inferred_count += 1
            elif explicit == "AMBIGUOUS":
                ambiguous_count += 1
            else:
                unknown_count += 1
        else:
            # Fall back to heuristic classification
            tier, _, _ = _classify_chunk_confidence(chunk)
            if tier == "EXTRACTED":
                extracted_count += 1
            elif tier == "INFERRED":
                inferred_count += 1
            elif tier == "AMBIGUOUS":
                ambiguous_count += 1
            else:
                unknown_count += 1

    total_count = len(chunks)

    return {
        "extracted_count": extracted_count,
        "inferred_count": inferred_count,
        "ambiguous_count": ambiguous_count,
        "unknown_count": unknown_count,
        "total_count": total_count,
    }
