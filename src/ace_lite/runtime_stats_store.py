from __future__ import annotations

import json
import os
import sqlite3
from contextlib import suppress
from pathlib import Path
from typing import Any

from ace_lite.runtime_db import connect_runtime_db
from ace_lite.runtime_paths import resolve_user_runtime_db_path
from ace_lite.runtime_stats import (
    RuntimeInvocationStats,
    RuntimeScopeRollup,
    RuntimeStatsSnapshot,
    normalize_runtime_invocation_stats,
    utc_now_iso,
)
from ace_lite.runtime_stats_schema import (
    RUNTIME_STATS_ALL_TIME_SCOPE_KEY,
    RUNTIME_STATS_COUNTER_FIELDS,
    RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE,
    RUNTIME_STATS_INVOCATIONS_TABLE,
    RUNTIME_STATS_ROLLUPS_TABLE,
    RUNTIME_STATS_STAGE_ROLLUPS_TABLE,
    RuntimeStatsScope,
    build_runtime_stats_migration_bootstrap,
    build_runtime_stats_scope_rows,
)


def _json_load_list(value: str) -> list[Any]:
    try:
        payload = json.loads(str(value or "").strip() or "[]")
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _counter_delta(stats: RuntimeInvocationStats) -> dict[str, int]:
    return {
        "invocation_count": 1,
        "success_count": 1 if stats.status == "succeeded" else 0,
        "degraded_count": 1 if stats.status == "degraded" else 0,
        "failure_count": 1 if stats.status == "failed" else 0,
        "contract_error_count": 1 if stats.contract_error_code else 0,
        "plan_replay_hit_count": 1 if stats.plan_replay_hit else 0,
        "plan_replay_safe_hit_count": 1 if stats.plan_replay_safe_hit else 0,
        "plan_replay_store_count": 1 if stats.plan_replay_store_written else 0,
        "trace_export_count": 1 if stats.trace_exported else 0,
        "trace_export_failure_count": 1 if stats.trace_export_failed else 0,
    }


