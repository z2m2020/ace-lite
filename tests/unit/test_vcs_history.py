from __future__ import annotations

from pathlib import Path

import ace_lite.vcs_history as vcs_history_module
from ace_lite.vcs_history import collect_git_commit_history, collect_git_head_snapshot


def test_collect_git_commit_history_skips_when_not_git_repo(tmp_path: Path) -> None:
    payload = collect_git_commit_history(repo_root=tmp_path, paths=["src/app.py"])

    assert payload["enabled"] is False
    assert payload["reason"] == "not_git_repo"
    assert payload["commit_count"] == 0


def test_collect_git_commit_history_parses_git_log_output(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)

    stdout = "\n".join(
        [
            "__ACE_COMMIT__|abc123|2026-02-14T00:00:00+00:00|Alice|Fix bug",
            "src/app.py",
            "",
            "__ACE_COMMIT__|def456|2026-02-13T00:00:00+00:00|Bob|Refactor code",
            "src/app.py",
            "src/util.py",
            "",
        ]
    )

    def fake_run_capture_output(*_args, **_kwargs):
        return 0, stdout, "", False

    monkeypatch.setattr("ace_lite.vcs_history.run_capture_output", fake_run_capture_output)

    payload = collect_git_commit_history(
        repo_root=tmp_path,
        paths=["./src/app.py", "src/app.py"],
        limit=5,
        timeout_seconds=0.05,
    )

    assert payload["enabled"] is True
    assert payload["reason"] == "ok"
    assert payload["path_count"] == 1
    assert payload["commit_count"] == 2
    assert payload["commits"][0]["hash"] == "abc123"
    assert payload["commits"][0]["files"] == ["src/app.py"]
    assert payload["commits"][1]["files"] == ["src/app.py", "src/util.py"]


def test_collect_git_head_snapshot_reads_head_and_branch(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)

    def fake_run_capture_output(args, *, cwd, timeout_seconds, env_overrides=None):
        _ = (cwd, timeout_seconds, env_overrides)
        command = list(args)
        if command == ["git", "rev-parse", "HEAD"]:
            return 0, "abc123\n", "", False
        if command == ["git", "symbolic-ref", "--short", "HEAD"]:
            return 0, "main\n", "", False
        return 1, "", "unexpected", False

    monkeypatch.setattr("ace_lite.vcs_history.run_capture_output", fake_run_capture_output)

    payload = collect_git_head_snapshot(repo_root=tmp_path, timeout_seconds=0.05)

    assert payload["enabled"] is True
    assert payload["reason"] == "ok"
    assert payload["head_commit"] == "abc123"
    assert payload["head_ref"] == "main"


def test_collect_git_commit_history_reuses_in_memory_cache(
    tmp_path: Path, monkeypatch
) -> None:
    git_dir = tmp_path / ".git"
    refs_dir = git_dir / "refs" / "heads"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (refs_dir / "main").write_text("abc123\n", encoding="utf-8")

    calls: list[list[str]] = []
    stdout = "\n".join(
        [
            "__ACE_COMMIT__|abc123|2026-02-14T00:00:00+00:00|Alice|Fix bug",
            "src/app.py",
            "",
        ]
    )

    def fake_run_capture_output(args, *, cwd, timeout_seconds, env_overrides=None):
        _ = (cwd, timeout_seconds, env_overrides)
        calls.append(list(args))
        return 0, stdout, "", False

    monkeypatch.setattr("ace_lite.vcs_history.run_capture_output", fake_run_capture_output)
    monkeypatch.setattr(vcs_history_module, "_GIT_COMMIT_HISTORY_MEMORY", {})

    first = collect_git_commit_history(
        repo_root=tmp_path,
        paths=["src/app.py"],
        limit=5,
        timeout_seconds=0.05,
    )
    second = collect_git_commit_history(
        repo_root=tmp_path,
        paths=["src/app.py"],
        limit=5,
        timeout_seconds=0.05,
    )

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert second["cached_elapsed_ms"] == first["elapsed_ms"]
    assert second["commits"] == first["commits"]
    assert len(calls) == 1
    assert calls[0][:4] == ["git", "--no-pager", "log", "-n5"]


