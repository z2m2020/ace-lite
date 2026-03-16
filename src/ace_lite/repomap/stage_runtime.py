from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RepomapStagePolicyRuntime:
    policy_name: str
    policy_version: str
    effective_enabled: bool
    effective_ranking_profile: str
    scaled_neighbor_limit: int
    neighbor_depth: int
    scaled_budget_tokens: int


def resolve_repomap_stage_policy_runtime(
    *,
    policy: dict[str, Any],
    repomap_enabled: bool,
    repomap_neighbor_limit: int,
    repomap_budget_tokens: int,
    repomap_ranking_profile: str,
    policy_version: str,
) -> RepomapStagePolicyRuntime:
    neighbor_scale = max(
        0.1, float(policy.get("repomap_neighbor_scale", 1.0) or 1.0)
    )
    neighbor_depth = max(1, int(policy.get("repomap_neighbor_depth", 1) or 1))
    budget_scale = max(0.1, float(policy.get("repomap_budget_scale", 1.0) or 1.0))
    scaled_neighbor_limit = max(0, round(repomap_neighbor_limit * neighbor_scale))
    scaled_budget_tokens = max(64, round(repomap_budget_tokens * budget_scale))
    policy_repomap_enabled = bool(policy.get("repomap_enabled", True))
    effective_enabled = bool(repomap_enabled and policy_repomap_enabled)
    policy_profile = str(policy.get("repomap_ranking_profile", "")).strip().lower()
    effective_ranking_profile = repomap_ranking_profile
    if (
        effective_ranking_profile == "graph"
        and policy_profile in {"graph", "graph_seeded"}
    ):
        effective_ranking_profile = policy_profile
    return RepomapStagePolicyRuntime(
        policy_name=str(policy.get("name", "general")),
        policy_version=str(policy.get("version", policy_version)),
        effective_enabled=effective_enabled,
        effective_ranking_profile=effective_ranking_profile,
        scaled_neighbor_limit=scaled_neighbor_limit,
        neighbor_depth=neighbor_depth,
        scaled_budget_tokens=scaled_budget_tokens,
    )


def build_disabled_repomap_payload(
    *,
    repomap_enabled: bool,
    runtime: RepomapStagePolicyRuntime,
) -> dict[str, Any]:
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
        "ranking_profile": runtime.effective_ranking_profile,
        "policy_name": runtime.policy_name,
        "policy_version": runtime.policy_version,
        "neighbor_limit": runtime.scaled_neighbor_limit,
        "neighbor_depth": runtime.neighbor_depth,
        "budget_tokens": runtime.scaled_budget_tokens,
        "repomap_enabled_effective": runtime.effective_enabled,
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


def finalize_repomap_stage_payload(
    *,
    payload: dict[str, Any],
    runtime: RepomapStagePolicyRuntime,
) -> dict[str, Any]:
    payload["policy_name"] = str(runtime.policy_name)
    payload["policy_version"] = str(runtime.policy_version)
    payload["neighbor_limit"] = runtime.scaled_neighbor_limit
    payload["neighbor_depth"] = runtime.neighbor_depth
    payload["budget_tokens"] = runtime.scaled_budget_tokens
    payload["repomap_enabled_effective"] = runtime.effective_enabled
    payload["ranking_profile_effective"] = runtime.effective_ranking_profile
    return payload


def build_repomap_error_payload(
    *,
    reason: str,
    runtime: RepomapStagePolicyRuntime,
    cache_meta: dict[str, Any],
    precompute_meta: dict[str, Any],
    worktree_seed_count: int,
    seed_candidates_count: int,
) -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": str(reason),
        "focused_files": [],
        "seed_paths": [],
        "neighbor_paths": [],
        "dependency_recall": {
            "expected_count": 0,
            "hit_count": 0,
            "hit_rate": 0.0,
        },
        "markdown": "",
        "ranking_profile": runtime.effective_ranking_profile,
        "policy_name": str(runtime.policy_name),
        "policy_version": str(runtime.policy_version),
        "neighbor_limit": runtime.scaled_neighbor_limit,
        "neighbor_depth": runtime.neighbor_depth,
        "budget_tokens": runtime.scaled_budget_tokens,
        "repomap_enabled_effective": runtime.effective_enabled,
        "cache": cache_meta,
        "precompute": precompute_meta,
        "worktree_seed_count": int(worktree_seed_count),
        "seed_candidates_count": int(seed_candidates_count),
    }


__all__ = [
    "RepomapStagePolicyRuntime",
    "build_repomap_error_payload",
    "build_disabled_repomap_payload",
    "finalize_repomap_stage_payload",
    "resolve_repomap_stage_policy_runtime",
]
