"""Repomap stage for the orchestrator pipeline.

This module handles repository map building for code context.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ace_lite.pipeline.types import StageContext
from ace_lite.repomap.builder import build_stage_precompute_payload, build_stage_repo_map
from ace_lite.repomap.cache import (
    build_repomap_cache_key,
    build_repomap_precompute_key,
    load_cached_repomap_checked,
    load_cached_repomap_precompute_checked,
    store_cached_repomap,
    store_cached_repomap_precompute,
)

_REPOMAP_CACHE_CONTENT_VERSION = "stage-repomap-v3"
_REPOMAP_PRECOMPUTE_CONTENT_VERSION = "stage-precompute-v2"


def _normalize_path(value: str) -> str:
    path = str(value or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def _inject_worktree_seed_candidates(
    *,
    files_map: dict[str, dict[str, Any]],
    seed_candidates: list[dict[str, Any]],
    worktree_prior: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    rows = [dict(item) for item in seed_candidates if isinstance(item, dict)]
    existing_paths = {
        _normalize_path(str(item.get("path") or ""))
        for item in rows
        if isinstance(item, dict)
    }
    changed = worktree_prior.get("changed_paths", [])
    if not isinstance(changed, list):
        changed = []
    added_count = 0
    for raw in changed:
        path = _normalize_path(str(raw or ""))
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


def run_repomap(
    *,
    ctx: StageContext,
    repomap_enabled: bool,
    repomap_neighbor_limit: int,
    repomap_budget_tokens: int,
    repomap_top_k: int,
    repomap_ranking_profile: str,
    repomap_signal_weights: dict[str, float] | None,
    tokenizer_model: str | None = None,
    policy_version: str,
) -> dict[str, Any]:
    """Run the repomap stage.

    Args:
        ctx: Stage context with query and state.
        repomap_enabled: Whether repomap is enabled.
        repomap_neighbor_limit: Maximum number of neighbors.
        repomap_budget_tokens: Token budget for the map.
        repomap_top_k: Top-k files to include.
        repomap_ranking_profile: Ranking profile ("graph" or "graph_seeded").
        repomap_signal_weights: Signal weights for ranking.
        policy_version: Policy version string.

    Returns:
        Dict with repomap data or disabled reason.
    """
    policy = (
        ctx.state.get("__policy", {})
        if isinstance(ctx.state.get("__policy"), dict)
        else {}
    )
    neighbor_scale = max(
        0.1, float(policy.get("repomap_neighbor_scale", 1.0) or 1.0)
    )
    neighbor_depth = max(1, int(policy.get("repomap_neighbor_depth", 1) or 1))
    budget_scale = max(0.1, float(policy.get("repomap_budget_scale", 1.0) or 1.0))
    scaled_neighbor_limit = max(
        0, round(repomap_neighbor_limit * neighbor_scale)
    )
    scaled_budget_tokens = max(
        64, round(repomap_budget_tokens * budget_scale)
    )
    policy_repomap_enabled = bool(policy.get("repomap_enabled", True))
    effective_enabled = bool(repomap_enabled and policy_repomap_enabled)
    policy_profile = str(policy.get("repomap_ranking_profile", "")).strip().lower()
    effective_ranking_profile = repomap_ranking_profile
    if (
        effective_ranking_profile == "graph"
        and policy_profile in {"graph", "graph_seeded"}
    ):
        effective_ranking_profile = policy_profile

    if not effective_enabled:
        reason = "disabled" if not repomap_enabled else "policy_disabled"
        return {
            "enabled": False,
            "reason": reason,
            "focused_files": [],
            "seed_paths": [],
            "neighbor_paths": [],
            "dependency_recall": {
                "expected_count": 0,
                "hit_count": 0,
                "hit_rate": 1.0,
            },
            "markdown": "",
            "ranking_profile": effective_ranking_profile,
            "policy_name": str(policy.get("name", "general")),
            "policy_version": str(policy.get("version", policy_version)),
            "neighbor_limit": scaled_neighbor_limit,
            "neighbor_depth": neighbor_depth,
            "budget_tokens": scaled_budget_tokens,
            "repomap_enabled_effective": effective_enabled,
            "cache": {
                "enabled": True,
                "hit": False,
                "store_written": False,
                "cache_key": "",
                "path": "",
            },
            "precompute": {
                "enabled": True,
                "hit": False,
                "store_written": False,
                "cache_key": "",
                "path": "",
            },
        }

    index_stage = ctx.state.get("index", {})
    index_files = ctx.state.get("__index_files", {})
    if not isinstance(index_files, dict):
        index_files = {}
    candidates = (
        index_stage.get("candidate_files", [])
        if isinstance(index_stage, dict)
        else []
    )
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
        if isinstance(index_stage, dict) and isinstance(index_stage.get("worktree_prior"), dict)
        else {}
    )
    seed_candidates, worktree_seed_count = _inject_worktree_seed_candidates(
        files_map=index_files,
        seed_candidates=seed_candidates_source,
        worktree_prior=worktree_prior,
    )
    seed_paths_for_cache: list[str] = []
    for item in seed_candidates[: max(1, int(repomap_top_k) * 2)]:
        if not isinstance(item, dict):
            continue
        path = _normalize_path(str(item.get("path") or ""))
        if not path or path in seed_paths_for_cache:
            continue
        seed_paths_for_cache.append(path)

    cache_dir = Path(ctx.root) / "context-map" / "repomap"
    cache_path = cache_dir / "cache.json"
    precompute_cache_path = cache_dir / "precompute_cache.json"
    index_hash = (
        str(index_stage.get("index_hash") or "")
        if isinstance(index_stage, dict)
        else ""
    )
    worktree_state_hash = (
        str(worktree_prior.get("state_hash") or "")
        if isinstance(worktree_prior, dict)
        else ""
    )
    index_fingerprint = str(index_hash).strip()
    if not index_fingerprint:
        sample_paths = sorted(str(path) for path in index_files)[:2048]
        index_fingerprint = hashlib.sha256(
            "\n".join(sample_paths).encode("utf-8", "ignore")
        ).hexdigest()
    cache_ttl_seconds = max(
        0, int(policy.get("repomap_cache_ttl_seconds", 1800) or 1800)
    )
    precompute_ttl_seconds = max(
        0, int(policy.get("repomap_precompute_ttl_seconds", 7200) or 7200)
    )
    cache_required_meta = {
        "policy_version": str(policy.get("version", policy_version)),
        "ranking_profile": str(effective_ranking_profile),
        "index_fingerprint": index_fingerprint,
        "tokenizer_model": str(tokenizer_model or ""),
        "content_version": _REPOMAP_CACHE_CONTENT_VERSION,
        "precompute_content_version": _REPOMAP_PRECOMPUTE_CONTENT_VERSION,
    }
    precompute_required_meta = {
        "policy_version": str(policy.get("version", policy_version)),
        "ranking_profile": str(effective_ranking_profile),
        "index_fingerprint": index_fingerprint,
        "content_version": _REPOMAP_PRECOMPUTE_CONTENT_VERSION,
    }
    cache_key = build_repomap_cache_key(
        index_hash=index_hash,
        worktree_state_hash=worktree_state_hash,
        ranking_profile=effective_ranking_profile,
        signal_weights=repomap_signal_weights,
        top_k=int(repomap_top_k),
        neighbor_limit=int(scaled_neighbor_limit),
        neighbor_depth=int(neighbor_depth),
        budget_tokens=int(scaled_budget_tokens),
        seed_paths=seed_paths_for_cache,
        tokenizer_model=tokenizer_model,
        content_version=_REPOMAP_CACHE_CONTENT_VERSION,
        precompute_content_version=_REPOMAP_PRECOMPUTE_CONTENT_VERSION,
    )
    cached_payload = load_cached_repomap_checked(
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
        "content_version": _REPOMAP_CACHE_CONTENT_VERSION,
        "precompute_content_version": _REPOMAP_PRECOMPUTE_CONTENT_VERSION,
    }
    precompute_key = build_repomap_precompute_key(
        index_hash=index_hash,
        ranking_profile=effective_ranking_profile,
        signal_weights=repomap_signal_weights,
        content_version=_REPOMAP_PRECOMPUTE_CONTENT_VERSION,
    )
    precomputed_payload = load_cached_repomap_precompute_checked(
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
        "content_version": _REPOMAP_PRECOMPUTE_CONTENT_VERSION,
    }

    try:
        if precomputed_payload is None:
            precomputed_payload = build_stage_precompute_payload(
                index_files=index_files,
                ranking_profile=effective_ranking_profile,
                signal_weights=repomap_signal_weights,
            )
            precompute_meta["store_written"] = bool(
                store_cached_repomap_precompute(
                    cache_path=precompute_cache_path,
                    key=precompute_key,
                    payload=precomputed_payload,
                    meta=precompute_required_meta,
                )
            )

        if cached_payload is None:
            payload = build_stage_repo_map(
                index_files=index_files,
                seed_candidates=seed_candidates,
                ranking_profile=effective_ranking_profile,
                signal_weights=repomap_signal_weights,
                top_k=repomap_top_k,
                neighbor_limit=scaled_neighbor_limit,
                neighbor_depth=neighbor_depth,
                budget_tokens=scaled_budget_tokens,
                precomputed_payload=precomputed_payload,
                tokenizer_model=tokenizer_model,
            )
            cache_meta["store_written"] = bool(
                store_cached_repomap(
                    cache_path=cache_path,
                    key=cache_key,
                    payload=payload,
                    meta=cache_required_meta,
                )
            )
        else:
            payload = cached_payload
        payload["policy_name"] = str(policy.get("name", "general"))
        payload["policy_version"] = str(policy.get("version", policy_version))
        payload["neighbor_limit"] = scaled_neighbor_limit
        payload["neighbor_depth"] = neighbor_depth
        payload["budget_tokens"] = scaled_budget_tokens
        payload["repomap_enabled_effective"] = effective_enabled
        payload["ranking_profile_effective"] = effective_ranking_profile
        payload["cache"] = cache_meta
        payload["precompute"] = precompute_meta
        payload["worktree_seed_count"] = int(worktree_seed_count)
        payload["seed_candidates_count"] = len(seed_candidates)
        return payload
    except ValueError as exc:
        return {
            "enabled": False,
            "reason": f"repomap_error:{exc}",
            "focused_files": [],
            "seed_paths": [],
            "neighbor_paths": [],
            "dependency_recall": {
                "expected_count": 0,
                "hit_count": 0,
                "hit_rate": 0.0,
            },
            "markdown": "",
            "ranking_profile": effective_ranking_profile,
            "policy_name": str(policy.get("name", "general")),
            "policy_version": str(policy.get("version", policy_version)),
            "neighbor_limit": scaled_neighbor_limit,
            "neighbor_depth": neighbor_depth,
            "budget_tokens": scaled_budget_tokens,
            "repomap_enabled_effective": effective_enabled,
            "cache": cache_meta,
            "precompute": precompute_meta,
            "worktree_seed_count": int(worktree_seed_count),
            "seed_candidates_count": len(seed_candidates),
        }


__all__ = ["run_repomap"]
