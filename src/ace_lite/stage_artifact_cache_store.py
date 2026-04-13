from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from ace_lite.runtime_db import connect_runtime_db
from ace_lite.runtime_db_migrate import RuntimeDbMigration, build_runtime_db_migration_bootstrap
from ace_lite.runtime_paths import resolve_repo_runtime_cache_db_path

STAGE_ARTIFACT_CACHE_SCHEMA_NAME = "stage_artifact_cache"
STAGE_ARTIFACT_CACHE_SCHEMA_VERSION = 1
STAGE_ARTIFACT_CACHE_SCHEMA_LABEL = "ace-lite-stage-artifact-cache-v1"
STAGE_ARTIFACT_CACHE_ENTRIES_TABLE = "stage_artifact_cache_entries"
STAGE_ARTIFACT_CACHE_DEFAULT_PAYLOAD_ROOT = "context-map/runtime-cache/stage-artifacts"
STAGE_ARTIFACT_CACHE_DEFAULT_TEMP_ROOT = "context-map/runtime-cache/stage-artifacts/tmp"
STAGE_ARTIFACT_CACHE_SELECT_ENTRY_SQL = (
    "SELECT * FROM stage_artifact_cache_entries WHERE stage_name = ? AND cache_key = ?"
)
STAGE_ARTIFACT_CACHE_UPSERT_ENTRY_SQL = (
    "INSERT INTO stage_artifact_cache_entries("
    "stage_name, cache_key, query_hash, fingerprint, settings_fingerprint, "
    "payload_relpath, payload_tmp_relpath, payload_sha256, payload_bytes, token_weight, "
    "ttl_seconds, soft_ttl_seconds, created_at, updated_at, last_accessed_at, expires_at, "
    "content_version, policy_name, trust_class, orphaned, orphan_reason"
    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT(stage_name, cache_key) DO UPDATE SET "
    "query_hash = excluded.query_hash, "
    "fingerprint = excluded.fingerprint, "
    "settings_fingerprint = excluded.settings_fingerprint, "
    "payload_relpath = excluded.payload_relpath, "
    "payload_tmp_relpath = excluded.payload_tmp_relpath, "
    "payload_sha256 = excluded.payload_sha256, "
    "payload_bytes = excluded.payload_bytes, "
    "token_weight = excluded.token_weight, "
    "ttl_seconds = excluded.ttl_seconds, "
    "soft_ttl_seconds = excluded.soft_ttl_seconds, "
    "created_at = excluded.created_at, "
    "updated_at = excluded.updated_at, "
    "last_accessed_at = excluded.last_accessed_at, "
    "expires_at = excluded.expires_at, "
    "content_version = excluded.content_version, "
    "policy_name = excluded.policy_name, "
    "trust_class = excluded.trust_class, "
    "orphaned = excluded.orphaned, "
    "orphan_reason = excluded.orphan_reason"
)
STAGE_ARTIFACT_CACHE_TTL_FIELDS = (
    "ttl_seconds",
    "soft_ttl_seconds",
    "expires_at",
    "last_accessed_at",
)
STAGE_ARTIFACT_CACHE_WRITE_ORDER = (
    "write_temp_payload",
    "flush_temp_payload",
    "atomic_rename_payload",
    "commit_metadata",
)
STAGE_ARTIFACT_CACHE_ORPHAN_POLICIES = (
    "Delete temp payloads left behind before metadata commit.",
    "Mark metadata rows with missing payloads as orphaned during verification scans.",
    "Keep ready payloads immutable and only reclaim orphaned payloads through explicit GC.",
)

_STAGE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")
_CACHE_KEY_RE = re.compile(r"[^A-Fa-f0-9]+")


@dataclass(frozen=True, slots=True)
class StageArtifactCacheTableSpec:
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


