"""Unit tests for the evidence_confidence taxonomy (L8503)."""

from __future__ import annotations

import pytest

from ace_lite.source_plan.evidence_confidence import (
    annotate_chunk_confidence,
    build_confidence_summary,
)


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


def _make_chunk(
    *,
    role: str = "direct",
    sources: list[str] | None = None,
    reference_sidecar: bool = False,
    score_breakdown: dict | None = None,
    extra: dict | None = None,
) -> dict:
    chunk = {
        "path": "src/test.py",
        "qualified_name": "test_fn",
        "kind": "function",
        "score": 7.0,
        "evidence": {
            "role": role,
            "direct_retrieval": role == "direct",
            "neighbor_context": role == "neighbor_context",
            "hint_only": role == "hint_only",
            "hint_support": "test_hint" in (sources or []),
            "reference_sidecar": reference_sidecar,
            "sources": sources or [],
            "granularity": [],
        },
    }
    if score_breakdown:
        chunk["score_breakdown"] = score_breakdown
    if extra:
        chunk.update(extra)
    return chunk


# ----------------------------------------------------------------------
# annotate_chunk_confidence tests
# ----------------------------------------------------------------------


def test_direct_retrieval_is_extracted():
    chunk = _make_chunk(role="direct", sources=["direct_candidate"])
    result = annotate_chunk_confidence([chunk])

    assert len(result) == 1
    assert result[0]["evidence_confidence"] == "EXTRACTED"
    assert result[0]["confidence_score"] == 1.0
    assert "direct retrieval" in result[0]["confidence_reason"]


def test_direct_with_reference_sidecar_is_extracted():
    chunk = _make_chunk(
        role="direct",
        sources=["direct_candidate"],
        reference_sidecar=True,
    )
    result = annotate_chunk_confidence([chunk])

    assert result[0]["evidence_confidence"] == "EXTRACTED"
    assert result[0]["confidence_score"] == 1.0


def test_direct_with_test_hint_is_extracted():
    chunk = _make_chunk(
        role="direct",
        sources=["direct_candidate", "test_hint"],
    )
    result = annotate_chunk_confidence([chunk])

    assert result[0]["evidence_confidence"] == "EXTRACTED"


def test_neighbor_context_is_inferred():
    chunk = _make_chunk(role="neighbor_context", sources=["focused_neighbor"])
    result = annotate_chunk_confidence([chunk])

    assert result[0]["evidence_confidence"] == "INFERRED"
    assert 0.6 <= result[0]["confidence_score"] <= 0.9


def test_neighbor_context_with_graph_closure_is_inferred():
    chunk = _make_chunk(
        role="neighbor_context",
        sources=["focused_neighbor"],
        score_breakdown={"graph_closure_bonus": 0.3},
    )
    result = annotate_chunk_confidence([chunk])

    assert result[0]["evidence_confidence"] == "INFERRED"
    assert result[0]["confidence_score"] == 0.85


def test_graph_closure_alone_is_inferred():
    chunk = _make_chunk(
        role="hint_only",
        sources=["test_hint"],
        score_breakdown={"graph_closure_bonus": 0.5},
    )
    result = annotate_chunk_confidence([chunk])

    assert result[0]["evidence_confidence"] == "INFERRED"


def test_cochange_boost_is_inferred():
    chunk = _make_chunk(
        role="hint_only",
        sources=[],
        score_breakdown={"cochange_boost": 0.4},
    )
    result = annotate_chunk_confidence([chunk])

    assert result[0]["evidence_confidence"] == "INFERRED"


def test_scip_reference_boost_is_inferred():
    chunk = _make_chunk(
        role="hint_only",
        sources=[],
        score_breakdown={"scip_reference_boost": 0.5},
    )
    result = annotate_chunk_confidence([chunk])

    assert result[0]["evidence_confidence"] == "INFERRED"
    assert result[0]["confidence_score"] == 0.82


