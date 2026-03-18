from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ace_lite.runtime_db_migrate import RuntimeDbMigration
from ace_lite.runtime_db_migrate import build_runtime_db_migration_bootstrap


PREFERENCE_CAPTURE_SCHEMA_NAME = "preference_capture"
PREFERENCE_CAPTURE_SCHEMA_VERSION = 1
PREFERENCE_CAPTURE_SCHEMA_LABEL = "ace-lite-preference-capture-v1"

PREFERENCE_CAPTURE_EVENTS_TABLE = "preference_capture_events"
PREFERENCE_CAPTURE_PREFERENCE_KINDS = (
    "selection_feedback",
    "note_capture",
    "retrieval_preference",
    "packing_preference",
    "validation_preference",
)
PREFERENCE_CAPTURE_SIGNAL_SOURCES = (
    "feedback_store",
    "benchmark",
    "manual",
    "runtime",
    "mcp",
    "cli",
)


@dataclass(frozen=True, slots=True)
class PreferenceCaptureTableSpec:
    name: str
    purpose: str
    create_sql: str
    indexes: tuple[str, ...]
    key_fields: tuple[str, ...]
    measure_fields: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "key_fields": list(self.key_fields),
            "measure_fields": list(self.measure_fields),
        }


def _build_table_specs() -> tuple[PreferenceCaptureTableSpec, ...]:
    events = PreferenceCaptureTableSpec(
        name=PREFERENCE_CAPTURE_EVENTS_TABLE,
        purpose=(
            "Append-friendly durable preference events decoupled from profile.json so "
            "benchmarking, observability, and future policy layers can read the same source."
        ),
        create_sql=(
            f"CREATE TABLE IF NOT EXISTS {PREFERENCE_CAPTURE_EVENTS_TABLE}("
            "event_id TEXT PRIMARY KEY, "
            "user_id TEXT NOT NULL DEFAULT '', "
            "repo_key TEXT NOT NULL DEFAULT '', "
            "profile_key TEXT NOT NULL DEFAULT '', "
            "preference_kind TEXT NOT NULL DEFAULT '', "
            "signal_source TEXT NOT NULL DEFAULT '', "
            "signal_key TEXT NOT NULL DEFAULT '', "
            "target_path TEXT NOT NULL DEFAULT '', "
            "value_text TEXT NOT NULL DEFAULT '', "
            "weight REAL NOT NULL DEFAULT 0.0, "
            "payload_json TEXT NOT NULL DEFAULT '{}', "
            "created_at TEXT NOT NULL)"
        ),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_preference_capture_events_repo_profile "
            f"ON {PREFERENCE_CAPTURE_EVENTS_TABLE}(repo_key, profile_key)",
            "CREATE INDEX IF NOT EXISTS idx_preference_capture_events_kind_source "
            f"ON {PREFERENCE_CAPTURE_EVENTS_TABLE}(preference_kind, signal_source)",
            "CREATE INDEX IF NOT EXISTS idx_preference_capture_events_target_path "
            f"ON {PREFERENCE_CAPTURE_EVENTS_TABLE}(target_path)",
            "CREATE INDEX IF NOT EXISTS idx_preference_capture_events_created_at "
            f"ON {PREFERENCE_CAPTURE_EVENTS_TABLE}(created_at)",
        ),
        key_fields=(
            "event_id",
            "user_id",
            "repo_key",
            "profile_key",
            "preference_kind",
            "signal_source",
            "signal_key",
            "target_path",
        ),
        measure_fields=("value_text", "weight", "payload_json", "created_at"),
    )
    return (events,)


PREFERENCE_CAPTURE_TABLE_SPECS = _build_table_specs()


def _apply_preference_capture_schema_v1(conn: Any) -> None:
    for table in PREFERENCE_CAPTURE_TABLE_SPECS:
        conn.execute(table.create_sql)
        for index_sql in table.indexes:
            conn.execute(index_sql)


def build_preference_capture_migrations() -> tuple[RuntimeDbMigration, ...]:
    return (
        RuntimeDbMigration(version=1, apply=_apply_preference_capture_schema_v1),
    )


def build_preference_capture_migration_bootstrap():
    return build_runtime_db_migration_bootstrap(
        schema_name=PREFERENCE_CAPTURE_SCHEMA_NAME,
        migrations=build_preference_capture_migrations(),
    )


def build_preference_capture_schema_document() -> dict[str, Any]:
    return {
        "schema_name": PREFERENCE_CAPTURE_SCHEMA_NAME,
        "schema_version": PREFERENCE_CAPTURE_SCHEMA_VERSION,
        "schema_label": PREFERENCE_CAPTURE_SCHEMA_LABEL,
        "preference_kinds": list(PREFERENCE_CAPTURE_PREFERENCE_KINDS),
        "signal_sources": list(PREFERENCE_CAPTURE_SIGNAL_SOURCES),
        "tables": [item.to_payload() for item in PREFERENCE_CAPTURE_TABLE_SPECS],
        "migration_plan": {
            "latest_version": PREFERENCE_CAPTURE_SCHEMA_VERSION,
            "versions": [item.version for item in build_preference_capture_migrations()],
        },
    }


__all__ = [
    "PREFERENCE_CAPTURE_EVENTS_TABLE",
    "PREFERENCE_CAPTURE_PREFERENCE_KINDS",
    "PREFERENCE_CAPTURE_SCHEMA_LABEL",
    "PREFERENCE_CAPTURE_SCHEMA_NAME",
    "PREFERENCE_CAPTURE_SCHEMA_VERSION",
    "PREFERENCE_CAPTURE_SIGNAL_SOURCES",
    "PREFERENCE_CAPTURE_TABLE_SPECS",
    "PreferenceCaptureTableSpec",
    "build_preference_capture_migration_bootstrap",
    "build_preference_capture_migrations",
    "build_preference_capture_schema_document",
]
