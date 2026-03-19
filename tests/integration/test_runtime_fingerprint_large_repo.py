from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from ace_lite.runtime_fingerprint import build_git_fast_fingerprint


def _require_launchable_git() -> None:
    if shutil.which("git") is None:
        pytest.skip("git is required for runtime fingerprint integration tests")
    try:
        completed = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        pytest.skip(f"git executable is present but cannot be launched: {exc}")
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        pytest.skip(
            "git executable is present but not launchable for integration tests: "
            f"{message}"
        )


def _run_git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        raise AssertionError(f"git {' '.join(args)} failed: {message}")
    return str(completed.stdout or "")


def _seed_large_dirty_repo(
    tmp_path: Path,
    *,
    tracked_files: int = 160,
    modified_files: int = 96,
    untracked_files: int = 32,
) -> Path:
    _require_launchable_git()

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    _run_git(repo_root, "init")
    _run_git(repo_root, "config", "user.email", "tests@example.com")
    _run_git(repo_root, "config", "user.name", "ACE Lite Tests")

    for index in range(tracked_files):
        path = repo_root / "src" / f"module_{index:04d}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"def value_{index}():\n    return {index}\n",
            encoding="utf-8",
        )

    _run_git(repo_root, "add", ".")
    _run_git(repo_root, "commit", "-m", "seed repo")

    for index in range(modified_files):
        path = repo_root / "src" / f"module_{index:04d}.py"
        path.write_text(
            f"def value_{index}():\n    return {index + 1}\n",
            encoding="utf-8",
        )

    for index in range(untracked_files):
        path = repo_root / "scratch" / f"note_{index:04d}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"dirty-{index}\n", encoding="utf-8")

    return repo_root


def test_runtime_fingerprint_stays_within_budget_on_large_dirty_repo(
    tmp_path: Path,
) -> None:
    repo_root = _seed_large_dirty_repo(tmp_path)

    fingerprint = build_git_fast_fingerprint(
        repo_root=repo_root,
        settings_fingerprint="settings-int-1",
        timeout_seconds=1.0,
        latency_budget_ms=2000.0,
        max_dirty_paths=256,
    )

    assert fingerprint.trust_class == "exact"
    assert fingerprint.timed_out is False
    assert fingerprint.head_commit
    assert fingerprint.dirty_path_count >= 96
    assert fingerprint.elapsed_ms <= 2000.0
    assert fingerprint.metadata is not None
    assert fingerprint.metadata["budget_ms"] == 2000.0
    assert fingerprint.metadata["budget_exhausted"] is False


def test_runtime_fingerprint_downgrades_on_tiny_budget_for_large_dirty_repo(
    tmp_path: Path,
) -> None:
    repo_root = _seed_large_dirty_repo(tmp_path)

    fingerprint = build_git_fast_fingerprint(
        repo_root=repo_root,
        settings_fingerprint="settings-int-2",
        timeout_seconds=1.0,
        latency_budget_ms=5.0,
        max_dirty_paths=256,
    )

    assert fingerprint.trust_class in {"git_partial", "fallback"}
    assert fingerprint.timed_out is True
    assert fingerprint.metadata is not None
    assert fingerprint.metadata["budget_ms"] == 5.0
    assert fingerprint.metadata["budget_exhausted"] is True
    assert fingerprint.metadata["downgrade_reason"] in {
        "timeout",
        "budget_exhausted",
        "latency_budget_exceeded",
    }
