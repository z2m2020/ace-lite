from __future__ import annotations

import sqlite3
from pathlib import Path

from ace_lite.runtime_stats import RuntimeInvocationStats, RuntimeStageLatency
from ace_lite.runtime_stats_schema import (
    RUNTIME_STATS_DEFAULT_EVENT_CLASS,
    RUNTIME_STATS_DOCTOR_EVENT_CLASS,
    RUNTIME_STATS_INVOCATIONS_TABLE,
)
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


def test_durable_stats_store_can_read_individual_invocation(tmp_path: Path) -> None:
    store = DurableStatsStore(db_path=tmp_path / "context-map" / "runtime-stats.db")
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-lookup",
            session_id="sess-1",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=18.5,
            started_at="2026-03-19T00:00:00+00:00",
            finished_at="2026-03-19T00:00:01+00:00",
            degraded_reason_codes=("memory_fallback",),
            learning_router_rollout_decision={
                "phase": "report_only",
                "decision": "stay_report_only",
                "reason": "adaptive_router_disabled",
                "eligible_for_guarded_rollout": False,
            },
        )
    )

    loaded = store.read_invocation(invocation_id="inv-lookup")

    assert loaded is not None
    assert loaded.invocation_id == "inv-lookup"
    assert loaded.repo_key == "repo-alpha"
    assert loaded.event_class == RUNTIME_STATS_DEFAULT_EVENT_CLASS
    assert loaded.degraded_reason_codes == ("memory_fallback",)
    assert loaded.learning_router_rollout_decision == {
        "phase": "report_only",
        "decision": "stay_report_only",
        "reason": "adaptive_router_disabled",
        "eligible_for_guarded_rollout": False,
    }


def test_durable_stats_store_canonicalizes_reason_aliases_but_preserves_unknown_codes(
    tmp_path: Path,
) -> None:
    store = DurableStatsStore(db_path=tmp_path / "context-map" / "runtime-stats.db")
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-alias",
            session_id="sess-1",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=12.0,
            degraded_reason_codes=("budget_exceeded", "custom_unknown_reason"),
        )
    )

    loaded = store.read_invocation(invocation_id="inv-alias")

    assert loaded is not None
    assert loaded.degraded_reason_codes == (
        "custom_unknown_reason",
        "latency_budget_exceeded",
    )


def test_durable_stats_store_can_filter_invocations_by_event_class(tmp_path: Path) -> None:
    store = DurableStatsStore(db_path=tmp_path / "context-map" / "runtime-stats.db")
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-runtime",
            session_id="session-alpha",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="succeeded",
            total_latency_ms=12.0,
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
            degraded_reason_codes=("git_unavailable",),
        )
    )

    visible = store.list_invocations(
        repo_key="repo-alpha",
        profile_key="bugfix",
        exclude_event_classes=(RUNTIME_STATS_DOCTOR_EVENT_CLASS,),
    )
    doctor_only = store.list_invocations(
        repo_key="repo-alpha",
        profile_key="bugfix",
        event_class=RUNTIME_STATS_DOCTOR_EVENT_CLASS,
    )

    assert [item.invocation_id for item in visible] == ["inv-runtime"]
    assert [item.invocation_id for item in doctor_only] == ["inv-doctor"]


def test_durable_stats_store_load_invocation_tolerates_legacy_rows_missing_new_columns(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy-runtime-stats.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        f"""
        CREATE TABLE {RUNTIME_STATS_INVOCATIONS_TABLE} (
            invocation_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            repo_key TEXT NOT NULL,
            profile_key TEXT NOT NULL,
            event_class TEXT NOT NULL,
            settings_fingerprint TEXT NOT NULL,
            status TEXT NOT NULL,
            contract_error_code TEXT NOT NULL DEFAULT '',
            degraded_reason_codes TEXT NOT NULL DEFAULT '[]',
            stage_latency_json TEXT NOT NULL DEFAULT '[]',
            total_latency_ms REAL NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL
        )
        """
        
    )
    conn.execute(
        f"""
        INSERT INTO {RUNTIME_STATS_INVOCATIONS_TABLE}(
            invocation_id, session_id, repo_key, profile_key, event_class,
            settings_fingerprint, status, contract_error_code, degraded_reason_codes,
            stage_latency_json, total_latency_ms, started_at, finished_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "legacy-inv",
            "legacy-session",
            "repo-alpha",
            "bugfix",
            RUNTIME_STATS_DEFAULT_EVENT_CLASS,
            "fp-legacy",
            "succeeded",
            "",
            '["git_unavailable"]',
            "[]",
            12.5,
            "2026-03-19T00:00:00+00:00",
            "2026-03-19T00:00:01+00:00",
        ),
    )
    conn.commit()

    store = DurableStatsStore(db_path=db_path)
    loaded = store._load_invocation(conn, "legacy-inv")
    conn.close()

    assert loaded is not None
    assert loaded.invocation_id == "legacy-inv"
    assert loaded.learning_router_rollout_decision == {}
    assert loaded.plan_replay_hit is False
    assert loaded.plan_replay_safe_hit is False
    assert loaded.plan_replay_store_written is False
    assert loaded.trace_exported is False
    assert loaded.trace_export_failed is False
