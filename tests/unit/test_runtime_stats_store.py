from __future__ import annotations

from pathlib import Path

from ace_lite.runtime_stats import RuntimeInvocationStats, RuntimeStageLatency
from ace_lite.runtime_stats_store import DurableStatsStore


def _scope_map(snapshot: object) -> dict[str, dict]:
    payload = snapshot.to_payload()  # type: ignore[union-attr]
    return {item["scope_kind"]: item for item in payload["scopes"]}


def test_durable_stats_store_records_rollups_for_required_scopes(tmp_path: Path) -> None:
    store = DurableStatsStore(db_path=tmp_path / "context-map" / "runtime-stats.db")
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-1",
            session_id="sess-1",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=42.0,
            stage_latencies=(
                RuntimeStageLatency(stage_name="memory", elapsed_ms=5.0),
                RuntimeStageLatency(stage_name="index", elapsed_ms=12.0),
                RuntimeStageLatency(stage_name="total", elapsed_ms=42.0),
            ),
            degraded_reason_codes=("memory_fallback", "router_fallback_applied"),
            plan_replay_hit=True,
            plan_replay_safe_hit=True,
        )
    )

    snapshot = store.read_snapshot(
        session_id="sess-1",
        repo_key="repo-alpha",
        profile_key="bugfix",
    )
    scopes = _scope_map(snapshot)

    assert set(scopes) == {"session", "all_time", "repo", "profile", "repo_profile"}
    assert scopes["session"]["counters"]["invocation_count"] == 1
    assert scopes["all_time"]["counters"]["degraded_count"] == 1
    assert scopes["repo"]["counters"]["plan_replay_hit_count"] == 1
    assert scopes["profile"]["latency"]["latency_ms_sum"] == 42.0
    assert [item["reason_code"] for item in scopes["repo_profile"]["degraded_states"]] == [
        "memory_fallback",
        "router_fallback_applied",
    ]
    assert [item["stage_name"] for item in scopes["session"]["stage_latencies"]] == [
        "index",
        "memory",
        "total",
    ]


def test_durable_stats_store_update_rebuilds_existing_invocation_without_double_count(
    tmp_path: Path,
) -> None:
    store = DurableStatsStore(db_path=tmp_path / "context-map" / "runtime-stats.db")
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-1",
            session_id="sess-1",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=40.0,
            stage_latencies=(RuntimeStageLatency(stage_name="total", elapsed_ms=40.0),),
            degraded_reason_codes=("memory_fallback",),
        )
    )
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-1",
            session_id="sess-1",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="succeeded",
            total_latency_ms=25.0,
            stage_latencies=(RuntimeStageLatency(stage_name="total", elapsed_ms=25.0),),
            degraded_reason_codes=(),
            plan_replay_store_written=True,
        )
    )

    scope = store.read_scope(scope_kind="repo_profile", scope_key="repo-alpha::bugfix")
    assert scope is not None
    payload = scope.to_payload()

    assert payload["counters"]["invocation_count"] == 1
    assert payload["counters"]["degraded_count"] == 0
    assert payload["counters"]["success_count"] == 1
    assert payload["counters"]["plan_replay_store_count"] == 1
    assert payload["latency"]["latency_ms_sum"] == 25.0
    assert payload["degraded_states"] == []
