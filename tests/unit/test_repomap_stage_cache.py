from __future__ import annotations

import json
from pathlib import Path

import ace_lite.pipeline.stages.repomap as repomap_stage
from ace_lite.pipeline.stages.repomap import run_repomap
from ace_lite.pipeline.types import StageContext


def test_run_repomap_uses_cache_with_index_and_worktree_hash(tmp_path: Path) -> None:
    files_map = {
        "src/a.py": {
            "language": "python",
            "module": "src.a",
            "symbols": [{"name": "a", "qualified_name": "src.a.a"}],
            "imports": [{"module": "src.b"}],
        },
        "src/b.py": {
            "language": "python",
            "module": "src.b",
            "symbols": [{"name": "b", "qualified_name": "src.b.b"}],
            "imports": [],
        },
    }
    index_payload = {
        "candidate_files": [{"path": "src/b.py", "score": 1.0}],
        "index_hash": "idx-hash-1",
        "worktree_prior": {
            "changed_paths": ["src/a.py"],
            "seed_paths": ["src/a.py", "src/b.py"],
            "state_hash": "worktree-hash-1",
        },
    }
    ctx = StageContext(
        query="how does module b call module a",
        repo="ace-lite-engine",
        root=str(tmp_path),
        state={
            "index": index_payload,
            "__index_files": files_map,
        },
    )

    first = run_repomap(
        ctx=ctx,
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_top_k=4,
        repomap_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        policy_version="v1",
    )
    second = run_repomap(
        ctx=ctx,
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_top_k=4,
        repomap_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        policy_version="v1",
    )

    assert first["enabled"] is True
    assert first["cache"]["hit"] is False
    assert first["cache"]["store_written"] is True
    assert first["precompute"]["hit"] is False
    assert first["precompute"]["store_written"] is True
    assert first["worktree_seed_count"] == 1
    assert Path(first["cache"]["path"]).exists()
    assert Path(first["precompute"]["path"]).exists()

    assert second["enabled"] is True
    assert second["cache"]["hit"] is True
    assert second["precompute"]["hit"] is True
    assert second["precompute"]["store_written"] is False
    assert second["cache"]["cache_key"] == first["cache"]["cache_key"]
    assert second["precompute"]["cache_key"] == first["precompute"]["cache_key"]
    assert second["seed_paths"] == first["seed_paths"]


def test_run_repomap_ignores_docs_hint_candidates_for_cache_key(tmp_path: Path) -> None:
    files_map = {
        "src/a.py": {
            "language": "python",
            "module": "src.a",
            "symbols": [{"name": "a", "qualified_name": "src.a.a"}],
            "imports": [],
        },
        "src/b.py": {
            "language": "python",
            "module": "src.b",
            "symbols": [{"name": "b", "qualified_name": "src.b.b"}],
            "imports": [{"module": "src.a"}],
        },
    }
    index_payload = {
        "candidate_files": [
            {"path": "src/b.py", "score": 1.0},
            {"path": "src/a.py", "score": 999.0, "retrieval_pass": "docs_hint"},
        ],
        "index_hash": "idx-hash-docs-hints",
        "worktree_prior": {
            "changed_paths": [],
            "seed_paths": ["src/b.py"],
            "state_hash": "worktree-hash-docs-hints",
        },
    }
    ctx = StageContext(
        query="how is module b related to module a",
        repo="ace-lite-engine",
        root=str(tmp_path),
        state={
            "index": index_payload,
            "__index_files": files_map,
        },
    )

    first = run_repomap(
        ctx=ctx,
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_top_k=4,
        repomap_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        policy_version="v1",
    )
    second = run_repomap(
        ctx=ctx,
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_top_k=4,
        repomap_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        policy_version="v1",
    )

    assert first["enabled"] is True
    assert "src/a.py" not in first["seed_paths"]
    assert second["cache"]["hit"] is True
    assert second["cache"]["cache_key"] == first["cache"]["cache_key"]


def test_run_repomap_invalidates_cache_when_policy_version_changes(tmp_path: Path) -> None:
    files_map = {
        "src/a.py": {
            "language": "python",
            "module": "src.a",
            "symbols": [{"name": "a", "qualified_name": "src.a.a"}],
            "imports": [{"module": "src.b"}],
        },
        "src/b.py": {
            "language": "python",
            "module": "src.b",
            "symbols": [{"name": "b", "qualified_name": "src.b.b"}],
            "imports": [],
        },
    }
    index_payload = {
        "candidate_files": [{"path": "src/b.py", "score": 1.0}],
        "index_hash": "idx-hash-1",
        "worktree_prior": {
            "changed_paths": ["src/a.py"],
            "seed_paths": ["src/a.py", "src/b.py"],
            "state_hash": "worktree-hash-1",
        },
    }
    ctx = StageContext(
        query="how does module b call module a",
        repo="ace-lite-engine",
        root=str(tmp_path),
        state={"index": index_payload, "__index_files": files_map},
    )

    first = run_repomap(
        ctx=ctx,
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_top_k=4,
        repomap_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        policy_version="v1",
    )
    second = run_repomap(
        ctx=ctx,
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_top_k=4,
        repomap_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        policy_version="v2",
    )

    assert first["cache"]["hit"] is False
    assert first["precompute"]["hit"] is False
    assert second["cache"]["hit"] is False
    assert second["precompute"]["hit"] is False
    assert second["cache"]["store_written"] is True
    assert second["precompute"]["store_written"] is True


