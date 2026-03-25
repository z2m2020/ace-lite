"""Persistent cache helpers for index candidate stage payloads."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from time import time
from typing import Any

from ace_lite.stage_artifact_cache import StageArtifactCache

_SCHEMA_VERSION = "index-candidate-cache-v1"
_MAX_ENTRIES = 96
_STAGE_NAME = "index_candidates"

_INDEX_CANDIDATE_ARTIFACT_MEMORY: dict[
    tuple[str, str, str], tuple[int, int, dict[str, Any]]
] = {}


def default_index_candidate_cache_path(*, root: str) -> Path:
    return Path(root) / "context-map" / "index_candidates" / "cache.json"


def build_index_candidate_cache_key(
    *,
    query: str,
    terms: list[str],
    memory_paths: list[str],
    index_hash: str,
    policy: dict[str, Any],
    requested_ranker: str,
    top_k_files: int,
    min_candidate_score: int,
    candidate_relative_threshold: float,
    chunk_top_k: int,
    chunk_per_file_limit: int,
    chunk_token_budget: int,
    chunk_disclosure: str,
    exact_search_enabled: bool,
    deterministic_refine_enabled: bool,
    embedding_enabled: bool,
    embedding_provider: str,
    embedding_model: str,
    embedding_dimension: int,
    feedback_enabled: bool,
    multi_channel_rrf_enabled: bool,
    chunk_guard_mode: str,
    topological_shield_mode: str,
    settings_payload: dict[str, Any] | None = None,
    content_version: str = "",
) -> str:
    payload = {
        "query": str(query or "").strip(),
        "terms": list(terms),
        "memory_paths": list(memory_paths),
        "index_hash": str(index_hash or ""),
        "policy": policy if isinstance(policy, dict) else {},
        "requested_ranker": str(requested_ranker or ""),
        "top_k_files": int(top_k_files),
        "min_candidate_score": int(min_candidate_score),
        "candidate_relative_threshold": float(candidate_relative_threshold),
        "chunk_top_k": int(chunk_top_k),
        "chunk_per_file_limit": int(chunk_per_file_limit),
        "chunk_token_budget": int(chunk_token_budget),
        "chunk_disclosure": str(chunk_disclosure or ""),
        "exact_search_enabled": bool(exact_search_enabled),
        "deterministic_refine_enabled": bool(deterministic_refine_enabled),
        "embedding_enabled": bool(embedding_enabled),
        "embedding_provider": str(embedding_provider or ""),
        "embedding_model": str(embedding_model or ""),
        "embedding_dimension": int(embedding_dimension),
        "feedback_enabled": bool(feedback_enabled),
        "multi_channel_rrf_enabled": bool(multi_channel_rrf_enabled),
        "chunk_guard_mode": str(chunk_guard_mode or ""),
        "topological_shield_mode": str(topological_shield_mode or ""),
        "settings_payload": (
            settings_payload if isinstance(settings_payload, dict) else {}
        ),
        "content_version": str(content_version or ""),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def clone_index_candidate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cloned = dict(payload)
    cloned.pop("candidate_cache", None)
    return cloned


def attach_index_candidate_cache_info(
    *,
    payload: dict[str, Any],
    cache_info: dict[str, Any],
) -> dict[str, Any]:
    materialized = clone_index_candidate_payload(payload)
    materialized["candidate_cache"] = dict(cache_info)
    return materialized


def refresh_cached_index_candidate_payload(
    *,
    payload: dict[str, Any],
    index_data: dict[str, Any],
    cache_info: dict[str, Any],
    index_hash: str,
    timings_ms: dict[str, float],
    benchmark_filter_payload: dict[str, Any],
) -> dict[str, Any]:
    materialized = clone_index_candidate_payload(payload)
    index_chunk_cache_contract = (
        dict(index_data.get("chunk_cache_contract", {}))
        if isinstance(index_data.get("chunk_cache_contract"), dict)
        else {}
    )
    materialized["index_hash"] = str(index_hash or "")
    materialized["file_count"] = int(index_data.get("file_count", 0) or 0)
    materialized["indexed_at"] = index_data.get("indexed_at")
    materialized["languages_covered"] = list(index_data.get("languages_covered", []))
    if index_chunk_cache_contract:
        materialized["chunk_cache_contract"] = {
            "schema_version": str(index_chunk_cache_contract.get("schema_version") or ""),
            "fingerprint": str(index_chunk_cache_contract.get("fingerprint") or ""),
            "file_count": int(index_chunk_cache_contract.get("file_count", 0) or 0),
            "chunk_count": int(index_chunk_cache_contract.get("chunk_count", 0) or 0),
        }
    materialized["parser"] = (
        dict(index_data.get("parser", {}))
        if isinstance(index_data.get("parser"), dict)
        else {}
    )
    materialized["cache"] = dict(cache_info)

    metadata = (
        dict(materialized.get("metadata", {}))
        if isinstance(materialized.get("metadata"), dict)
        else {}
    )
    previous_timings = metadata.get("timings_ms")
    if isinstance(previous_timings, dict):
        metadata["cached_payload_timings_ms"] = dict(previous_timings)
    metadata["timings_ms"] = dict(timings_ms)
    metadata["candidate_cache_reused"] = True
    materialized["metadata"] = metadata

    if benchmark_filter_payload.get("requested", False):
        materialized["benchmark_filters"] = dict(benchmark_filter_payload)
    return materialized


def load_cached_index_candidates_checked(
    *,
    cache_path: Path,
    key: str,
    max_age_seconds: int,
    required_meta: dict[str, Any] | None,
) -> dict[str, Any] | None:
    payload = _load_cache_payload(cache_path=cache_path, schema_version=_SCHEMA_VERSION)
    if payload is None:
        return None
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        return None
    now_epoch = float(time())
    backend = str(payload.get("backend") or "").strip()
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
        legacy_payload = entry.get("payload")
        if isinstance(legacy_payload, dict):
            return copy.deepcopy(legacy_payload)
        if backend != "stage_artifact_cache":
            continue

        memoized = _load_artifact_memory(cache_path=cache_path, key=key)
        if memoized is not None:
            return memoized

        manager = _build_stage_artifact_cache(cache_path=cache_path)
        cached = manager.get_artifact(
            stage_name=str(entry.get("stage_name") or _STAGE_NAME),
            cache_key=key,
        )
        if cached is None:
            continue
        materialized = copy.deepcopy(cached.payload)
        _store_artifact_memory(
            cache_path=cache_path,
            key=key,
            payload=materialized,
        )
        return materialized
    return None


def store_cached_index_candidates(
    *,
    cache_path: Path,
    key: str,
    payload: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> bool:
    normalized_meta = _normalize_cache_meta(meta)
    existing = _load_cache_payload(cache_path=cache_path, schema_version=_SCHEMA_VERSION)
    if existing is None:
        existing = {"schema_version": _SCHEMA_VERSION, "entries": []}

    entries = existing.get("entries", [])
    if not isinstance(entries, list):
        entries = []

    trimmed_entries: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        if str(item.get("key") or "") == str(key):
            continue
        trimmed_entries.append(
            {
                "key": str(item.get("key") or ""),
                "updated_at_epoch": float(item.get("updated_at_epoch", 0.0) or 0.0),
                "meta": _normalize_cache_meta(item.get("meta")),
                "stage_name": str(item.get("stage_name") or _STAGE_NAME),
                **(
                    {"payload": copy.deepcopy(item["payload"])}
                    if isinstance(item.get("payload"), dict)
                    else {}
                ),
            }
        )

    try:
        manager = _build_stage_artifact_cache(cache_path=cache_path)
        manager.put_artifact(
            stage_name=_STAGE_NAME,
            cache_key=key,
            query_hash=_build_query_hash(str(normalized_meta.get("query") or "")),
            fingerprint=str(key),
            settings_fingerprint=_build_meta_fingerprint(normalized_meta),
            payload=copy.deepcopy(payload),
            token_weight=_estimate_payload_token_weight(payload),
            ttl_seconds=max(0, int(normalized_meta.get("ttl_seconds") or 0)),
            content_version=str(normalized_meta.get("content_version") or _SCHEMA_VERSION),
            policy_name=str(normalized_meta.get("policy_name") or _STAGE_NAME),
            trust_class=str(normalized_meta.get("trust_class") or "exact"),
            write_token=_STAGE_NAME,
        )
        trimmed_entries.insert(
            0,
            {
                "key": str(key),
                "updated_at_epoch": round(float(time()), 3),
                "meta": normalized_meta,
                "stage_name": _STAGE_NAME,
            },
        )
        if len(trimmed_entries) > _MAX_ENTRIES:
            trimmed_entries = trimmed_entries[:_MAX_ENTRIES]
        _write_cache_payload(
            cache_path=cache_path,
            payload={
                "schema_version": _SCHEMA_VERSION,
                "backend": "stage_artifact_cache",
                "entries": trimmed_entries,
            },
        )
        _store_artifact_memory(
            cache_path=cache_path,
            key=key,
            payload=payload,
        )
        return True
    except Exception:
        return False


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


def _build_query_hash(value: str) -> str:
    normalized = " ".join(str(value or "").strip().lower().split())
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8", "ignore")).hexdigest()


def _estimate_payload_token_weight(payload: dict[str, Any]) -> int:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return max(1, len(text) // 4)


def _build_meta_fingerprint(meta: dict[str, Any]) -> str:
    text = json.dumps(meta, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def _normalize_cache_meta(meta: Any) -> dict[str, Any]:
    if not isinstance(meta, dict):
        return {}
    return {
        str(key): value
        for key, value in meta.items()
        if isinstance(key, str) and str(key).strip()
    }


def _entry_meta_matches(
    *,
    entry: dict[str, Any],
    required_meta: dict[str, Any] | None,
) -> bool:
    if not required_meta:
        return True
    entry_meta = entry.get("meta")
    if not isinstance(entry_meta, dict):
        return False
    for key, expected in required_meta.items():
        if entry_meta.get(key) != expected:
            return False
    return True


def _is_entry_expired(
    *,
    entry: dict[str, Any],
    now_epoch: float,
    max_age_seconds: int,
) -> bool:
    if max_age_seconds <= 0:
        return False
    try:
        updated_at_epoch = float(entry.get("updated_at_epoch", 0.0) or 0.0)
    except Exception:
        return True
    if updated_at_epoch <= 0.0:
        return True
    return (now_epoch - updated_at_epoch) > float(max_age_seconds)


def _load_cache_payload(*, cache_path: Path, schema_version: str) -> dict[str, Any] | None:
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
    return payload


def _write_cache_payload(*, cache_path: Path, payload: dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_artifact_memory(
    *,
    cache_path: Path,
    key: str,
) -> dict[str, Any] | None:
    try:
        stat = cache_path.stat()
    except OSError:
        return None
    memory_key = (_SCHEMA_VERSION, str(cache_path.resolve()), str(key))
    cached = _INDEX_CANDIDATE_ARTIFACT_MEMORY.get(memory_key)
    if cached is None:
        return None
    if cached[0] != stat.st_mtime_ns or cached[1] != stat.st_size:
        _INDEX_CANDIDATE_ARTIFACT_MEMORY.pop(memory_key, None)
        return None
    return copy.deepcopy(cached[2])


def _store_artifact_memory(
    *,
    cache_path: Path,
    key: str,
    payload: dict[str, Any],
) -> None:
    try:
        stat = cache_path.stat()
    except OSError:
        return
    memory_key = (_SCHEMA_VERSION, str(cache_path.resolve()), str(key))
    _INDEX_CANDIDATE_ARTIFACT_MEMORY[memory_key] = (
        stat.st_mtime_ns,
        stat.st_size,
        copy.deepcopy(payload),
    )


__all__ = [
    "attach_index_candidate_cache_info",
    "build_index_candidate_cache_key",
    "clone_index_candidate_payload",
    "default_index_candidate_cache_path",
    "load_cached_index_candidates_checked",
    "refresh_cached_index_candidate_payload",
    "store_cached_index_candidates",
]
