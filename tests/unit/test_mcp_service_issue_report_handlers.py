from __future__ import annotations

from pathlib import Path

from ace_lite.mcp_server.service_issue_report_handlers import (
    handle_issue_report_apply_fix_request,
    handle_issue_report_export_case_request,
    handle_issue_report_list_request,
    handle_issue_report_record_request,
    resolve_issue_report_store_path,
)


def test_resolve_issue_report_store_path_defaults_under_root(tmp_path: Path) -> None:
    path = resolve_issue_report_store_path(root_path=tmp_path, store_path=None)

    assert path == (tmp_path / "context-map" / "issue_reports.db").resolve()


def test_handle_issue_report_record_and_list_round_trip(tmp_path: Path) -> None:
    selected = tmp_path / "src" / "demo.py"
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text("print('demo')\n", encoding="utf-8")

    recorded = handle_issue_report_record_request(
        title="validation payload missing selected path",
        query="validation missing selected path",
        actual_behavior="selected path missing from validation payload",
        repo="demo",
        user_id="mcp-user",
        profile_key="bugfix",
        root_path=tmp_path,
        default_repo="default-demo",
        store_path="context-map/issue_reports.db",
        category="validation",
        severity="high",
        status="open",
        expected_behavior="selected path should be included",
        repro_steps=["run ace_plan", "inspect output"],
        selected_path=str(selected),
        plan_payload_ref="run-123",
        attachments=["artifact://validation.json"],
        occurred_at="2026-03-19T00:00:00+00:00",
        resolved_at=None,
        resolution_note=None,
    )

    listed = handle_issue_report_list_request(
        repo="demo",
        user_id="mcp-user",
        profile_key="bugfix",
        root_path=tmp_path,
        store_path="context-map/issue_reports.db",
        status="open",
        category="validation",
        severity="high",
        limit=10,
    )

    assert recorded["ok"] is True
    assert recorded["report"]["selected_path"] == "src/demo.py"
    assert listed["ok"] is True
    assert listed["count"] == 1
    assert listed["reports"][0]["plan_payload_ref"] == "run-123"


def test_handle_issue_report_export_case_and_apply_fix(tmp_path: Path) -> None:
    selected = tmp_path / "src" / "demo.py"
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text("print('demo')\n", encoding="utf-8")

    handle_issue_report_record_request(
        title="validation payload missing selected path",
        query="validation missing selected path",
        actual_behavior="selected path missing from validation payload",
        repo="demo",
        user_id="mcp-user",
        profile_key="bugfix",
        root_path=tmp_path,
        default_repo="default-demo",
        store_path="context-map/issue_reports.db",
        category="validation",
        severity="high",
        status="open",
        expected_behavior="selected path should be included",
        repro_steps=["run ace_plan", "inspect output"],
        selected_path=str(selected),
        plan_payload_ref="run-123",
        attachments=["artifact://validation.json"],
        occurred_at="2026-03-19T00:00:00+00:00",
        resolved_at=None,
        resolution_note=None,
        issue_id="iss_demo1234",
    )
    from ace_lite.dev_feedback_store import DevFeedbackStore

    DevFeedbackStore(db_path=tmp_path / "context-map" / "dev_feedback.db").record_fix(
        {
            "fix_id": "devf_demo1234",
            "issue_id": "iss_demo1234",
            "reason_code": "memory_fallback",
            "repo": "demo",
            "user_id": "mcp-user",
            "profile_key": "bugfix",
            "query": "validation missing selected path",
            "selected_path": str(selected),
            "resolution_note": "patched validation payload",
            "created_at": "2026-03-19T00:05:00+00:00",
        }
    )

    exported = handle_issue_report_export_case_request(
        issue_id="iss_demo1234",
        root_path=tmp_path,
        store_path="context-map/issue_reports.db",
        output_path="benchmark/cases/feedback_issue_reports.yaml",
        case_id=None,
        comparison_lane="issue_report_feedback",
        top_k=8,
        min_validation_tests=1,
        append=True,
    )
    resolved = handle_issue_report_apply_fix_request(
        issue_id="iss_demo1234",
        fix_id="devf_demo1234",
        root_path=tmp_path,
        issue_store_path="context-map/issue_reports.db",
        dev_feedback_path=str(tmp_path / "context-map" / "dev_feedback.db"),
        status="resolved",
        resolved_at=None,
    )
    exported_after_resolution = handle_issue_report_export_case_request(
        issue_id="iss_demo1234",
        root_path=tmp_path,
        store_path="context-map/issue_reports.db",
        output_path="benchmark/cases/feedback_issue_reports.yaml",
        case_id=None,
        comparison_lane="dev_feedback_resolution",
        top_k=8,
        min_validation_tests=1,
        append=True,
    )

    assert exported["ok"] is True
    assert exported["case"]["case_id"] == "issue-report-iss-demo1234"
    assert resolved["ok"] is True
    assert resolved["report"]["status"] == "resolved"
    assert resolved["report"]["resolution_note"] == "patched validation payload"
    assert exported_after_resolution["case"]["dev_feedback"] == {
        "issue_count": 1,
        "linked_fix_issue_count": 1,
        "resolved_issue_count": 1,
        "created_at": "2026-03-19T00:00:00+00:00",
        "resolved_at": "2026-03-19T00:05:00+00:00",
    }
