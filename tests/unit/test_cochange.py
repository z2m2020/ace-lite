from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ace_lite import cochange as cochange_module
from ace_lite.cochange import load_or_build_cochange_matrix, query_cochange_neighbors


def test_query_cochange_neighbors_aggregates_scores() -> None:
    matrix = {
        "src/a.py": {"src/b.py": 2.0, "src/c.py": 1.0},
        "src/x.py": {"src/b.py": 1.5},
    }

    payload = query_cochange_neighbors(matrix=matrix, seed_paths=["src/a.py", "src/x.py"], top_n=2)

    assert [item["path"] for item in payload] == ["src/b.py", "src/c.py"]
    assert payload[0]["score"] == pytest.approx(3.5)


def test_query_cochange_neighbors_normalizes_backslash_seed() -> None:
    matrix = {
        "src/a.py": {"src/b.py": 2.0},
    }

    payload = query_cochange_neighbors(matrix=matrix, seed_paths=[r"src\a.py"], top_n=5)

    assert payload
    assert payload[0]["path"] == "src/b.py"


def test_load_or_build_cochange_matrix_reuses_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)
    call_counter = {"run_git_log": 0}

    def fake_git_head(repo_root: Path) -> str:
        return "deadbeef"

    def fake_run_git_log(*, repo_root: Path, lookback_commits: int):
        call_counter["run_git_log"] += 1
        return [
            (now, ["src/a.py", "src/b.py"]),
            (now, ["src/a.py", "src/c.py"]),
        ]

    monkeypatch.setattr(cochange_module, "_git_head", fake_git_head)
    monkeypatch.setattr(cochange_module, "_run_git_log", fake_run_git_log)
    cochange_module._MEM_CACHE.clear()

    cache_path = tmp_path / "context-map" / "cochange.json"

    first_matrix, first_info = load_or_build_cochange_matrix(
        repo_root=tmp_path,
        cache_path=cache_path,
        lookback_commits=10,
        half_life_days=30.0,
    )
    second_matrix, second_info = load_or_build_cochange_matrix(
        repo_root=tmp_path,
        cache_path=cache_path,
        lookback_commits=10,
        half_life_days=30.0,
    )

    assert call_counter["run_git_log"] == 1
    assert first_info["mode"] == "rebuilt"
    assert second_info["mode"] in {"cache", "memory"}
    assert second_info["cache_hit"] is True
    assert first_matrix == second_matrix
    assert cache_path.exists()


def test_load_or_build_cochange_matrix_neighbor_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(timezone.utc)

    def fake_git_head(repo_root: Path) -> str:
        return "cafebabe"

    def fake_run_git_log(*, repo_root: Path, lookback_commits: int):
        return [
            (now, ["src/a.py", "src/b.py", "src/c.py", "src/d.py"]),
        ]

    monkeypatch.setattr(cochange_module, "_git_head", fake_git_head)
    monkeypatch.setattr(cochange_module, "_run_git_log", fake_run_git_log)
    cochange_module._MEM_CACHE.clear()

    matrix, info = load_or_build_cochange_matrix(
        repo_root=tmp_path,
        cache_path=tmp_path / "context-map" / "cochange.json",
        lookback_commits=10,
        half_life_days=30.0,
        neighbor_cap=2,
    )

    assert info["neighbor_cap"] == 2
    assert matrix
    for targets in matrix.values():
        assert len(targets) <= 2


def test_git_head_uses_timeout_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACE_LITE_GIT_TIMEOUT_SECONDS", "0.25")

    observed: dict[str, object] = {}

    def fake_run_capture_output(*args, **kwargs):
        observed.update(kwargs)
        return 1, "", "", True

    monkeypatch.setattr(cochange_module, "run_capture_output", fake_run_capture_output)

    assert cochange_module._git_head(tmp_path) is None
    assert observed.get("timeout_seconds") == 0.25


def test_run_git_log_uses_timeout_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACE_LITE_GIT_TIMEOUT_SECONDS", "0.25")

    observed: dict[str, object] = {}

    def fake_run_capture_output(*args, **kwargs):
        observed.update(kwargs)
        return 1, "", "", True

    monkeypatch.setattr(cochange_module, "run_capture_output", fake_run_capture_output)

    assert cochange_module._run_git_log(repo_root=tmp_path, lookback_commits=5) == []
    assert observed.get("timeout_seconds") == 0.25
