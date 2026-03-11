from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:  # pragma: no cover - sqlite3 may be unavailable in minimal runtimes
    import sqlite3
except Exception:  # pragma: no cover
    sqlite3 = None  # type: ignore[assignment]


DEFAULT_RUNTIME_DB_JOURNAL_MODE = "WAL"
DEFAULT_RUNTIME_DB_SYNCHRONOUS = "NORMAL"
DEFAULT_RUNTIME_DB_BUSY_TIMEOUT_MS = 5000

RuntimeDbBootstrap = Callable[[Any], None]


@dataclass(frozen=True, slots=True)
class RuntimeDbPragmas:
    journal_mode: str
    synchronous: str
    busy_timeout_ms: int


def _normalize_journal_mode(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalize_synchronous(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if raw in {"0", "OFF"}:
        return "OFF"
    if raw in {"1", "NORMAL"}:
        return "NORMAL"
    if raw in {"2", "FULL"}:
        return "FULL"
    if raw in {"3", "EXTRA"}:
        return "EXTRA"
    return raw or DEFAULT_RUNTIME_DB_SYNCHRONOUS


def _read_pragma_value(conn: Any, statement: str) -> Any:
    row = conn.execute(statement).fetchone()
    if row is None:
        return None
    try:
        return row[0]
    except Exception:
        return row


def apply_runtime_db_pragmas(
    conn: Any,
    *,
    journal_mode: str = DEFAULT_RUNTIME_DB_JOURNAL_MODE,
    synchronous: str = DEFAULT_RUNTIME_DB_SYNCHRONOUS,
    busy_timeout_ms: int = DEFAULT_RUNTIME_DB_BUSY_TIMEOUT_MS,
) -> RuntimeDbPragmas:
    normalized_journal_mode = _normalize_journal_mode(journal_mode)
    normalized_synchronous = _normalize_synchronous(synchronous)
    normalized_busy_timeout = max(0, int(busy_timeout_ms))

    journal_mode_value = _read_pragma_value(
        conn,
        f"PRAGMA journal_mode={normalized_journal_mode}",
    )
    conn.execute(f"PRAGMA synchronous={normalized_synchronous}")
    conn.execute(f"PRAGMA busy_timeout={normalized_busy_timeout}")

    return RuntimeDbPragmas(
        journal_mode=_normalize_journal_mode(journal_mode_value),
        synchronous=_normalize_synchronous(
            _read_pragma_value(conn, "PRAGMA synchronous")
        ),
        busy_timeout_ms=max(
            0,
            int(_read_pragma_value(conn, "PRAGMA busy_timeout") or normalized_busy_timeout),
        ),
    )


def bootstrap_runtime_db(
    conn: Any,
    *,
    schema_bootstrap: RuntimeDbBootstrap | None = None,
    migration_bootstrap: RuntimeDbBootstrap | None = None,
) -> None:
    if schema_bootstrap is not None:
        schema_bootstrap(conn)
    if migration_bootstrap is not None:
        migration_bootstrap(conn)


def connect_runtime_db(
    *,
    db_path: str | Path,
    row_factory: Any | None = None,
    journal_mode: str = DEFAULT_RUNTIME_DB_JOURNAL_MODE,
    synchronous: str = DEFAULT_RUNTIME_DB_SYNCHRONOUS,
    busy_timeout_ms: int = DEFAULT_RUNTIME_DB_BUSY_TIMEOUT_MS,
    schema_bootstrap: RuntimeDbBootstrap | None = None,
    migration_bootstrap: RuntimeDbBootstrap | None = None,
) -> Any:
    if sqlite3 is None:
        raise RuntimeError("sqlite3_unavailable")

    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    timeout_seconds = float(max(0, int(busy_timeout_ms))) / 1000.0
    conn = sqlite3.connect(str(target), timeout=timeout_seconds)

    try:
        if row_factory is not None:
            conn.row_factory = row_factory
        apply_runtime_db_pragmas(
            conn,
            journal_mode=journal_mode,
            synchronous=synchronous,
            busy_timeout_ms=busy_timeout_ms,
        )
        bootstrap_runtime_db(
            conn,
            schema_bootstrap=schema_bootstrap,
            migration_bootstrap=migration_bootstrap,
        )
        return conn
    except Exception:
        with suppress(Exception):
            conn.close()
        raise


__all__ = [
    "DEFAULT_RUNTIME_DB_BUSY_TIMEOUT_MS",
    "DEFAULT_RUNTIME_DB_JOURNAL_MODE",
    "DEFAULT_RUNTIME_DB_SYNCHRONOUS",
    "RuntimeDbBootstrap",
    "RuntimeDbPragmas",
    "apply_runtime_db_pragmas",
    "bootstrap_runtime_db",
    "connect_runtime_db",
]
