from __future__ import annotations

from pathlib import Path

from ace_lite.cli_app.runtime_stats_summary_support import build_runtime_scope_map
from ace_lite.runtime_stats import RuntimeInvocationStats, RuntimeStageLatency
from ace_lite.runtime_stats_schema import RUNTIME_STATS_DOCTOR_EVENT_CLASS
from ace_lite.runtime_stats_store import DurableStatsStore


def test_build_runtime_scope_map_excludes_doctor_events_from_filtered_scopes(
    tmp_path: Path,
) -> None:
    store = DurableStatsStore(db_path=tmp_path / "runtime-stats.db")
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-runtime",
            session_id="session-alpha",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=50.0,
            started_at="2026-03-21T00:00:00+00:00",
            finished_at="2026-03-21T00:00:01+00:00",
            degraded_reason_codes=("memory_fallback",),
            stage_latencies=(
                RuntimeStageLatency(stage_name="memory", elapsed_ms=10.0),
                RuntimeStageLatency(stage_name="total", elapsed_ms=50.0),
            ),
        )
    )
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-doctor",
            session_id="runtime-doctor::repo-alpha",
            repo_key="repo-alpha",
            profile_key="bugfix",
            event_class=RUNTIME_STATS_DOCTOR_EVENT_CLASS,
            status="degraded",
            total_latency_ms=0.0,
            started_at="2026-03-21T00:00:02+00:00",
            finished_at="2026-03-21T00:00:02+00:00",
            degraded_reason_codes=("git_unavailable",),
        )
    )

    latest_match = {
        "invocation_id": "inv-runtime",
        "session_id": "session-alpha",
        "repo_key": "repo-alpha",
        "profile_key": "bugfix",
        "event_class": "runtime_invocation",
        "finished_at": "2026-03-21T00:00:01+00:00",
    }
    scope_map = build_runtime_scope_map(
        store=store,
        latest_match=latest_match,
        excluded_event_classes=(RUNTIME_STATS_DOCTOR_EVENT_CLASS,),
    )

    assert scope_map["all_time"] is not None
    assert scope_map["all_time"]["counters"]["invocation_count"] == 1
    assert scope_map["repo_profile"] is not None
    assert scope_map["repo_profile"]["latency"]["latency_ms_avg"] == 50.0
    assert scope_map["repo_profile"]["degraded_states"][0]["reason_code"] == "memory_fallback"
