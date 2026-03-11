from __future__ import annotations

from pathlib import Path

from ace_lite.runtime_db import connect_runtime_db
from ace_lite.runtime_db_migrate import get_runtime_db_schema_version
from ace_lite.runtime_stats_schema import (
    RUNTIME_STATS_DEGRADED_REASON_CODES,
    RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE,
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
        assert get_runtime_db_schema_version(conn, schema_name=RUNTIME_STATS_SCHEMA_NAME) == (
            RUNTIME_STATS_SCHEMA_VERSION
        )
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
    assert "xref_budget_exhausted" in RUNTIME_STATS_DEGRADED_REASON_CODES
    assert "router_fallback_applied" in RUNTIME_STATS_DEGRADED_REASON_CODES
