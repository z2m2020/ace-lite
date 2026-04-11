from __future__ import annotations

from ace_lite.problem_surface import (
    extract_confidence_summary_input,
    extract_context_report_input,
    extract_problem_surface_payload,
    extract_validation_feedback_input,
)


def test_extract_problem_surface_payload_warns_when_confidence_summary_missing() -> None:
    plan_payload = {
        "query": "trace fallback",
        "repo": "ace-lite-engine",
        "root": "/repo",
        "source_plan": {
            "candidate_files": [{"path": "src/ace_lite/problem_surface.py", "score": 1.0}],
            "candidate_chunks": [{"path": "src/ace_lite/problem_surface.py", "score": 0.9}],
            "validation_tests": ["pytest -q tests/unit/test_problem_surface_extractors.py"],
            "steps": [
                {
                    "stage": "validate",
                    "validation_feedback_summary": {
                        "status": "failed",
                        "issue_count": 1,
                        "probe_status": "executed",
                        "probe_issue_count": 1,
                        "probe_executed_count": 1,
                        "selected_test_count": 1,
                        "executed_test_count": 1,
                    },
                }
            ],
        },
    }

    payload = extract_problem_surface_payload(
        plan_payload,
        git_sha="abc123",
        phase="triage",
        generated_at="2026-04-12T00:00:00+00:00",
    )

    assert payload["schema_version"] == "problem_surface_v1"
    assert "missing_confidence_summary" in payload["warnings"]
    assert payload["surfaces"]["context"]["candidate_file_count"] == 1
    assert payload["surfaces"]["confidence"]["unknown_count"] == 0
    assert payload["surfaces"]["validation"]["status"] == "failed"


def test_extract_inputs_prefer_existing_payload_shapes() -> None:
    plan_payload = {
        "context_report": {
            "schema_version": "context_report_v1",
            "query": "investigate graph closure",
            "repo": "ace-lite-engine",
            "root": "/workspace",
            "summary": {
                "candidate_file_count": 2,
                "candidate_chunk_count": 3,
                "validation_test_count": 1,
                "degraded_reason_count": 0,
            },
            "confidence_breakdown": {"total_count": 3},
        },
        "source_plan": {
            "confidence_summary": {
                "extracted_count": 1,
                "inferred_count": 1,
                "ambiguous_count": 0,
                "unknown_count": 1,
                "total_count": 3,
            },
            "steps": [
                {
                    "stage": "validate",
                    "validation_feedback_summary": {
                        "status": "degraded",
                        "issue_count": 2,
                        "probe_status": "unknown",
                        "probe_issue_count": 0,
                        "probe_executed_count": 0,
                        "selected_test_count": 1,
                        "executed_test_count": 0,
                    },
                }
            ],
        },
    }

    context_report, context_warnings = extract_context_report_input(plan_payload)
    confidence_summary, confidence_warnings = extract_confidence_summary_input(plan_payload)
    validation_feedback, validation_warnings = extract_validation_feedback_input(plan_payload)

    assert context_warnings == []
    assert confidence_warnings == []
    assert validation_warnings == []
    assert context_report["summary"]["candidate_chunk_count"] == 3
    assert confidence_summary["unknown_count"] == 1
    assert validation_feedback["status"] == "degraded"


def test_extract_problem_surface_payload_uses_unknown_defaults_for_missing_minimal_payload() -> (
    None
):
    payload = extract_problem_surface_payload({}, generated_at="2026-04-12T00:00:00+00:00")

    assert "missing_context_report" in payload["warnings"]
    assert "missing_confidence_summary" in payload["warnings"]
    assert "missing_validation_feedback" in payload["warnings"]
    assert payload["surfaces"]["context"]["query"] == "unknown"
    assert payload["surfaces"]["validation"]["status"] == "unknown"
    assert payload["surfaces"]["validation"]["probe_status"] == "unknown"
