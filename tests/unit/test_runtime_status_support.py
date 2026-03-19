from __future__ import annotations

from ace_lite.cli_app import runtime_status_support
from ace_lite.cli_app.runtime_command_support import (
    DEFAULT_RUNTIME_STATS_DB_PATH,
    build_runtime_status_payload,
    build_runtime_status_snapshot,
    load_latest_runtime_stats_match,
    load_runtime_dev_feedback_summary,
    load_runtime_preference_capture_summary,
    load_runtime_stats_summary,
    resolve_user_runtime_stats_path,
)


def test_runtime_status_support_facade_reexports_status_helpers() -> None:
    assert DEFAULT_RUNTIME_STATS_DB_PATH == runtime_status_support.DEFAULT_RUNTIME_STATS_DB_PATH
    assert resolve_user_runtime_stats_path is runtime_status_support.resolve_user_runtime_stats_path
    assert load_latest_runtime_stats_match is runtime_status_support.load_latest_runtime_stats_match
    assert load_runtime_stats_summary is runtime_status_support.load_runtime_stats_summary
    assert (
        load_runtime_dev_feedback_summary
        is runtime_status_support.load_runtime_dev_feedback_summary
    )
    assert (
        load_runtime_preference_capture_summary
        is runtime_status_support.load_runtime_preference_capture_summary
    )
    assert build_runtime_status_payload is runtime_status_support.build_runtime_status_payload
    assert build_runtime_status_snapshot is runtime_status_support.build_runtime_status_snapshot
