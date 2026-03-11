from __future__ import annotations

import json
import os
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from ace_lite.subprocess_utils import run_capture_output
from ace_lite.utils import to_float

_CACHE_SCHEMA_VERSION = "2"
_COMMIT_MARKER = "__ACE_COMMIT__"
_DEFAULT_NEIGHBOR_CAP = 64
_MEM_CACHE_MAX_SIZE = 8


class NeighborRow(TypedDict):
    path: str
    score: float


_MEM_CACHE: OrderedDict[
    tuple[str, str, int, float, int], dict[str, list[NeighborRow]]
] = OrderedDict()
_MEM_CACHE_LOCK = threading.Lock()

_GIT_TIMEOUT_ENV = "ACE_LITE_GIT_TIMEOUT_SECONDS"
_DEFAULT_GIT_TIMEOUT_SECONDS = 2.0


def _git_timeout_seconds() -> float:
    raw = str(os.getenv(_GIT_TIMEOUT_ENV, "")).strip()
    if not raw:
        return _DEFAULT_GIT_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_GIT_TIMEOUT_SECONDS
    return max(0.1, value)


def _normalize_path(value: str) -> str:
    return str(value or "").strip().replace("\\", "/")


def _git_head(repo_root: Path) -> str | None:
    returncode, stdout, _stderr, timed_out = run_capture_output(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        timeout_seconds=_git_timeout_seconds(),
        env_overrides={"GIT_TERMINAL_PROMPT": "0"},
    )
    if timed_out:
        return None
    if returncode != 0:
        return None

    head = str(stdout or "").strip()
    return head or None


