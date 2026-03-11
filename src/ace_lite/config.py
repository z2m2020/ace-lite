"""Layered configuration loading for CLI defaults.

Configuration is merged from (in order): user home, repository root, and the
active working directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_FILE = ".ace-lite.yml"


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def _read_config(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}

    return payload if isinstance(payload, dict) else {}


def find_git_root(start: str | Path) -> Path | None:
    current = Path(start).resolve()
    for candidate in [current, *current.parents]:
        git_marker = candidate / ".git"
        if git_marker.exists():
            return candidate
    return None


def load_layered_config(
    *,
    root_dir: str | Path,
    cwd: str | Path | None = None,
    filename: str = DEFAULT_CONFIG_FILE,
) -> dict[str, Any]:
    root = Path(root_dir).resolve()
    active_cwd = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()

    cwd_within_repo = active_cwd == root or root in active_cwd.parents
    home_path = Path.home() / filename
    repo_path = root / filename
    cwd_path = active_cwd / filename if cwd_within_repo else None

    merged: dict[str, Any] = {}
    loaded_files: list[str] = []

    candidates = [home_path, repo_path]
    if cwd_path is not None:
        candidates.append(cwd_path)

    for candidate in candidates:
        if candidate in {Path(path) for path in loaded_files}:
            continue
        payload = _read_config(candidate)
        if not payload:
            continue
        _deep_merge(merged, payload)
        loaded_files.append(str(candidate.resolve()))

    merged["_meta"] = {
        "loaded_files": loaded_files,
        "repo_root": str(root),
        "cwd": str(active_cwd),
        "filename": filename,
    }
    return merged


def config_get(config: dict[str, Any], *path: str, default: Any = None) -> Any:
    current: Any = config
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


__all__ = [
    "DEFAULT_CONFIG_FILE",
    "config_get",
    "find_git_root",
    "load_layered_config",
]