def test_collect_git_commit_history_cache_invalidates_when_head_changes(
    tmp_path: Path, monkeypatch
) -> None:
    git_dir = tmp_path / ".git"
    refs_dir = git_dir / "refs" / "heads"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    ref_path = refs_dir / "main"
    ref_path.write_text("abc123\n", encoding="utf-8")

    calls: list[int] = []

    def fake_run_capture_output(args, *, cwd, timeout_seconds, env_overrides=None):
        _ = (args, cwd, timeout_seconds, env_overrides)
        calls.append(1)
        if len(calls) == 1:
            stdout = "\n".join(
                [
                    "__ACE_COMMIT__|abc123|2026-02-14T00:00:00+00:00|Alice|Fix bug",
                    "src/app.py",
                    "",
                ]
            )
        else:
            stdout = "\n".join(
                [
                    "__ACE_COMMIT__|def456|2026-02-15T00:00:00+00:00|Bob|Follow-up fix",
                    "src/app.py",
                    "",
                ]
            )
        return 0, stdout, "", False

    monkeypatch.setattr("ace_lite.vcs_history.run_capture_output", fake_run_capture_output)
    monkeypatch.setattr(vcs_history_module, "_GIT_COMMIT_HISTORY_MEMORY", {})

    first = collect_git_commit_history(
        repo_root=tmp_path,
        paths=["src/app.py"],
        limit=5,
        timeout_seconds=0.05,
    )

    ref_path.write_text("def456\n", encoding="utf-8")

    second = collect_git_commit_history(
        repo_root=tmp_path,
        paths=["src/app.py"],
        limit=5,
        timeout_seconds=0.05,
    )

    assert len(calls) == 2
    assert first["commits"][0]["hash"] == "abc123"
    assert second["commits"][0]["hash"] == "def456"


def test_collect_git_commit_history_cache_hit_returns_nested_isolated_payload(
    tmp_path: Path, monkeypatch
) -> None:
    git_dir = tmp_path / ".git"
    refs_dir = git_dir / "refs" / "heads"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (refs_dir / "main").write_text("abc123\n", encoding="utf-8")

    calls: list[list[str]] = []
    stdout = "\n".join(
        [
            "__ACE_COMMIT__|abc123|2026-02-14T00:00:00+00:00|Alice|Fix bug",
            "src/app.py",
            "",
        ]
    )

    def fake_run_capture_output(args, *, cwd, timeout_seconds, env_overrides=None):
        _ = (cwd, timeout_seconds, env_overrides)
        calls.append(list(args))
        return 0, stdout, "", False

    monkeypatch.setattr("ace_lite.vcs_history.run_capture_output", fake_run_capture_output)
    monkeypatch.setattr(vcs_history_module, "_GIT_COMMIT_HISTORY_MEMORY", {})

    first = collect_git_commit_history(
        repo_root=tmp_path,
        paths=["src/app.py"],
        limit=5,
        timeout_seconds=0.05,
    )
    second = collect_git_commit_history(
        repo_root=tmp_path,
        paths=["src/app.py"],
        limit=5,
        timeout_seconds=0.05,
    )

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True

    second["commits"][0]["hash"] = "mutated"
    second["commits"][0]["files"][0] = "src/changed.py"

    third = collect_git_commit_history(
        repo_root=tmp_path,
        paths=["src/app.py"],
        limit=5,
        timeout_seconds=0.05,
    )

    assert third["cache_hit"] is True
    assert third["commits"][0]["hash"] == "abc123"
    assert third["commits"][0]["files"] == ["src/app.py"]
    assert len(calls) == 1
