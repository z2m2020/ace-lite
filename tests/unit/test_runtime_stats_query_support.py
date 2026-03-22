from __future__ import annotations

from pathlib import Path

from ace_lite.cli_app.runtime_stats_query_support import load_latest_runtime_stats_match
from ace_lite.runtime_stats import RuntimeInvocationStats
from ace_lite.runtime_stats_schema import RUNTIME_STATS_DOCTOR_EVENT_CLASS
from ace_lite.runtime_stats_store import DurableStatsStore


def test_runtime_stats_query_support_excludes_synthetic_doctor_sessions_by_default(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "runtime-stats.db"
    store = DurableStatsStore(db_path=db_path)
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-normal",
            session_id="session-alpha",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="succeeded",
            total_latency_ms=25.0,
            started_at="2026-03-21T00:00:00+00:00",
            finished_at="2026-03-21T00:00:01+00:00",
        )
    )
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-doctor",
            session_id="runtime-doctor::repo-alpha",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=0.0,
            started_at="2026-03-21T00:00:02+00:00",
            finished_at="2026-03-21T00:00:02+00:00",
            degraded_reason_codes=("git_unavailable",),
        )
    )

    latest_match = load_latest_runtime_stats_match(
        db_path=db_path,
        repo_key="repo-alpha",
        profile_key="bugfix",
    )

    assert latest_match is not None
    assert latest_match["invocation_id"] == "inv-normal"
    assert latest_match["session_id"] == "session-alpha"
    assert latest_match["event_class"] == "runtime_invocation"


def test_runtime_stats_query_support_keeps_explicit_doctor_session_queries(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "runtime-stats.db"
    store = DurableStatsStore(db_path=db_path)
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-doctor",
            session_id="runtime-doctor::repo-alpha",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=0.0,
            started_at="2026-03-21T00:00:02+00:00",
            finished_at="2026-03-21T00:00:02+00:00",
            degraded_reason_codes=("git_unavailable",),
        )
    )

    latest_match = load_latest_runtime_stats_match(
        db_path=db_path,
        session_id="runtime-doctor::repo-alpha",
        repo_key="repo-alpha",
        profile_key="bugfix",
    )

    assert latest_match is not None
    assert latest_match["invocation_id"] == "inv-doctor"
    assert latest_match["session_id"] == "runtime-doctor::repo-alpha"
    assert latest_match["event_class"] == RUNTIME_STATS_DOCTOR_EVENT_CLASS
