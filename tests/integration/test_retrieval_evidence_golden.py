"""Golden snapshot tests for retrieval evidence contract (ALH1-0105.T2).

These tests load pre-generated fixtures and verify that schema guard
validation is stable across contract versions. If a contract field changes,
these tests will fail and the fixture must be regenerated (see maintenance doc).

Fixtures are generated from the deterministic _minimal_cli_plan_payload()
and committed to tests/fixtures/retrieval_evidence_*.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ace_lite.context_report import (
    build_context_report_payload,
    validate_context_report_payload,
)
from ace_lite.retrieval_graph_view import (
    build_retrieval_graph_view,
    validate_retrieval_graph_view_payload,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_retrieval_evidence_golden_plan_payload_schema_guard(tmp_path: Path) -> None:
    """Golden: minimal CLI plan payload passes schema guard (no mutation)."""
    fixture_path = FIXTURES_DIR / "retrieval_evidence_minimal_plan.json"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}")

    raw = json.loads(fixture_path.read_text(encoding="utf-8"))

    # Build derived payloads (no exceptions allowed)
    context_payload = build_context_report_payload(raw)
    retrieval_graph_payload = build_retrieval_graph_view(raw)

    # Both must pass their schema guards
    validated_context = validate_context_report_payload(context_payload)
    validated_retrieval = validate_retrieval_graph_view_payload(retrieval_graph_payload)

    # Schema versions must be stable
    assert validated_context["schema_version"] == "context_report_v1"
    assert validated_retrieval["schema_version"] == "retrieval_graph_view_v1"


def test_retrieval_evidence_golden_context_report_stable_fields(
    tmp_path: Path,
) -> None:
    """Golden: context_report output has stable required fields."""
    fixture_path = FIXTURES_DIR / "retrieval_evidence_context_report.json"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}")

    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    validated = validate_context_report_payload(payload)

    # Must have all required top-level fields
    assert validated["ok"] is True
    assert validated["schema_version"] == "context_report_v1"
    assert "query" in validated
    assert "summary" in validated
    assert "core_nodes" in validated
    assert "confidence_breakdown" in validated
    assert "knowledge_gaps" in validated
    assert "suggested_questions" in validated

    # confidence_breakdown must have all expected counts
    breakdown = validated["confidence_breakdown"]
    assert (
        breakdown["extracted_count"]
        + breakdown["inferred_count"]
        + breakdown["ambiguous_count"]
        + breakdown["unknown_count"]
        == breakdown["total_count"]
    )


def test_retrieval_evidence_golden_retrieval_graph_stable_fields(
    tmp_path: Path,
) -> None:
    """Golden: retrieval_graph output has stable required fields."""
    fixture_path = FIXTURES_DIR / "retrieval_evidence_retrieval_graph.json"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}")

    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    validated = validate_retrieval_graph_view_payload(payload)

    # Must have all required top-level fields
    assert validated["schema_version"] == "retrieval_graph_view_v1"
    assert "nodes" in validated
    assert "edges" in validated
    assert "warnings" in validated
    assert isinstance(validated["nodes"], list)
    assert isinstance(validated["edges"], list)
    assert isinstance(validated["warnings"], list)
    assert "ok" in validated
    assert "summary" in validated
