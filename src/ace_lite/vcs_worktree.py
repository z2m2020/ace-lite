from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path
from time import perf_counter
from typing import Any

from ace_lite.subprocess_utils import run_capture_output

_GIT_TERMINAL_ENV = {"GIT_TERMINAL_PROMPT": "0"}
_DEFAULT_TIMEOUT_SECONDS = 0.35
_DEFAULT_MAX_FILES = 64


def _remaining_timeout_seconds(*, started: float, total_timeout_seconds: float) -> float:
    return max(0.0, float(total_timeout_seconds) - (perf_counter() - started))


def collect_git_worktree_summary(
    *,
    repo_root: str | Path,
    max_files: int = _DEFAULT_MAX_FILES,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    if not (root / ".git").exists():
        return {
            "enabled": False,
            "reason": "not_git_repo",
            "changed_count": 0,
            "staged_count": 0,
            "unstaged_count": 0,
            "untracked_count": 0,
            "entries": [],
            "diffstat": {
                "staged": _empty_diffstat(),
                "unstaged": _empty_diffstat(),
            },
        }

    resolved_timeout = (
        float(timeout_seconds)
        if isinstance(timeout_seconds, (int, float))
        else float(os.getenv("ACE_LITE_GIT_WORKTREE_TIMEOUT_SECONDS", "0") or 0.0)
    )
    if resolved_timeout <= 0.0:
        resolved_timeout = _DEFAULT_TIMEOUT_SECONDS

    resolved_max_files = max(1, int(max_files))
    started = perf_counter()

    status_remaining = _remaining_timeout_seconds(
        started=started,
        total_timeout_seconds=resolved_timeout,
    )
    if status_remaining <= 0.0:
        return _fail_payload(
            enabled=True,
            reason="timeout",
            error="status_timeout",
            elapsed_ms=(perf_counter() - started) * 1000.0,
            timeout_seconds=resolved_timeout,
            max_files=resolved_max_files,
        )

    status = _collect_porcelain_status(root=root, timeout_seconds=status_remaining)
    if status.get("timed_out"):
        return _fail_payload(
            enabled=True,
            reason="timeout",
            error="status_timeout",
            elapsed_ms=(perf_counter() - started) * 1000.0,
            timeout_seconds=resolved_timeout,
            max_files=resolved_max_files,
        )
    if status.get("error"):
        return _fail_payload(
            enabled=True,
            reason="error",
            error=str(status.get("error")),
            elapsed_ms=(perf_counter() - started) * 1000.0,
            timeout_seconds=resolved_timeout,
            max_files=resolved_max_files,
        )

    entries = status.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    status_truncated = len(entries) > resolved_max_files

    unstaged_remaining = _remaining_timeout_seconds(
        started=started,
        total_timeout_seconds=resolved_timeout,
    )
    if unstaged_remaining <= 0.0:
        diff_unstaged = _empty_diffstat()
        diff_unstaged["timed_out"] = True
        diff_unstaged["error"] = "timeout"
    else:
        diff_unstaged = _collect_numstat(
            root=root,
            args=["git", "--no-pager", "diff", "--numstat"],
            timeout_seconds=unstaged_remaining,
            max_files=resolved_max_files,
        )

    staged_remaining = _remaining_timeout_seconds(
        started=started,
        total_timeout_seconds=resolved_timeout,
    )
    if staged_remaining <= 0.0:
        diff_staged = _empty_diffstat()
        diff_staged["timed_out"] = True
        diff_staged["error"] = "timeout"
    else:
        diff_staged = _collect_numstat(
            root=root,
            args=["git", "--no-pager", "diff", "--cached", "--numstat"],
            timeout_seconds=staged_remaining,
            max_files=resolved_max_files,
        )

    staged_count, unstaged_count, untracked_count = _count_status_entries(entries)
    changed_count = len(entries)

    elapsed_ms = (perf_counter() - started) * 1000.0
    reason = "ok"
    error: str | None = None
    if diff_unstaged.get("timed_out") or diff_staged.get("timed_out"):
        reason = "partial"
        error = "diff_timeout"
    elif diff_unstaged.get("error") or diff_staged.get("error"):
        reason = "partial"
        error = str(diff_unstaged.get("error") or diff_staged.get("error") or "diff_error")

    truncated = (
        status_truncated
        or bool(status.get("truncated"))
        or bool(diff_unstaged.get("truncated"))
        or bool(diff_staged.get("truncated"))
    )

    return {
        "enabled": True,
        "reason": reason,
        "changed_count": int(changed_count),
        "staged_count": int(staged_count),
        "unstaged_count": int(unstaged_count),
        "untracked_count": int(untracked_count),
        "entries": entries[:resolved_max_files],
        "diffstat": {
            "staged": diff_staged,
            "unstaged": diff_unstaged,
        },
        "error": error,
        "elapsed_ms": round(elapsed_ms, 3),
        "timeout_seconds": float(resolved_timeout),
        "max_files": resolved_max_files,
        "truncated": truncated,
    }


def _fail_payload(
    *,
    enabled: bool,
    reason: str,
    error: str,
    elapsed_ms: float,
    timeout_seconds: float,
    max_files: int,
) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "reason": str(reason),
        "changed_count": 0,
        "staged_count": 0,
        "unstaged_count": 0,
        "untracked_count": 0,
        "entries": [],
        "diffstat": {
            "staged": _empty_diffstat(),
            "unstaged": _empty_diffstat(),
        },
        "error": str(error),
        "elapsed_ms": round(float(elapsed_ms), 3),
        "timeout_seconds": float(timeout_seconds),
        "max_files": int(max_files),
        "truncated": False,
    }


