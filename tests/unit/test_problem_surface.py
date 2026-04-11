from __future__ import annotations

import pytest

from ace_lite.problem_surface import (
    SCHEMA_VERSION,
    build_problem_surface_payload,
    dump_problem_surface_payload,
    dumps_problem_surface_payload,
    load_problem_surface_payload,
    loads_problem_surface_payload,
)
from ace_lite.problem_surface_schema import (
    PROBLEM_SURFACE_SCHEMA_NAME,
    PROBLEM_SURFACE_SCHEMA_VERSION,
    build_problem_surface_schema_document,
)


def test_problem_surface_schema_document_exposes_required_contract() -> None:
    payload = build_problem_surface_schema_document()

    assert payload["schema_name"] == PROBLEM_SURFACE_SCHEMA_NAME
    assert payload["schema_version"] == PROBLEM_SURFACE_SCHEMA_VERSION
    assert payload["required_keys"] == [
        "schema_version",
        "generated_at",
        "git_sha",
        "phase",
        "inputs",
        "surfaces",
        "warnings",
    ]


def test_problem_surface_roundtrip_is_stable() -> None:
    payload = build_problem_surface_payload(
        context_report={
            "schema_version": "context_report_v1",
            "query": "trace fallback",
            "repo": "ace-lite-engine",
            "root": "/repo",
            "summary": {
                "candidate_file_count": 2,
                "candidate_chunk_count": 3,
                "validation_test_count": 1,
                "degraded_reason_count": 1,
            },
            "confidence_breakdown": {"total_count": 3},
            "degraded_reasons": ["memory_fallback"],
            "warnings": [],
        },
        confidence_summary={
            "extracted_count": 1,
            "inferred_count": 1,
            "ambiguous_count": 1,
            "unknown_count": 0,
            "total_count": 3,
        },
        validation_feedback={
            "status": "failed",
            "issue_count": 2,
            "probe_status": "executed",
            "probe_issue_count": 1,
            "probe_executed_count": 1,
            "selected_test_count": 2,
            "executed_test_count": 1,
        },
        git_sha="abc123",
        phase="triage",
        generated_at="2026-04-11T00:00:00+00:00",
    )

    dumped = dump_problem_surface_payload(payload)
    reloaded = loads_problem_surface_payload(dumps_problem_surface_payload(payload))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert dumped == reloaded
    assert reloaded["surfaces"]["context"]["candidate_chunk_count"] == 3
    assert reloaded["surfaces"]["confidence"]["ambiguous_count"] == 1
    assert reloaded["surfaces"]["validation"]["issue_count"] == 2


def test_problem_surface_load_rejects_missing_required_keys() -> None:
    with pytest.raises(ValueError, match="generated_at is required"):
        load_problem_surface_payload(
            {
                "schema_version": SCHEMA_VERSION,
                "git_sha": "abc123",
                "phase": "triage",
                "inputs": {},
                "surfaces": {},
                "warnings": [],
            }
        )


def test_problem_surface_build_maps_synthetic_inputs() -> None:
    payload = build_problem_surface_payload(
        context_report={
            "schema_version": "context_report_v1",
            "query": "trace planner degradation",
            "repo": "ace-lite-engine",
            "root": "/workspace",
            "summary": {
                "candidate_file_count": 1,
                "candidate_chunk_count": 2,
                "validation_test_count": 1,
                "degraded_reason_count": 1,
            },
            "confidence_breakdown": {"total_count": 2},
            "degraded_reasons": ["candidate_ranker_fallback"],
            "warnings": ["low_support"],
        },
        confidence_summary={
            "extracted_count": 0,
            "inferred_count": 1,
            "ambiguous_count": 1,
            "unknown_count": 0,
            "total_count": 2,
        },
        validation_feedback={
            "status": "degraded",
            "issue_count": 1,
            "probe_status": "disabled",
            "probe_issue_count": 0,
            "probe_executed_count": 0,
            "selected_test_count": 1,
            "executed_test_count": 0,
        },
        git_sha="deadbeef",
        phase="analysis",
        generated_at="2026-04-11T00:00:00+00:00",
    )

    assert payload["inputs"]["context_report"]["present"] is True
    assert payload["inputs"]["confidence_summary"]["present"] is True
    assert payload["inputs"]["validation_feedback"]["present"] is True
    assert payload["surfaces"]["context"]["degraded_reasons"] == ["candidate_ranker_fallback"]
    assert payload["surfaces"]["confidence"]["inferred_count"] == 1
    assert payload["surfaces"]["validation"]["status"] == "degraded"
    assert payload["warnings"] == []
