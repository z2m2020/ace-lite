"""Repository-relative path helpers for the index stage."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def resolve_repo_relative_path(*, root: str, configured_path: str) -> Path:
    path = Path(str(configured_path or "").strip() or "context-map/index.json")
    if path.is_absolute():
        return path
    return Path(root) / path


def normalize_repo_path(value: Any, *, strip_leading_slash: bool = False) -> str:
    path = str(value or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if strip_leading_slash:
        path = path.lstrip("/")
    return path


__all__ = ["normalize_repo_path", "resolve_repo_relative_path"]
