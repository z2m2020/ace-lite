from __future__ import annotations

import sqlite3
from pathlib import Path

from ace_lite.runtime_db import connect_runtime_db
from ace_lite.runtime_db_migrate import get_runtime_db_schema_version, set_runtime_db_schema_version
from ace_lite.runtime_stats_schema import (
    RUNTIME_STATS_DEFAULT_EVENT_CLASS,
    RUNTIME_STATS_DEGRADED_REASON_CODES,
    RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE,
    RUNTIME_STATS_DOCTOR_EVENT_CLASS,
    RUNTIME_STATS_EVENT_CLASS_VALUES,
    RUNTIME_STATS_INVOCATIONS_TABLE,
    RUNTIME_STATS_REQUIRED_ROLLUP_KINDS,
    RUNTIME_STATS_ROLLUPS_TABLE,
    RUNTIME_STATS_SCHEMA_NAME,
    RUNTIME_STATS_SCHEMA_VERSION,
    RUNTIME_STATS_STAGE_ROLLUPS_TABLE,
    build_runtime_stats_migration_bootstrap,
    build_runtime_stats_schema_document,
    build_runtime_stats_scope_rows,
)


def test_runtime_stats_scope_rows_cover_required_rollups() -> None:
    rows = build_runtime_stats_scope_rows(
        session_id="session-123",
        repo_key="repo-alpha",
        profile_key="bugfix",
    )

    kinds = {item.kind for item in rows}

    assert set(RUNTIME_STATS_REQUIRED_ROLLUP_KINDS).issubset(kinds)
    assert "repo_profile" in kinds
    assert any(
        item.kind == "repo_profile"
        and item.scope_key == "repo-alpha::bugfix"
        and item.repo_key == "repo-alpha"
        and item.profile_key == "bugfix"
        for item in rows
    )


def test_runtime_stats_schema_document_includes_tables_aggregates_and_degraded_states() -> None:
    payload = build_runtime_stats_schema_document()
    table_names = {item["name"] for item in payload["tables"]}

    assert payload["schema_name"] == RUNTIME_STATS_SCHEMA_NAME
    assert payload["schema_version"] == RUNTIME_STATS_SCHEMA_VERSION
    assert set(RUNTIME_STATS_REQUIRED_ROLLUP_KINDS).issubset(payload["rollup_kinds"])
    assert "invocation_count" in payload["counter_fields"]
    assert "latency_ms_sum" in payload["latency_aggregate_fields"]
    assert payload["event_class_values"] == list(RUNTIME_STATS_EVENT_CLASS_VALUES)
    assert "memory_fallback" in payload["degraded_reason_codes"]
    assert "contract_error" in payload["degraded_reason_codes"]
    assert table_names == {
        RUNTIME_STATS_INVOCATIONS_TABLE,
        RUNTIME_STATS_ROLLUPS_TABLE,
        RUNTIME_STATS_STAGE_ROLLUPS_TABLE,
        RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE,
    }
    assert payload["migration_plan"]["latest_version"] == RUNTIME_STATS_SCHEMA_VERSION


def test_runtime_stats_schema_bootstrap_creates_expected_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "context-map" / "runtime-stats.db"

    conn = connect_runtime_db(
        db_path=db_path,
        migration_bootstrap=build_runtime_stats_migration_bootstrap(),
    )
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        invocation_columns = {
            str(row[1])
            for row in conn.execute(
                f"PRAGMA table_info({RUNTIME_STATS_INVOCATIONS_TABLE})"
            ).fetchall()
        }
        assert get_runtime_db_schema_version(conn, schema_name=RUNTIME_STATS_SCHEMA_NAME) == (
            RUNTIME_STATS_SCHEMA_VERSION
        )
        assert "event_class" in invocation_columns
        assert {
            RUNTIME_STATS_INVOCATIONS_TABLE,
            RUNTIME_STATS_ROLLUPS_TABLE,
            RUNTIME_STATS_STAGE_ROLLUPS_TABLE,
            RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE,
        }.issubset(tables)
    finally:
        conn.close()


def test_runtime_stats_schema_reasons_cover_existing_runtime_fallback_signals() -> None:
    assert "memory_fallback" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "embedding_time_budget_exceeded" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "chunk_semantic_fallback" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "chunk_guard_fallback" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "stage_artifact_cache_corrupt" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "git_unavailable" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "install_drift" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "validation_timeout" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "validation_apply_failed" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "xref_budget_exhausted" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "router_fallback_applied" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "evidence_insufficient" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "noisy_hit" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "manual_override" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "repeated_retry" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "latency_budget_exceeded" in RUNTIME_STATS_DEGRADED_REASON_CODES


