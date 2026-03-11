from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable
from typing import Any

from ace_lite.vcs_history import collect_git_head_snapshot
from ace_lite.vcs_worktree import (
    build_git_worktree_state_token,
    collect_git_worktree_summary,
)


GIT_FAST_FINGERPRINT_TRUST_CLASSES = ("exact", "git_partial", "fallback")


def _normalize_text(value: Any, *, max_len: int = 255) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return " ".join(raw.split())[:max_len]


def _normalize_float(value: Any) -> float:
    try:
        parsed = float(value)
    except Exception:
        return 0.0
    if parsed < 0.0:
        return 0.0
    return round(parsed, 6)


def _normalize_count(value: Any) -> int:
    try:
        parsed = int(value)
    except Exception:
        return 0
    return max(0, parsed)


def _normalize_budget_ms(value: Any) -> float | None:
    if value is None:
        return None
    parsed = _normalize_float(value)
    if parsed <= 0.0:
        return None
    return parsed


def _normalize_dirty_paths(value: Any) -> tuple[str, ...]:
    rows = value if isinstance(value, (list, tuple, set)) else ()
    normalized: list[str] = []
    seen: set[str] = set()
    for item in rows:
        path = _normalize_text(item, max_len=512)
        if not path or path in seen:
            continue
        seen.add(path)
        normalized.append(path)
    return tuple(normalized[:32])


def _hash_payload(payload: dict[str, Any]) -> str:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


def _resolve_subcall_timeout_seconds(
    *,
    timeout_seconds: float | None,
    remaining_budget_ms: float | None,
) -> float | None:
    candidates: list[float] = []
    if isinstance(timeout_seconds, (int, float)) and float(timeout_seconds) > 0.0:
        candidates.append(float(timeout_seconds))
    if remaining_budget_ms is not None:
        candidates.append(max(float(remaining_budget_ms) / 1000.0, 0.001))
    if not candidates:
        return None
    return min(candidates)


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


def _budget_exhausted_worktree_summary(
    *,
    timeout_seconds: float | None,
    max_files: int,
) -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": "budget_exhausted",
        "changed_count": 0,
        "staged_count": 0,
        "unstaged_count": 0,
        "untracked_count": 0,
        "entries": [],
        "diffstat": {
            "staged": _empty_diffstat(),
            "unstaged": _empty_diffstat(),
        },
        "error": "latency_budget_exhausted",
        "elapsed_ms": 0.0,
        "timeout_seconds": _normalize_float(timeout_seconds),
        "max_files": max(1, int(max_files)),
        "truncated": False,
    }


@dataclass(frozen=True, slots=True)
class GitFastFingerprint:
    fingerprint: str
    trust_class: str = "fallback"
    strategy: str = "git_fast"
    repo_root: str = ""
    head_commit: str = ""
    head_ref: str = ""
    settings_fingerprint: str = ""
    dirty_path_count: int = 0
    dirty_paths_sample: tuple[str, ...] = ()
    elapsed_ms: float = 0.0
    timed_out: bool = False
    fallback_reason: str = ""
    git_available: bool = True
    worktree_available: bool = True
    metadata: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "trust_class": self.trust_class,
            "strategy": self.strategy,
            "repo_root": self.repo_root,
            "head_commit": self.head_commit,
            "head_ref": self.head_ref,
            "settings_fingerprint": self.settings_fingerprint,
            "dirty_path_count": self.dirty_path_count,
            "dirty_paths_sample": list(self.dirty_paths_sample),
            "elapsed_ms": self.elapsed_ms,
            "timed_out": self.timed_out,
            "fallback_reason": self.fallback_reason,
            "git_available": self.git_available,
            "worktree_available": self.worktree_available,
            "metadata": dict(self.metadata or {}),
        }

    def to_observability_payload(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "trust_class": self.trust_class,
            "strategy": self.strategy,
            "head_commit": self.head_commit,
            "head_ref": self.head_ref,
            "settings_fingerprint": self.settings_fingerprint,
            "dirty_path_count": self.dirty_path_count,
            "dirty_paths_sample": list(self.dirty_paths_sample),
            "elapsed_ms": self.elapsed_ms,
            "timed_out": self.timed_out,
            "fallback_reason": self.fallback_reason,
            "git_available": self.git_available,
            "worktree_available": self.worktree_available,
        }


