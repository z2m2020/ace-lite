"""Persistent exact replay cache helpers for orchestrator plan payloads."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from time import time
from typing import Any

from ace_lite.stage_artifact_cache import StageArtifactCache

_SCHEMA_VERSION = "plan-replay-cache-v1"
_CONTENT_VERSION = "plan-replay-v1"
_MAX_ENTRIES = 64

_PLAN_REPLAY_CACHE_MEMORY: dict[tuple[str, str], tuple[int, int, dict[str, Any]]] = {}


def normalize_plan_query(query: str) -> str:
    return " ".join(str(query or "").split())


def build_repo_root_fingerprint(*, repo: str, root: str) -> str:
    payload = {
        "repo": str(repo or "").strip(),
        "root": str(Path(root).resolve()),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def build_plan_component_fingerprint(
    payload: dict[str, Any] | None,
    *,
    exclude_keys: set[str] | None = None,
) -> str:
    normalized = _normalize_for_fingerprint(payload or {}, exclude_keys=exclude_keys or set())
    text = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def build_plan_replay_cache_key(
    *,
    normalized_query: str,
    repo_root_fingerprint: str,
    temporal_input: dict[str, Any],
    plugins_loaded: list[str],
    conventions_hashes: dict[str, str],
    memory_fingerprint: str,
    index_fingerprint: str,
    index_hash: str,
    worktree_state_hash: str,
    retrieval_policy: str,
    policy_version: str,
    candidate_ranker: str,
    budget_knobs: dict[str, Any],
    upstream_fingerprints: dict[str, str] | None = None,
    content_version: str = _CONTENT_VERSION,
) -> str:
    payload = {
        "normalized_query": str(normalized_query or ""),
        "repo_root_fingerprint": str(repo_root_fingerprint or ""),
        "temporal_input": _normalize_for_fingerprint(temporal_input or {}, exclude_keys=set()),
        "plugins_loaded": sorted(str(item) for item in plugins_loaded if str(item).strip()),
        "conventions_hashes": _normalize_for_fingerprint(
            conventions_hashes or {},
            exclude_keys=set(),
        ),
        "memory_fingerprint": str(memory_fingerprint or ""),
        "index_fingerprint": str(index_fingerprint or ""),
        "index_hash": str(index_hash or ""),
        "worktree_state_hash": str(worktree_state_hash or ""),
        "retrieval_policy": str(retrieval_policy or ""),
        "policy_version": str(policy_version or ""),
        "candidate_ranker": str(candidate_ranker or ""),
        "budget_knobs": _normalize_for_fingerprint(budget_knobs or {}, exclude_keys=set()),
        "upstream_fingerprints": _normalize_for_fingerprint(
            upstream_fingerprints or {},
            exclude_keys=set(),
        ),
        "content_version": str(content_version or _CONTENT_VERSION),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def load_cached_plan(*, cache_path: Path, key: str) -> dict[str, Any] | None:
    manager = _build_stage_artifact_cache(cache_path=cache_path)
    cached = manager.get_artifact(stage_name="source_plan", cache_key=key)
    if cached is not None:
        return copy.deepcopy(cached.payload)

    payload = _load_cache_payload(cache_path=cache_path, schema_version=_SCHEMA_VERSION)
    if payload is None:
        return None
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("key") or "") != str(key):
            continue
        cached_payload = entry.get("payload")
        if isinstance(cached_payload, dict):
            return copy.deepcopy(cached_payload)
    return None


def store_cached_plan(
    *,
    cache_path: Path,
    key: str,
    payload: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> bool:
    normalized_meta = _normalize_cache_meta(meta)
    manager = _build_stage_artifact_cache(cache_path=cache_path)
    try:
        manager.put_artifact(
            stage_name=str(normalized_meta.get("stage") or "source_plan"),
            cache_key=key,
            query_hash=_build_query_hash(str(normalized_meta.get("query") or "")),
            fingerprint=str(key),
            settings_fingerprint=str(normalized_meta.get("settings_fingerprint") or ""),
            payload=copy.deepcopy(payload),
            token_weight=_estimate_payload_token_weight(payload),
            ttl_seconds=max(0, int(normalized_meta.get("ttl_seconds") or 0)),
            soft_ttl_seconds=max(0, int(normalized_meta.get("soft_ttl_seconds") or 0)),
            content_version=_CONTENT_VERSION,
            policy_name=str(normalized_meta.get("stage") or "source_plan"),
            trust_class=str(normalized_meta.get("trust_class") or "exact"),
            write_token="plan_replay",
        )
        _write_cache_payload(
            cache_path=cache_path,
            payload={
                "schema_version": _SCHEMA_VERSION,
                "backend": "stage_artifact_cache",
                "updated_at_epoch": round(float(time()), 3),
                "last_key": str(key),
                "meta": normalized_meta,
            },
        )
        return True
    except Exception:
        pass

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
            "payload": copy.deepcopy(payload),
        },
    )
    if len(normalized_entries) > _MAX_ENTRIES:
        normalized_entries = normalized_entries[:_MAX_ENTRIES]

    _write_cache_payload(
        cache_path=cache_path,
        payload={
            "schema_version": _SCHEMA_VERSION,
            "entries": normalized_entries,
        },
    )
    return True


def strip_plan_replay_runtime_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    cloned = copy.deepcopy(payload)
    observability = cloned.get("observability")
    if isinstance(observability, dict):
        observability.pop("plan_replay_cache", None)
    return cloned


def default_plan_replay_cache_path(*, root: str) -> Path:
    return Path(root) / "context-map" / "plan-replay" / "cache.json"


def content_version() -> str:
    return _CONTENT_VERSION


def _build_stage_artifact_cache(*, cache_path: Path) -> StageArtifactCache:
    anchor = Path(cache_path).resolve()
    payload_root = anchor.parent / "artifacts"
    temp_root = payload_root / "tmp"
    db_path = anchor.parent / "stage-artifact-cache.db"
    return StageArtifactCache(
        repo_root=anchor.parent,
        db_path=db_path,
        payload_root=payload_root,
        temp_root=temp_root,
    )


def _build_query_hash(query: str) -> str:
    normalized = normalize_plan_query(query)
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8", "ignore")).hexdigest()


def _estimate_payload_token_weight(payload: dict[str, Any]) -> int:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return max(1, len(text) // 4)


def _load_cache_payload(*, cache_path: Path, schema_version: str) -> dict[str, Any] | None:
    try:
        stat = cache_path.stat()
    except OSError:
        return None

    if not cache_path.is_file():
        return None

    cache_key = (str(schema_version), str(cache_path.resolve()))
    cached = _PLAN_REPLAY_CACHE_MEMORY.get(cache_key)
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
    if str(payload.get("backend") or "").strip() == "stage_artifact_cache":
        return None

    _PLAN_REPLAY_CACHE_MEMORY[cache_key] = (stat.st_mtime_ns, stat.st_size, payload)
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
        _PLAN_REPLAY_CACHE_MEMORY.pop(
            (str(payload.get("schema_version", "")), str(cache_path.resolve())),
            None,
        )
        return

    cache_key = (str(payload.get("schema_version", "")), str(cache_path.resolve()))
    _PLAN_REPLAY_CACHE_MEMORY[cache_key] = (stat.st_mtime_ns, stat.st_size, payload)


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


def _normalize_for_fingerprint(value: Any, *, exclude_keys: set[str]) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for raw_key in sorted(value.keys(), key=lambda item: str(item)):
            key = str(raw_key)
            if key in exclude_keys:
                continue
            normalized[key] = _normalize_for_fingerprint(
                value.get(raw_key),
                exclude_keys=exclude_keys,
            )
        return normalized
    if isinstance(value, list):
        return [
            _normalize_for_fingerprint(item, exclude_keys=exclude_keys) for item in value
        ]
    if isinstance(value, tuple):
        return [
            _normalize_for_fingerprint(item, exclude_keys=exclude_keys) for item in value
        ]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


__all__ = [
    "build_plan_component_fingerprint",
    "build_plan_replay_cache_key",
    "build_repo_root_fingerprint",
    "content_version",
    "default_plan_replay_cache_path",
    "load_cached_plan",
    "normalize_plan_query",
    "store_cached_plan",
    "strip_plan_replay_runtime_metadata",
]
