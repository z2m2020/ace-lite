from __future__ import annotations

from pathlib import Path

from ace_lite.runtime_db import connect_runtime_db
from ace_lite.runtime_db_migrate import get_runtime_db_schema_version
from ace_lite.stage_artifact_cache_store import (
    STAGE_ARTIFACT_CACHE_DEFAULT_PAYLOAD_ROOT,
    STAGE_ARTIFACT_CACHE_DEFAULT_TEMP_ROOT,
    STAGE_ARTIFACT_CACHE_ENTRIES_TABLE,
    STAGE_ARTIFACT_CACHE_SCHEMA_NAME,
    STAGE_ARTIFACT_CACHE_SCHEMA_VERSION,
    STAGE_ARTIFACT_CACHE_TTL_FIELDS,
    STAGE_ARTIFACT_CACHE_WRITE_ORDER,
    build_stage_artifact_cache_migration_bootstrap,
    build_stage_artifact_cache_schema_document,
    build_stage_artifact_payload_relpath,
    build_stage_artifact_temp_relpath,
    resolve_stage_artifact_payload_root,
    resolve_stage_artifact_temp_root,
)


def test_stage_artifact_cache_schema_document_includes_ttl_paths_and_write_order() -> None:
    payload = build_stage_artifact_cache_schema_document()
    table_names = {item["name"] for item in payload["tables"]}
    entry_fields = payload["tables"][0]["key_fields"] + payload["tables"][0]["measure_fields"]

    assert payload["schema_name"] == STAGE_ARTIFACT_CACHE_SCHEMA_NAME
    assert payload["schema_version"] == STAGE_ARTIFACT_CACHE_SCHEMA_VERSION
    assert payload["payload_root"] == STAGE_ARTIFACT_CACHE_DEFAULT_PAYLOAD_ROOT
    assert payload["temp_root"] == STAGE_ARTIFACT_CACHE_DEFAULT_TEMP_ROOT
    assert payload["ttl_fields"] == list(STAGE_ARTIFACT_CACHE_TTL_FIELDS)
    assert payload["write_order"] == list(STAGE_ARTIFACT_CACHE_WRITE_ORDER)
    assert table_names == {STAGE_ARTIFACT_CACHE_ENTRIES_TABLE}
    assert "query_hash" in entry_fields
    assert "fingerprint" in entry_fields
    assert "settings_fingerprint" in entry_fields
    assert "payload_relpath" in entry_fields
    assert "token_weight" in entry_fields
    assert "ttl_seconds" in entry_fields
    assert payload["path_examples"]["payload_relpath"].startswith("source_plan/")
    assert payload["path_examples"]["temp_relpath"].startswith("source_plan/")


def test_stage_artifact_cache_path_helpers_build_sharded_payload_paths() -> None:
    payload_relpath = build_stage_artifact_payload_relpath(
        stage_name="source plan",
        cache_key="ABCDEF0123456789",
    )
    temp_relpath = build_stage_artifact_temp_relpath(
        stage_name="source plan",
        cache_key="ABCDEF0123456789",
        write_token="worker 01",
    )

    assert payload_relpath == "source_plan/ab/abcdef0123456789.json"
    assert temp_relpath == "source_plan/ab/abcdef0123456789.worker_01.json.tmp"


def test_stage_artifact_cache_root_helpers_resolve_relative_paths(tmp_path: Path) -> None:
    payload_root = resolve_stage_artifact_payload_root(root_path=tmp_path)
    temp_root = resolve_stage_artifact_temp_root(root_path=tmp_path)

    assert payload_root == tmp_path / STAGE_ARTIFACT_CACHE_DEFAULT_PAYLOAD_ROOT
    assert temp_root == tmp_path / STAGE_ARTIFACT_CACHE_DEFAULT_TEMP_ROOT


def test_stage_artifact_cache_schema_bootstrap_creates_expected_table(tmp_path: Path) -> None:
    db_path = tmp_path / "context-map" / "runtime-cache" / "cache.db"

    conn = connect_runtime_db(
        db_path=db_path,
        migration_bootstrap=build_stage_artifact_cache_migration_bootstrap(),
    )
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert get_runtime_db_schema_version(
            conn,
            schema_name=STAGE_ARTIFACT_CACHE_SCHEMA_NAME,
        ) == STAGE_ARTIFACT_CACHE_SCHEMA_VERSION
        assert STAGE_ARTIFACT_CACHE_ENTRIES_TABLE in tables
    finally:
        conn.close()
