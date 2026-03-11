from __future__ import annotations

from pathlib import Path

from ace_lite.plan_replay_cache import (
    build_plan_component_fingerprint,
    build_plan_replay_cache_key,
    build_repo_root_fingerprint,
    content_version,
    default_plan_replay_cache_path,
    load_cached_plan,
    load_cached_plan_with_meta,
    normalize_plan_query,
    store_cached_plan,
    strip_plan_replay_runtime_metadata,
)


def _shared_cache_kwargs() -> dict[str, object]:
    return {
        "repo_root_fingerprint": "repo-root",
        "temporal_input": {},
        "plugins_loaded": [],
        "conventions_hashes": {},
        "memory_fingerprint": "memory",
        "index_fingerprint": "index",
        "index_hash": "idx",
        "worktree_state_hash": "worktree",
        "retrieval_policy": "auto",
        "policy_version": "v1",
        "candidate_ranker": "rrf_hybrid",
        "budget_knobs": {"chunk_top_k": 24, "skills_token_budget": 800},
        "upstream_fingerprints": {
            "repomap": "repomap",
            "augment": "augment",
            "skills": "skills",
        },
        "content_version": content_version(),
    }


def test_normalize_plan_query_collapses_whitespace() -> None:
    assert normalize_plan_query("  fix   auth   flow \n retry ") == "fix auth flow retry"


def test_build_repo_root_fingerprint_is_stable_for_same_root(tmp_path: Path) -> None:
    first = build_repo_root_fingerprint(repo="ace-lite-engine", root=str(tmp_path))
    second = build_repo_root_fingerprint(
        repo="ace-lite-engine",
        root=str(tmp_path / "."),
    )

    assert first == second


def test_build_plan_component_fingerprint_ignores_excluded_keys() -> None:
    first = build_plan_component_fingerprint(
        {"query": "fix auth flow", "hits": [{"path": "a.py"}]},
        exclude_keys={"query"},
    )
    second = build_plan_component_fingerprint(
        {"query": "  different wording  ", "hits": [{"path": "a.py"}]},
        exclude_keys={"query"},
    )

    assert first == second


def test_build_plan_replay_cache_key_normalizes_query_whitespace() -> None:
    first = build_plan_replay_cache_key(
        normalized_query=normalize_plan_query("fix bug in auth flow"),
        **_shared_cache_kwargs(),
    )
    second = build_plan_replay_cache_key(
        normalized_query=normalize_plan_query("  fix   bug in  auth flow "),
        **_shared_cache_kwargs(),
    )

    assert first == second


def test_build_plan_replay_cache_key_changes_when_budget_knob_changes() -> None:
    first = build_plan_replay_cache_key(
        normalized_query="fix auth flow",
        **_shared_cache_kwargs(),
    )
    changed = dict(_shared_cache_kwargs())
    changed["budget_knobs"] = {"chunk_top_k": 8, "skills_token_budget": 800}
    second = build_plan_replay_cache_key(
        normalized_query="fix auth flow",
        **changed,
    )

    assert first != second


def test_build_plan_replay_cache_key_changes_when_upstream_fingerprint_changes() -> None:
    first = build_plan_replay_cache_key(
        normalized_query="fix auth flow",
        **_shared_cache_kwargs(),
    )
    changed = dict(_shared_cache_kwargs())
    changed["upstream_fingerprints"] = {
        "repomap": "repomap",
        "augment": "augment",
        "skills": "skills-v2",
    }
    second = build_plan_replay_cache_key(
        normalized_query="fix auth flow",
        **changed,
    )

    assert first != second


def test_store_and_load_cached_plan_round_trip(tmp_path: Path) -> None:
    cache_path = default_plan_replay_cache_path(root=str(tmp_path))
    key = "plan-key"
    payload = {
        "query": "fix auth flow",
        "source_plan": {"steps": [{"id": 1, "stage": "index"}]},
    }

    assert store_cached_plan(
        cache_path=cache_path,
        key=key,
        payload=payload,
        meta={"policy_version": "v1"},
    )

    loaded = load_cached_plan(cache_path=cache_path, key=key)
    assert loaded == payload

    assert loaded is not payload
    assert cache_path.exists()


def test_load_cached_plan_fails_open_on_invalid_json(tmp_path: Path) -> None:
    cache_path = default_plan_replay_cache_path(root=str(tmp_path))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{not-json", encoding="utf-8")

    assert load_cached_plan(cache_path=cache_path, key="missing") is None


def test_load_cached_plan_with_meta_reports_backend_origin(tmp_path: Path) -> None:
    cache_path = default_plan_replay_cache_path(root=str(tmp_path))
    payload = {"source_plan": {"steps": [{"id": 1, "stage": "source_plan"}]}}

    assert store_cached_plan(
        cache_path=cache_path,
        key="plan-key",
        payload=payload,
        meta={
            "query": "fix auth flow",
            "stage": "source_plan",
            "trust_class": "exact",
            "policy_name": "source_plan",
        },
    )

    loaded, meta = load_cached_plan_with_meta(cache_path=cache_path, key="plan-key")

    assert loaded == payload
    assert meta["origin"] == "stage_artifact_cache"
    assert meta["policy_name"] == "source_plan"
    assert meta["trust_class"] == "exact"
    assert float(meta["age_seconds"]) >= 0.0


def test_strip_plan_replay_runtime_metadata_removes_cache_observability() -> None:
    payload = {
        "observability": {
            "total_ms": 12.3,
            "plan_replay_cache": {"hit": True},
        },
        "source_plan": {"steps": []},
    }

    stripped = strip_plan_replay_runtime_metadata(payload)

    assert stripped["observability"] == {"total_ms": 12.3}
    assert payload["observability"]["plan_replay_cache"] == {"hit": True}