def normalize_git_fast_fingerprint(
    value: GitFastFingerprint | dict[str, Any],
) -> GitFastFingerprint:
    raw = asdict(value) if isinstance(value, GitFastFingerprint) else dict(value)
    fingerprint = _normalize_text(raw.get("fingerprint"), max_len=128)
    if not fingerprint:
        raise ValueError("fingerprint must be non-empty")
    trust_class = _normalize_text(raw.get("trust_class"), max_len=32).lower() or "fallback"
    if trust_class not in GIT_FAST_FINGERPRINT_TRUST_CLASSES:
        raise ValueError(f"unsupported git fast fingerprint trust_class: {trust_class}")
    metadata_raw = raw.get("metadata")
    metadata = dict(metadata_raw) if isinstance(metadata_raw, dict) else {}
    return GitFastFingerprint(
        fingerprint=fingerprint,
        trust_class=trust_class,
        strategy=_normalize_text(raw.get("strategy"), max_len=64) or "git_fast",
        repo_root=_normalize_text(raw.get("repo_root"), max_len=512),
        head_commit=_normalize_text(raw.get("head_commit"), max_len=64),
        head_ref=_normalize_text(raw.get("head_ref"), max_len=128),
        settings_fingerprint=_normalize_text(
            raw.get("settings_fingerprint"),
            max_len=128,
        ),
        dirty_path_count=_normalize_count(raw.get("dirty_path_count")),
        dirty_paths_sample=_normalize_dirty_paths(raw.get("dirty_paths_sample")),
        elapsed_ms=_normalize_float(raw.get("elapsed_ms")),
        timed_out=bool(raw.get("timed_out")),
        fallback_reason=_normalize_text(raw.get("fallback_reason"), max_len=128),
        git_available=bool(raw.get("git_available", True)),
        worktree_available=bool(raw.get("worktree_available", True)),
        metadata=metadata,
    )


