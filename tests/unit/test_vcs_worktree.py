from __future__ import annotations

from pathlib import Path

from ace_lite.vcs_worktree import build_git_worktree_state_token
from ace_lite.vcs_worktree import collect_git_worktree_summary


def test_collect_git_worktree_summary_skips_when_not_git_repo(tmp_path: Path) -> None:
    payload = collect_git_worktree_summary(repo_root=tmp_path)

    assert payload["enabled"] is False
    assert payload["reason"] == "not_git_repo"
    assert payload["changed_count"] == 0


def test_collect_git_worktree_summary_parses_status_and_diffstat(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)

    status_stdout = "\0".join(
        [
            " M src/app.py",
            "?? new.txt",
            "R  old.py",
            "new.py",
            "",
        ]
    )
    diff_unstaged_stdout = "\n".join(
        [
            "3\t1\tsrc/app.py",
            "-\t-\tbin.dat",
            "",
        ]
    )
    diff_staged_stdout = "\n".join(
        [
            "10\t0\tsrc/app.py",
            "",
        ]
    )

    def fake_run_capture_output(args, *, cwd, timeout_seconds, env_overrides=None):
        command = list(args)
        if command[:3] == ["git", "status", "--porcelain"]:
            return 0, status_stdout, "", False
        if command[:4] == ["git", "--no-pager", "diff", "--numstat"]:
            return 0, diff_unstaged_stdout, "", False
        if command[:5] == ["git", "--no-pager", "diff", "--cached", "--numstat"]:
            return 0, diff_staged_stdout, "", False
        return 1, "", "unexpected", False

    monkeypatch.setattr(
        "ace_lite.vcs_worktree.run_capture_output", fake_run_capture_output
    )

    payload = collect_git_worktree_summary(
        repo_root=tmp_path,
        max_files=2,
        timeout_seconds=0.05,
    )

    assert payload["enabled"] is True
    assert payload["reason"] == "ok"
    assert payload["changed_count"] == 3
    assert payload["staged_count"] == 1
    assert payload["unstaged_count"] == 1
    assert payload["untracked_count"] == 1
    assert payload["truncated"] is True

    assert payload["entries"][0]["path"] == "new.py"
    assert payload["entries"][0]["renamed_from"] == "old.py"
    assert payload["entries"][0]["staged"] is True

    diffstat = payload["diffstat"]
    assert diffstat["unstaged"]["file_count"] == 2
    assert diffstat["unstaged"]["binary_count"] == 1
    assert diffstat["unstaged"]["additions"] == 3
    assert diffstat["unstaged"]["deletions"] == 1
    assert diffstat["staged"]["file_count"] == 1
    assert diffstat["staged"]["additions"] == 10


def test_build_git_worktree_state_token_is_stable() -> None:
    payload = {
        "enabled": True,
        "reason": "ok",
        "changed_count": 1,
        "staged_count": 1,
        "unstaged_count": 0,
        "untracked_count": 0,
        "entries": [{"path": "src/app.py", "status": "M ", "renamed_from": ""}],
        "diffstat": {
            "staged": {"file_count": 1, "binary_count": 0, "additions": 3, "deletions": 1},
            "unstaged": {"file_count": 0, "binary_count": 0, "additions": 0, "deletions": 0},
        },
    }

    first = build_git_worktree_state_token(payload)
    second = build_git_worktree_state_token(dict(payload))

    assert first == second
