from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

SCHEMA_TABLE_NAME = "runtime_db_schema"

MigrationApply = Callable[[Any], None]


@dataclass(frozen=True, slots=True)
class RuntimeDbMigration:
    version: int
    apply: MigrationApply


@dataclass(frozen=True, slots=True)
class RuntimeDbMigrationResult:
    schema_name: str
    previous_version: int
    current_version: int
    applied_versions: tuple[int, ...]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_runtime_db_schema_table(conn: Any) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS runtime_db_schema("
        "schema_name TEXT PRIMARY KEY, "
        "version INTEGER NOT NULL, "
        "updated_at TEXT NOT NULL)"
    )


def get_runtime_db_schema_version(conn: Any, *, schema_name: str) -> int:
    ensure_runtime_db_schema_table(conn)
    row = conn.execute(
        "SELECT version FROM runtime_db_schema WHERE schema_name = ?",
        (str(schema_name),),
    ).fetchone()
    if row is None:
        return 0
    try:
        return max(0, int(row[0]))
    except Exception:
        return 0


def set_runtime_db_schema_version(conn: Any, *, schema_name: str, version: int) -> None:
    ensure_runtime_db_schema_table(conn)
    conn.execute(
        "INSERT INTO runtime_db_schema(schema_name, version, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(schema_name) DO UPDATE SET "
        "version = excluded.version, updated_at = excluded.updated_at",
        (str(schema_name), max(0, int(version)), _utc_now_iso()),
    )


def run_runtime_db_migrations(
    conn: Any,
    *,
    schema_name: str,
    migrations: Iterable[RuntimeDbMigration],
) -> RuntimeDbMigrationResult:
    normalized_schema_name = str(schema_name or "").strip()
    if not normalized_schema_name:
        raise ValueError("schema_name must be non-empty")

    ordered = sorted(migrations, key=lambda item: int(item.version))
    versions = [int(item.version) for item in ordered]
    if len(versions) != len(set(versions)):
        raise ValueError("migration versions must be unique")

    previous_version = get_runtime_db_schema_version(
        conn,
        schema_name=normalized_schema_name,
    )

    if not ordered:
        set_runtime_db_schema_version(
            conn,
            schema_name=normalized_schema_name,
            version=previous_version,
        )
        return RuntimeDbMigrationResult(
            schema_name=normalized_schema_name,
            previous_version=previous_version,
            current_version=previous_version,
            applied_versions=(),
        )

    pending = [item for item in ordered if int(item.version) > previous_version]
    if not pending:
        return RuntimeDbMigrationResult(
            schema_name=normalized_schema_name,
            previous_version=previous_version,
            current_version=previous_version,
            applied_versions=(),
        )

    applied_versions: list[int] = []
    try:
        conn.execute("BEGIN")
        for migration in pending:
            migration.apply(conn)
            set_runtime_db_schema_version(
                conn,
                schema_name=normalized_schema_name,
                version=int(migration.version),
            )
            applied_versions.append(int(migration.version))
        conn.execute("COMMIT")
    except Exception:
        with suppress(Exception):
            conn.execute("ROLLBACK")
        raise

    current_version = previous_version
    if applied_versions:
        current_version = applied_versions[-1]

    return RuntimeDbMigrationResult(
        schema_name=normalized_schema_name,
        previous_version=previous_version,
        current_version=current_version,
        applied_versions=tuple(applied_versions),
    )


def build_runtime_db_migration_bootstrap(
    *,
    schema_name: str,
    migrations: Iterable[RuntimeDbMigration],
) -> MigrationApply:
    frozen_migrations = tuple(migrations)

    def _bootstrap(conn: Any) -> None:
        run_runtime_db_migrations(
            conn,
            schema_name=schema_name,
            migrations=frozen_migrations,
        )

    return _bootstrap


__all__ = [
    "SCHEMA_TABLE_NAME",
    "RuntimeDbMigration",
    "RuntimeDbMigrationResult",
    "build_runtime_db_migration_bootstrap",
    "ensure_runtime_db_schema_table",
    "get_runtime_db_schema_version",
    "run_runtime_db_migrations",
    "set_runtime_db_schema_version",
]
