from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ace_lite.repomap.stage_support import extract_seed_candidate_paths


def normalize_repomap_path(value: str) -> str:
    path = str(value or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def build_subgraph_contract_salt(index_stage: dict[str, Any]) -> str:
    payload = (
        index_stage.get("subgraph_payload", {})
        if isinstance(index_stage.get("subgraph_payload"), dict)
        else {}
    )
    if not payload:
        return ""
    seed_paths_raw = payload.get("seed_paths")
    seed_paths = (
        [normalize_repomap_path(str(item or "")) for item in seed_paths_raw]
        if isinstance(seed_paths_raw, list)
        else []
    )
    seed_paths = [item for item in seed_paths if item]
    edge_counts_raw = payload.get("edge_counts")
    edge_counts = (
        {
            str(key).strip(): max(0, int(value or 0))
            for key, value in edge_counts_raw.items()
            if str(key).strip()
        }
        if isinstance(edge_counts_raw, dict)
        else {}
    )
    return "|".join(
        [
            str(payload.get("payload_version") or ""),
            str(payload.get("taxonomy_version") or ""),
            str(bool(payload.get("enabled", False))).lower(),
            str(payload.get("reason") or ""),
            ",".join(seed_paths),
            ",".join(f"{key}:{edge_counts[key]}" for key in sorted(edge_counts)),
        ]
    )


def inject_worktree_seed_candidates(
    *,
    files_map: dict[str, dict[str, Any]],
    seed_candidates: list[dict[str, Any]],
    worktree_prior: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    rows = [dict(item) for item in seed_candidates if isinstance(item, dict)]
    existing_paths = {
        normalize_repomap_path(str(item.get("path") or ""))
        for item in rows
        if isinstance(item, dict)
    }
    changed = worktree_prior.get("changed_paths", [])
    if not isinstance(changed, list):
        changed = []
    added_count = 0
    for raw in changed:
        path = normalize_repomap_path(str(raw or ""))
        if not path or path in existing_paths or path not in files_map:
            continue
        entry = files_map.get(path, {})
        if not isinstance(entry, dict):
            continue
        rows.insert(
            added_count,
            {
                "path": path,
                "score": 1_000_000.0 - float(added_count),
                "language": str(entry.get("language") or ""),
                "module": str(entry.get("module") or ""),
                "retrieval_pass": "worktree_seed",
                "score_breakdown": {"worktree_seed": 1.0},
            },
        )
        existing_paths.add(path)
        added_count += 1
    return rows, added_count


@dataclass(frozen=True, slots=True)
class RepomapSeedRuntime:
    seed_candidates: list[dict[str, Any]]
    seed_paths_for_cache: list[str]
    worktree_prior: dict[str, Any]
    worktree_seed_count: int
    subgraph_seed_count: int


@dataclass(slots=True)
class RepomapStageCacheRuntime:
    seed_runtime: RepomapSeedRuntime
    cache_path: Path
    precompute_cache_path: Path
    cache_required_meta: dict[str, Any]
    precompute_required_meta: dict[str, Any]
    cache_meta: dict[str, Any]
    precompute_meta: dict[str, Any]
    cache_key: str
    precompute_key: str
    cached_payload: dict[str, Any] | None
    precomputed_payload: dict[str, Any] | None


def prepare_repomap_seed_runtime(
    *,
    index_stage: dict[str, Any],
    index_files: dict[str, dict[str, Any]],
    repomap_top_k: int,
    normalize_path: Callable[[str], str],
    inject_worktree_seed_candidates: Callable[..., tuple[list[dict[str, Any]], int]],
) -> RepomapSeedRuntime:
    candidates = index_stage.get("candidate_files", [])
    if not isinstance(candidates, list):
        candidates = []
    seed_candidates_source = [
        dict(item)
        for item in candidates
        if isinstance(item, dict)
        and str(item.get("retrieval_pass") or "").strip().lower() != "docs_hint"
    ]
    worktree_prior = (
        index_stage.get("worktree_prior", {})
        if isinstance(index_stage.get("worktree_prior"), dict)
        else {}
    )
    seed_candidates, worktree_seed_count = inject_worktree_seed_candidates(
        files_map=index_files,
        seed_candidates=seed_candidates_source,
        worktree_prior=worktree_prior,
    )
    subgraph_payload = (
        index_stage.get("subgraph_payload", {})
        if isinstance(index_stage.get("subgraph_payload"), dict)
        else {}
    )
    subgraph_seed_paths_raw = subgraph_payload.get("seed_paths")
    subgraph_seed_count = len(
        {
            normalize_path(str(item or ""))
            for item in (
                subgraph_seed_paths_raw if isinstance(subgraph_seed_paths_raw, list) else []
            )
            if normalize_path(str(item or ""))
        }
    )
    normalized_seed_candidates = [
        {
            **item,
            "path": normalize_path(str(item.get("path") or "")),
        }
        for item in seed_candidates
        if isinstance(item, dict)
    ]
    seed_paths_for_cache = extract_seed_candidate_paths(
        files=index_files,
        seed_candidates=normalized_seed_candidates,
        top_k=max(1, int(repomap_top_k) * 2),
    )
    return RepomapSeedRuntime(
        seed_candidates=seed_candidates,
        seed_paths_for_cache=seed_paths_for_cache,
        worktree_prior=worktree_prior,
        worktree_seed_count=worktree_seed_count,
        subgraph_seed_count=subgraph_seed_count,
    )


def prepare_repomap_stage_cache_runtime(
    *,
    ctx_root: str,
    index_stage: dict[str, Any],
    index_files: dict[str, dict[str, Any]],
    policy: dict[str, Any],
    policy_version: str,
    effective_ranking_profile: str,
    repomap_signal_weights: dict[str, float] | None,
    repomap_top_k: int,
    scaled_neighbor_limit: int,
    neighbor_depth: int,
    scaled_budget_tokens: int,
    tokenizer_model: str | None,
    cache_content_version: str,
    precompute_content_version: str,
    seed_runtime: RepomapSeedRuntime,
    build_subgraph_contract_salt: Callable[[dict[str, Any]], str],
    build_repomap_cache_key_fn: Callable[..., str],
    build_repomap_precompute_key_fn: Callable[..., str],
    load_cached_repomap_checked_fn: Callable[..., dict[str, Any] | None],
    load_cached_repomap_precompute_checked_fn: Callable[..., dict[str, Any] | None],
) -> RepomapStageCacheRuntime:
    cache_dir = Path(ctx_root) / "context-map" / "repomap"
    cache_path = cache_dir / "cache.json"
    precompute_cache_path = cache_dir / "precompute_cache.json"
    index_hash = str(index_stage.get("index_hash") or "")
    worktree_state_hash = str(seed_runtime.worktree_prior.get("state_hash") or "")
    subgraph_contract_salt = build_subgraph_contract_salt(index_stage)
    index_fingerprint = str(index_hash).strip()
    if not index_fingerprint:
        sample_paths = sorted(str(path) for path in index_files)[:2048]
        index_fingerprint = hashlib.sha256(
            "\n".join(sample_paths).encode("utf-8", "ignore")
        ).hexdigest()

    cache_ttl_seconds = max(0, int(policy.get("repomap_cache_ttl_seconds", 1800) or 1800))
    precompute_ttl_seconds = max(0, int(policy.get("repomap_precompute_ttl_seconds", 7200) or 7200))
    cache_required_meta = {
        "policy_version": str(policy_version),
        "ranking_profile": str(effective_ranking_profile),
        "index_fingerprint": index_fingerprint,
        "subgraph_contract_salt": subgraph_contract_salt,
        "tokenizer_model": str(tokenizer_model or ""),
        "content_version": cache_content_version,
        "precompute_content_version": precompute_content_version,
    }
    precompute_required_meta = {
        "policy_version": str(policy_version),
        "ranking_profile": str(effective_ranking_profile),
        "index_fingerprint": index_fingerprint,
        "content_version": precompute_content_version,
    }
    cache_key = build_repomap_cache_key_fn(
        index_hash=index_hash,
        worktree_state_hash=worktree_state_hash,
        ranking_profile=effective_ranking_profile,
        signal_weights=repomap_signal_weights,
        top_k=int(repomap_top_k),
        neighbor_limit=int(scaled_neighbor_limit),
        neighbor_depth=int(neighbor_depth),
        budget_tokens=int(scaled_budget_tokens),
        seed_paths=seed_runtime.seed_paths_for_cache,
        subgraph_contract_salt=subgraph_contract_salt,
        tokenizer_model=tokenizer_model,
        content_version=cache_content_version,
        precompute_content_version=precompute_content_version,
    )
    cached_payload = load_cached_repomap_checked_fn(
        cache_path=cache_path,
        key=cache_key,
        max_age_seconds=cache_ttl_seconds,
        required_meta=cache_required_meta,
    )
    cache_meta = {
        "enabled": True,
        "hit": bool(cached_payload is not None),
        "store_written": False,
        "cache_key": cache_key,
        "path": str(cache_path),
        "ttl_seconds": int(cache_ttl_seconds),
        "content_version": cache_content_version,
        "precompute_content_version": precompute_content_version,
    }
    precompute_key = build_repomap_precompute_key_fn(
        index_hash=index_hash,
        ranking_profile=effective_ranking_profile,
        signal_weights=repomap_signal_weights,
        content_version=precompute_content_version,
    )
    precomputed_payload = load_cached_repomap_precompute_checked_fn(
        cache_path=precompute_cache_path,
        key=precompute_key,
        max_age_seconds=precompute_ttl_seconds,
        required_meta=precompute_required_meta,
    )
    precompute_meta = {
        "enabled": True,
        "hit": bool(precomputed_payload is not None),
        "store_written": False,
        "cache_key": precompute_key,
        "path": str(precompute_cache_path),
        "ttl_seconds": int(precompute_ttl_seconds),
        "content_version": precompute_content_version,
    }
    return RepomapStageCacheRuntime(
        seed_runtime=seed_runtime,
        cache_path=cache_path,
        precompute_cache_path=precompute_cache_path,
        cache_required_meta=cache_required_meta,
        precompute_required_meta=precompute_required_meta,
        cache_meta=cache_meta,
        precompute_meta=precompute_meta,
        cache_key=cache_key,
        precompute_key=precompute_key,
        cached_payload=cached_payload,
        precomputed_payload=precomputed_payload,
    )


def build_repomap_stage_payload_from_cache_runtime(
    *,
    index_stage: dict[str, Any],
    index_files: dict[str, dict[str, Any]],
    effective_ranking_profile: str,
    repomap_signal_weights: dict[str, float] | None,
    repomap_top_k: int,
    scaled_neighbor_limit: int,
    neighbor_depth: int,
    scaled_budget_tokens: int,
    tokenizer_model: str | None,
    cache_runtime: RepomapStageCacheRuntime,
    build_stage_precompute_payload_fn: Callable[..., dict[str, Any]],
    build_stage_repo_map_fn: Callable[..., dict[str, Any]],
    store_cached_repomap_fn: Callable[..., bool],
    store_cached_repomap_precompute_fn: Callable[..., bool],
) -> dict[str, Any]:
    precomputed_payload = cache_runtime.precomputed_payload
    if precomputed_payload is None:
        precomputed_payload = build_stage_precompute_payload_fn(
            index_files=index_files,
            ranking_profile=effective_ranking_profile,
            signal_weights=repomap_signal_weights,
        )
        cache_runtime.precompute_meta["store_written"] = bool(
            store_cached_repomap_precompute_fn(
                cache_path=cache_runtime.precompute_cache_path,
                key=cache_runtime.precompute_key,
                payload=precomputed_payload,
                meta={
                    **cache_runtime.precompute_required_meta,
                    "ttl_seconds": int(cache_runtime.precompute_meta.get("ttl_seconds") or 0),
                    "policy_name": "repomap_precompute",
                    "trust_class": "exact",
                },
            )
        )
        cache_runtime.precomputed_payload = precomputed_payload

    payload = cache_runtime.cached_payload
    if payload is None:
        payload = build_stage_repo_map_fn(
            index_files=index_files,
            seed_candidates=cache_runtime.seed_runtime.seed_candidates,
            ranking_profile=effective_ranking_profile,
            signal_weights=repomap_signal_weights,
            top_k=repomap_top_k,
            neighbor_limit=scaled_neighbor_limit,
            neighbor_depth=neighbor_depth,
            budget_tokens=scaled_budget_tokens,
            subgraph_payload=(
                index_stage.get("subgraph_payload", {})
                if isinstance(index_stage.get("subgraph_payload"), dict)
                else {}
            ),
            precomputed_payload=precomputed_payload,
            tokenizer_model=tokenizer_model,
        )
        cache_runtime.cache_meta["store_written"] = bool(
            store_cached_repomap_fn(
                cache_path=cache_runtime.cache_path,
                key=cache_runtime.cache_key,
                payload=payload,
                meta={
                    **cache_runtime.cache_required_meta,
                    "ttl_seconds": int(cache_runtime.cache_meta.get("ttl_seconds") or 0),
                    "policy_name": "repomap",
                    "trust_class": "exact",
                },
            )
        )
        cache_runtime.cached_payload = payload

    payload["cache"] = cache_runtime.cache_meta
    payload["precompute"] = cache_runtime.precompute_meta
    payload["worktree_seed_count"] = int(cache_runtime.seed_runtime.worktree_seed_count)
    payload["subgraph_seed_count"] = int(cache_runtime.seed_runtime.subgraph_seed_count)
    payload["seed_candidates_count"] = len(cache_runtime.seed_runtime.seed_candidates)
    return payload


__all__ = [
    "RepomapSeedRuntime",
    "RepomapStageCacheRuntime",
    "build_repomap_stage_payload_from_cache_runtime",
    "build_subgraph_contract_salt",
    "inject_worktree_seed_candidates",
    "normalize_repomap_path",
    "prepare_repomap_seed_runtime",
    "prepare_repomap_stage_cache_runtime",
]
