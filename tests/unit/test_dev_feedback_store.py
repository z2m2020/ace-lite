from __future__ import annotations

from pathlib import Path

import pytest

from ace_lite.dev_feedback_store import (
    DevFeedbackStore,
    normalize_dev_fix,
    normalize_dev_issue,
    resolve_dev_feedback_store_path,
)


def test_resolve_dev_feedback_store_path_defaults_under_home(tmp_path: Path) -> None:
    path = resolve_dev_feedback_store_path(home_path=tmp_path)

    assert path == (tmp_path / ".ace-lite" / "dev_feedback.db").resolve()


def test_dev_feedback_store_records_issue_fix_and_summarizes_by_reason(tmp_path: Path) -> None:
    store = DevFeedbackStore(db_path=tmp_path / "context-map" / "dev_feedback.db")
    issue = store.record_issue(
        {
            "issue_id": "devi_memory_fallback",
            "title": "Memory fallback while planning",
            "reason_code": "Memory Fallback",
            "status": "Open",
            "repo": "demo",
            "user_id": "bench-user",
            "profile_key": "bugfix",
            "query": "why did memory fallback",
            "selected_path": r".\src\planner.py",
            "related_invocation_id": "inv-123",
            "notes": "first report",
            "created_at": "2026-03-19T00:00:00+00:00",
            "updated_at": "2026-03-19T00:00:00+00:00",
        }
    )
    fix = store.record_fix(
        {
            "fix_id": "devf_memory_fallback",
            "issue_id": issue.issue_id,
            "reason_code": "memory_fallback",
            "repo": "demo",
            "user_id": "bench-user",
            "profile_key": "bugfix",
            "query": "why did memory fallback",
            "selected_path": "src/planner.py",
            "related_invocation_id": "inv-123",
            "resolution_note": "added fallback diagnostics",
            "created_at": "2026-03-19T00:05:00+00:00",
        }
    )

    summary = store.summarize(repo="demo", user_id="bench-user", profile_key="bugfix")

    assert issue.reason_code == "memory_fallback"
    assert issue.status == "open"
    assert issue.selected_path == "src/planner.py"
    assert fix.reason_code == "memory_fallback"
    assert summary["issue_count"] == 1
    assert summary["open_issue_count"] == 1
    assert summary["resolved_issue_count"] == 0
    assert summary["fix_count"] == 1
    assert summary["linked_fix_issue_count"] == 1
    assert summary["dev_issue_to_fix_rate"] == 1.0
    assert summary["issue_time_to_fix_case_count"] == 0
    assert summary["issue_time_to_fix_hours_mean"] == 0.0
    assert summary["by_reason_code"] == [
        {
            "reason_code": "memory_fallback",
            "reason_family": "memory",
            "capture_class": "fallback",
            "issue_count": 1,
            "open_issue_count": 1,
            "fix_count": 1,
            "resolved_issue_count": 0,
            "linked_fix_issue_count": 1,
            "dev_issue_to_fix_rate": 1.0,
            "issue_time_to_fix_case_count": 0,
            "issue_time_to_fix_hours_mean": 0.0,
            "last_seen_at": "2026-03-19T00:05:00+00:00",
        }
    ]


def test_dev_feedback_store_apply_fix_resolves_issue_and_updates_summary(
    tmp_path: Path,
) -> None:
    store = DevFeedbackStore(db_path=tmp_path / "context-map" / "dev_feedback.db")
    store.record_issue(
        {
            "issue_id": "devi_memory_fallback",
            "title": "Memory fallback while planning",
            "reason_code": "memory_fallback",
            "status": "open",
            "repo": "demo",
            "user_id": "bench-user",
            "profile_key": "bugfix",
            "notes": "first report",
            "created_at": "2026-03-19T00:00:00+00:00",
            "updated_at": "2026-03-19T00:00:00+00:00",
        }
    )
    store.record_fix(
        {
            "fix_id": "devf_memory_fallback",
            "issue_id": "devi_memory_fallback",
            "reason_code": "memory_fallback",
            "repo": "demo",
            "user_id": "bench-user",
            "profile_key": "bugfix",
            "resolution_note": "added fallback diagnostics",
            "created_at": "2026-03-19T00:05:00+00:00",
        }
    )

    resolved = store.apply_fix(
        issue_id="devi_memory_fallback",
        fix_id="devf_memory_fallback",
        status="fixed",
    )
    summary = store.summarize(repo="demo", user_id="bench-user", profile_key="bugfix")

    assert resolved.status == "fixed"
    assert resolved.resolved_at == "2026-03-19T00:05:00+00:00"
    assert "resolved_by_fix=devf_memory_fallback" in resolved.notes
    assert summary["issue_count"] == 1
    assert summary["open_issue_count"] == 0
    assert summary["resolved_issue_count"] == 1
    assert summary["fix_count"] == 1
    assert summary["linked_fix_issue_count"] == 1
    assert summary["dev_issue_to_fix_rate"] == 1.0
    assert summary["issue_time_to_fix_case_count"] == 1
    assert summary["issue_time_to_fix_hours_mean"] == pytest.approx(5.0 / 60.0)
    assert summary["by_reason_code"][0]["open_issue_count"] == 0
    assert summary["by_reason_code"][0]["resolved_issue_count"] == 1
    assert summary["by_reason_code"][0]["linked_fix_issue_count"] == 1
    assert summary["by_reason_code"][0]["dev_issue_to_fix_rate"] == 1.0
    assert summary["by_reason_code"][0]["issue_time_to_fix_case_count"] == 1
    assert summary["by_reason_code"][0]["issue_time_to_fix_hours_mean"] == pytest.approx(
        5.0 / 60.0
    )


def test_dev_feedback_store_summary_filters_scope(tmp_path: Path) -> None:
    store = DevFeedbackStore(db_path=tmp_path / "context-map" / "dev_feedback.db")
    store.record_issue(
        {
            "issue_id": "devi_a",
            "title": "Memory fallback",
            "reason_code": "memory_fallback",
            "status": "open",
            "repo": "demo",
            "user_id": "user-a",
            "profile_key": "bugfix",
            "created_at": "2026-03-19T00:00:00+00:00",
            "updated_at": "2026-03-19T00:00:00+00:00",
        }
    )
    store.record_issue(
        {
            "issue_id": "devi_b",
            "title": "Docs drift",
            "reason_code": "docs_drift",
            "status": "fixed",
            "repo": "demo",
            "user_id": "user-b",
            "profile_key": "docs",
            "created_at": "2026-03-19T00:01:00+00:00",
            "updated_at": "2026-03-19T00:01:00+00:00",
        }
    )

    summary = store.summarize(repo="demo", user_id="user-a", profile_key="bugfix")

    assert summary["repo"] == "demo"
    assert summary["user_id"] == "user-a"
    assert summary["profile_key"] == "bugfix"
    assert summary["issue_count"] == 1
    assert summary["open_issue_count"] == 1
    assert summary["resolved_issue_count"] == 0
    assert summary["fix_count"] == 0
    assert summary["linked_fix_issue_count"] == 0
    assert summary["dev_issue_to_fix_rate"] == 0.0
    assert summary["by_reason_code"][0]["reason_code"] == "memory_fallback"


def test_normalize_dev_feedback_validates_required_fields() -> None:
    with pytest.raises(ValueError, match="title cannot be empty"):
        normalize_dev_issue({"title": " ", "repo": "demo"})

    with pytest.raises(ValueError, match="resolution_note cannot be empty"):
        normalize_dev_fix({"repo": "demo", "resolution_note": " "})
