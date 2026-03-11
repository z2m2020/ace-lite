from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.subprocess_utils import run_capture_output

_GIT_TERMINAL_ENV = {"GIT_TERMINAL_PROMPT": "0"}
_COMMIT_MARKER = "__ACE_COMMIT__"
_DEFAULT_TIMEOUT_SECONDS = 0.35


def collect_git_head_snapshot(
    *,
    repo_root: str | Path,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    if not (root / ".git").exists():
        return {
            "enabled": False,
            "reason": "not_git_repo",
            "head_commit": "",
            "head_ref": "",
            "error": None,
        }

    resolved_timeout = (
        float(timeout_seconds)
        if isinstance(timeout_seconds, (int, float))
        else float(os.getenv("ACE_LITE_GIT_HISTORY_TIMEOUT_SECONDS", "0") or 0.0)
    )
    if resolved_timeout <= 0.0:
        resolved_timeout = _DEFAULT_TIMEOUT_SECONDS

    started = perf_counter()
    head_code, head_stdout, head_stderr, head_timed_out = run_capture_output(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        timeout_seconds=max(0.05, float(resolved_timeout)),
        env_overrides=_GIT_TERMINAL_ENV,
    )
    if head_timed_out:
        return {
            "enabled": True,
            "reason": "timeout",
            "head_commit": "",
            "head_ref": "",
            "error": "timeout",
            "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
            "timeout_seconds": float(resolved_timeout),
        }
    if head_code != 0:
        error = str(head_stderr or head_stdout or "").strip()[:240]
        return {
            "enabled": True,
            "reason": "error",
            "head_commit": "",
            "head_ref": "",
            "error": error or f"git_returncode:{head_code}",
            "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
            "timeout_seconds": float(resolved_timeout),
        }

    ref_code, ref_stdout, ref_stderr, ref_timed_out = run_capture_output(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=root,
        timeout_seconds=max(0.05, float(resolved_timeout)),
        env_overrides=_GIT_TERMINAL_ENV,
    )
    head_ref = ""
    reason = "ok"
    error = None
    if ref_timed_out:
        reason = "partial"
        error = "head_ref_timeout"
    elif ref_code == 0:
        head_ref = str(ref_stdout or "").strip()
    elif ref_code != 0:
        reason = "partial"
        error = str(ref_stderr or ref_stdout or "").strip()[:240] or f"git_returncode:{ref_code}"

    return {
        "enabled": True,
        "reason": reason,
        "head_commit": str(head_stdout or "").strip(),
        "head_ref": head_ref,
        "error": error,
        "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
        "timeout_seconds": float(resolved_timeout),
    }


def collect_git_commit_history(
    *,
    repo_root: str | Path,
    paths: Sequence[str],
    limit: int = 12,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    if not (root / ".git").exists():
        return {
            "enabled": False,
            "reason": "not_git_repo",
            "path_count": 0,
            "commit_count": 0,
            "commits": [],
        }

    normalized_paths: list[str] = []
    for item in paths:
        value = str(item or "").strip().replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        if value and value not in normalized_paths:
            normalized_paths.append(value)

    if not normalized_paths:
        return {
            "enabled": False,
            "reason": "no_paths",
            "path_count": 0,
            "commit_count": 0,
            "commits": [],
        }

    resolved_timeout = (
        float(timeout_seconds)
        if isinstance(timeout_seconds, (int, float))
        else float(os.getenv("ACE_LITE_GIT_HISTORY_TIMEOUT_SECONDS", "0") or 0.0)
    )
    if resolved_timeout <= 0.0:
        resolved_timeout = _DEFAULT_TIMEOUT_SECONDS

    resolved_limit = max(1, int(limit))

    command = [
        "git",
        "--no-pager",
        "log",
        f"-n{resolved_limit}",
        "--date=iso-strict",
        "--name-only",
        f"--pretty=format:{_COMMIT_MARKER}|%H|%cI|%an|%s",
        "--",
        *normalized_paths,
    ]

    started = perf_counter()
    returncode, stdout, stderr, timed_out = run_capture_output(
        command,
        cwd=root,
        timeout_seconds=max(0.05, float(resolved_timeout)),
        env_overrides=_GIT_TERMINAL_ENV,
    )
    elapsed_ms = (perf_counter() - started) * 1000.0

    if timed_out:
        return {
            "enabled": True,
            "reason": "timeout",
            "path_count": len(normalized_paths),
            "commit_count": 0,
            "commits": [],
            "error": "timeout",
            "elapsed_ms": round(elapsed_ms, 3),
            "timeout_seconds": float(resolved_timeout),
            "limit": resolved_limit,
        }

    if returncode != 0:
        error = str(stderr or stdout or "").strip()[:240]
        return {
            "enabled": True,
            "reason": "error",
            "path_count": len(normalized_paths),
            "commit_count": 0,
            "commits": [],
            "error": error or f"git_returncode:{returncode}",
            "elapsed_ms": round(elapsed_ms, 3),
            "timeout_seconds": float(resolved_timeout),
            "limit": resolved_limit,
        }

    commits = _parse_git_log_output(str(stdout or ""))
    return {
        "enabled": True,
        "reason": "ok" if commits else "no_commits",
        "path_count": len(normalized_paths),
        "commit_count": len(commits),
        "commits": commits,
        "error": None,
        "elapsed_ms": round(elapsed_ms, 3),
        "timeout_seconds": float(resolved_timeout),
        "limit": resolved_limit,
    }


def _parse_git_log_output(stdout: str) -> list[dict[str, Any]]:
    commits: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        files = current.get("files")
        if not isinstance(files, list):
            current["files"] = []
        commits.append(current)
        current = None

    for raw in str(stdout or "").splitlines():
        line = str(raw or "").strip()
        if not line:
            continue

        if line.startswith(f"{_COMMIT_MARKER}|"):
            flush()
            parts = line.split("|", 4)
            commit_hash = parts[1].strip() if len(parts) > 1 else ""
            committed_at = parts[2].strip() if len(parts) > 2 else ""
            author = parts[3].strip() if len(parts) > 3 else ""
            subject = parts[4].strip() if len(parts) > 4 else ""
            if len(subject) > 240:
                subject = subject[:240].rstrip() + "..."
            current = {
                "hash": commit_hash,
                "committed_at": committed_at,
                "author": author,
                "subject": subject,
                "files": [],
            }
            continue

        if current is None:
            continue

        normalized = line.replace("\\", "/").lstrip("./")
        if normalized:
            files = current.get("files", [])
            if isinstance(files, list) and normalized not in files:
                files.append(normalized)

    flush()

    normalized_commits: list[dict[str, Any]] = []
    for item in commits:
        if not isinstance(item, dict):
            continue
        commit_hash = str(item.get("hash") or "").strip()
        if not commit_hash:
            continue
        normalized_commits.append(item)
    return normalized_commits


__all__ = ["collect_git_commit_history", "collect_git_head_snapshot"]