def test_runtime_stats_schema_v2_backfills_event_class_for_legacy_doctor_rows(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "context-map" / "runtime-stats.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"CREATE TABLE {RUNTIME_STATS_INVOCATIONS_TABLE}("
            "invocation_id TEXT PRIMARY KEY, "
            "session_id TEXT NOT NULL, "
            "repo_key TEXT NOT NULL, "
            "profile_key TEXT NOT NULL DEFAULT '', "
            "settings_fingerprint TEXT NOT NULL DEFAULT '', "
            "status TEXT NOT NULL, "
            "contract_error_code TEXT NOT NULL DEFAULT '', "
            "degraded_reason_codes TEXT NOT NULL DEFAULT '[]', "
            "stage_latency_json TEXT NOT NULL DEFAULT '[]', "
            "plan_replay_hit INTEGER NOT NULL DEFAULT 0, "
            "plan_replay_safe_hit INTEGER NOT NULL DEFAULT 0, "
            "plan_replay_store_written INTEGER NOT NULL DEFAULT 0, "
            "trace_exported INTEGER NOT NULL DEFAULT 0, "
            "trace_export_failed INTEGER NOT NULL DEFAULT 0, "
            "total_latency_ms REAL NOT NULL DEFAULT 0.0, "
            "started_at TEXT NOT NULL, "
            "finished_at TEXT NOT NULL)"
        )
        conn.execute(
            f"INSERT INTO {RUNTIME_STATS_INVOCATIONS_TABLE}("
            "invocation_id, session_id, repo_key, profile_key, settings_fingerprint, "
            "status, contract_error_code, degraded_reason_codes, stage_latency_json, "
            "plan_replay_hit, plan_replay_safe_hit, plan_replay_store_written, "
            "trace_exported, trace_export_failed, total_latency_ms, started_at, finished_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "inv-runtime",
                "session-alpha",
                "repo-alpha",
                "bugfix",
                "",
                "succeeded",
                "",
                "[]",
                "[]",
                0,
                0,
                0,
                0,
                0,
                10.0,
                "2026-03-21T00:00:00+00:00",
                "2026-03-21T00:00:01+00:00",
            ),
        )
        conn.execute(
            f"INSERT INTO {RUNTIME_STATS_INVOCATIONS_TABLE}("
            "invocation_id, session_id, repo_key, profile_key, settings_fingerprint, "
            "status, contract_error_code, degraded_reason_codes, stage_latency_json, "
            "plan_replay_hit, plan_replay_safe_hit, plan_replay_store_written, "
            "trace_exported, trace_export_failed, total_latency_ms, started_at, finished_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "inv-doctor",
                "runtime-doctor::repo-alpha",
                "repo-alpha",
                "bugfix",
                "",
                "degraded",
                "",
                "[\"git_unavailable\"]",
                "[]",
                0,
                0,
                0,
                0,
                0,
                0.0,
                "2026-03-21T00:00:02+00:00",
                "2026-03-21T00:00:02+00:00",
            ),
        )
        set_runtime_db_schema_version(
            conn,
            schema_name=RUNTIME_STATS_SCHEMA_NAME,
            version=1,
        )
        conn.commit()
    finally:
        conn.close()

    migrated = connect_runtime_db(
        db_path=db_path,
        migration_bootstrap=build_runtime_stats_migration_bootstrap(),
    )
    try:
        rows = migrated.execute(
            f"SELECT invocation_id, event_class FROM {RUNTIME_STATS_INVOCATIONS_TABLE} "
            "ORDER BY invocation_id"
        ).fetchall()
        assert get_runtime_db_schema_version(
            migrated,
            schema_name=RUNTIME_STATS_SCHEMA_NAME,
        ) == RUNTIME_STATS_SCHEMA_VERSION
        assert [(str(row[0]), str(row[1])) for row in rows] == [
            ("inv-doctor", RUNTIME_STATS_DOCTOR_EVENT_CLASS),
            ("inv-runtime", RUNTIME_STATS_DEFAULT_EVENT_CLASS),
        ]
    finally:
        migrated.close()
