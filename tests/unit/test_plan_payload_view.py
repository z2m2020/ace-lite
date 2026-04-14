"""Unit tests for plan_payload_view fallback helpers."""

from __future__ import annotations

from ace_lite.plan_payload_view import (
    coerce_payload,
    resolve_candidate_chunks,
    resolve_candidate_files,
    resolve_candidate_review,
    resolve_confidence_summary,
    resolve_evidence_summary,
    resolve_history_hits,
    resolve_pipeline_stage_names,
    resolve_repomap_payload,
    resolve_session_end_report,
    resolve_source_plan_payload,
    resolve_subgraph_payload,
    resolve_validation_findings,
    resolve_validation_result,
    resolve_validation_tests,
)


def test_coerce_payload_accepts_plain_mapping() -> None:
    class CustomMapping(dict):
        pass

    payload = coerce_payload(CustomMapping(query="q"))
    assert payload == {"query": "q"}


def test_resolve_source_plan_payload_prefers_nested_shape() -> None:
    payload = {
        "candidate_files": [{"path": "top.py"}],
        "source_plan": {
            "candidate_files": [{"path": "nested.py"}],
        },
    }

    source_plan = resolve_source_plan_payload(payload)

    assert source_plan == {"candidate_files": [{"path": "nested.py"}]}
    assert resolve_candidate_files(payload, source_plan=source_plan) == [{"path": "nested.py"}]


def test_resolve_helpers_fall_back_to_top_level_when_nested_missing() -> None:
    payload = {
        "candidate_chunks": [{"path": "src/a.py", "qualified_name": "f"}],
        "candidate_files": [{"path": "src/a.py", "score": 1.0}],
        "validation_tests": ["pytest tests/test_a.py"],
        "history_hits": {"hits": [{"hash": "abc"}]},
        "candidate_review": {"status": "watch"},
        "validation_findings": {"warn_count": 1},
        "session_end_report": {"next_actions": ["run tests"]},
        "evidence_summary": {"direct_count": 1},
        "confidence_summary": {"extracted_count": 1, "total_count": 1},
        "subgraph_payload": {"seed_paths": ["src/a.py"]},
        "repomap": {"focused_files": ["src/a.py"]},
    }

    assert resolve_candidate_chunks(payload) == [{"path": "src/a.py", "qualified_name": "f"}]
    assert resolve_candidate_files(payload) == [{"path": "src/a.py", "score": 1.0}]
    assert resolve_validation_tests(payload) == ["pytest tests/test_a.py"]
    assert resolve_history_hits(payload) == {"hits": [{"hash": "abc"}]}
    assert resolve_candidate_review(payload) == {"status": "watch"}
    assert resolve_validation_findings(payload) == {"warn_count": 1}
    assert resolve_session_end_report(payload) == {"next_actions": ["run tests"]}
    assert resolve_evidence_summary(payload) == {"direct_count": 1}
    assert resolve_confidence_summary(payload) == {"extracted_count": 1, "total_count": 1}
    assert resolve_subgraph_payload(payload) == {"seed_paths": ["src/a.py"]}
    assert resolve_repomap_payload(payload) == {"focused_files": ["src/a.py"]}


def test_resolve_pipeline_stage_names_prefers_nested_then_pipeline_order_then_stages() -> None:
    nested = {
        "pipeline_order": ["top_pipeline"],
        "stages": ["top_stage"],
        "source_plan": {"stages": ["nested_stage"]},
    }
    pipeline_order = {
        "pipeline_order": ["top_pipeline"],
        "stages": ["top_stage"],
    }
    top_level = {"stages": ["top_stage"]}

    assert resolve_pipeline_stage_names(nested) == ["nested_stage"]
    assert resolve_pipeline_stage_names(pipeline_order) == ["top_pipeline"]
    assert resolve_pipeline_stage_names(top_level) == ["top_stage"]


def test_resolve_validation_result_prefers_nested_then_validation_then_top_level() -> None:
    nested = {
        "validation_result": {"summary": {"status": "top"}},
        "validation": {"result": {"summary": {"status": "validation"}}},
        "source_plan": {"validation_result": {"summary": {"status": "nested"}}},
    }
    validation = {
        "validation_result": {"summary": {"status": "top"}},
        "validation": {"result": {"summary": {"status": "validation"}}},
    }
    top_level = {"validation_result": {"summary": {"status": "top"}}}

    assert resolve_validation_result(nested)["summary"]["status"] == "nested"
    assert resolve_validation_result(validation)["summary"]["status"] == "validation"
    assert resolve_validation_result(top_level)["summary"]["status"] == "top"


def test_resolve_report_only_helpers_prefer_nested_shape() -> None:
    payload = {
        "history_hits": {"hits": [{"hash": "top"}]},
        "candidate_review": {"status": "top"},
        "validation_findings": {"warn_count": 9},
        "session_end_report": {"next_actions": ["top"]},
        "source_plan": {
            "history_hits": {"hits": [{"hash": "nested"}]},
            "candidate_review": {"status": "nested"},
            "validation_findings": {"warn_count": 1},
            "session_end_report": {"next_actions": ["nested"]},
        },
    }

    source_plan = resolve_source_plan_payload(payload)

    assert resolve_history_hits(payload, source_plan=source_plan) == {
        "hits": [{"hash": "nested"}]
    }
    assert resolve_candidate_review(payload, source_plan=source_plan) == {
        "status": "nested"
    }
    assert resolve_validation_findings(payload, source_plan=source_plan) == {
        "warn_count": 1
    }
    assert resolve_session_end_report(payload, source_plan=source_plan) == {
        "next_actions": ["nested"]
    }