def test_hint_only_is_ambiguous():
    chunk = _make_chunk(role="hint_only", sources=["test_hint"])
    result = annotate_chunk_confidence([chunk])

    assert result[0]["evidence_confidence"] == "AMBIGUOUS"
    assert 0.1 <= result[0]["confidence_score"] <= 0.5


def test_pure_hint_only_is_ambiguous():
    chunk = _make_chunk(role="hint_only", sources=[])
    result = annotate_chunk_confidence([chunk])

    assert result[0]["evidence_confidence"] == "AMBIGUOUS"
    assert result[0]["confidence_score"] == 0.28


def test_no_evidence_is_unknown():
    chunk = _make_chunk(role="", sources=[])
    result = annotate_chunk_confidence([chunk])

    assert result[0]["evidence_confidence"] == "UNKNOWN"
    assert result[0]["confidence_score"] == 0.0


def test_annotation_does_not_mutate_original():
    original = _make_chunk(role="direct", sources=["direct_candidate"])
    original_copy = dict(original)
    result = annotate_chunk_confidence([original])

    assert "evidence_confidence" not in original
    assert original == original_copy
    assert "evidence_confidence" in result[0]


def test_annotation_preserves_other_fields():
    chunk = _make_chunk(
        role="neighbor_context",
        sources=["focused_neighbor"],
        score_breakdown={"graph_closure_bonus": 0.2},
        extra={"path": "src/foo.py", "lineno": 10},
    )
    result = annotate_chunk_confidence([chunk])

    assert result[0]["path"] == "src/foo.py"
    assert result[0]["lineno"] == 10
    assert result[0]["score"] == 7.0


def test_annotation_empty_list():
    result = annotate_chunk_confidence([])
    assert result == []


# ----------------------------------------------------------------------
# build_confidence_summary tests
# ----------------------------------------------------------------------


def test_summary_counts_all_tiers():
    chunks = [
        _make_chunk(role="direct", sources=["direct_candidate"]),  # EXTRACTED
        _make_chunk(role="direct", sources=["direct_candidate"]),  # EXTRACTED
        _make_chunk(role="neighbor_context", sources=["focused_neighbor"]),  # INFERRED
        _make_chunk(role="hint_only", sources=["test_hint"]),  # AMBIGUOUS
    ]
    result = build_confidence_summary(chunks)

    assert result["extracted_count"] == 2
    assert result["inferred_count"] == 1
    assert result["ambiguous_count"] == 1
    assert result["unknown_count"] == 0
    assert result["total_count"] == 4


def test_summary_empty_chunks():
    result = build_confidence_summary([])
    assert result["extracted_count"] == 0
    assert result["inferred_count"] == 0
    assert result["ambiguous_count"] == 0
    assert result["unknown_count"] == 0
    assert result["total_count"] == 0


def test_summary_uses_explicit_field_when_present():
    chunks = [
        {"evidence_confidence": "EXTRACTED", "confidence_score": 1.0},
        {"evidence_confidence": "INFERRED", "confidence_score": 0.72},
    ]
    result = build_confidence_summary(chunks)

    assert result["extracted_count"] == 1
    assert result["inferred_count"] == 1
    assert result["total_count"] == 2


def test_summary_falls_back_to_heuristic_when_no_explicit():
    chunks = [
        _make_chunk(role="direct", sources=["direct_candidate"]),
    ]
    result = build_confidence_summary(chunks)

    assert result["extracted_count"] == 1
    assert result["total_count"] == 1


def test_summary_unknown_count():
    chunks = [
        _make_chunk(role="", sources=[]),  # UNKNOWN
    ]
    result = build_confidence_summary(chunks)
    assert result["unknown_count"] == 1


def test_summary_total_equals_chunk_count():
    chunks = [_make_chunk(role="direct", sources=["direct_candidate"]) for _ in range(7)]
    result = build_confidence_summary(chunks)
    assert result["total_count"] == 7
    counts_sum = (
        result["extracted_count"]
        + result["inferred_count"]
        + result["ambiguous_count"]
        + result["unknown_count"]
    )
    assert counts_sum == 7
