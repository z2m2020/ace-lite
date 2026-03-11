from __future__ import annotations

from pathlib import Path

import pytest

from ace_lite.index_stage import apply_cochange_neighbors


def test_cochange_rerank_does_not_expand_candidates_by_default(
    tmp_path: Path,
    fake_skill_manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files_map = {
        "src/a.py": {"module": "src.a", "language": "python", "symbols": [], "imports": []},
        "src/b.py": {"module": "src.b", "language": "python", "symbols": [], "imports": []},
    }
    candidates = [{"path": "src/a.py", "score": 2.0, "score_breakdown": {}}]

    monkeypatch.setattr(
        "ace_lite.index_stage.cochange.load_or_build_cochange_matrix",
        lambda **kwargs: (
            {"src/a.py": [{"path": "src/b.py", "score": 1.0}]},
            {"enabled": True, "cache_hit": True, "mode": "cache", "edge_count": 1, "neighbor_cap": 64},
        ),
    )
    monkeypatch.setattr(
        "ace_lite.index_stage.cochange.query_cochange_neighbors",
        lambda **kwargs: [{"path": "src/b.py", "score": 1.0}],
    )

    ranked, payload = apply_cochange_neighbors(
        repo_root=str(tmp_path),
        cache_path=tmp_path / "context-map" / "cochange.json",
        files_map=files_map,
        candidates=candidates,
        memory_paths=[],
        policy={"cochange_weight": 1.0, "cochange_expand_candidates": False},
        lookback_commits=256,
        half_life_days=90.0,
        neighbor_cap=64,
        top_k_files=8,
        top_neighbors=16,
        boost_weight=1.0,
        min_neighbor_score=0.0,
        max_boost=4.0,
    )

    assert len(ranked) == 1
    assert ranked[0]["path"] == "src/a.py"
    assert payload["neighbors_added"] == 0
    assert payload["expand_candidates"] is False


def test_cochange_expand_candidates_when_policy_enabled(
    tmp_path: Path,
    fake_skill_manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files_map = {
        "src/a.py": {"module": "src.a", "language": "python", "symbols": [], "imports": []},
        "src/b.py": {"module": "src.b", "language": "python", "symbols": [], "imports": []},
    }
    candidates = [{"path": "src/a.py", "score": 2.0, "score_breakdown": {}}]

    monkeypatch.setattr(
        "ace_lite.index_stage.cochange.load_or_build_cochange_matrix",
        lambda **kwargs: (
            {"src/a.py": [{"path": "src/b.py", "score": 1.0}]},
            {"enabled": True, "cache_hit": True, "mode": "cache", "edge_count": 1, "neighbor_cap": 64},
        ),
    )
    monkeypatch.setattr(
        "ace_lite.index_stage.cochange.query_cochange_neighbors",
        lambda **kwargs: [{"path": "src/b.py", "score": 1.0}],
    )

    ranked, payload = apply_cochange_neighbors(
        repo_root=str(tmp_path),
        cache_path=tmp_path / "context-map" / "cochange.json",
        files_map=files_map,
        candidates=candidates,
        memory_paths=[],
        policy={"cochange_weight": 1.0, "cochange_expand_candidates": True},
        lookback_commits=256,
        half_life_days=90.0,
        neighbor_cap=64,
        top_k_files=8,
        top_neighbors=16,
        boost_weight=1.0,
        min_neighbor_score=0.0,
        max_boost=4.0,
    )

    paths = [item["path"] for item in ranked]
    assert "src/b.py" in paths
    assert payload["neighbors_added"] == 1
    assert payload["expand_candidates"] is True
