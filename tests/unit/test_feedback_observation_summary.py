from __future__ import annotations

from pathlib import Path

from ace_lite.dev_feedback_store import DevFeedbackStore
from ace_lite.feedback_observation_summary import build_feedback_observation_overview
from ace_lite.feedback_store import SelectionFeedbackStore
from ace_lite.issue_report_store import IssueReportStore


def test_build_feedback_observation_overview_aggregates_three_feedback_channels(
    tmp_path: Path,
) -> None:
    dev_store = DevFeedbackStore(db_path=tmp_path / "dev-feedback.db")
    dev_store.record_issue(
        {
            "issue_id": "devi_memory_fallback",
            "title": "Memory fallback while planning",
            "reason_code": "memory_fallback",
            "status": "open",
            "repo": "demo",
            "user_id": "cli-user",
            "profile_key": "bugfix",
            "created_at": "2026-03-19T00:00:00+00:00",
            "updated_at": "2026-03-19T00:00:00+00:00",
        }
    )
    IssueReportStore(db_path=tmp_path / "context-map" / "issue_reports.db").record(
        {
            "issue_id": "iss_validation_payload",
            "title": "validation payload missing selected path",
            "query": "validation payload",
            "actual_behavior": "selected path omitted",
            "repo": "demo",
            "root": str(tmp_path),
            "status": "open",
            "created_at": "2026-03-19T00:00:00+00:00",
            "updated_at": "2026-03-19T00:00:00+00:00",
            "occurred_at": "2026-03-19T00:00:00+00:00",
            "category": "retrieval",
            "severity": "high",
        },
        root_path=tmp_path,
    )
    SelectionFeedbackStore(profile_path=tmp_path / "profile.json").record(
        query="validation payload",
        repo="demo",
        selected_path="src/planner.py",
        user_id="cli-user",
        profile_key="bugfix",
    )

    payload = build_feedback_observation_overview(
        repo="demo",
        user_id="cli-user",
        profile_key="bugfix",
        root=tmp_path,
        dev_feedback_store_path=tmp_path / "dev-feedback.db",
        profile_path=tmp_path / "profile.json",
    )

    assert payload["developer_feedback"]["issue_count"] == 1
    assert payload["issue_reports"]["report_count"] == 1
    assert payload["selection_feedback"]["event_count"] == 1
    assert payload["cross_store_gaps"]["has_split_feedback_signals"] is True
