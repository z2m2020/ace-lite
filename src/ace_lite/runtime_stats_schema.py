from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ace_lite.runtime_db_migrate import RuntimeDbMigration
from ace_lite.runtime_db_migrate import build_runtime_db_migration_bootstrap


RUNTIME_STATS_SCHEMA_NAME = "runtime_stats"
RUNTIME_STATS_SCHEMA_VERSION = 1
RUNTIME_STATS_SCHEMA_LABEL = "ace-lite-runtime-stats-v1"
RUNTIME_STATS_ALL_TIME_SCOPE_KEY = "all"

RUNTIME_STATS_REQUIRED_ROLLUP_KINDS = (
    "session",
    "all_time",
    "repo",
    "profile",
)
RUNTIME_STATS_ROLLUP_KINDS = (*RUNTIME_STATS_REQUIRED_ROLLUP_KINDS, "repo_profile")
RUNTIME_STATS_STAGE_NAMES = (
    "memory",
    "index",
    "repomap",
    "augment",
    "skills",
    "source_plan",
    "total",
)
RUNTIME_STATS_STATUS_VALUES = ("succeeded", "degraded", "failed")
RUNTIME_STATS_COUNTER_FIELDS = (
    "invocation_count",
    "success_count",
    "degraded_count",
    "failure_count",
    "contract_error_count",
    "plan_replay_hit_count",
    "plan_replay_safe_hit_count",
    "plan_replay_store_count",
    "trace_export_count",
    "trace_export_failure_count",
)
RUNTIME_STATS_LATENCY_AGGREGATE_FIELDS = (
    "latency_ms_sum",
    "latency_ms_min",
    "latency_ms_max",
    "latency_ms_last",
)
RUNTIME_STATS_DEGRADED_REASON_CODES = (
    "memory_fallback",
    "memory_namespace_fallback",
    "candidate_ranker_fallback",
    "plan_replay_invalid_cached_payload",
    "plan_replay_store_failed",
    "embedding_time_budget_exceeded",
    "embedding_fallback",
    "chunk_semantic_time_budget_exceeded",
    "chunk_semantic_fallback",
    "chunk_guard_fallback",
    "parallel_docs_timeout",
    "parallel_worktree_timeout",
    "xref_budget_exhausted",
    "skills_budget_exhausted",
    "router_fallback_applied",
    "plugin_policy_blocked",
    "plugin_policy_warn",
    "contract_error",
    "trace_export_failed",
)

RUNTIME_STATS_INVOCATIONS_TABLE = "runtime_stats_invocations"
RUNTIME_STATS_ROLLUPS_TABLE = "runtime_stats_rollups"
RUNTIME_STATS_STAGE_ROLLUPS_TABLE = "runtime_stats_stage_rollups"
RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE = "runtime_stats_degraded_rollups"


@dataclass(frozen=True, slots=True)
class RuntimeStatsScope:
    kind: str
    scope_key: str
    repo_key: str = ""
    profile_key: str = ""

    def to_payload(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "scope_key": self.scope_key,
            "repo_key": self.repo_key,
            "profile_key": self.profile_key,
        }


@dataclass(frozen=True, slots=True)
class RuntimeStatsTableSpec:
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


def _normalize_stats_key(value: Any, *, max_len: int = 255) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return " ".join(raw.split())[:max_len]


def _repo_profile_scope_key(*, repo_key: str, profile_key: str) -> str:
    return f"{repo_key}::{profile_key}"