def build_git_fast_fingerprint(
    *,
    repo_root: str | Path,
    settings_fingerprint: str = "",
    timeout_seconds: float | None = None,
    latency_budget_ms: float | None = None,
    max_dirty_paths: int = 32,
    collect_head_snapshot_fn: Callable[..., dict[str, Any]] = collect_git_head_snapshot,
    collect_worktree_summary_fn: Callable[..., dict[str, Any]] = collect_git_worktree_summary,
    build_worktree_state_token_fn: Callable[..., str] = build_git_worktree_state_token,
) -> GitFastFingerprint:
    normalized_root = str(Path(repo_root).resolve())
    normalized_settings = _normalize_text(settings_fingerprint, max_len=128)
    normalized_budget_ms = _normalize_budget_ms(latency_budget_ms)
    head_timeout_seconds = _resolve_subcall_timeout_seconds(
        timeout_seconds=timeout_seconds,
        remaining_budget_ms=normalized_budget_ms,
    )
    head = collect_head_snapshot_fn(
        repo_root=normalized_root,
        timeout_seconds=head_timeout_seconds,
    )
    head_elapsed_ms = _normalize_float(head.get("elapsed_ms"))
    remaining_budget_ms = (
        max(0.0, normalized_budget_ms - head_elapsed_ms)
        if normalized_budget_ms is not None
        else None
    )
    worktree_timeout_seconds = _resolve_subcall_timeout_seconds(
        timeout_seconds=timeout_seconds,
        remaining_budget_ms=remaining_budget_ms,
    )
    if normalized_budget_ms is not None and remaining_budget_ms is not None and remaining_budget_ms <= 0.0:
        worktree = _budget_exhausted_worktree_summary(
            timeout_seconds=worktree_timeout_seconds,
            max_files=max_dirty_paths,
        )
    else:
        worktree = collect_worktree_summary_fn(
            repo_root=normalized_root,
            max_files=max(1, int(max_dirty_paths)),
            timeout_seconds=worktree_timeout_seconds,
        )

    head_reason = str(head.get("reason") or "").strip()
    worktree_reason = str(worktree.get("reason") or "").strip()
    head_commit = _normalize_text(head.get("head_commit"), max_len=64)
    head_ref = _normalize_text(head.get("head_ref"), max_len=128)
    dirty_paths_sample = _normalize_dirty_paths(
        [
            str(item.get("path") or "").strip()
            for item in (worktree.get("entries", []) if isinstance(worktree.get("entries"), list) else [])
            if isinstance(item, dict)
        ]
    )[: max(1, int(max_dirty_paths))]
    worktree_token = build_worktree_state_token_fn(worktree, max_entries=max_dirty_paths)
    worktree_truncated = bool(worktree.get("truncated", False))

    trust_class = "fallback"
    fallback_reason = ""
    downgrade_reason = ""
    git_available = bool(head.get("enabled", False))
    worktree_available = bool(worktree.get("enabled", False))
    if head_commit:
        if (
            git_available
            and worktree_available
            and head_reason == "ok"
            and worktree_reason == "ok"
            and not worktree_truncated
        ):
            trust_class = "exact"
        else:
            trust_class = "git_partial"
            downgrade_reason = worktree_reason or head_reason or (
                "worktree_truncated" if worktree_truncated else "partial"
            )
            fallback_reason = downgrade_reason
    else:
        trust_class = "fallback"
        downgrade_reason = head_reason or "missing_head"
        fallback_reason = downgrade_reason

    worktree_elapsed_ms = _normalize_float(worktree.get("elapsed_ms"))
    elapsed_ms = head_elapsed_ms + worktree_elapsed_ms
    budget_exhausted = bool(
        normalized_budget_ms is not None
        and (
            elapsed_ms > normalized_budget_ms
            or worktree_reason == "budget_exhausted"
        )
    )
    if budget_exhausted and not downgrade_reason:
        downgrade_reason = "latency_budget_exceeded"
        fallback_reason = downgrade_reason
        if head_commit:
            trust_class = "git_partial"
        else:
            trust_class = "fallback"

    fingerprint = _hash_payload(
        {
            "repo_root": normalized_root,
            "head_commit": head_commit,
            "head_ref": head_ref,
            "settings_fingerprint": normalized_settings,
            "worktree_token": worktree_token,
            "trust_class": trust_class,
            "fallback_reason": fallback_reason,
        }
    )
    timed_out = (
        head_reason == "timeout"
        or worktree_reason == "timeout"
        or budget_exhausted
    )
    metadata = {
        "head_reason": head_reason,
        "worktree_reason": worktree_reason,
        "worktree_token": worktree_token,
        "worktree_truncated": worktree_truncated,
    }
    if head_timeout_seconds is not None:
        metadata["head_timeout_seconds"] = _normalize_float(head_timeout_seconds)
    if worktree_timeout_seconds is not None:
        metadata["worktree_timeout_seconds"] = _normalize_float(worktree_timeout_seconds)
    if normalized_budget_ms is not None:
        metadata["budget_ms"] = normalized_budget_ms
        metadata["budget_remaining_ms"] = _normalize_float(
            max(0.0, normalized_budget_ms - elapsed_ms)
        )
        metadata["budget_exhausted"] = budget_exhausted
    if downgrade_reason:
        metadata["downgrade_reason"] = downgrade_reason
    return GitFastFingerprint(
        fingerprint=fingerprint,
        trust_class=trust_class,
        strategy="git_head_dirty_settings",
        repo_root=normalized_root,
        head_commit=head_commit,
        head_ref=head_ref,
        settings_fingerprint=normalized_settings,
        dirty_path_count=_normalize_count(worktree.get("changed_count")),
        dirty_paths_sample=dirty_paths_sample,
        elapsed_ms=elapsed_ms,
        timed_out=timed_out,
        fallback_reason=fallback_reason,
        git_available=git_available,
        worktree_available=worktree_available,
        metadata=metadata,
    )


def build_git_fast_fingerprint_observability(
    value: GitFastFingerprint | dict[str, Any],
) -> dict[str, Any]:
    return normalize_git_fast_fingerprint(value).to_observability_payload()


__all__ = [
    "GIT_FAST_FINGERPRINT_TRUST_CLASSES",
    "GitFastFingerprint",
    "build_git_fast_fingerprint",
    "build_git_fast_fingerprint_observability",
    "normalize_git_fast_fingerprint",
]
