from __future__ import annotations

from pathlib import Path

from ace_lite.vcs_history import collect_git_head_snapshot
from ace_lite.vcs_history import collect_git_commit_history


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
