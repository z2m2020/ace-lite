from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ace_lite.cli_app.runtime_stats_data_support import (
    normalize_runtime_stats_filter_value,
)
from ace_lite.runtime_db import connect_runtime_db
from ace_lite.runtime_stats_schema import (
    RUNTIME_STATS_DOCTOR_EVENT_CLASS,
    RUNTIME_STATS_INVOCATIONS_TABLE,
    build_runtime_stats_migration_bootstrap,
)


def _connect_runtime_stats_db(db_path: Path) -> Any:
    return connect_runtime_db(
        db_path=db_path,
        row_factory=sqlite3.Row,
        migration_bootstrap=build_runtime_stats_migration_bootstrap(),
    )


def load_latest_runtime_stats_match(
    *,
    db_path: str | Path,
    session_id: str | None = None,
    repo_key: str | None = None,
    profile_key: str | None = None,
    exclude_doctor_sessions: bool = True,
) -> dict[str, Any] | None:
    resolved_path = Path(db_path).resolve()
    normalized_session = normalize_runtime_stats_filter_value(session_id)
    normalized_repo = normalize_runtime_stats_filter_value(repo_key)
    normalized_profile = normalize_runtime_stats_filter_value(profile_key)
    conn = _connect_runtime_stats_db(resolved_path)
    try:
        clauses: list[str] = []
        params: list[str] = []
        if normalized_session is not None:
            clauses.append("session_id = ?")
            params.append(normalized_session)
        elif exclude_doctor_sessions:
            clauses.append("event_class != ?")
            params.append(RUNTIME_STATS_DOCTOR_EVENT_CLASS)
        if normalized_repo is not None:
            clauses.append("repo_key = ?")
            params.append(normalized_repo)
        if normalized_profile is not None:
            clauses.append("profile_key = ?")
            params.append(normalized_profile)
        sql = (
            f"SELECT invocation_id, session_id, repo_key, profile_key, event_class, finished_at "
            f"FROM {RUNTIME_STATS_INVOCATIONS_TABLE}"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY finished_at DESC, invocation_id DESC LIMIT 1"
        row = conn.execute(sql, tuple(params)).fetchone()
        if row is None:
            return None
        return {
            "invocation_id": str(row["invocation_id"]),
            "session_id": str(row["session_id"]),
            "repo_key": str(row["repo_key"]),
            "profile_key": str(row["profile_key"]),
            "event_class": str(row["event_class"]),
            "finished_at": str(row["finished_at"]),
        }
    finally:
        conn.close()


__all__ = ["load_latest_runtime_stats_match"]
