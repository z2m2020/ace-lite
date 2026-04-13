from __future__ import annotations

from ace_lite.repomap.stage_runtime import (
    build_disabled_repomap_payload,
    build_repomap_error_payload,
    finalize_repomap_stage_payload,
    resolve_repomap_stage_policy_runtime,
)


def test_resolve_repomap_stage_policy_runtime_scales_and_overrides_profile() -> None:
    runtime = resolve_repomap_stage_policy_runtime(
        policy={
            "name": "feature",
            "version": "v2",
            "repomap_enabled": True,
            "repomap_neighbor_scale": 1.5,
            "repomap_neighbor_depth": 2,
            "repomap_budget_scale": 0.5,
            "repomap_ranking_profile": "graph_seeded",
        },
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_ranking_profile="graph",
        policy_version="v1",
    )

    assert runtime.policy_name == "feature"
    assert runtime.policy_version == "v2"
    assert runtime.effective_enabled is True
    assert runtime.effective_ranking_profile == "graph_seeded"
    assert runtime.scaled_neighbor_limit == 12
    assert runtime.neighbor_depth == 2
    assert runtime.scaled_budget_tokens == 128


def test_build_disabled_repomap_payload_reflects_runtime_contract() -> None:
    runtime = resolve_repomap_stage_policy_runtime(
        policy={"name": "general", "version": "v1", "repomap_enabled": False},
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_ranking_profile="graph_seeded",
        policy_version="v1",
    )

    payload = build_disabled_repomap_payload(
        repomap_enabled=True,
        runtime=runtime,
    )

    assert payload["enabled"] is False
    assert payload["reason"] == "policy_disabled"
    assert payload["policy_name"] == "general"
    assert payload["policy_version"] == "v1"
    assert payload["neighbor_limit"] == 8
    assert payload["budget_tokens"] == 256
    assert payload["cache"]["hit"] is False
    assert payload["precompute"]["hit"] is False


def test_finalize_repomap_stage_payload_attaches_runtime_fields() -> None:
    runtime = resolve_repomap_stage_policy_runtime(
        policy={"name": "general", "version": "v3"},
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_ranking_profile="graph_seeded",
        policy_version="v1",
    )

    payload = finalize_repomap_stage_payload(
        payload={"enabled": True},
        runtime=runtime,
    )

    assert payload["policy_name"] == "general"
    assert payload["policy_version"] == "v3"
    assert payload["neighbor_limit"] == runtime.scaled_neighbor_limit
    assert payload["budget_tokens"] == runtime.scaled_budget_tokens
    assert payload["ranking_profile_effective"] == "graph_seeded"


def test_build_repomap_error_payload_reuses_runtime_and_cache_metadata() -> None:
    runtime = resolve_repomap_stage_policy_runtime(
        policy={"name": "general", "version": "v4"},
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_ranking_profile="graph_seeded",
        policy_version="v1",
    )

    payload = build_repomap_error_payload(
        reason="repomap_error:boom",
        runtime=runtime,
        cache_meta={"hit": False, "path": "cache.json"},
        precompute_meta={"hit": True, "path": "precompute_cache.json"},
        worktree_seed_count=2,
        subgraph_seed_count=3,
        seed_candidates_count=5,
    )

    assert payload["enabled"] is False
    assert payload["reason"] == "repomap_error:boom"
    assert payload["policy_version"] == "v4"
    assert payload["cache"]["path"] == "cache.json"
    assert payload["precompute"]["hit"] is True
    assert payload["worktree_seed_count"] == 2
    assert payload["subgraph_seed_count"] == 3
    assert payload["seed_candidates_count"] == 5
