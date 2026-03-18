from __future__ import annotations

from pathlib import Path

from ace_lite.preference_capture_schema import (
    PREFERENCE_CAPTURE_EVENTS_TABLE,
    PREFERENCE_CAPTURE_PREFERENCE_KINDS,
    PREFERENCE_CAPTURE_SCHEMA_NAME,
    PREFERENCE_CAPTURE_SCHEMA_VERSION,
    PREFERENCE_CAPTURE_SIGNAL_SOURCES,
    build_preference_capture_migration_bootstrap,
    build_preference_capture_schema_document,
)
from ace_lite.runtime_db import connect_runtime_db
from ace_lite.runtime_db_migrate import get_runtime_db_schema_version


def test_preference_capture_schema_document_exposes_expected_table() -> None:
    payload = build_preference_capture_schema_document()
    table_names = {item["name"] for item in payload["tables"]}

    assert payload["schema_name"] == PREFERENCE_CAPTURE_SCHEMA_NAME
    assert payload["schema_version"] == PREFERENCE_CAPTURE_SCHEMA_VERSION
    assert table_names == {PREFERENCE_CAPTURE_EVENTS_TABLE}
    assert payload["preference_kinds"] == list(PREFERENCE_CAPTURE_PREFERENCE_KINDS)
    assert payload["signal_sources"] == list(PREFERENCE_CAPTURE_SIGNAL_SOURCES)
    assert payload["migration_plan"]["latest_version"] == PREFERENCE_CAPTURE_SCHEMA_VERSION


def test_preference_capture_schema_bootstrap_creates_events_table(tmp_path: Path) -> None:
    db_path = tmp_path / "context-map" / "preference-capture.db"

    conn = connect_runtime_db(
        db_path=db_path,
        migration_bootstrap=build_preference_capture_migration_bootstrap(),
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
            schema_name=PREFERENCE_CAPTURE_SCHEMA_NAME,
        ) == PREFERENCE_CAPTURE_SCHEMA_VERSION
        assert PREFERENCE_CAPTURE_EVENTS_TABLE in tables
    finally:
        conn.close()