def build_runtime_stats_scope_rows(
    *,
    session_id: str,
    repo_key: str,
    profile_key: str | None = None,
) -> tuple[RuntimeStatsScope, ...]:
    normalized_session = _normalize_stats_key(session_id)
    if not normalized_session:
        raise ValueError("session_id must be non-empty")

    normalized_repo = _normalize_stats_key(repo_key)
    normalized_profile = _normalize_stats_key(profile_key)

    scopes = [
        RuntimeStatsScope(kind="session", scope_key=normalized_session),
        RuntimeStatsScope(kind="all_time", scope_key=RUNTIME_STATS_ALL_TIME_SCOPE_KEY),
    ]
    if normalized_repo:
        scopes.append(
            RuntimeStatsScope(
                kind="repo",
                scope_key=normalized_repo,
                repo_key=normalized_repo,
            )
        )
    if normalized_profile:
        scopes.append(
            RuntimeStatsScope(
                kind="profile",
                scope_key=normalized_profile,
                profile_key=normalized_profile,
            )
        )
    if normalized_repo and normalized_profile:
        scopes.append(
            RuntimeStatsScope(
                kind="repo_profile",
                scope_key=_repo_profile_scope_key(
                    repo_key=normalized_repo,
                    profile_key=normalized_profile,
                ),
                repo_key=normalized_repo,
                profile_key=normalized_profile,
            )
        )
    return tuple(scopes)