def _empty_diffstat() -> dict[str, Any]:
    return {
        "file_count": 0,
        "binary_count": 0,
        "additions": 0,
        "deletions": 0,
        "files": [],
        "error": None,
        "timed_out": False,
        "truncated": False,
    }


def build_git_worktree_state_token(
    summary: dict[str, Any] | None,
    *,
    max_entries: int = 32,
) -> str:
    payload = summary if isinstance(summary, dict) else {}
    diffstat = payload.get("diffstat", {}) if isinstance(payload.get("diffstat"), dict) else {}
    staged = diffstat.get("staged", {}) if isinstance(diffstat.get("staged"), dict) else {}
    unstaged = (
        diffstat.get("unstaged", {})
        if isinstance(diffstat.get("unstaged"), dict)
        else {}
    )
    entries_raw = payload.get("entries", [])
    entries = entries_raw if isinstance(entries_raw, list) else []
    normalized_entries: list[dict[str, Any]] = []
    for item in entries[: max(1, int(max_entries))]:
        if not isinstance(item, dict):
            continue
        normalized_entries.append(
            {
                "path": str(item.get("path") or "").strip(),
                "status": str(item.get("status") or "").strip(),
                "renamed_from": str(item.get("renamed_from") or "").strip(),
            }
        )
    fingerprint_payload = {
        "enabled": bool(payload.get("enabled", False)),
        "reason": str(payload.get("reason") or "").strip(),
        "changed_count": int(payload.get("changed_count", 0) or 0),
        "staged_count": int(payload.get("staged_count", 0) or 0),
        "unstaged_count": int(payload.get("unstaged_count", 0) or 0),
        "untracked_count": int(payload.get("untracked_count", 0) or 0),
        "truncated": bool(payload.get("truncated", False)),
        "entries": normalized_entries,
        "diffstat": {
            "staged": {
                "file_count": int(staged.get("file_count", 0) or 0),
                "binary_count": int(staged.get("binary_count", 0) or 0),
                "additions": int(staged.get("additions", 0) or 0),
                "deletions": int(staged.get("deletions", 0) or 0),
            },
            "unstaged": {
                "file_count": int(unstaged.get("file_count", 0) or 0),
                "binary_count": int(unstaged.get("binary_count", 0) or 0),
                "additions": int(unstaged.get("additions", 0) or 0),
                "deletions": int(unstaged.get("deletions", 0) or 0),
            },
        },
    }
    text = json.dumps(
        fingerprint_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def _normalize_path(value: str) -> str:
    path = str(value or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def _collect_porcelain_status(*, root: Path, timeout_seconds: float) -> dict[str, Any]:
    returncode, stdout, stderr, timed_out = run_capture_output(
        ["git", "status", "--porcelain", "-z"],
        cwd=root,
        timeout_seconds=max(0.05, float(timeout_seconds)),
        env_overrides=_GIT_TERMINAL_ENV,
    )
    if timed_out:
        return {"timed_out": True, "error": None, "entries": [], "truncated": False}
    if returncode != 0:
        message = str(stderr or stdout or "").strip()[:240]
        return {"timed_out": False, "error": message or f"git_returncode:{returncode}", "entries": [], "truncated": False}

    entries = _parse_porcelain_output(str(stdout or ""))
    return {
        "timed_out": False,
        "error": None,
        "entries": entries,
        "truncated": False,
    }


def _parse_porcelain_output(stdout: str) -> list[dict[str, Any]]:
    text = str(stdout or "")
    if "\0" in text:
        return _parse_porcelain_z(text)
    return _parse_porcelain_lines(text)


def _parse_porcelain_lines(stdout: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for raw in str(stdout or "").splitlines():
        line = str(raw or "").rstrip("\n")
        if not line:
            continue
        status = line[:2]
        path_part = line[2:].lstrip()
        path = _normalize_path(path_part)
        if not path:
            continue
        entries.append(_status_entry(status=status, path=path, renamed_from=None))
    entries.sort(key=lambda item: str(item.get("path") or ""))
    return entries


def _parse_porcelain_z(stdout: str) -> list[dict[str, Any]]:
    parts = [part for part in str(stdout or "").split("\0") if part]
    entries: list[dict[str, Any]] = []

    index = 0
    while index < len(parts):
        token = str(parts[index] or "")
        if len(token) < 2:
            index += 1
            continue

        status = token[:2]
        path_part = token[2:].lstrip()
        path = _normalize_path(path_part)
        if not path:
            index += 1
            continue

        is_rename = status[0] in {"R", "C"} or status[1] in {"R", "C"}
        if is_rename and index + 1 < len(parts):
            new_path = _normalize_path(parts[index + 1])
            if new_path:
                entries.append(_status_entry(status=status, path=new_path, renamed_from=path))
                index += 2
                continue

        entries.append(_status_entry(status=status, path=path, renamed_from=None))
        index += 1

    entries.sort(key=lambda item: str(item.get("path") or ""))
    return entries


def _status_entry(*, status: str, path: str, renamed_from: str | None) -> dict[str, Any]:
    normalized_status = str(status or "")[:2].ljust(2)
    untracked = normalized_status == "??"
    staged = (not untracked) and normalized_status[0] != " "
    unstaged = (not untracked) and normalized_status[1] != " "
    payload: dict[str, Any] = {
        "path": path,
        "status": normalized_status,
        "staged": bool(staged),
        "unstaged": bool(unstaged),
        "untracked": bool(untracked),
    }
    if renamed_from:
        payload["renamed_from"] = str(renamed_from)
    return payload


def _count_status_entries(entries: Iterable[Any]) -> tuple[int, int, int]:
    staged_count = 0
    unstaged_count = 0
    untracked_count = 0
    for item in entries:
        if not isinstance(item, dict):
            continue
        if bool(item.get("untracked")):
            untracked_count += 1
        if bool(item.get("staged")):
            staged_count += 1
        if bool(item.get("unstaged")):
            unstaged_count += 1
    return staged_count, unstaged_count, untracked_count


def _collect_numstat(
    *,
    root: Path,
    args: list[str],
    timeout_seconds: float,
    max_files: int,
) -> dict[str, Any]:
    returncode, stdout, stderr, timed_out = run_capture_output(
        args,
        cwd=root,
        timeout_seconds=max(0.05, float(timeout_seconds)),
        env_overrides=_GIT_TERMINAL_ENV,
    )
    if timed_out:
        payload = _empty_diffstat()
        payload["timed_out"] = True
        payload["error"] = "timeout"
        return payload

    if returncode != 0:
        payload = _empty_diffstat()
        payload["error"] = str(stderr or stdout or "").strip()[:240] or f"git_returncode:{returncode}"
        return payload

    parsed = _parse_numstat(stdout, max_files=max_files)
    return parsed


def _parse_numstat(stdout: str, *, max_files: int) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    additions = 0
    deletions = 0
    binary_count = 0

    for raw in str(stdout or "").splitlines():
        line = str(raw or "").strip()
        if not line:
            continue

        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue

        raw_add, raw_del, raw_path = parts
        path = _normalize_path(raw_path)
        if not path:
            continue

        binary = raw_add.strip() == "-" or raw_del.strip() == "-"
        add_value: int | None
        del_value: int | None
        if binary:
            add_value = None
            del_value = None
            binary_count += 1
        else:
            try:
                add_value = int(raw_add)
            except ValueError:
                add_value = 0
            try:
                del_value = int(raw_del)
            except ValueError:
                del_value = 0
            additions += max(0, int(add_value))
            deletions += max(0, int(del_value))

        files.append(
            {
                "path": path,
                "additions": add_value,
                "deletions": del_value,
                "binary": bool(binary),
            }
        )

    files.sort(key=lambda item: str(item.get("path") or ""))
    truncated = len(files) > max(1, int(max_files))
    limited = files[: max(1, int(max_files))]
    return {
        "file_count": len(files),
        "binary_count": int(binary_count),
        "additions": int(additions),
        "deletions": int(deletions),
        "files": limited,
        "error": None,
        "timed_out": False,
        "truncated": truncated,
    }


__all__ = ["build_git_worktree_state_token", "collect_git_worktree_summary"]
