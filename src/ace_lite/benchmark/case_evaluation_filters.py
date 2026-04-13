"""Candidate path filter helpers for benchmark case evaluation."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any


def coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        normalized = str(item or "").strip()
        if normalized:
            output.append(normalized)
    return output


def normalize_benchmark_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/")


def resolve_candidate_path_filters(case: dict[str, Any]) -> dict[str, list[str]]:
    filters = case.get("filters", {}) if isinstance(case.get("filters"), dict) else {}
    include_paths = [
        normalize_benchmark_path(item)
        for item in coerce_string_list(filters.get("include_paths"))
    ]
    include_globs = [
        normalize_benchmark_path(item)
        for item in coerce_string_list(filters.get("include_globs"))
    ]
    exclude_paths = [
        normalize_benchmark_path(item)
        for item in coerce_string_list(filters.get("exclude_paths"))
    ]
    exclude_globs = [
        normalize_benchmark_path(item)
        for item in coerce_string_list(filters.get("exclude_globs"))
    ]
    return {
        "include_paths": [item for item in include_paths if item],
        "include_globs": [item for item in include_globs if item],
        "exclude_paths": [item for item in exclude_paths if item],
        "exclude_globs": [item for item in exclude_globs if item],
    }


def candidate_path_matches_filters(
    path: Any,
    *,
    include_paths: list[str],
    include_globs: list[str],
    exclude_paths: list[str],
    exclude_globs: list[str],
) -> bool:
    normalized_path = normalize_benchmark_path(path)
    if not normalized_path:
        return False
    include_requested = bool(include_paths or include_globs)
    if include_requested:
        included = normalized_path in include_paths or any(
            fnmatchcase(normalized_path, pattern) for pattern in include_globs
        )
        if not included:
            return False
    return (
        normalized_path not in exclude_paths
        and not any(fnmatchcase(normalized_path, pattern) for pattern in exclude_globs)
    )


def filter_candidate_path_items(
    items: Any,
    *,
    include_paths: list[str],
    include_globs: list[str],
    exclude_paths: list[str],
    exclude_globs: list[str],
) -> list[Any]:
    if not isinstance(items, list):
        return []
    output: list[Any] = []
    for item in items:
        if not isinstance(item, dict):
            output.append(item)
            continue
        if not candidate_path_matches_filters(
            item.get("path"),
            include_paths=include_paths,
            include_globs=include_globs,
            exclude_paths=exclude_paths,
            exclude_globs=exclude_globs,
        ):
            continue
        output.append(item)
    return output


__all__ = [
    "candidate_path_matches_filters",
    "coerce_string_list",
    "filter_candidate_path_items",
    "normalize_benchmark_path",
    "resolve_candidate_path_filters",
]
