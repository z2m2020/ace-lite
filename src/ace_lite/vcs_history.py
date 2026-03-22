from __future__ import annotations

import copy
import os
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.subprocess_utils import run_capture_output

_GIT_TERMINAL_ENV = {"GIT_TERMINAL_PROMPT": "0"}
_COMMIT_MARKER = "__ACE_COMMIT__"
_DEFAULT_TIMEOUT_SECONDS = 0.35
_GIT_COMMIT_HISTORY_MEMORY: dict[
    tuple[str, str, tuple[str, ...], int], dict[str, Any]
] = {}


def _read_git_ref_sha(*, git_dir: Path, ref: str) -> str:
    ref_name = str(ref or "").strip()
    if not ref_name:
        return ""

    ref_path = git_dir / ref_name
    if ref_path.exists() and ref_path.is_file():
        try:
            return ref_path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return ""

    packed_refs = git_dir / "packed-refs"
    if not packed_refs.exists() or not packed_refs.is_file():
        return ""
    try:
        lines = packed_refs.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    suffix = f" {ref_name}"
    for line in lines:
        text = str(line or "").strip()
        if not text or text.startswith("#") or text.startswith("^"):
            continue
        if text.endswith(suffix):
            return text.split(" ", 1)[0].strip()
    return ""


def _read_git_head_commit_fast(*, repo_root: Path) -> str:
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return ""
    head_path = git_dir / "HEAD"
    if not head_path.exists() or not head_path.is_file():
        return ""
    try:
        head_raw = head_path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    if not head_raw:
        return ""
    if head_raw.lower().startswith("ref:"):
        ref_name = head_raw.split(":", 1)[1].strip()
        return _read_git_ref_sha(git_dir=git_dir, ref=ref_name)
    return head_raw


def _read_git_head_ref_fast(*, repo_root: Path) -> str:
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return ""
    head_path = git_dir / "HEAD"
    if not head_path.exists() or not head_path.is_file():
        return ""
    try:
        head_raw = head_path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    if not head_raw or not head_raw.lower().startswith("ref:"):
        return ""
    ref_name = head_raw.split(":", 1)[1].strip()
    if ref_name.startswith("refs/heads/"):
        return ref_name[len("refs/heads/") :]
    return ref_name


def _build_commit_history_cache_key(
    *,
    repo_root: Path,
    normalized_paths: Sequence[str],
    limit: int,
) -> tuple[str, str, tuple[str, ...], int] | None:
    head_commit = _read_git_head_commit_fast(repo_root=repo_root)
    if not head_commit:
        return None
    return (
        str(repo_root.resolve()),
        head_commit,
        tuple(str(item) for item in normalized_paths),
        int(limit),
    )


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
    head_commit_fast = _read_git_head_commit_fast(repo_root=root)
    if head_commit_fast:
        head_ref_fast = _read_git_head_ref_fast(repo_root=root)
        return {
            "enabled": True,
            "reason": "ok" if head_ref_fast else "partial",
            "head_commit": head_commit_fast,
            "head_ref": head_ref_fast,
            "error": None if head_ref_fast else "head_ref_unavailable",
            "elapsed_ms": round((perf_counter() - started) * 1000.0, 3),
            "timeout_seconds": float(resolved_timeout),
        }

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
    started = perf_counter()
    cache_key = _build_commit_history_cache_key(
        repo_root=root,
        normalized_paths=normalized_paths,
        limit=resolved_limit,
    )
    if cache_key is not None:
        cached = _GIT_COMMIT_HISTORY_MEMORY.get(cache_key)
        if isinstance(cached, dict):
            materialized = copy.deepcopy(cached)
            cached_elapsed_ms = max(
                0.0, float(materialized.get("elapsed_ms", 0.0) or 0.0)
            )
            materialized["cache_hit"] = True
            materialized["cached_elapsed_ms"] = cached_elapsed_ms
            materialized["elapsed_ms"] = round(
                (perf_counter() - started) * 1000.0,
                3,
            )
            return materialized

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
    payload = {
        "enabled": True,
        "reason": "ok" if commits else "no_commits",
        "path_count": len(normalized_paths),
        "commit_count": len(commits),
        "commits": commits,
        "error": None,
        "elapsed_ms": round(elapsed_ms, 3),
        "timeout_seconds": float(resolved_timeout),
        "limit": resolved_limit,
        "cache_hit": False,
    }
    if cache_key is not None:
        _GIT_COMMIT_HISTORY_MEMORY[cache_key] = copy.deepcopy(payload)
    return payload


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
