from __future__ import annotations

from pathlib import Path

from ace_lite.repomap.cache_runtime import (
    RepomapSeedRuntime,
    build_repomap_stage_payload_from_cache_runtime,
    build_subgraph_contract_salt,
    inject_worktree_seed_candidates,
    normalize_repomap_path,
    prepare_repomap_seed_runtime,
    prepare_repomap_stage_cache_runtime,
)


def test_build_subgraph_contract_salt_normalizes_seed_paths_and_edges() -> None:
    salt = build_subgraph_contract_salt(
        {
            "subgraph_payload": {
                "payload_version": "v1",
                "taxonomy_version": "tax-v1",
                "enabled": True,
                "reason": "ok",
                "seed_paths": ["./src/a.py", "src/b.py"],
                "edge_counts": {"imports": 2, "calls": 1},
            }
        }
    )

    assert salt == "v1|tax-v1|true|ok|src/a.py,src/b.py|calls:1,imports:2"


def test_inject_worktree_seed_candidates_adds_missing_changed_paths() -> None:
    rows, count = inject_worktree_seed_candidates(
        files_map={"src/a.py": {"language": "python", "module": "src.a"}},
        seed_candidates=[{"path": "./src/b.py", "score": 1.0}],
        worktree_prior={"changed_paths": ["./src/a.py", "./src/b.py"]},
    )

    assert count == 1
    assert rows[0]["path"] == "src/a.py"
    assert rows[0]["retrieval_pass"] == "worktree_seed"


def test_prepare_repomap_seed_runtime_filters_docs_hint_and_dedupes_paths() -> None:
    files_map = {
        "src/a.py": {"language": "python", "module": "src.a"},
        "src/b.py": {"language": "python", "module": "src.b"},
    }
    index_stage = {
        "candidate_files": [
            {"path": "./src/b.py", "score": 2.0},
            {"path": "src/a.py", "score": 99.0, "retrieval_pass": "docs_hint"},
        ],
        "subgraph_payload": {
            "seed_paths": ["src/b.py", "./src/a.py", "src/b.py"],
        },
        "worktree_prior": {
            "changed_paths": ["src/a.py", "src/b.py"],
            "state_hash": "wt-1",
        },
    }

    runtime = prepare_repomap_seed_runtime(
        index_stage=index_stage,
        index_files=files_map,
        repomap_top_k=1,
        normalize_path=normalize_repomap_path,
        inject_worktree_seed_candidates=lambda **kwargs: (
            [
                {"path": "src/a.py", "score": 1000.0},
                *kwargs["seed_candidates"],
            ],
            1,
        ),
    )

    assert runtime.worktree_seed_count == 1
    assert runtime.subgraph_seed_count == 2
    assert [item["path"] for item in runtime.seed_candidates] == ["src/a.py", "./src/b.py"]
    assert runtime.seed_paths_for_cache == ["src/a.py", "src/b.py"]


def test_prepare_repomap_stage_cache_runtime_builds_keys_and_meta(tmp_path: Path) -> None:
    seed_runtime = RepomapSeedRuntime(
        seed_candidates=[{"path": "src/a.py", "score": 1.0}],
        seed_paths_for_cache=["src/a.py"],
        worktree_prior={"state_hash": "wt-2"},
        worktree_seed_count=1,
        subgraph_seed_count=2,
    )
    seen: dict[str, object] = {}

    def build_cache_key(**kwargs: object) -> str:
        seen["cache_key_kwargs"] = kwargs
        return "cache-key"

    def build_precompute_key(**kwargs: object) -> str:
        seen["precompute_key_kwargs"] = kwargs
        return "pre-key"

    def load_cache(**kwargs: object) -> None:
        seen["cache_load_kwargs"] = kwargs
        return None

    def load_precompute(**kwargs: object) -> dict[str, bool]:
        seen["precompute_load_kwargs"] = kwargs
        return {"ready": True}

    runtime = prepare_repomap_stage_cache_runtime(
        ctx_root=str(tmp_path),
        index_stage={"index_hash": "", "subgraph_payload": {"payload_version": "v1"}},
        index_files={"src/a.py": {"language": "python"}},
        policy={"repomap_cache_ttl_seconds": 10, "repomap_precompute_ttl_seconds": 20},
        policy_version="pv-1",
        effective_ranking_profile="graph_seeded",
        repomap_signal_weights={"graph": 1.0},
        repomap_top_k=4,
        scaled_neighbor_limit=8,
        neighbor_depth=2,
        scaled_budget_tokens=256,
        tokenizer_model="tok-x",
        cache_content_version="cache-v1",
        precompute_content_version="pre-v1",
        seed_runtime=seed_runtime,
        build_subgraph_contract_salt=lambda stage: f"salt:{stage['subgraph_payload']['payload_version']}",
        build_repomap_cache_key_fn=build_cache_key,
        build_repomap_precompute_key_fn=build_precompute_key,
        load_cached_repomap_checked_fn=load_cache,
        load_cached_repomap_precompute_checked_fn=load_precompute,
    )

    assert runtime.cache_key == "cache-key"
    assert runtime.precompute_key == "pre-key"
    assert runtime.cache_meta["hit"] is False
    assert runtime.precompute_meta["hit"] is True
    assert runtime.cache_required_meta["policy_version"] == "pv-1"
    assert runtime.cache_required_meta["subgraph_contract_salt"] == "salt:v1"
    assert runtime.precompute_required_meta["content_version"] == "pre-v1"
    assert runtime.cache_meta["path"] == str(tmp_path / "context-map" / "repomap" / "cache.json")
    assert runtime.precompute_meta["path"] == str(
        tmp_path / "context-map" / "repomap" / "precompute_cache.json"
    )


