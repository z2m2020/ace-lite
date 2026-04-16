from __future__ import annotations

from typing import Any

from ace_lite.report_signals import normalize_signal_path, normalize_signal_paths


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _str(value: Any) -> str:
    return str(value) if value is not None else ""


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_history_hits(
    *,
    vcs_history: dict[str, Any] | None,
    focused_files: list[str],
    limit: int = 5,
) -> dict[str, Any]:
    payload = _dict(vcs_history)
    commits = [item for item in _list(payload.get("commits")) if isinstance(item, dict)]
    normalized_focus = set(normalize_signal_paths(focused_files))
    hits: list[dict[str, Any]] = []
    for item in commits[: max(1, int(limit))]:
        files = [
            normalize_signal_path(path)
            for path in _list(item.get("files"))
            if normalize_signal_path(path)
        ]
        matched_paths = [path for path in files if path in normalized_focus]
        if not matched_paths:
            continue
        hits.append(
            {
                "hash": _str(item.get("hash")).strip(),
                "subject": _str(item.get("subject")).strip(),
                "author": _str(item.get("author")).strip(),
                "committed_at": _str(item.get("committed_at")).strip(),
                "matched_paths": matched_paths,
                "matched_path_count": len(matched_paths),
                "file_count": len(files),
            }
        )

    return {
        "schema_version": "history_hits_v1",
        "enabled": bool(payload.get("enabled", False)),
        "reason": _str(payload.get("reason")).strip() or "disabled",
        "commit_count": _int(payload.get("commit_count"), len(commits)),
        "path_count": _int(payload.get("path_count"), len(normalized_focus)),
        "hit_count": len(hits),
        "hits": hits,
    }


__all__ = ["build_history_hits"]
