from __future__ import annotations

import hashlib
import json
import os
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import Any, Callable, cast

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
from ace_lite.token_estimator import estimate_payload_tokens, normalize_tokenizer_model

WriteStepRecorder = Callable[[str], None]
_HOT_TIER_DEFAULT_MAX_ENTRIES = 32
_HOT_TIER_DEFAULT_MAX_TOKENS = 16_384
_HOT_TIER_REGISTRY: dict[tuple[str, str, int, int, str], "_StageArtifactHotTier"] = {}
_HOT_TIER_REGISTRY_LOCK = Lock()


@dataclass(frozen=True, slots=True)
class StageArtifactCacheHit:
    entry: StageArtifactCacheEntry
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _StageArtifactHotEntry:
    stage_name: str
    cache_key: str
    payload: dict[str, Any]
    token_weight: int


class _StageArtifactHotTier:
    def __init__(self, *, max_entries: int, max_tokens: int) -> None:
        self._max_entries = max(0, int(max_entries))
        self._max_tokens = max(0, int(max_tokens))
        self._entries: OrderedDict[tuple[str, str], _StageArtifactHotEntry] = OrderedDict()
        self._token_total = 0
        self._lock = Lock()

    def get(self, *, stage_name: str, cache_key: str) -> dict[str, Any] | None:
        key = (str(stage_name), str(cache_key))
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            self._entries.move_to_end(key)
            return cast(
                dict[str, Any],
                json.loads(json.dumps(entry.payload, ensure_ascii=False)),
            )

    def put(
        self,
        *,
        stage_name: str,
        cache_key: str,
        payload: dict[str, Any],
        token_weight: int,
    ) -> None:
        key = (str(stage_name), str(cache_key))
        normalized_weight = max(1, int(token_weight))
        with self._lock:
            existing = self._entries.pop(key, None)
            if existing is not None:
                self._token_total = max(
                    0,
                    self._token_total - max(1, int(existing.token_weight)),
                )

            if self._max_entries <= 0 or self._max_tokens <= 0:
                return
            if normalized_weight > self._max_tokens:
                return

            self._entries[key] = _StageArtifactHotEntry(
                stage_name=str(stage_name),
                cache_key=str(cache_key),
                payload=json.loads(json.dumps(payload, ensure_ascii=False)),
                token_weight=normalized_weight,
            )
            self._token_total += normalized_weight
            self._evict_locked()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "max_entries": int(self._max_entries),
                "max_tokens": int(self._max_tokens),
                "entry_count": len(self._entries),
                "token_total": int(self._token_total),
                "entries": [
                    {
                        "stage_name": entry.stage_name,
                        "cache_key": entry.cache_key,
                        "token_weight": int(entry.token_weight),
                    }
                    for entry in self._entries.values()
                ],
            }

    def _evict_locked(self) -> None:
        while (
            len(self._entries) > self._max_entries
            or self._token_total > self._max_tokens
        ):
            _key, entry = self._entries.popitem(last=False)
            self._token_total = max(
                0,
                self._token_total - max(1, int(entry.token_weight)),
            )


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


def _hot_tier_namespace_key(
    *,
    repo_root: Path,
    payload_root: Path,
    max_entries: int,
    max_tokens: int,
    tokenizer_model: str,
) -> tuple[str, str, int, int, str]:
    return (
        str(repo_root.resolve()),
        str(payload_root.resolve()),
        max(0, int(max_entries)),
        max(0, int(max_tokens)),
        normalize_tokenizer_model(tokenizer_model),
    )


def _get_or_create_hot_tier(
    *,
    repo_root: Path,
    payload_root: Path,
    max_entries: int,
    max_tokens: int,
    tokenizer_model: str,
) -> _StageArtifactHotTier:
    key = _hot_tier_namespace_key(
        repo_root=repo_root,
        payload_root=payload_root,
        max_entries=max_entries,
        max_tokens=max_tokens,
        tokenizer_model=tokenizer_model,
    )
    with _HOT_TIER_REGISTRY_LOCK:
        existing = _HOT_TIER_REGISTRY.get(key)
        if existing is not None:
            return existing
        created = _StageArtifactHotTier(
            max_entries=max_entries,
            max_tokens=max_tokens,
        )
        _HOT_TIER_REGISTRY[key] = created
        return created


class StageArtifactCache:
    def __init__(
        self,
        *,
        repo_root: str | Path,
        db_path: str | Path | None = None,
        configured_db_path: str | Path | None = None,
        payload_root: str | Path | None = None,
        temp_root: str | Path | None = None,
        hot_max_entries: int = _HOT_TIER_DEFAULT_MAX_ENTRIES,
        hot_max_tokens: int = _HOT_TIER_DEFAULT_MAX_TOKENS,
        hot_tokenizer_model: str | None = None,
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
        self._hot_tokenizer_model = normalize_tokenizer_model(hot_tokenizer_model)
        self._hot_tier = _get_or_create_hot_tier(
            repo_root=self._repo_root,
            payload_root=self._payload_root,
            max_entries=max(0, int(hot_max_entries)),
            max_tokens=max(0, int(hot_max_tokens)),
            tokenizer_model=self._hot_tokenizer_model,
        )
        self._write_step_recorder = write_step_recorder

    @property
    def store(self) -> StageArtifactCacheStore:
        return self._store

    @property
    def payload_root(self) -> Path:
        return Path(self._payload_root)

    @property
    def temp_root(self) -> Path:
        return Path(self._temp_root)

    def hot_tier_snapshot(self) -> dict[str, Any]:
        return self._hot_tier.snapshot()

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
        explicit_token_weight = max(0, int(token_weight))
        effective_token_weight = max(
            1,
            explicit_token_weight
            if explicit_token_weight > 0
            else estimate_payload_tokens(
                payload,
                model=self._hot_tokenizer_model,
            ),
        )
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
                token_weight=effective_token_weight,
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
        committed = self._store.upsert_entry(entry)
        self._hot_tier.put(
            stage_name=committed.stage_name,
            cache_key=committed.cache_key,
            payload=payload,
            token_weight=committed.token_weight,
        )
        return committed

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

        hot_payload = self._hot_tier.get(
            stage_name=entry.stage_name,
            cache_key=entry.cache_key,
        )
        if hot_payload is not None:
            refreshed = replace(
                entry,
                last_accessed_at=now.isoformat(),
                updated_at=entry.updated_at,
            )
            self._store.upsert_entry(refreshed)
            return StageArtifactCacheHit(entry=refreshed, payload=hot_payload)

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
        self._hot_tier.put(
            stage_name=refreshed.stage_name,
            cache_key=refreshed.cache_key,
            payload=payload,
            token_weight=refreshed.token_weight,
        )
        return StageArtifactCacheHit(entry=refreshed, payload=payload)

    def cleanup_temp_payloads(self) -> int:
        if not self._temp_root.exists():
            return 0

        deleted = 0
        for path in sorted(self._temp_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
                deleted += 1
                continue
            if path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        return deleted

    def _record_step(self, step: str) -> None:
        if step not in STAGE_ARTIFACT_CACHE_WRITE_ORDER:
            return
        if self._write_step_recorder is not None:
            self._write_step_recorder(step)


__all__ = ["StageArtifactCache", "StageArtifactCacheHit"]
