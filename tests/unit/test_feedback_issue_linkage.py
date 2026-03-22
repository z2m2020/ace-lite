from __future__ import annotations

from pathlib import Path

import yaml

from ace_lite.dev_feedback_store import DevFix
from ace_lite.feedback_issue_linkage import (
    build_issue_report_benchmark_case,
    build_issue_report_resolution_from_fix,
    derive_dev_feedback_case_payload,
    export_issue_report_benchmark_case,
)
from ace_lite.issue_report_store import IssueReport


def _sample_report() -> IssueReport:
    return IssueReport(
        issue_id="iss_demo1234",
        title="validation payload missing selected path",
        category="validation",
        severity="high",
        status="open",
        query="validation missing selected path",
        repo="demo",
        root="F:/repo",
        user_id="bench-user",
        profile_key="bugfix",
        expected_behavior="selected path should be included",
        actual_behavior="selected path missing from validation payload",
        repro_steps=["run ace_plan", "inspect output"],
        plan_payload_ref="run-123",
        selected_path="src/ace_lite/validation/result.py",
        attachments=["artifact://validation.json"],
        occurred_at="2026-03-19T00:00:00+00:00",
        resolved_at="",
        resolution_note="",
        created_at="2026-03-19T00:00:00+00:00",
        updated_at="2026-03-19T00:00:00+00:00",
    )


def test_build_issue_report_benchmark_case_uses_selected_path_filters() -> None:
    report = _sample_report()

    payload = build_issue_report_benchmark_case(report=report)

    assert payload["case_id"] == "issue-report-iss-demo1234"
    assert payload["query"] == "validation missing selected path"
    assert payload["comparison_lane"] == "issue_report_feedback"
    assert payload["top_k"] == 8
    assert payload["task_success"] == {"mode": "positive", "min_validation_tests": 1}
    assert payload["filters"] == {"include_paths": ["src/ace_lite/validation/result.py"]}
    assert "validation" in payload["expected_keys"]
    assert payload["issue_report"]["issue_id"] == "iss_demo1234"
    assert payload["issue_report"]["attachments"] == ["artifact://validation.json"]
    assert payload["issue_report"]["occurred_at"] == "2026-03-19T00:00:00+00:00"
    assert payload["issue_report"]["resolved_at"] == ""
    assert payload["issue_report"]["created_at"] == "2026-03-19T00:00:00+00:00"
    assert payload["issue_report"]["updated_at"] == "2026-03-19T00:00:00+00:00"
    assert "dev_feedback" not in payload


def test_export_issue_report_benchmark_case_replaces_same_case_id(tmp_path: Path) -> None:
    report = _sample_report()
    output_path = tmp_path / "benchmark" / "cases" / "feedback_issue_reports.yaml"

    first = export_issue_report_benchmark_case(report=report, output_path=output_path)
    second = export_issue_report_benchmark_case(report=report, output_path=output_path)

    payload = yaml.safe_load(output_path.read_text(encoding="utf-8"))

    assert first["case_count"] == 1
    assert second["case_count"] == 1
    assert payload["cases"][0]["case_id"] == "issue-report-iss-demo1234"


def test_export_issue_report_benchmark_case_normalizes_existing_cases(tmp_path: Path) -> None:
    report = _sample_report()
    output_path = tmp_path / "benchmark" / "cases" / "feedback_issue_reports.yaml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(
            {
                "cases": [
                    {
                        "case_id": "runtime-capture-legacy",
                        "query": "runtime capture",
                        "expected_keys": ["runtime"],
                        "top_k": 8,
                        "comparison_lane": "dev_issue_capture",
                        "feedback_surface": "runtime_issue_capture_cli",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    export_issue_report_benchmark_case(report=report, output_path=output_path)

    payload = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    legacy_case = next(
        item
        for item in payload["cases"]
        if item["case_id"] == "runtime-capture-legacy"
    )

    assert legacy_case["dev_feedback"] == {"issue_count": 1}


def test_build_issue_report_resolution_from_fix_attaches_dev_fix_reference() -> None:
    report = _sample_report()
    fix = DevFix(
        fix_id="devf_demo1234",
        issue_id="iss_demo1234",
        reason_code="memory_fallback",
        repo="demo",
        user_id="bench-user",
        profile_key="bugfix",
        query="validation missing selected path",
        selected_path="src/ace_lite/validation/result.py",
        related_invocation_id="inv-123",
        resolution_note="patched validation payload",
        created_at="2026-03-19T00:05:00+00:00",
    )

    payload = build_issue_report_resolution_from_fix(report=report, fix=fix)

    assert payload["status"] == "resolved"
    assert payload["resolved_at"] == "2026-03-19T00:05:00+00:00"
    assert payload["resolution_note"] == "patched validation payload"
    assert "dev-fix://devf_demo1234" in payload["attachments"]


def test_build_issue_report_benchmark_case_derives_dev_feedback_metadata_from_fix_attachment(
) -> None:
    report = _sample_report()
    resolved_report = IssueReport(
        **build_issue_report_resolution_from_fix(
            report=report,
            fix=DevFix(
                fix_id="devf_demo1234",
                issue_id="iss_demo1234",
                reason_code="memory_fallback",
                repo="demo",
                user_id="bench-user",
                profile_key="bugfix",
                query="validation missing selected path",
                selected_path="src/ace_lite/validation/result.py",
                related_invocation_id="inv-123",
                resolution_note="patched validation payload",
                created_at="2026-03-19T00:05:00+00:00",
            ),
        )
    )

    payload = build_issue_report_benchmark_case(
        report=resolved_report,
        comparison_lane="dev_feedback_resolution",
    )

    assert payload["comparison_lane"] == "dev_feedback_resolution"
    assert payload["dev_feedback"] == {
        "issue_count": 1,
        "linked_fix_issue_count": 1,
        "resolved_issue_count": 1,
        "created_at": "2026-03-19T00:00:00+00:00",
        "resolved_at": "2026-03-19T00:05:00+00:00",
    }


def test_derive_dev_feedback_case_payload_accepts_issue_report_dict() -> None:
    payload = derive_dev_feedback_case_payload(
        report={
            "attachments": ["artifact://validation.json", "dev-fix://devf_demo1234"],
            "status": "resolved",
            "occurred_at": "2026-03-19T00:00:00+00:00",
            "resolved_at": "2026-03-19T00:05:00+00:00",
        }
    )

    assert payload == {
        "issue_count": 1,
        "linked_fix_issue_count": 1,
        "resolved_issue_count": 1,
        "created_at": "2026-03-19T00:00:00+00:00",
        "resolved_at": "2026-03-19T00:05:00+00:00",
    }