class DurableStatsStore:
    def __init__(
        self,
        *,
        db_path: str | Path | None = None,
        home_path: str | Path | None = None,
        configured_path: str | Path | None = None,
    ) -> None:
        resolved_home = (
            Path(home_path).expanduser()
            if home_path is not None
            else Path(
                os.environ.get("HOME")
                or os.environ.get("USERPROFILE")
                or str(Path.home())
            ).expanduser()
        )
        self._db_path = (
            Path(db_path).resolve()
            if db_path is not None
            else Path(
                resolve_user_runtime_db_path(
                    home_path=str(resolved_home),
                    configured_path=configured_path,
                )
            )
        )

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> Any:
        return connect_runtime_db(
            db_path=self._db_path,
            row_factory=sqlite3.Row,
            migration_bootstrap=build_runtime_stats_migration_bootstrap(),
        )

    def record_invocation(
        self,
        stats: RuntimeInvocationStats | dict[str, Any],
    ) -> RuntimeInvocationStats:
        normalized = normalize_runtime_invocation_stats(stats)
        current_scopes = build_runtime_stats_scope_rows(
            session_id=normalized.session_id,
            repo_key=normalized.repo_key,
            profile_key=normalized.profile_key,
        )
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            previous = self._load_invocation(conn, normalized.invocation_id)
            self._upsert_invocation_row(conn, normalized)
            if previous is None:
                self._increment_scope_rollups(
                    conn=conn,
                    stats=normalized,
                    scopes=current_scopes,
                )
            else:
                affected: dict[tuple[str, str, str, str], RuntimeStatsScope] = {
                    (item.kind, item.scope_key, item.repo_key, item.profile_key): item
                    for item in current_scopes
                }
                for item in build_runtime_stats_scope_rows(
                    session_id=previous.session_id,
                    repo_key=previous.repo_key,
                    profile_key=previous.profile_key,
                ):
                    affected[(item.kind, item.scope_key, item.repo_key, item.profile_key)] = item
                for scope in affected.values():
                    self._rebuild_scope(conn, scope)
            conn.execute("COMMIT")
            return normalized
        except Exception:
            with suppress(Exception):
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def read_scope(self, *, scope_kind: str, scope_key: str) -> RuntimeScopeRollup | None:
        conn = self._connect()
        try:
            return self._read_scope(conn, scope_kind=scope_kind, scope_key=scope_key)
        finally:
            conn.close()

    def read_snapshot(
        self,
        *,
        session_id: str,
        repo_key: str,
        profile_key: str | None = None,
    ) -> RuntimeStatsSnapshot:
        scopes = build_runtime_stats_scope_rows(
            session_id=session_id,
            repo_key=repo_key,
            profile_key=profile_key,
        )
        conn = self._connect()
        try:
            rows = [
                item
                for item in (
                    self._read_scope(conn, scope_kind=scope.kind, scope_key=scope.scope_key)
                    for scope in scopes
                )
                if item is not None
            ]
            return RuntimeStatsSnapshot(scopes=tuple(rows))
        finally:
            conn.close()

    def read_invocation(self, *, invocation_id: str) -> RuntimeInvocationStats | None:
        normalized_invocation_id = str(invocation_id or "").strip()
        if not normalized_invocation_id:
            return None
        conn = self._connect()
        try:
            return self._load_invocation(conn, normalized_invocation_id)
        finally:
            conn.close()

    def _load_invocation(self, conn: Any, invocation_id: str) -> RuntimeInvocationStats | None:
        row = conn.execute(
            f"SELECT * FROM {RUNTIME_STATS_INVOCATIONS_TABLE} WHERE invocation_id = ?",
            (invocation_id,),
        ).fetchone()
        if row is None:
            return None
        return normalize_runtime_invocation_stats(
            {
                "invocation_id": row["invocation_id"],
                "session_id": row["session_id"],
                "repo_key": row["repo_key"],
                "profile_key": row["profile_key"],
                "settings_fingerprint": row["settings_fingerprint"],
                "status": row["status"],
                "total_latency_ms": row["total_latency_ms"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "contract_error_code": row["contract_error_code"],
                "degraded_reason_codes": _json_load_list(row["degraded_reason_codes"]),
                "stage_latencies": _json_load_list(row["stage_latency_json"]),
                "plan_replay_hit": bool(row["plan_replay_hit"]),
                "plan_replay_safe_hit": bool(row["plan_replay_safe_hit"]),
                "plan_replay_store_written": bool(row["plan_replay_store_written"]),
                "trace_exported": bool(row["trace_exported"]),
                "trace_export_failed": bool(row["trace_export_failed"]),
            }
        )

    def _upsert_invocation_row(self, conn: Any, stats: RuntimeInvocationStats) -> None:
        payload = stats.to_storage_payload()
        conn.execute(
            f"INSERT INTO {RUNTIME_STATS_INVOCATIONS_TABLE}("
            "invocation_id, session_id, repo_key, profile_key, settings_fingerprint, "
            "status, contract_error_code, degraded_reason_codes, stage_latency_json, "
            "plan_replay_hit, plan_replay_safe_hit, plan_replay_store_written, "
            "trace_exported, trace_export_failed, total_latency_ms, started_at, finished_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(invocation_id) DO UPDATE SET "
            "session_id = excluded.session_id, "
            "repo_key = excluded.repo_key, "
            "profile_key = excluded.profile_key, "
            "settings_fingerprint = excluded.settings_fingerprint, "
            "status = excluded.status, "
            "contract_error_code = excluded.contract_error_code, "
            "degraded_reason_codes = excluded.degraded_reason_codes, "
            "stage_latency_json = excluded.stage_latency_json, "
            "plan_replay_hit = excluded.plan_replay_hit, "
            "plan_replay_safe_hit = excluded.plan_replay_safe_hit, "
            "plan_replay_store_written = excluded.plan_replay_store_written, "
            "trace_exported = excluded.trace_exported, "
            "trace_export_failed = excluded.trace_export_failed, "
            "total_latency_ms = excluded.total_latency_ms, "
            "started_at = excluded.started_at, "
            "finished_at = excluded.finished_at",
            (
                payload["invocation_id"],
                payload["session_id"],
                payload["repo_key"],
                payload["profile_key"],
                payload["settings_fingerprint"],
                payload["status"],
                payload["contract_error_code"],
                payload["degraded_reason_codes"],
                payload["stage_latency_json"],
                payload["plan_replay_hit"],
                payload["plan_replay_safe_hit"],
                payload["plan_replay_store_written"],
                payload["trace_exported"],
                payload["trace_export_failed"],
                payload["total_latency_ms"],
                payload["started_at"],
                payload["finished_at"],
            ),
        )

    def _increment_scope_rollups(
        self,
        *,
        conn: Any,
        stats: RuntimeInvocationStats,
        scopes: tuple[RuntimeStatsScope, ...],
    ) -> None:
        counters = _counter_delta(stats)
        updated_at = utc_now_iso()
        for scope in scopes:
            self._upsert_rollup_row(
                conn=conn,
                scope=scope,
                counters=counters,
                total_latency_ms=stats.total_latency_ms,
                updated_at=updated_at,
            )
            for stage in stats.stage_latencies:
                self._upsert_stage_rollup_row(
                    conn=conn,
                    scope=scope,
                    stage_name=stage.stage_name,
                    elapsed_ms=stage.elapsed_ms,
                    updated_at=updated_at,
                )
            for reason_code in stats.degraded_reason_codes:
                conn.execute(
                    f"INSERT INTO {RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE}("
                    "scope_kind, scope_key, repo_key, profile_key, reason_code, event_count, last_seen_at"
                    ") VALUES (?, ?, ?, ?, ?, 1, ?) "
                    "ON CONFLICT(scope_kind, scope_key, reason_code) DO UPDATE SET "
                    "repo_key = excluded.repo_key, "
                    "profile_key = excluded.profile_key, "
                    "event_count = event_count + 1, "
                    "last_seen_at = excluded.last_seen_at",
                    (
                        scope.kind,
                        scope.scope_key,
                        scope.repo_key,
                        scope.profile_key,
                        reason_code,
                        updated_at,
                    ),
                )

    def _upsert_rollup_row(
        self,
        *,
        conn: Any,
        scope: RuntimeStatsScope,
        counters: dict[str, int],
        total_latency_ms: float,
        updated_at: str,
    ) -> None:
        conn.execute(
            f"INSERT INTO {RUNTIME_STATS_ROLLUPS_TABLE}("
            "scope_kind, scope_key, repo_key, profile_key, "
            "invocation_count, success_count, degraded_count, failure_count, "
            "contract_error_count, plan_replay_hit_count, plan_replay_safe_hit_count, "
            "plan_replay_store_count, trace_export_count, trace_export_failure_count, "
            "latency_ms_sum, latency_ms_min, latency_ms_max, latency_ms_last, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(scope_kind, scope_key) DO UPDATE SET "
            "repo_key = excluded.repo_key, "
            "profile_key = excluded.profile_key, "
            "invocation_count = invocation_count + excluded.invocation_count, "
            "success_count = success_count + excluded.success_count, "
            "degraded_count = degraded_count + excluded.degraded_count, "
            "failure_count = failure_count + excluded.failure_count, "
            "contract_error_count = contract_error_count + excluded.contract_error_count, "
            "plan_replay_hit_count = plan_replay_hit_count + excluded.plan_replay_hit_count, "
            "plan_replay_safe_hit_count = plan_replay_safe_hit_count + excluded.plan_replay_safe_hit_count, "
            "plan_replay_store_count = plan_replay_store_count + excluded.plan_replay_store_count, "
            "trace_export_count = trace_export_count + excluded.trace_export_count, "
            "trace_export_failure_count = trace_export_failure_count + excluded.trace_export_failure_count, "
            "latency_ms_sum = latency_ms_sum + excluded.latency_ms_sum, "
            "latency_ms_min = CASE WHEN invocation_count <= 0 OR excluded.latency_ms_min < latency_ms_min "
            "THEN excluded.latency_ms_min ELSE latency_ms_min END, "
            "latency_ms_max = CASE WHEN excluded.latency_ms_max > latency_ms_max "
            "THEN excluded.latency_ms_max ELSE latency_ms_max END, "
            "latency_ms_last = excluded.latency_ms_last, "
            "updated_at = excluded.updated_at",
            (
                scope.kind,
                scope.scope_key,
                scope.repo_key,
                scope.profile_key,
                *[counters[field] for field in RUNTIME_STATS_COUNTER_FIELDS],
                total_latency_ms,
                total_latency_ms,
                total_latency_ms,
                total_latency_ms,
                updated_at,
            ),
        )

    def _upsert_stage_rollup_row(
        self,
        *,
        conn: Any,
        scope: RuntimeStatsScope,
        stage_name: str,
        elapsed_ms: float,
        updated_at: str,
    ) -> None:
        conn.execute(
            f"INSERT INTO {RUNTIME_STATS_STAGE_ROLLUPS_TABLE}("
            "scope_kind, scope_key, repo_key, profile_key, stage_name, "
            "invocation_count, latency_ms_sum, latency_ms_min, latency_ms_max, latency_ms_last, updated_at"
            ") VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?) "
            "ON CONFLICT(scope_kind, scope_key, stage_name) DO UPDATE SET "
            "repo_key = excluded.repo_key, "
            "profile_key = excluded.profile_key, "
            "invocation_count = invocation_count + 1, "
            "latency_ms_sum = latency_ms_sum + excluded.latency_ms_sum, "
            "latency_ms_min = CASE WHEN invocation_count <= 0 OR excluded.latency_ms_min < latency_ms_min "
            "THEN excluded.latency_ms_min ELSE latency_ms_min END, "
            "latency_ms_max = CASE WHEN excluded.latency_ms_max > latency_ms_max "
            "THEN excluded.latency_ms_max ELSE latency_ms_max END, "
            "latency_ms_last = excluded.latency_ms_last, "
            "updated_at = excluded.updated_at",
            (
                scope.kind,
                scope.scope_key,
                scope.repo_key,
                scope.profile_key,
                stage_name,
                elapsed_ms,
                elapsed_ms,
                elapsed_ms,
                elapsed_ms,
                updated_at,
            ),
        )

    def _rebuild_scope(self, conn: Any, scope: RuntimeStatsScope) -> None:
        invocations = self._load_scope_invocations(conn, scope)
        conn.execute(
            f"DELETE FROM {RUNTIME_STATS_STAGE_ROLLUPS_TABLE} WHERE scope_kind = ? AND scope_key = ?",
            (scope.kind, scope.scope_key),
        )
        conn.execute(
            f"DELETE FROM {RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE} WHERE scope_kind = ? AND scope_key = ?",
            (scope.kind, scope.scope_key),
        )
        if not invocations:
            conn.execute(
                f"DELETE FROM {RUNTIME_STATS_ROLLUPS_TABLE} WHERE scope_kind = ? AND scope_key = ?",
                (scope.kind, scope.scope_key),
            )
            return

        counters = {field: 0 for field in RUNTIME_STATS_COUNTER_FIELDS}
        total_latencies: list[float] = []
        stage_values: dict[str, list[float]] = {}
        degraded_counts: dict[str, int] = {}
        updated_at = utc_now_iso()
        for stats in invocations:
            delta = _counter_delta(stats)
            for field, value in delta.items():
                counters[field] += value
            total_latencies.append(stats.total_latency_ms)
            for stage in stats.stage_latencies:
                stage_values.setdefault(stage.stage_name, []).append(stage.elapsed_ms)
            for reason_code in stats.degraded_reason_codes:
                degraded_counts[reason_code] = degraded_counts.get(reason_code, 0) + 1

        conn.execute(
            f"INSERT INTO {RUNTIME_STATS_ROLLUPS_TABLE}("
            "scope_kind, scope_key, repo_key, profile_key, "
            "invocation_count, success_count, degraded_count, failure_count, "
            "contract_error_count, plan_replay_hit_count, plan_replay_safe_hit_count, "
            "plan_replay_store_count, trace_export_count, trace_export_failure_count, "
            "latency_ms_sum, latency_ms_min, latency_ms_max, latency_ms_last, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(scope_kind, scope_key) DO UPDATE SET "
            "repo_key = excluded.repo_key, "
            "profile_key = excluded.profile_key, "
            "invocation_count = excluded.invocation_count, "
            "success_count = excluded.success_count, "
            "degraded_count = excluded.degraded_count, "
            "failure_count = excluded.failure_count, "
            "contract_error_count = excluded.contract_error_count, "
            "plan_replay_hit_count = excluded.plan_replay_hit_count, "
            "plan_replay_safe_hit_count = excluded.plan_replay_safe_hit_count, "
            "plan_replay_store_count = excluded.plan_replay_store_count, "
            "trace_export_count = excluded.trace_export_count, "
            "trace_export_failure_count = excluded.trace_export_failure_count, "
            "latency_ms_sum = excluded.latency_ms_sum, "
            "latency_ms_min = excluded.latency_ms_min, "
            "latency_ms_max = excluded.latency_ms_max, "
            "latency_ms_last = excluded.latency_ms_last, "
            "updated_at = excluded.updated_at",
            (
                scope.kind,
                scope.scope_key,
                scope.repo_key,
                scope.profile_key,
                *[counters[field] for field in RUNTIME_STATS_COUNTER_FIELDS],
                sum(total_latencies),
                min(total_latencies),
                max(total_latencies),
                total_latencies[-1],
                updated_at,
            ),
        )
        for stage_name, values in stage_values.items():
            conn.execute(
                f"INSERT INTO {RUNTIME_STATS_STAGE_ROLLUPS_TABLE}("
                "scope_kind, scope_key, repo_key, profile_key, stage_name, "
                "invocation_count, latency_ms_sum, latency_ms_min, latency_ms_max, latency_ms_last, updated_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    scope.kind,
                    scope.scope_key,
                    scope.repo_key,
                    scope.profile_key,
                    stage_name,
                    len(values),
                    sum(values),
                    min(values),
                    max(values),
                    values[-1],
                    updated_at,
                ),
            )
        for reason_code, event_count in degraded_counts.items():
            conn.execute(
                f"INSERT INTO {RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE}("
                "scope_kind, scope_key, repo_key, profile_key, reason_code, event_count, last_seen_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    scope.kind,
                    scope.scope_key,
                    scope.repo_key,
                    scope.profile_key,
                    reason_code,
                    event_count,
                    updated_at,
                ),
            )

    def _load_scope_invocations(self, conn: Any, scope: RuntimeStatsScope) -> list[RuntimeInvocationStats]:
        sql = f"SELECT invocation_id FROM {RUNTIME_STATS_INVOCATIONS_TABLE}"
        params: tuple[Any, ...] = ()
        if scope.kind == "session":
            sql += " WHERE session_id = ?"
            params = (scope.scope_key,)
        elif scope.kind == "repo":
            sql += " WHERE repo_key = ?"
            params = (scope.scope_key,)
        elif scope.kind == "profile":
            sql += " WHERE profile_key = ?"
            params = (scope.scope_key,)
        elif scope.kind == "repo_profile":
            sql += " WHERE repo_key = ? AND profile_key = ?"
            params = (scope.repo_key, scope.profile_key)
        elif not (scope.kind == "all_time" and scope.scope_key == RUNTIME_STATS_ALL_TIME_SCOPE_KEY):
            return []
        sql += " ORDER BY finished_at, invocation_id"
        rows = conn.execute(sql, params).fetchall()
        result: list[RuntimeInvocationStats] = []
        for row in rows:
            loaded = self._load_invocation(conn, row["invocation_id"])
            if loaded is not None:
                result.append(loaded)
        return result

    def _read_scope(
        self,
        conn: Any,
        *,
        scope_kind: str,
        scope_key: str,
    ) -> RuntimeScopeRollup | None:
        row = conn.execute(
            f"SELECT * FROM {RUNTIME_STATS_ROLLUPS_TABLE} WHERE scope_kind = ? AND scope_key = ?",
            (scope_kind, scope_key),
        ).fetchone()
        if row is None:
            return None
        stage_rows = conn.execute(
            f"SELECT stage_name, invocation_count, latency_ms_sum, latency_ms_min, latency_ms_max, latency_ms_last, updated_at "
            f"FROM {RUNTIME_STATS_STAGE_ROLLUPS_TABLE} WHERE scope_kind = ? AND scope_key = ? ORDER BY stage_name",
            (scope_kind, scope_key),
        ).fetchall()
        degraded_rows = conn.execute(
            f"SELECT reason_code, event_count, last_seen_at FROM {RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE} "
            "WHERE scope_kind = ? AND scope_key = ? ORDER BY reason_code",
            (scope_kind, scope_key),
        ).fetchall()
        return RuntimeScopeRollup(
            scope_kind=str(row["scope_kind"]),
            scope_key=str(row["scope_key"]),
            repo_key=str(row["repo_key"]),
            profile_key=str(row["profile_key"]),
            counters={field: int(row[field] or 0) for field in RUNTIME_STATS_COUNTER_FIELDS},
            latency={
                "latency_ms_sum": float(row["latency_ms_sum"] or 0.0),
                "latency_ms_min": float(row["latency_ms_min"] or 0.0),
                "latency_ms_max": float(row["latency_ms_max"] or 0.0),
                "latency_ms_last": float(row["latency_ms_last"] or 0.0),
            },
            updated_at=str(row["updated_at"]),
            stage_latencies=tuple(
                {
                    "stage_name": str(item["stage_name"]),
                    "invocation_count": int(item["invocation_count"] or 0),
                    "latency_ms_sum": float(item["latency_ms_sum"] or 0.0),
                    "latency_ms_min": float(item["latency_ms_min"] or 0.0),
                    "latency_ms_max": float(item["latency_ms_max"] or 0.0),
                    "latency_ms_last": float(item["latency_ms_last"] or 0.0),
                    "updated_at": str(item["updated_at"]),
                }
                for item in stage_rows
            ),
            degraded_states=tuple(
                {
                    "reason_code": str(item["reason_code"]),
                    "event_count": int(item["event_count"] or 0),
                    "last_seen_at": str(item["last_seen_at"]),
                }
                for item in degraded_rows
            ),
        )


__all__ = ["DurableStatsStore"]
