from __future__ import annotations

from pathlib import Path

from ace_lite.cli_app.runtime_stats_data_support import (
    load_runtime_dev_feedback_summary,
    load_runtime_preference_capture_summary,
    normalize_runtime_stats_filter_value,
)
from ace_lite.dev_feedback_store import DevFeedbackStore
from ace_lite.feedback_store import SelectionFeedbackStore


def test_runtime_stats_data_support_normalizes_filters_and_loaders(tmp_path: Path) -> None:
    assert normalize_runtime_stats_filter_value("  bugfix  ") == "bugfix"
    assert normalize_runtime_stats_filter_value("   ") is None

    feedback_path = tmp_path / "profile.json"
    SelectionFeedbackStore(profile_path=feedback_path, max_entries=8).record(
        query="runtime summary",
        repo="repo-alpha",
        user_id="bench-user",
        profile_key="bugfix",
        selected_path="src/app.py",
        captured_at="2026-03-18T00:00:00+00:00",
        position=1,
    )
    preference_payload = load_runtime_preference_capture_summary(
        feedback_path=feedback_path,
        repo_key="repo-alpha",
        user_id="bench-user",
        profile_key="bugfix",
    )

    assert preference_payload["event_count"] == 1
    assert preference_payload["user_id"] == "bench-user"
    assert preference_payload["profile_key"] == "bugfix"

    dev_feedback_store = DevFeedbackStore(db_path=tmp_path / ".ace-lite" / "dev_feedback.db")
    dev_feedback_store.record_issue(
        {
            "issue_id": "devi_memory_fallback",
            "title": "Memory fallback",
            "reason_code": "memory_fallback",
            "status": "open",
            "repo": "repo-alpha",
            "user_id": "bench-user",
            "profile_key": "bugfix",
            "created_at": "2026-03-19T00:00:00+00:00",
            "updated_at": "2026-03-19T00:00:00+00:00",
        }
    )
    dev_payload = load_runtime_dev_feedback_summary(
        dev_feedback_path=dev_feedback_store.db_path,
        repo_key="repo-alpha",
        user_id="bench-user",
        profile_key="bugfix",
    )

    assert dev_payload["issue_count"] == 1
    assert dev_payload["repo_key"] == "repo-alpha"
    assert dev_payload["user_id"] == "bench-user"