def _build_table_specs() -> tuple[RuntimeStatsTableSpec, ...]:
    invocations = RuntimeStatsTableSpec(
        name=RUNTIME_STATS_INVOCATIONS_TABLE,
        purpose=(
            "Compact per-invocation fact rows used for idempotent updates, debugging, "
            "and future replayable rollup rebuilds."
        ),
        create_sql=(
            f"CREATE TABLE IF NOT EXISTS {RUNTIME_STATS_INVOCATIONS_TABLE}("
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
        ),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_runtime_stats_invocations_session "
            f"ON {RUNTIME_STATS_INVOCATIONS_TABLE}(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_runtime_stats_invocations_repo_profile "
            f"ON {RUNTIME_STATS_INVOCATIONS_TABLE}(repo_key, profile_key)",
            "CREATE INDEX IF NOT EXISTS idx_runtime_stats_invocations_status "
            f"ON {RUNTIME_STATS_INVOCATIONS_TABLE}(status)",
        ),
        key_fields=("invocation_id", "session_id", "repo_key", "profile_key"),
        measure_fields=(
            "status",
            "contract_error_code",
            "degraded_reason_codes",
            "stage_latency_json",
            "plan_replay_hit",
            "plan_replay_safe_hit",
            "plan_replay_store_written",
            "trace_exported",
            "trace_export_failed",
            "total_latency_ms",
            "started_at",
            "finished_at",
        ),
    )
    rollups = RuntimeStatsTableSpec(
        name=RUNTIME_STATS_ROLLUPS_TABLE,
        purpose=(
            "Hot-path durable counters and total-latency aggregates for session, "
            "all-time, repo, profile, and repo_profile scopes."
        ),
        create_sql=(
            f"CREATE TABLE IF NOT EXISTS {RUNTIME_STATS_ROLLUPS_TABLE}("
            "scope_kind TEXT NOT NULL, "
            "scope_key TEXT NOT NULL, "
            "repo_key TEXT NOT NULL DEFAULT '', "
            "profile_key TEXT NOT NULL DEFAULT '', "
            "invocation_count INTEGER NOT NULL DEFAULT 0, "
            "success_count INTEGER NOT NULL DEFAULT 0, "
            "degraded_count INTEGER NOT NULL DEFAULT 0, "
            "failure_count INTEGER NOT NULL DEFAULT 0, "
            "contract_error_count INTEGER NOT NULL DEFAULT 0, "
            "plan_replay_hit_count INTEGER NOT NULL DEFAULT 0, "
            "plan_replay_safe_hit_count INTEGER NOT NULL DEFAULT 0, "
            "plan_replay_store_count INTEGER NOT NULL DEFAULT 0, "
            "trace_export_count INTEGER NOT NULL DEFAULT 0, "
            "trace_export_failure_count INTEGER NOT NULL DEFAULT 0, "
            "latency_ms_sum REAL NOT NULL DEFAULT 0.0, "
            "latency_ms_min REAL NOT NULL DEFAULT 0.0, "
            "latency_ms_max REAL NOT NULL DEFAULT 0.0, "
            "latency_ms_last REAL NOT NULL DEFAULT 0.0, "
            "updated_at TEXT NOT NULL, "
            "PRIMARY KEY(scope_kind, scope_key))"
        ),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_runtime_stats_rollups_repo_profile "
            f"ON {RUNTIME_STATS_ROLLUPS_TABLE}(repo_key, profile_key)",
        ),
        key_fields=("scope_kind", "scope_key", "repo_key", "profile_key"),
        measure_fields=(
            *RUNTIME_STATS_COUNTER_FIELDS,
            *RUNTIME_STATS_LATENCY_AGGREGATE_FIELDS,
            "updated_at",
        ),
    )
    stage_rollups = RuntimeStatsTableSpec(
        name=RUNTIME_STATS_STAGE_ROLLUPS_TABLE,
        purpose=(
            "Per-stage latency aggregates keyed by the same rollup dimensions so "
            "runtime stats and benchmark summaries share stage names."
        ),
        create_sql=(
            f"CREATE TABLE IF NOT EXISTS {RUNTIME_STATS_STAGE_ROLLUPS_TABLE}("
            "scope_kind TEXT NOT NULL, "
            "scope_key TEXT NOT NULL, "
            "repo_key TEXT NOT NULL DEFAULT '', "
            "profile_key TEXT NOT NULL DEFAULT '', "
            "stage_name TEXT NOT NULL, "
            "invocation_count INTEGER NOT NULL DEFAULT 0, "
            "latency_ms_sum REAL NOT NULL DEFAULT 0.0, "
            "latency_ms_min REAL NOT NULL DEFAULT 0.0, "
            "latency_ms_max REAL NOT NULL DEFAULT 0.0, "
            "latency_ms_last REAL NOT NULL DEFAULT 0.0, "
            "updated_at TEXT NOT NULL, "
            "PRIMARY KEY(scope_kind, scope_key, stage_name))"
        ),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_runtime_stats_stage_rollups_stage "
            f"ON {RUNTIME_STATS_STAGE_ROLLUPS_TABLE}(stage_name)",
            "CREATE INDEX IF NOT EXISTS idx_runtime_stats_stage_rollups_repo_profile "
            f"ON {RUNTIME_STATS_STAGE_ROLLUPS_TABLE}(repo_key, profile_key)",
        ),
        key_fields=(
            "scope_kind",
            "scope_key",
            "repo_key",
            "profile_key",
            "stage_name",
        ),
        measure_fields=("invocation_count", *RUNTIME_STATS_LATENCY_AGGREGATE_FIELDS, "updated_at"),
    )
    degraded_rollups = RuntimeStatsTableSpec(
        name=RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE,
        purpose=(
            "Normalized degraded-state counters so CLI and monthly reviews can "
            "surface top fallback and timeout signatures."
        ),
        create_sql=(
            f"CREATE TABLE IF NOT EXISTS {RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE}("
            "scope_kind TEXT NOT NULL, "
            "scope_key TEXT NOT NULL, "
            "repo_key TEXT NOT NULL DEFAULT '', "
            "profile_key TEXT NOT NULL DEFAULT '', "
            "reason_code TEXT NOT NULL, "
            "event_count INTEGER NOT NULL DEFAULT 0, "
            "last_seen_at TEXT NOT NULL, "
            "PRIMARY KEY(scope_kind, scope_key, reason_code))"
        ),
        indexes=(
            "CREATE INDEX IF NOT EXISTS idx_runtime_stats_degraded_rollups_reason "
            f"ON {RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE}(reason_code)",
            "CREATE INDEX IF NOT EXISTS idx_runtime_stats_degraded_rollups_repo_profile "
            f"ON {RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE}(repo_key, profile_key)",
        ),
        key_fields=(
            "scope_kind",
            "scope_key",
            "repo_key",
            "profile_key",
            "reason_code",
        ),
        measure_fields=("event_count", "last_seen_at"),
    )
    return (invocations, rollups, stage_rollups, degraded_rollups)