def test_run_repomap_invalidates_full_cache_when_content_version_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    files_map = {
        "src/a.py": {
            "language": "python",
            "module": "src.a",
            "symbols": [{"name": "a", "qualified_name": "src.a.a"}],
            "imports": [{"module": "src.b"}],
        },
        "src/b.py": {
            "language": "python",
            "module": "src.b",
            "symbols": [{"name": "b", "qualified_name": "src.b.b"}],
            "imports": [],
        },
    }
    index_payload = {
        "candidate_files": [{"path": "src/b.py", "score": 1.0}],
        "index_hash": "idx-hash-content-version",
        "worktree_prior": {
            "changed_paths": [],
            "seed_paths": ["src/b.py"],
            "state_hash": "worktree-hash-content-version",
        },
    }
    ctx = StageContext(
        query="trace repomap content version cache behavior",
        repo="ace-lite-engine",
        root=str(tmp_path),
        state={"index": index_payload, "__index_files": files_map},
    )

    first = run_repomap(
        ctx=ctx,
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_top_k=4,
        repomap_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        policy_version="v1",
    )

    monkeypatch.setattr(
        repomap_stage,
        "_REPOMAP_CACHE_CONTENT_VERSION",
        "stage-repomap-vNEXT",
    )

    second = run_repomap(
        ctx=ctx,
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_top_k=4,
        repomap_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        policy_version="v1",
    )

    assert first["cache"]["hit"] is False
    assert first["precompute"]["hit"] is False
    assert first["cache"]["content_version"] == "stage-repomap-v3"
    assert second["cache"]["hit"] is False
    assert second["cache"]["store_written"] is True
    assert second["cache"]["content_version"] == "stage-repomap-vNEXT"
    assert second["precompute"]["hit"] is True
    assert second["precompute"]["store_written"] is False


def test_run_repomap_ttl_expiry_invalidates_cache(tmp_path: Path) -> None:
    files_map = {
        "src/a.py": {
            "language": "python",
            "module": "src.a",
            "symbols": [{"name": "a", "qualified_name": "src.a.a"}],
            "imports": [{"module": "src.b"}],
        },
        "src/b.py": {
            "language": "python",
            "module": "src.b",
            "symbols": [{"name": "b", "qualified_name": "src.b.b"}],
            "imports": [],
        },
    }
    index_payload = {
        "candidate_files": [{"path": "src/b.py", "score": 1.0}],
        "index_hash": "idx-hash-2",
        "worktree_prior": {
            "changed_paths": [],
            "seed_paths": ["src/b.py"],
            "state_hash": "worktree-hash-2",
        },
    }
    ctx = StageContext(
        query="trace repomap cache behavior",
        repo="ace-lite-engine",
        root=str(tmp_path),
        state={
            "index": index_payload,
            "__index_files": files_map,
            "__policy": {
                "name": "general",
                "version": "v1",
                "repomap_cache_ttl_seconds": 1,
                "repomap_precompute_ttl_seconds": 1,
            },
        },
    )

    first = run_repomap(
        ctx=ctx,
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_top_k=4,
        repomap_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        policy_version="v1",
    )
    assert first["cache"]["hit"] is False
    assert first["precompute"]["hit"] is False

    cache_path = Path(first["cache"]["path"])
    precompute_path = Path(first["precompute"]["path"])
    cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
    precompute_payload = json.loads(precompute_path.read_text(encoding="utf-8"))
    cache_payload["entries"][0]["updated_at_epoch"] = 0.0
    precompute_payload["entries"][0]["updated_at_epoch"] = 0.0
    cache_path.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    precompute_path.write_text(
        json.dumps(precompute_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    second = run_repomap(
        ctx=ctx,
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_top_k=4,
        repomap_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        policy_version="v1",
    )

    assert second["cache"]["ttl_seconds"] == 1
    assert second["precompute"]["ttl_seconds"] == 1
    assert second["cache"]["hit"] is False
    assert second["precompute"]["hit"] is False


def test_run_repomap_invalidates_precompute_cache_when_content_version_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    files_map = {
        "src/a.py": {
            "language": "python",
            "module": "src.a",
            "symbols": [{"name": "a", "qualified_name": "src.a.a"}],
            "imports": [{"module": "src.b"}],
        },
        "src/b.py": {
            "language": "python",
            "module": "src.b",
            "symbols": [{"name": "b", "qualified_name": "src.b.b"}],
            "imports": [],
        },
    }
    index_payload = {
        "candidate_files": [{"path": "src/a.py", "score": 1.0}],
        "index_hash": "idx-hash-precompute-version",
        "worktree_prior": {
            "changed_paths": [],
            "seed_paths": ["src/a.py"],
            "state_hash": "worktree-hash-precompute-version",
        },
    }
    ctx = StageContext(
        query="trace repomap precompute version invalidation",
        repo="ace-lite-engine",
        root=str(tmp_path),
        state={"index": index_payload, "__index_files": files_map},
    )

    first = run_repomap(
        ctx=ctx,
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_top_k=4,
        repomap_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        policy_version="v1",
    )

    monkeypatch.setattr(
        repomap_stage,
        "_REPOMAP_PRECOMPUTE_CONTENT_VERSION",
        "stage-precompute-vNEXT",
    )

    second = run_repomap(
        ctx=ctx,
        repomap_enabled=True,
        repomap_neighbor_limit=8,
        repomap_budget_tokens=256,
        repomap_top_k=4,
        repomap_ranking_profile="graph_seeded",
        repomap_signal_weights=None,
        policy_version="v1",
    )

    assert first["cache"]["hit"] is False
    assert first["precompute"]["hit"] is False
    assert first["precompute"]["content_version"] == "stage-precompute-v2"
    assert second["precompute"]["hit"] is False
    assert second["precompute"]["store_written"] is True
    assert second["precompute"]["content_version"] == "stage-precompute-vNEXT"
    assert second["cache"]["hit"] is False
    assert second["cache"]["store_written"] is True
    assert second["cache"]["precompute_content_version"] == "stage-precompute-vNEXT"
