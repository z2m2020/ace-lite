from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


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


def build_git_fast_fingerprint_observability(
    value: GitFastFingerprint | dict[str, Any],
) -> dict[str, Any]:
    return normalize_git_fast_fingerprint(value).to_observability_payload()


__all__ = [
    "GIT_FAST_FINGERPRINT_TRUST_CLASSES",
    "GitFastFingerprint",
    "build_git_fast_fingerprint_observability",
    "normalize_git_fast_fingerprint",
]