@dataclass(frozen=True, slots=True)
class StageArtifactCacheEntry:
    stage_name: str
    cache_key: str
    query_hash: str
    fingerprint: str
    settings_fingerprint: str = ""
    payload_relpath: str = ""
    payload_tmp_relpath: str = ""
    payload_sha256: str = ""
    payload_bytes: int = 0
    token_weight: int = 0
    ttl_seconds: int = 0
    soft_ttl_seconds: int = 0
    created_at: str = ""
    updated_at: str = ""
    last_accessed_at: str = ""
    expires_at: str = ""
    content_version: str = ""
    policy_name: str = ""
    trust_class: str = ""
    orphaned: bool = False
    orphan_reason: str = ""

    def to_storage_payload(self) -> dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "cache_key": self.cache_key,
            "query_hash": self.query_hash,
            "fingerprint": self.fingerprint,
            "settings_fingerprint": self.settings_fingerprint,
            "payload_relpath": self.payload_relpath,
            "payload_tmp_relpath": self.payload_tmp_relpath,
            "payload_sha256": self.payload_sha256,
            "payload_bytes": self.payload_bytes,
            "token_weight": self.token_weight,
            "ttl_seconds": self.ttl_seconds,
            "soft_ttl_seconds": self.soft_ttl_seconds,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_accessed_at": self.last_accessed_at,
            "expires_at": self.expires_at,
            "content_version": self.content_version,
            "policy_name": self.policy_name,
            "trust_class": self.trust_class,
            "orphaned": 1 if self.orphaned else 0,
            "orphan_reason": self.orphan_reason,
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_stage_segment(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "artifact"
    normalized = _STAGE_SEGMENT_RE.sub("_", raw).strip("._-")
    return normalized or "artifact"


def _normalize_cache_key(value: Any) -> str:
    raw = _CACHE_KEY_RE.sub("", str(value or "").strip().lower())
    if len(raw) >= 8:
        return raw
    return (raw + "00000000")[:8]


def _normalize_text(value: Any, *, max_len: int = 512) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return " ".join(raw.split())[:max_len]


def _normalize_count(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def normalize_stage_artifact_cache_entry(
    value: StageArtifactCacheEntry | dict[str, Any],
) -> StageArtifactCacheEntry:
    raw = value.to_storage_payload() if isinstance(value, StageArtifactCacheEntry) else dict(value)
    return StageArtifactCacheEntry(
        stage_name=_normalize_stage_segment(raw.get("stage_name")),
        cache_key=_normalize_cache_key(raw.get("cache_key")),
        query_hash=_normalize_cache_key(raw.get("query_hash")),
        fingerprint=_normalize_text(raw.get("fingerprint"), max_len=128),
        settings_fingerprint=_normalize_text(raw.get("settings_fingerprint"), max_len=128),
        payload_relpath=str(PurePosixPath(str(raw.get("payload_relpath") or "").strip()))
        if str(raw.get("payload_relpath") or "").strip()
        else "",
        payload_tmp_relpath=str(PurePosixPath(str(raw.get("payload_tmp_relpath") or "").strip()))
        if str(raw.get("payload_tmp_relpath") or "").strip()
        else "",
        payload_sha256=_normalize_cache_key(raw.get("payload_sha256")),
        payload_bytes=_normalize_count(raw.get("payload_bytes")),
        token_weight=_normalize_count(raw.get("token_weight")),
        ttl_seconds=_normalize_count(raw.get("ttl_seconds")),
        soft_ttl_seconds=_normalize_count(raw.get("soft_ttl_seconds")),
        created_at=_normalize_text(raw.get("created_at"), max_len=64),
        updated_at=_normalize_text(raw.get("updated_at"), max_len=64),
        last_accessed_at=_normalize_text(raw.get("last_accessed_at"), max_len=64),
        expires_at=_normalize_text(raw.get("expires_at"), max_len=64),
        content_version=_normalize_text(raw.get("content_version"), max_len=64),
        policy_name=_normalize_text(raw.get("policy_name"), max_len=64),
        trust_class=_normalize_text(raw.get("trust_class"), max_len=32),
        orphaned=bool(raw.get("orphaned")),
        orphan_reason=_normalize_text(raw.get("orphan_reason"), max_len=128),
    )


def build_stage_artifact_payload_relpath(
    *,
    stage_name: str,
    cache_key: str,
    suffix: str = ".json",
) -> str:
    stage_segment = _normalize_stage_segment(stage_name)
    key = _normalize_cache_key(cache_key)
    extension = str(suffix or ".json").strip() or ".json"
    if not extension.startswith("."):
        extension = f".{extension}"
    return PurePosixPath(stage_segment, key[:2], f"{key}{extension}").as_posix()


def build_stage_artifact_temp_relpath(
    *,
    stage_name: str,
    cache_key: str,
    write_token: str,
    suffix: str = ".json.tmp",
) -> str:
    stage_segment = _normalize_stage_segment(stage_name)
    key = _normalize_cache_key(cache_key)
    token = _normalize_stage_segment(write_token)
    extension = str(suffix or ".json.tmp").strip() or ".json.tmp"
    if not extension.startswith("."):
        extension = f".{extension}"
    return PurePosixPath(stage_segment, key[:2], f"{key}.{token}{extension}").as_posix()


def resolve_stage_artifact_payload_root(
    *,
    root_path: str | Path,
    configured_path: str | Path | None = None,
) -> Path:
    base = Path(root_path)
    candidate = Path(configured_path or STAGE_ARTIFACT_CACHE_DEFAULT_PAYLOAD_ROOT)
    if candidate.is_absolute():
        return candidate
    return base / candidate


def resolve_stage_artifact_temp_root(
    *,
    root_path: str | Path,
    configured_path: str | Path | None = None,
) -> Path:
    base = Path(root_path)
    candidate = Path(configured_path or STAGE_ARTIFACT_CACHE_DEFAULT_TEMP_ROOT)
    if candidate.is_absolute():
        return candidate
    return base / candidate


def _build_table_specs() -> tuple[StageArtifactCacheTableSpec, ...]:
    return (
        StageArtifactCacheTableSpec(
            name=STAGE_ARTIFACT_CACHE_ENTRIES_TABLE,
            purpose=(
                "Repo-local metadata rows for immutable stage artifact payloads, "
                "tracking identity, payload location, token weight, TTL, and orphan state."
            ),
            create_sql=(
                f"CREATE TABLE IF NOT EXISTS {STAGE_ARTIFACT_CACHE_ENTRIES_TABLE}("
                "stage_name TEXT NOT NULL, "
                "cache_key TEXT NOT NULL, "
                "query_hash TEXT NOT NULL, "
                "fingerprint TEXT NOT NULL, "
                "settings_fingerprint TEXT NOT NULL DEFAULT '', "
                "payload_relpath TEXT NOT NULL, "
                "payload_tmp_relpath TEXT NOT NULL DEFAULT '', "
                "payload_sha256 TEXT NOT NULL DEFAULT '', "
                "payload_bytes INTEGER NOT NULL DEFAULT 0, "
                "token_weight INTEGER NOT NULL DEFAULT 0, "
                "ttl_seconds INTEGER NOT NULL DEFAULT 0, "
                "soft_ttl_seconds INTEGER NOT NULL DEFAULT 0, "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "last_accessed_at TEXT NOT NULL, "
                "expires_at TEXT NOT NULL DEFAULT '', "
                "content_version TEXT NOT NULL DEFAULT '', "
                "policy_name TEXT NOT NULL DEFAULT '', "
                "trust_class TEXT NOT NULL DEFAULT '', "
                "orphaned INTEGER NOT NULL DEFAULT 0, "
                "orphan_reason TEXT NOT NULL DEFAULT '', "
                "PRIMARY KEY(stage_name, cache_key))"
            ),
            indexes=(
                "CREATE INDEX IF NOT EXISTS idx_stage_artifact_cache_query "
                f"ON {STAGE_ARTIFACT_CACHE_ENTRIES_TABLE}(stage_name, query_hash)",
                "CREATE INDEX IF NOT EXISTS idx_stage_artifact_cache_fingerprint "
                f"ON {STAGE_ARTIFACT_CACHE_ENTRIES_TABLE}(stage_name, fingerprint, settings_fingerprint)",
                "CREATE INDEX IF NOT EXISTS idx_stage_artifact_cache_expiry "
                f"ON {STAGE_ARTIFACT_CACHE_ENTRIES_TABLE}(expires_at, orphaned)",
                "CREATE INDEX IF NOT EXISTS idx_stage_artifact_cache_access "
                f"ON {STAGE_ARTIFACT_CACHE_ENTRIES_TABLE}(last_accessed_at)",
            ),
            key_fields=(
                "stage_name",
                "cache_key",
                "query_hash",
                "fingerprint",
                "settings_fingerprint",
            ),
            measure_fields=(
                "payload_relpath",
                "payload_tmp_relpath",
                "payload_sha256",
                "payload_bytes",
                "token_weight",
                *STAGE_ARTIFACT_CACHE_TTL_FIELDS,
                "content_version",
                "policy_name",
                "trust_class",
                "orphaned",
                "orphan_reason",
            ),
        ),
    )


STAGE_ARTIFACT_CACHE_TABLE_SPECS = _build_table_specs()


def _apply_stage_artifact_cache_schema_v1(conn: Any) -> None:
    for table in STAGE_ARTIFACT_CACHE_TABLE_SPECS:
        conn.execute(table.create_sql)
        for index_sql in table.indexes:
            conn.execute(index_sql)


STAGE_ARTIFACT_CACHE_MIGRATIONS = (
    RuntimeDbMigration(version=1, apply=_apply_stage_artifact_cache_schema_v1),
)


def build_stage_artifact_cache_migration_bootstrap():
    return build_runtime_db_migration_bootstrap(
        schema_name=STAGE_ARTIFACT_CACHE_SCHEMA_NAME,
        migrations=STAGE_ARTIFACT_CACHE_MIGRATIONS,
    )


def build_stage_artifact_cache_schema_document() -> dict[str, Any]:
    example_key = "abcdef0123456789"
    example_writer = "writer_example"
    return {
        "schema_name": STAGE_ARTIFACT_CACHE_SCHEMA_NAME,
        "schema_version": STAGE_ARTIFACT_CACHE_SCHEMA_VERSION,
        "schema_label": STAGE_ARTIFACT_CACHE_SCHEMA_LABEL,
        "payload_root": STAGE_ARTIFACT_CACHE_DEFAULT_PAYLOAD_ROOT,
        "temp_root": STAGE_ARTIFACT_CACHE_DEFAULT_TEMP_ROOT,
        "ttl_fields": list(STAGE_ARTIFACT_CACHE_TTL_FIELDS),
        "write_order": list(STAGE_ARTIFACT_CACHE_WRITE_ORDER),
        "orphan_policy": list(STAGE_ARTIFACT_CACHE_ORPHAN_POLICIES),
        "tables": [table.to_payload() for table in STAGE_ARTIFACT_CACHE_TABLE_SPECS],
        "path_examples": {
            "payload_relpath": build_stage_artifact_payload_relpath(
                stage_name="source_plan",
                cache_key=example_key,
            ),
            "temp_relpath": build_stage_artifact_temp_relpath(
                stage_name="source_plan",
                cache_key=example_key,
                write_token=example_writer,
            ),
        },
        "migration_plan": {
            "schema_name": STAGE_ARTIFACT_CACHE_SCHEMA_NAME,
            "initial_version": 1,
            "latest_version": STAGE_ARTIFACT_CACHE_SCHEMA_VERSION,
            "strategy": [
                "Keep payload files immutable once metadata is committed.",
                "Use additive schema changes for future cache policy versions.",
                "Preserve payload path conventions so GC can reason about orphans deterministically.",
            ],
        },
    }


class StageArtifactCacheStore:
    def __init__(
        self,
        *,
        repo_root: str | Path,
        db_path: str | Path | None = None,
        configured_db_path: str | Path | None = None,
    ) -> None:
        self._repo_root = Path(repo_root).resolve()
        self._db_path = (
            Path(db_path).resolve()
            if db_path is not None
            else Path(
                resolve_repo_runtime_cache_db_path(
                    root_path=str(self._repo_root),
                    configured_path=configured_db_path,
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
            migration_bootstrap=build_stage_artifact_cache_migration_bootstrap(),
        )

    def load_entry(self, *, stage_name: str, cache_key: str) -> StageArtifactCacheEntry | None:
        conn = self._connect()
        try:
            row = conn.execute(
                STAGE_ARTIFACT_CACHE_SELECT_ENTRY_SQL,
                (_normalize_stage_segment(stage_name), _normalize_cache_key(cache_key)),
            ).fetchone()
            if row is None:
                return None
            return normalize_stage_artifact_cache_entry(dict(row))
        finally:
            conn.close()

    def upsert_entry(
        self,
        entry: StageArtifactCacheEntry | dict[str, Any],
    ) -> StageArtifactCacheEntry:
        normalized = normalize_stage_artifact_cache_entry(entry)
        payload = normalized.to_storage_payload()
        now = _utc_now_iso()
        if not payload["created_at"]:
            payload["created_at"] = now
        if not payload["updated_at"]:
            payload["updated_at"] = now
        if not payload["last_accessed_at"]:
            payload["last_accessed_at"] = payload["updated_at"]

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                STAGE_ARTIFACT_CACHE_UPSERT_ENTRY_SQL,
                (
                    payload["stage_name"],
                    payload["cache_key"],
                    payload["query_hash"],
                    payload["fingerprint"],
                    payload["settings_fingerprint"],
                    payload["payload_relpath"],
                    payload["payload_tmp_relpath"],
                    payload["payload_sha256"],
                    payload["payload_bytes"],
                    payload["token_weight"],
                    payload["ttl_seconds"],
                    payload["soft_ttl_seconds"],
                    payload["created_at"],
                    payload["updated_at"],
                    payload["last_accessed_at"],
                    payload["expires_at"],
                    payload["content_version"],
                    payload["policy_name"],
                    payload["trust_class"],
                    payload["orphaned"],
                    payload["orphan_reason"],
                ),
            )
            conn.execute("COMMIT")
            return normalize_stage_artifact_cache_entry(payload)
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()


__all__ = [
    "STAGE_ARTIFACT_CACHE_DEFAULT_PAYLOAD_ROOT",
    "STAGE_ARTIFACT_CACHE_DEFAULT_TEMP_ROOT",
    "STAGE_ARTIFACT_CACHE_ENTRIES_TABLE",
    "STAGE_ARTIFACT_CACHE_MIGRATIONS",
    "STAGE_ARTIFACT_CACHE_ORPHAN_POLICIES",
    "STAGE_ARTIFACT_CACHE_SCHEMA_LABEL",
    "STAGE_ARTIFACT_CACHE_SCHEMA_NAME",
    "STAGE_ARTIFACT_CACHE_SCHEMA_VERSION",
    "STAGE_ARTIFACT_CACHE_SELECT_ENTRY_SQL",
    "STAGE_ARTIFACT_CACHE_TABLE_SPECS",
    "STAGE_ARTIFACT_CACHE_TTL_FIELDS",
    "STAGE_ARTIFACT_CACHE_UPSERT_ENTRY_SQL",
    "STAGE_ARTIFACT_CACHE_WRITE_ORDER",
    "StageArtifactCacheEntry",
    "StageArtifactCacheStore",
    "StageArtifactCacheTableSpec",
    "build_stage_artifact_cache_migration_bootstrap",
    "build_stage_artifact_cache_schema_document",
    "build_stage_artifact_payload_relpath",
    "build_stage_artifact_temp_relpath",
    "normalize_stage_artifact_cache_entry",
    "resolve_stage_artifact_payload_root",
    "resolve_stage_artifact_temp_root",
]
