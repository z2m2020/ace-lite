"""Repomap stage for the orchestrator pipeline.

This module handles repository map building for code context.
"""

from __future__ import annotations

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
from ace_lite.repomap.cache_runtime import (
    build_subgraph_contract_salt as _build_subgraph_contract_salt,
    build_repomap_stage_payload_from_cache_runtime,
    inject_worktree_seed_candidates as _inject_worktree_seed_candidates,
    normalize_repomap_path as _normalize_path,
    prepare_repomap_seed_runtime,
    prepare_repomap_stage_cache_runtime,
)
from ace_lite.repomap.stage_runtime import (
    build_disabled_repomap_payload,
    build_repomap_error_payload,
    finalize_repomap_stage_payload,
    resolve_repomap_stage_policy_runtime,
)

_REPOMAP_CACHE_CONTENT_VERSION = "stage-repomap-v4"
_REPOMAP_PRECOMPUTE_CONTENT_VERSION = "stage-precompute-v2"


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
    policy_runtime = resolve_repomap_stage_policy_runtime(
        policy=policy,
        repomap_enabled=repomap_enabled,
        repomap_neighbor_limit=repomap_neighbor_limit,
        repomap_budget_tokens=repomap_budget_tokens,
        repomap_ranking_profile=repomap_ranking_profile,
        policy_version=policy_version,
    )
    scaled_neighbor_limit = policy_runtime.scaled_neighbor_limit
    scaled_budget_tokens = policy_runtime.scaled_budget_tokens
    neighbor_depth = policy_runtime.neighbor_depth
    effective_enabled = policy_runtime.effective_enabled
    effective_ranking_profile = policy_runtime.effective_ranking_profile

    if not effective_enabled:
        return build_disabled_repomap_payload(
            repomap_enabled=repomap_enabled,
            runtime=policy_runtime,
        )

    index_stage = ctx.state.get("index", {})
    if not isinstance(index_stage, dict):
        index_stage = {}
    index_files = ctx.state.get("__index_files", {})
    if not isinstance(index_files, dict):
        index_files = {}
    seed_runtime = prepare_repomap_seed_runtime(
        index_stage=index_stage,
        index_files=index_files,
        repomap_top_k=repomap_top_k,
        normalize_path=_normalize_path,
        inject_worktree_seed_candidates=_inject_worktree_seed_candidates,
    )
    cache_runtime = prepare_repomap_stage_cache_runtime(
        ctx_root=ctx.root,
        index_stage=index_stage,
        index_files=index_files,
        policy=policy,
        policy_version=str(policy_runtime.policy_version),
        effective_ranking_profile=effective_ranking_profile,
        repomap_signal_weights=repomap_signal_weights,
        repomap_top_k=repomap_top_k,
        scaled_neighbor_limit=scaled_neighbor_limit,
        neighbor_depth=neighbor_depth,
        scaled_budget_tokens=scaled_budget_tokens,
        tokenizer_model=tokenizer_model,
        cache_content_version=_REPOMAP_CACHE_CONTENT_VERSION,
        precompute_content_version=_REPOMAP_PRECOMPUTE_CONTENT_VERSION,
        seed_runtime=seed_runtime,
        build_subgraph_contract_salt=_build_subgraph_contract_salt,
        build_repomap_cache_key_fn=build_repomap_cache_key,
        build_repomap_precompute_key_fn=build_repomap_precompute_key,
        load_cached_repomap_checked_fn=load_cached_repomap_checked,
        load_cached_repomap_precompute_checked_fn=load_cached_repomap_precompute_checked,
    )

    try:
        payload = build_repomap_stage_payload_from_cache_runtime(
            index_stage=index_stage,
            index_files=index_files,
            effective_ranking_profile=effective_ranking_profile,
            repomap_signal_weights=repomap_signal_weights,
            repomap_top_k=repomap_top_k,
            scaled_neighbor_limit=scaled_neighbor_limit,
            neighbor_depth=neighbor_depth,
            scaled_budget_tokens=scaled_budget_tokens,
            tokenizer_model=tokenizer_model,
            cache_runtime=cache_runtime,
            build_stage_precompute_payload_fn=build_stage_precompute_payload,
            build_stage_repo_map_fn=build_stage_repo_map,
            store_cached_repomap_fn=store_cached_repomap,
            store_cached_repomap_precompute_fn=store_cached_repomap_precompute,
        )
        return finalize_repomap_stage_payload(
            payload=payload,
            runtime=policy_runtime,
        )
    except ValueError as exc:
        return build_repomap_error_payload(
            reason=f"repomap_error:{exc}",
            runtime=policy_runtime,
            cache_meta=cache_runtime.cache_meta,
            precompute_meta=cache_runtime.precompute_meta,
            worktree_seed_count=seed_runtime.worktree_seed_count,
            seed_candidates_count=len(seed_runtime.seed_candidates),
        )


__all__ = ["run_repomap"]