def test_build_repomap_stage_payload_from_cache_runtime_stores_missing_artifacts(
    tmp_path: Path,
) -> None:
    seed_runtime = RepomapSeedRuntime(
        seed_candidates=[{"path": "src/a.py", "score": 1.0}],
        seed_paths_for_cache=["src/a.py"],
        worktree_prior={"state_hash": "wt-3"},
        worktree_seed_count=1,
        subgraph_seed_count=2,
    )
    cache_runtime = prepare_repomap_stage_cache_runtime(
        ctx_root=str(tmp_path),
        index_stage={"index_hash": "idx-3"},
        index_files={"src/a.py": {"language": "python"}},
        policy={},
        policy_version="pv-3",
        effective_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        repomap_top_k=4,
        scaled_neighbor_limit=8,
        neighbor_depth=1,
        scaled_budget_tokens=256,
        tokenizer_model=None,
        cache_content_version="cache-v3",
        precompute_content_version="pre-v3",
        seed_runtime=seed_runtime,
        build_subgraph_contract_salt=lambda stage: "",
        build_repomap_cache_key_fn=lambda **kwargs: "cache-key-3",
        build_repomap_precompute_key_fn=lambda **kwargs: "pre-key-3",
        load_cached_repomap_checked_fn=lambda **kwargs: None,
        load_cached_repomap_precompute_checked_fn=lambda **kwargs: None,
    )
    calls: dict[str, list[dict[str, object]]] = {"store": []}

    payload = build_repomap_stage_payload_from_cache_runtime(
        index_stage={"subgraph_payload": {"enabled": True}},
        index_files={"src/a.py": {"language": "python"}},
        effective_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        repomap_top_k=4,
        scaled_neighbor_limit=8,
        neighbor_depth=1,
        scaled_budget_tokens=256,
        tokenizer_model="tok-y",
        cache_runtime=cache_runtime,
        build_stage_precompute_payload_fn=lambda **kwargs: {"precomputed": True, **kwargs},
        build_stage_repo_map_fn=lambda **kwargs: {"enabled": True, "seed_paths": ["src/a.py"], **kwargs},
        store_cached_repomap_fn=lambda **kwargs: calls["store"].append({"kind": "cache", **kwargs}) or True,
        store_cached_repomap_precompute_fn=lambda **kwargs: calls["store"].append({"kind": "precompute", **kwargs}) or True,
    )

    assert payload["enabled"] is True
    assert payload["cache"]["store_written"] is True
    assert payload["precompute"]["store_written"] is True
    assert payload["worktree_seed_count"] == 1
    assert payload["subgraph_seed_count"] == 2
    assert payload["seed_candidates_count"] == 1
    assert [item["kind"] for item in calls["store"]] == ["precompute", "cache"]
    assert calls["store"][0]["meta"]["policy_name"] == "repomap_precompute"
    assert calls["store"][1]["meta"]["policy_name"] == "repomap"