def _parse_git_date(value: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _run_git_log(
    *, repo_root: Path, lookback_commits: int
) -> list[tuple[datetime, list[str]]]:
    command = [
        "git",
        "--no-pager",
        "log",
        f"-n{max(1, int(lookback_commits))}",
        "--name-only",
        "--date=iso-strict",
        f"--pretty=format:{_COMMIT_MARKER}|%H|%cI",
    ]

    returncode, stdout, _stderr, timed_out = run_capture_output(
        command,
        cwd=repo_root,
        timeout_seconds=_git_timeout_seconds(),
        env_overrides={"GIT_TERMINAL_PROMPT": "0"},
    )
    if timed_out:
        return []
    if returncode != 0:
        return []

    commits: list[tuple[datetime, list[str]]] = []
    commit_date: datetime | None = None
    commit_files: list[str] = []

    def flush() -> None:
        nonlocal commit_date, commit_files
        if commit_date is None:
            return
        unique_paths = sorted({path for path in commit_files if path})
        commits.append((commit_date, unique_paths))
        commit_date = None
        commit_files = []

    for raw in str(stdout or "").splitlines():
        line = str(raw or "").strip()
        if not line:
            continue
        if line.startswith(f"{_COMMIT_MARKER}|"):
            flush()
            parts = line.split("|", 2)
            if len(parts) >= 3:
                try:
                    commit_date = _parse_git_date(parts[2])
                except (ValueError, IndexError):
                    commit_date = datetime.now(timezone.utc)
            else:
                commit_date = datetime.now(timezone.utc)
            continue

        normalized = _normalize_path(line)
        if normalized:
            commit_files.append(normalized)

    flush()
    return commits


def _compute_matrix(
    *, commits: list[tuple[datetime, list[str]]], half_life_days: float
) -> dict[str, dict[str, float]]:
    matrix: dict[str, dict[str, float]] = {}
    now = datetime.now(timezone.utc)
    half_life = max(1.0, float(half_life_days or 60.0))

    for committed_at, changed_files in commits:
        if len(changed_files) < 2:
            continue

        age_days = max(0.0, (now - committed_at).total_seconds() / 86400.0)
        decay = 0.5 ** (age_days / half_life)
        if decay <= 0.0:
            continue

        size = len(changed_files)
        for index in range(size):
            source = changed_files[index]
            for inner in range(index + 1, size):
                target = changed_files[inner]
                if source == target:
                    continue

                matrix.setdefault(source, {})
                matrix.setdefault(target, {})
                matrix[source][target] = float(matrix[source].get(target, 0.0)) + float(
                    decay
                )
                matrix[target][source] = float(matrix[target].get(source, 0.0)) + float(
                    decay
                )

    return matrix


def _to_sparse_neighbors(
    *, matrix: dict[str, dict[str, float]], neighbor_cap: int
) -> dict[str, list[NeighborRow]]:
    cap = max(1, int(neighbor_cap or _DEFAULT_NEIGHBOR_CAP))
    neighbors_by_path: dict[str, list[NeighborRow]] = {}

    for source, targets in matrix.items():
        source_path = _normalize_path(str(source))
        if not source_path or not isinstance(targets, dict):
            continue

        ranked_rows: list[NeighborRow] = []
        for target, score in targets.items():
            target_path = _normalize_path(str(target))
            if not target_path:
                continue
            parsed_score = float(score)
            if parsed_score <= 0.0:
                continue
            ranked_rows.append({"path": target_path, "score": parsed_score})

        ranked = sorted(
            ranked_rows,
            key=lambda item: (-item["score"], item["path"]),
        )

        if ranked:
            neighbors_by_path[source_path] = ranked[:cap]

    return neighbors_by_path


def _cache_payload(
    *,
    head: str,
    lookback_commits: int,
    half_life_days: float,
    neighbor_cap: int,
    neighbors_by_path: dict[str, list[NeighborRow]],
) -> dict[str, Any]:
    return {
        "schema_version": _CACHE_SCHEMA_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "head": head,
        "lookback_commits": int(lookback_commits),
        "half_life_days": float(half_life_days),
        "neighbor_cap": int(max(1, int(neighbor_cap))),
        "neighbors_by_path": {
            source: [
                {
                    "path": str(item["path"]),
                    "score": float(item["score"]),
                }
                for item in targets
                if str(item["path"]).strip()
            ]
            for source, targets in sorted(
                neighbors_by_path.items(), key=lambda item: item[0]
            )
            if isinstance(source, str) and source.strip() and isinstance(targets, list)
        },
    }


def _coerce_neighbors_by_path(raw: Any) -> dict[str, list[NeighborRow]]:
    if not isinstance(raw, dict):
        return {}

    payload: dict[str, list[NeighborRow]] = {}
    for source, targets in raw.items():
        source_path = _normalize_path(str(source))
        if not source_path:
            continue

        normalized_targets: list[NeighborRow] = []
        if isinstance(targets, list):
            for item in targets:
                if not isinstance(item, dict):
                    continue
                target_path = _normalize_path(str(item.get("path") or ""))
                if not target_path:
                    continue
                score = float(to_float(item.get("score"), default=0.0) or 0.0)
                if score <= 0.0:
                    continue
                normalized_targets.append(
                    {
                        "path": target_path,
                        "score": score,
                    }
                )
        elif isinstance(targets, dict):
            for target, score in targets.items():
                target_path = _normalize_path(str(target))
                if not target_path:
                    continue
                parsed_score = float(to_float(score, default=0.0) or 0.0)
                if parsed_score <= 0.0:
                    continue
                normalized_targets.append(
                    {
                        "path": target_path,
                        "score": parsed_score,
                    }
                )

        normalized_targets.sort(
            key=lambda item: (-float(item.get("score", 0.0)), str(item.get("path", "")))
        )
        if normalized_targets:
            payload[source_path] = normalized_targets

    return payload


def _load_cache(
    *,
    cache_path: Path,
    head: str,
    lookback_commits: int,
    half_life_days: float,
    neighbor_cap: int,
) -> dict[str, list[NeighborRow]] | None:
    if not cache_path.exists() or not cache_path.is_file():
        return None

    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None

    if not isinstance(raw, dict):
        return None

    schema_version = str(raw.get("schema_version", "")).strip()
    if schema_version != _CACHE_SCHEMA_VERSION:
        return None

    if str(raw.get("head", "")) != str(head):
        return None

    if int(raw.get("lookback_commits", 0) or 0) != int(lookback_commits):
        return None

    if abs(float(raw.get("half_life_days", 0.0) or 0.0) - float(half_life_days)) > 1e-9:
        return None

    if int(raw.get("neighbor_cap", 0) or 0) != int(max(1, int(neighbor_cap))):
        return None

    payload = _coerce_neighbors_by_path(raw.get("neighbors_by_path", {}))
    if not payload:
        return None
    return payload


def load_or_build_cochange_matrix(
    *,
    repo_root: str | Path,
    cache_path: str | Path,
    lookback_commits: int = 400,
    half_life_days: float = 60.0,
    neighbor_cap: int = _DEFAULT_NEIGHBOR_CAP,
) -> tuple[dict[str, list[NeighborRow]], dict[str, Any]]:
    root = Path(repo_root).resolve()
    cache = Path(cache_path)
    if not cache.is_absolute():
        cache = root / cache

    normalized_neighbor_cap = max(1, int(neighbor_cap or _DEFAULT_NEIGHBOR_CAP))

    head = _git_head(root)
    if not head:
        return {}, {
            "enabled": False,
            "cache_hit": False,
            "mode": "git_unavailable",
            "head": None,
            "cache_path": str(cache),
            "edge_count": 0,
            "neighbor_cap": normalized_neighbor_cap,
        }

    mem_key = (
        str(cache),
        str(head),
        int(lookback_commits),
        float(half_life_days),
        int(normalized_neighbor_cap),
    )
    with _MEM_CACHE_LOCK:
        mem_cached = _MEM_CACHE.get(mem_key)
        if mem_cached is not None:
            _MEM_CACHE.move_to_end(mem_key)
    if mem_cached is not None:
        edge_count = sum(len(targets) for targets in mem_cached.values())
        return mem_cached, {
            "enabled": True,
            "cache_hit": True,
            "mode": "memory",
            "head": head,
            "cache_path": str(cache),
            "edge_count": int(edge_count),
            "lookback_commits": int(lookback_commits),
            "half_life_days": float(half_life_days),
            "neighbor_cap": normalized_neighbor_cap,
        }

    cached = _load_cache(
        cache_path=cache,
        head=head,
        lookback_commits=lookback_commits,
        half_life_days=half_life_days,
        neighbor_cap=normalized_neighbor_cap,
    )
    if cached is not None:
        with _MEM_CACHE_LOCK:
            _MEM_CACHE[mem_key] = cached
            if len(_MEM_CACHE) > _MEM_CACHE_MAX_SIZE:
                _MEM_CACHE.popitem(last=False)
        edge_count = sum(len(targets) for targets in cached.values())
        return cached, {
            "enabled": True,
            "cache_hit": True,
            "mode": "cache",
            "head": head,
            "cache_path": str(cache),
            "edge_count": int(edge_count),
            "lookback_commits": int(lookback_commits),
            "half_life_days": float(half_life_days),
            "neighbor_cap": normalized_neighbor_cap,
        }

    commits = _run_git_log(repo_root=root, lookback_commits=lookback_commits)
    matrix = _compute_matrix(commits=commits, half_life_days=half_life_days)
    neighbors_by_path = _to_sparse_neighbors(
        matrix=matrix, neighbor_cap=normalized_neighbor_cap
    )

    cache.parent.mkdir(parents=True, exist_ok=True)
    payload = _cache_payload(
        head=head,
        lookback_commits=lookback_commits,
        half_life_days=half_life_days,
        neighbor_cap=normalized_neighbor_cap,
        neighbors_by_path=neighbors_by_path,
    )
    cache.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with _MEM_CACHE_LOCK:
        _MEM_CACHE[mem_key] = neighbors_by_path
        if len(_MEM_CACHE) > _MEM_CACHE_MAX_SIZE:
            _MEM_CACHE.popitem(last=False)
    edge_count = sum(len(targets) for targets in neighbors_by_path.values())
    return neighbors_by_path, {
        "enabled": True,
        "cache_hit": False,
        "mode": "rebuilt",
        "head": head,
        "cache_path": str(cache),
        "edge_count": int(edge_count),
        "commit_count": len(commits),
        "lookback_commits": int(lookback_commits),
        "half_life_days": float(half_life_days),
        "neighbor_cap": normalized_neighbor_cap,
    }


def query_cochange_neighbors(
    *,
    matrix: dict[str, Any],
    seed_paths: list[str],
    top_n: int = 12,
) -> list[dict[str, Any]]:
    if not isinstance(matrix, dict) or not matrix:
        return []

    seeds = {_normalize_path(item) for item in seed_paths if _normalize_path(item)}
    if not seeds:
        return []

    aggregated: dict[str, float] = {}
    for seed in sorted(seeds):
        neighbors = matrix.get(seed, {})

        if isinstance(neighbors, dict):
            iterator = (
                {
                    "path": _normalize_path(str(target)),
                    "score": float(score),
                }
                for target, score in neighbors.items()
            )
        elif isinstance(neighbors, list):
            iterator = (
                 {
                     "path": _normalize_path(
                         str(item.get("path") if isinstance(item, dict) else "")
                     ),
                    "score": to_float(
                        item.get("score") if isinstance(item, dict) else 0.0,
                        default=0.0,
                    )
                    or 0.0,
                 }
                 for item in neighbors
             )
        else:
            continue

        for item in iterator:
            target_path = _normalize_path(str(item.get("path") or ""))
            score = to_float(item.get("score"), default=0.0) or 0.0
            if not target_path or target_path in seeds or score <= 0.0:
                continue
            aggregated[target_path] = float(aggregated.get(target_path, 0.0)) + score

    ranked = sorted(
        (
            {
                "path": path,
                "score": float(score),
            }
            for path, score in aggregated.items()
            if float(score) > 0.0
        ),
        key=lambda item: (
            -(to_float(item.get("score"), default=0.0) or 0.0),
            str(item.get("path", "")),
        ),
    )
    return ranked[: max(0, int(top_n))]


__all__ = ["load_or_build_cochange_matrix", "query_cochange_neighbors"]