RUNTIME_STATS_TABLE_SPECS = _build_table_specs()


def _apply_runtime_stats_schema_v1(conn: Any) -> None:
    for table in RUNTIME_STATS_TABLE_SPECS:
        conn.execute(table.create_sql)
        for index_sql in table.indexes:
            conn.execute(index_sql)


RUNTIME_STATS_MIGRATIONS = (
    RuntimeDbMigration(version=1, apply=_apply_runtime_stats_schema_v1),
)


def build_runtime_stats_migration_bootstrap():
    return build_runtime_db_migration_bootstrap(
        schema_name=RUNTIME_STATS_SCHEMA_NAME,
        migrations=RUNTIME_STATS_MIGRATIONS,
    )


def build_runtime_stats_schema_document() -> dict[str, Any]:
    return {
        "schema_name": RUNTIME_STATS_SCHEMA_NAME,
        "schema_version": RUNTIME_STATS_SCHEMA_VERSION,
        "schema_label": RUNTIME_STATS_SCHEMA_LABEL,
        "required_rollup_kinds": list(RUNTIME_STATS_REQUIRED_ROLLUP_KINDS),
        "rollup_kinds": list(RUNTIME_STATS_ROLLUP_KINDS),
        "stage_names": list(RUNTIME_STATS_STAGE_NAMES),
        "status_values": list(RUNTIME_STATS_STATUS_VALUES),
        "counter_fields": list(RUNTIME_STATS_COUNTER_FIELDS),
        "latency_aggregate_fields": list(RUNTIME_STATS_LATENCY_AGGREGATE_FIELDS),
        "degraded_reason_codes": list(RUNTIME_STATS_DEGRADED_REASON_CODES),
        "tables": [table.to_payload() for table in RUNTIME_STATS_TABLE_SPECS],
        "migration_plan": {
            "schema_name": RUNTIME_STATS_SCHEMA_NAME,
            "initial_version": 1,
            "latest_version": RUNTIME_STATS_SCHEMA_VERSION,
            "strategy": [
                "Additive migrations only for v1 runtime rollout.",
                "Append new counters and degraded reason codes with safe defaults.",
                "Keep raw invocation facts compact so rollups can be rebuilt in-place.",
                "Preserve rollup scope keys across releases to avoid CLI filter drift.",
            ],
        },
    }


__all__ = [
    "RUNTIME_STATS_ALL_TIME_SCOPE_KEY",
    "RUNTIME_STATS_COUNTER_FIELDS",
    "RUNTIME_STATS_DEGRADED_REASON_CODES",
    "RUNTIME_STATS_DEGRADED_ROLLUPS_TABLE",
    "RUNTIME_STATS_INVOCATIONS_TABLE",
    "RUNTIME_STATS_LATENCY_AGGREGATE_FIELDS",
    "RUNTIME_STATS_MIGRATIONS",
    "RUNTIME_STATS_REQUIRED_ROLLUP_KINDS",
    "RUNTIME_STATS_ROLLUPS_TABLE",
    "RUNTIME_STATS_ROLLUP_KINDS",
    "RUNTIME_STATS_SCHEMA_LABEL",
    "RUNTIME_STATS_SCHEMA_NAME",
    "RUNTIME_STATS_SCHEMA_VERSION",
    "RUNTIME_STATS_STAGE_NAMES",
    "RUNTIME_STATS_STAGE_ROLLUPS_TABLE",
    "RUNTIME_STATS_STATUS_VALUES",
    "RUNTIME_STATS_TABLE_SPECS",
    "RuntimeStatsScope",
    "RuntimeStatsTableSpec",
    "build_runtime_stats_migration_bootstrap",
    "build_runtime_stats_schema_document",
    "build_runtime_stats_scope_rows",
]
