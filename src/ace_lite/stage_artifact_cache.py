from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any
from typing import Callable

from ace_lite.stage_artifact_cache_store import (
    STAGE_ARTIFACT_CACHE_WRITE_ORDER,
    StageArtifactCacheEntry,
    StageArtifactCacheStore,
    build_stage_artifact_payload_relpath,
    build_stage_artifact_temp_relpath,
    normalize_stage_artifact_cache_entry,
    resolve_stage_artifact_payload_root,
    resolve_stage_artifact_temp_root,
)


WriteStepRecorder = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class StageArtifactCacheHit:
    entry: StageArtifactCacheEntry
    payload: dict[str, Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _coerce_relpath(value: str) -> Path:
    pure = PurePosixPath(str(value or "").strip())
    return Path(*pure.parts) if pure.parts else Path()


def _serialize_payload(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8", "ignore")


def _load_payload(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_bytes_with_flush(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _expires_at_iso(*, now: datetime, ttl_seconds: int) -> str:
    ttl = max(0, int(ttl_seconds))
    if ttl <= 0:
        return ""
    return (now + timedelta(seconds=ttl)).isoformat()


def _is_expired(expires_at: str, *, now: datetime) -> bool:
    text = str(expires_at or "").strip()
    if not text:
        return False
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= now


class StageArtifactCache:
    def __init__(
        self,
        *,
        repo_root: str | Path,
        db_path: str | Path | None = None,
        configured_db_path: str | Path | None = None,
        payload_root: str | Path | None = None,
        temp_root: str | Path | None = None,
        write_step_recorder: WriteStepRecorder | None = None,
    ) -> None:
        self._repo_root = Path(repo_root).resolve()
        self._store = StageArtifactCacheStore(
            repo_root=self._repo_root,
            db_path=db_path,
            configured_db_path=configured_db_path,
        )
        self._payload_root = resolve_stage_artifact_payload_root(
            root_path=self._repo_root,
            configured_path=payload_root,
        )
        self._temp_root = resolve_stage_artifact_temp_root(
            root_path=self._repo_root,
            configured_path=temp_root,
        )
        self._write_step_recorder = write_step_recorder

    @property
    def store(self) -> StageArtifactCacheStore:
        return self._store

    @property
    def payload_root(self) -> Path:
        return self._payload_root

    @property
    def temp_root(self) -> Path:
        return self._temp_root

    def put_artifact(
        self,
        *,
        stage_name: str,
        cache_key: str,
        query_hash: str,
        fingerprint: str,
        settings_fingerprint: str = "",
        payload: dict[str, Any],
        token_weight: int = 0,
        ttl_seconds: int = 0,
        soft_ttl_seconds: int = 0,
        content_version: str = "",
        policy_name: str = "",
        trust_class: str = "",
        write_token: str = "writer",
    ) -> StageArtifactCacheEntry:
        existing = self._store.load_entry(stage_name=stage_name, cache_key=cache_key)
        if existing is not None:
            payload_path = self._payload_root / _coerce_relpath(existing.payload_relpath)
            if payload_path.is_file() and not existing.orphaned:
                return existing

        now = _utc_now()
        now_iso = now.isoformat()
        payload_bytes = _serialize_payload(payload)
        payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
        payload_relpath = build_stage_artifact_payload_relpath(
            stage_name=stage_name,
            cache_key=cache_key,
        )
        temp_relpath = build_stage_artifact_temp_relpath(
            stage_name=stage_name,
            cache_key=cache_key,
            write_token=write_token,
        )
        temp_path = self._temp_root / _coerce_relpath(temp_relpath)
        payload_path = self._payload_root / _coerce_relpath(payload_relpath)

        self._record_step("write_temp_payload")
        _write_bytes_with_flush(temp_path, payload_bytes)
        self._record_step("flush_temp_payload")
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        self._record_step("atomic_rename_payload")
        os.replace(temp_path, payload_path)

        entry = normalize_stage_artifact_cache_entry(
            StageArtifactCacheEntry(
                stage_name=stage_name,
                cache_key=cache_key,
                query_hash=query_hash,
                fingerprint=fingerprint,
                settings_fingerprint=settings_fingerprint,
                payload_relpath=payload_relpath,
                payload_tmp_relpath=temp_relpath,
                payload_sha256=payload_sha256,
                payload_bytes=len(payload_bytes),
                token_weight=token_weight,
                ttl_seconds=ttl_seconds,
                soft_ttl_seconds=soft_ttl_seconds,
                created_at=existing.created_at if existing is not None else now_iso,
                updated_at=now_iso,
                last_accessed_at=now_iso,
                expires_at=_expires_at_iso(now=now, ttl_seconds=ttl_seconds),
                content_version=content_version,
                policy_name=policy_name,
                trust_class=trust_class,
                orphaned=False,
                orphan_reason="",
            )
        )
        self._record_step("commit_metadata")
        return self._store.upsert_entry(entry)

    def get_artifact(
        self,
        *,
        stage_name: str,
        cache_key: str,
    ) -> StageArtifactCacheHit | None:
        entry = self._store.load_entry(stage_name=stage_name, cache_key=cache_key)
        if entry is None or entry.orphaned:
            return None

        now = _utc_now()
        if _is_expired(entry.expires_at, now=now):
            return None

        payload_path = self._payload_root / _coerce_relpath(entry.payload_relpath)
        if not payload_path.is_file():
            orphaned = replace(
                entry,
                updated_at=now.isoformat(),
                last_accessed_at=now.isoformat(),
                orphaned=True,
                orphan_reason="missing_payload",
            )
            self._store.upsert_entry(orphaned)
            return None

        payload = _load_payload(payload_path)
        if payload is None:
            orphaned = replace(
                entry,
                updated_at=now.isoformat(),
                last_accessed_at=now.isoformat(),
                orphaned=True,
                orphan_reason="invalid_payload",
            )
            self._store.upsert_entry(orphaned)
            return None

        refreshed = replace(
            entry,
            last_accessed_at=now.isoformat(),
            updated_at=entry.updated_at,
        )
        self._store.upsert_entry(refreshed)
        return StageArtifactCacheHit(entry=refreshed, payload=payload)

    def _record_step(self, step: str) -> None:
        if step not in STAGE_ARTIFACT_CACHE_WRITE_ORDER:
            return
        if self._write_step_recorder is not None:
            self._write_step_recorder(step)


__all__ = ["StageArtifactCache", "StageArtifactCacheHit"]
