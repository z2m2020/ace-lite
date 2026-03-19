from __future__ import annotations

from pathlib import Path

import yaml

from ace_lite.dev_feedback_store import DevFix
from ace_lite.issue_report_store import IssueReportStore


def test_issue_report_store_records_and_lists_reports(tmp_path: Path) -> None:
    store = IssueReportStore(db_path=tmp_path / "context-map" / "issue_reports.db")
    selected = tmp_path / "src" / "demo.py"
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text("print('demo')\n", encoding="utf-8")

    report = store.record(
        {
            "title": "validation result missing selected path",
            "query": "validation missing selected path",
            "repo": "demo",
            "root": str(tmp_path),
            "user_id": "bench-user",
            "profile_key": "bugfix",
            "category": "validation",
            "severity": "high",
            "status": "open",
            "actual_behavior": "validation payload omitted the selected path",
            "expected_behavior": "selected path should be carried into output",
            "repro_steps": ["run ace_plan", "inspect validation payload"],
            "selected_path": str(selected),
            "plan_payload_ref": "run-123",
            "attachments": ["artifact://validation.json"],
            "occurred_at": "2026-03-19T00:00:00+00:00",
        },
        root_path=tmp_path,
    )

    rows = store.list_reports(repo="demo", status="open", limit=10)

    assert report.repo == "demo"
    assert report.selected_path == "src/demo.py"
    assert len(rows) == 1
    assert rows[0].title == "validation result missing selected path"
    assert rows[0].attachments == ["artifact://validation.json"]


def test_issue_report_store_exports_case_and_applies_fix(tmp_path: Path) -> None:
    store = IssueReportStore(db_path=tmp_path / "context-map" / "issue_reports.db")
    selected = tmp_path / "src" / "demo.py"
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text("print('demo')\n", encoding="utf-8")

    report = store.record(
        {
            "issue_id": "iss_demo1234",
            "title": "validation result missing selected path",
            "query": "validation missing selected path",
            "repo": "demo",
            "root": str(tmp_path),
            "user_id": "bench-user",
            "profile_key": "bugfix",
            "category": "validation",
            "severity": "high",
            "status": "open",
            "actual_behavior": "validation payload omitted the selected path",
            "expected_behavior": "selected path should be carried into output",
            "repro_steps": ["run ace_plan", "inspect validation payload"],
            "selected_path": str(selected),
            "plan_payload_ref": "run-123",
            "attachments": ["artifact://validation.json"],
            "occurred_at": "2026-03-19T00:00:00+00:00",
        },
        root_path=tmp_path,
    )

    exported = store.export_case(
        issue_id=report.issue_id,
        output_path=tmp_path / "benchmark" / "cases" / "feedback_issue_reports.yaml",
    )
    resolved = store.resolve_with_fix(
        issue_id=report.issue_id,
        fix=DevFix(
            fix_id="devf_demo1234",
            issue_id=report.issue_id,
            reason_code="memory_fallback",
            repo="demo",
            user_id="bench-user",
            profile_key="bugfix",
            query=report.query,
            selected_path=report.selected_path,
            related_invocation_id="inv-123",
            resolution_note="patched validation payload",
            created_at="2026-03-19T00:05:00+00:00",
        ),
    )
    exported_yaml = yaml.safe_load(
        Path(exported["output_path"]).read_text(encoding="utf-8")
    )

    assert exported["case"]["case_id"] == "issue-report-iss-demo1234"
    assert exported_yaml["cases"][0]["filters"]["include_paths"] == ["src/demo.py"]
    assert resolved.status == "resolved"
    assert resolved.resolution_note == "patched validation payload"
    assert "dev-fix://devf_demo1234" in resolved.attachments
