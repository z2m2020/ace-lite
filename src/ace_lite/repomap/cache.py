"""Persistent cache helpers for repomap stage payloads."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from time import time
from typing import Any

from ace_lite.token_estimator import normalize_tokenizer_model

_SCHEMA_VERSION = "repomap-cache-v3"
_MAX_ENTRIES = 96
_PRECOMPUTE_SCHEMA_VERSION = "repomap-precompute-cache-v3"
_PRECOMPUTE_MAX_ENTRIES = 32

_REPOMAP_CACHE_MEMORY: dict[tuple[str, str], tuple[int, int, dict[str, Any]]] = {}


def build_repomap_cache_key(
    *,
    index_hash: str,
    worktree_state_hash: str,
    ranking_profile: str,
    signal_weights: dict[str, float] | None,
    top_k: int,
    neighbor_limit: int,
    neighbor_depth: int,
    budget_tokens: int,
    seed_paths: list[str],
    tokenizer_model: str | None,
    content_version: str = "",
    precompute_content_version: str = "",
) -> str:
    payload = {
        "index_hash": str(index_hash or ""),
        "worktree_state_hash": str(worktree_state_hash or ""),
        "ranking_profile": str(ranking_profile or ""),
        "signal_weights": signal_weights or {},
        "top_k": int(top_k),
        "neighbor_limit": int(neighbor_limit),
        "neighbor_depth": int(neighbor_depth),
        "budget_tokens": int(budget_tokens),
        "seed_paths": list(seed_paths),
        "tokenizer_model": normalize_tokenizer_model(tokenizer_model),
        "content_version": str(content_version or ""),
        "precompute_content_version": str(precompute_content_version or ""),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def build_repomap_precompute_key(
    *,
    index_hash: str,
    ranking_profile: str,
    signal_weights: dict[str, float] | None,
    content_version: str = "",
) -> str:
    payload = {
        "index_hash": str(index_hash or ""),
        "ranking_profile": str(ranking_profile or ""),
        "signal_weights": signal_weights or {},
        "content_version": str(content_version or ""),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def load_cached_repomap(*, cache_path: Path, key: str) -> dict[str, Any] | None:
    return _load_cached_payload_entry(
        cache_path=cache_path,
        schema_version=_SCHEMA_VERSION,
        key=key,
        max_age_seconds=0,
        required_meta=None,
    )


def load_cached_repomap_checked(
    *,
    cache_path: Path,
    key: str,
    max_age_seconds: int,
    required_meta: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return _load_cached_payload_entry(
        cache_path=cache_path,
        schema_version=_SCHEMA_VERSION,
        key=key,
        max_age_seconds=max_age_seconds,
        required_meta=required_meta,
    )


def load_cached_repomap_precompute(*, cache_path: Path, key: str) -> dict[str, Any] | None:
    return _load_cached_payload_entry(
        cache_path=cache_path,
        schema_version=_PRECOMPUTE_SCHEMA_VERSION,
        key=key,
        max_age_seconds=0,
        required_meta=None,
    )


def load_cached_repomap_precompute_checked(
    *,
    cache_path: Path,
    key: str,
    max_age_seconds: int,
    required_meta: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return _load_cached_payload_entry(
        cache_path=cache_path,
        schema_version=_PRECOMPUTE_SCHEMA_VERSION,
        key=key,
        max_age_seconds=max_age_seconds,
        required_meta=required_meta,
    )


def _load_cached_payload_entry(
    *,
    cache_path: Path,
    schema_version: str,
    key: str,
    max_age_seconds: int,
    required_meta: dict[str, Any] | None,
) -> dict[str, Any] | None:
    payload = _load_cache_payload(cache_path=cache_path, schema_version=schema_version)
    if payload is None:
        return None
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        return None
    now_epoch = float(time())
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("key") or "") != str(key):
            continue
        if _is_entry_expired(
            entry=entry,
            now_epoch=now_epoch,
            max_age_seconds=max_age_seconds,
        ):
            continue
        if not _entry_meta_matches(entry=entry, required_meta=required_meta):
            continue
        map_payload = entry.get("payload")
        if isinstance(map_payload, dict):
            return dict(map_payload)
    return None


def store_cached_repomap(
    *,
    cache_path: Path,
    key: str,
    payload: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> bool:
    existing = _load_cache_payload(cache_path=cache_path, schema_version=_SCHEMA_VERSION)
    if existing is None:
        existing = {"schema_version": _SCHEMA_VERSION, "entries": []}

    entries = existing.get("entries", [])
    if not isinstance(entries, list):
        entries = []

    normalized_entries: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        if str(item.get("key") or "") == str(key):
            continue
        normalized_entries.append(item)

    normalized_entries.insert(
        0,
        {
            "key": str(key),
            "updated_at_epoch": round(float(time()), 3),
            "meta": _normalize_cache_meta(meta),
            "payload": dict(payload),
        },
    )
    if len(normalized_entries) > _MAX_ENTRIES:
        normalized_entries = normalized_entries[:_MAX_ENTRIES]

    final_payload = {
        "schema_version": _SCHEMA_VERSION,
        "entries": normalized_entries,
    }
    _write_cache_payload(cache_path=cache_path, payload=final_payload)
    return True


def store_cached_repomap_precompute(
    *,
    cache_path: Path,
    key: str,
    payload: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> bool:
    existing = _load_cache_payload(
        cache_path=cache_path,
        schema_version=_PRECOMPUTE_SCHEMA_VERSION,
    )
    if existing is None:
        existing = {"schema_version": _PRECOMPUTE_SCHEMA_VERSION, "entries": []}

    entries = existing.get("entries", [])
    if not isinstance(entries, list):
        entries = []

    normalized_entries: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        if str(item.get("key") or "") == str(key):
            continue
        normalized_entries.append(item)

    normalized_entries.insert(
        0,
        {
            "key": str(key),
            "updated_at_epoch": round(float(time()), 3),
            "meta": _normalize_cache_meta(meta),
            "payload": dict(payload),
        },
    )
    if len(normalized_entries) > _PRECOMPUTE_MAX_ENTRIES:
        normalized_entries = normalized_entries[:_PRECOMPUTE_MAX_ENTRIES]

    final_payload = {
        "schema_version": _PRECOMPUTE_SCHEMA_VERSION,
        "entries": normalized_entries,
    }
    _write_cache_payload(cache_path=cache_path, payload=final_payload)
    return True


def _load_cache_payload(*, cache_path: Path, schema_version: str) -> dict[str, Any] | None:
    try:
        stat = cache_path.stat()
    except OSError:
        return None

    if not cache_path.is_file():
        return None

    cache_key = (str(schema_version), str(cache_path.resolve()))
    cached = _REPOMAP_CACHE_MEMORY.get(cache_key)
    if cached is not None and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]
    try:
        raw = cache_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("schema_version") or "") != str(schema_version):
        return None

    _REPOMAP_CACHE_MEMORY[cache_key] = (stat.st_mtime_ns, stat.st_size, payload)
    return payload


def _write_cache_payload(*, cache_path: Path, payload: dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    try:
        stat = cache_path.stat()
    except OSError:
        _REPOMAP_CACHE_MEMORY.pop((str(payload.get("schema_version", "")), str(cache_path.resolve())), None)
        return

    cache_key = (str(payload.get("schema_version", "")), str(cache_path.resolve()))
    _REPOMAP_CACHE_MEMORY[cache_key] = (stat.st_mtime_ns, stat.st_size, payload)


def _normalize_cache_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(meta, dict):
        return {}
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in meta.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        if isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
            normalized[key] = raw_value
        else:
            normalized[key] = str(raw_value)
    return normalized


def _is_entry_expired(
    *,
    entry: dict[str, Any],
    now_epoch: float,
    max_age_seconds: int,
) -> bool:
    ttl = max(0, int(max_age_seconds or 0))
    if ttl <= 0:
        return False
    try:
        updated_at = float(entry.get("updated_at_epoch", 0.0) or 0.0)
    except Exception:
        return True
    if updated_at <= 0.0:
        return True
    return (now_epoch - updated_at) > float(ttl)


def _entry_meta_matches(
    *,
    entry: dict[str, Any],
    required_meta: dict[str, Any] | None,
) -> bool:
    expected = _normalize_cache_meta(required_meta)
    if not expected:
        return True
    meta_raw = entry.get("meta")
    meta = meta_raw if isinstance(meta_raw, dict) else {}
    for key, value in expected.items():
        if key not in meta:
            return False
        if meta.get(key) != value:
            return False
    return True


__all__ = [
    "build_repomap_cache_key",
    "build_repomap_precompute_key",
    "load_cached_repomap",
    "load_cached_repomap_checked",
    "load_cached_repomap_precompute",
    "load_cached_repomap_precompute_checked",
    "store_cached_repomap",
    "store_cached_repomap_precompute",
]
