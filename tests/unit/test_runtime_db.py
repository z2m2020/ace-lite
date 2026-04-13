from __future__ import annotations

from pathlib import Path

from ace_lite.runtime_db import DEFAULT_RUNTIME_DB_BUSY_TIMEOUT_MS, connect_runtime_db
from ace_lite.runtime_db_migrate import (
    RuntimeDbMigration,
    build_runtime_db_migration_bootstrap,
    get_runtime_db_schema_version,
)


def _journal_mode(conn: object) -> str:
    return str(conn.execute("PRAGMA journal_mode").fetchone()[0]).strip().upper()  # type: ignore[union-attr]


def _busy_timeout(conn: object) -> int:
    return int(conn.execute("PRAGMA busy_timeout").fetchone()[0])  # type: ignore[union-attr]


def _synchronous(conn: object) -> int:
    return int(conn.execute("PRAGMA synchronous").fetchone()[0])  # type: ignore[union-attr]


def test_connect_runtime_db_applies_runtime_pragmas(tmp_path: Path) -> None:
    db_path = tmp_path / "context-map" / "runtime.db"

    conn = connect_runtime_db(db_path=db_path)
    try:
        assert db_path.exists()
        assert _journal_mode(conn) == "WAL"
        assert _synchronous(conn) == 1
        assert _busy_timeout(conn) == DEFAULT_RUNTIME_DB_BUSY_TIMEOUT_MS
    finally:
        conn.close()


def test_connect_runtime_db_runs_schema_and_migration_bootstrap(tmp_path: Path) -> None:
    db_path = tmp_path / "context-map" / "runtime.db"
    calls: list[str] = []

    def _schema_bootstrap(conn: object) -> None:
        calls.append("schema")
        conn.execute("CREATE TABLE IF NOT EXISTS demo(key TEXT PRIMARY KEY)")  # type: ignore[union-attr]

    def _migration_bootstrap(conn: object) -> None:
        calls.append("migration")
        conn.execute("INSERT INTO demo(key) VALUES ('ok')")  # type: ignore[union-attr]

    conn = connect_runtime_db(
        db_path=db_path,
        schema_bootstrap=_schema_bootstrap,
        migration_bootstrap=_migration_bootstrap,
    )
    try:
        row = conn.execute("SELECT key FROM demo").fetchone()
        assert calls == ["schema", "migration"]
        assert row[0] == "ok"
    finally:
        conn.close()


def test_runtime_db_migrations_fresh_init(tmp_path: Path) -> None:
    db_path = tmp_path / "context-map" / "runtime.db"

    def _create_demo(conn: object) -> None:
        conn.execute("CREATE TABLE IF NOT EXISTS demo(id INTEGER PRIMARY KEY, note TEXT)")  # type: ignore[union-attr]

    def _seed_demo(conn: object) -> None:
        conn.execute("INSERT INTO demo(note) VALUES ('fresh')")  # type: ignore[union-attr]

    conn = connect_runtime_db(
        db_path=db_path,
        migration_bootstrap=build_runtime_db_migration_bootstrap(
            schema_name="demo",
            migrations=(
                RuntimeDbMigration(version=1, apply=_create_demo),
                RuntimeDbMigration(version=2, apply=_seed_demo),
            ),
        ),
    )
    try:
        row = conn.execute("SELECT note FROM demo").fetchone()
        assert row[0] == "fresh"
        assert get_runtime_db_schema_version(conn, schema_name="demo") == 2
    finally:
        conn.close()


def test_runtime_db_migrations_noop_when_already_current(tmp_path: Path) -> None:
    db_path = tmp_path / "context-map" / "runtime.db"
    apply_calls: list[int] = []

    def _create_demo(conn: object) -> None:
        apply_calls.append(1)
        conn.execute("CREATE TABLE IF NOT EXISTS demo(id INTEGER PRIMARY KEY, note TEXT)")  # type: ignore[union-attr]

    def _seed_demo(conn: object) -> None:
        apply_calls.append(2)
        conn.execute("INSERT INTO demo(note) VALUES ('noop')")  # type: ignore[union-attr]

    bootstrap = build_runtime_db_migration_bootstrap(
        schema_name="demo",
        migrations=(
            RuntimeDbMigration(version=1, apply=_create_demo),
            RuntimeDbMigration(version=2, apply=_seed_demo),
        ),
    )

    first = connect_runtime_db(
        db_path=db_path,
        migration_bootstrap=bootstrap,
    )
    first.close()

    second = connect_runtime_db(
        db_path=db_path,
        migration_bootstrap=bootstrap,
    )
    try:
        row = second.execute("SELECT COUNT(*) FROM demo").fetchone()
        assert apply_calls == [1, 2]
        assert row[0] == 1
        assert get_runtime_db_schema_version(second, schema_name="demo") == 2
    finally:
        second.close()
