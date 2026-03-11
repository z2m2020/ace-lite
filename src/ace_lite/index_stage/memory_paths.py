"""Memory-hit path extraction for the index stage."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_memory_paths(*, memory_stage: dict[str, Any], root: str) -> list[str]:
    """Extract repo-relative paths from memory hit metadata."""
    paths: list[str] = []
    root_path = Path(root)

    hits = memory_stage.get("hits", [])
    if not isinstance(hits, list):
        hits = []
    if not hits:
        hits = memory_stage.get("hits_preview", [])
    if not isinstance(hits, list):
        hits = []

    for hit in hits:
        if not isinstance(hit, dict):
            continue
        metadata = hit.get("metadata")
        if not isinstance(metadata, dict):
            continue
        path = metadata.get("path")
        if not isinstance(path, str):
            continue

        candidate = Path(path)
        if candidate.is_absolute():
            try:
                normalized = candidate.resolve().relative_to(root_path).as_posix()
            except ValueError:
                normalized = candidate.as_posix()
        else:
            normalized = candidate.as_posix()

        if normalized not in paths:
            paths.append(normalized)

    return paths


__all__ = ["extract_memory_paths"]

