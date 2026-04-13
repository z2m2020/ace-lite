from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any

from ace_lite.pipeline.types import StageContext


def _normalize_candidate_filter_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/")


def _coerce_candidate_filter_list(value: Any) -> list[str]:
    if isinstance(value, str):
        normalized = _normalize_candidate_filter_path(value)
        return [normalized] if normalized else []
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        normalized = _normalize_candidate_filter_path(item)
        if normalized:
            output.append(normalized)
    return output


def _path_looks_like_docs(path: str) -> bool:
    normalized = _normalize_candidate_filter_path(path).lower()
    if not normalized:
        return False
    if normalized.endswith(".md"):
        return True
    if normalized.startswith("docs/") or "/docs/" in normalized:
        return True
    return normalized in {
        "readme",
        "readme.md",
        "changelog",
        "changelog.md",
        "contributing",
        "contributing.md",
        "security",
        "security.md",
    }


def _candidate_path_matches_filters(
    path: Any,
    *,
    include_paths: list[str],
    include_globs: list[str],
    exclude_paths: list[str],
    exclude_globs: list[str],
) -> bool:
    normalized = _normalize_candidate_filter_path(path)
    if not normalized:
        return False
    include_requested = bool(include_paths or include_globs)
    if include_requested:
        included = normalized in include_paths or any(
            fnmatchcase(normalized, pattern) for pattern in include_globs
        )
        if not included:
            return False
    return (
        normalized not in exclude_paths
        and not any(fnmatchcase(normalized, pattern) for pattern in exclude_globs)
    )


def resolve_benchmark_candidate_filters(ctx: StageContext) -> dict[str, Any]:
    raw = ctx.state.get("benchmark_filters")
    filters = raw if isinstance(raw, dict) else {}
    include_paths = _coerce_candidate_filter_list(filters.get("include_paths"))
    include_globs = _coerce_candidate_filter_list(filters.get("include_globs"))
    exclude_paths = _coerce_candidate_filter_list(filters.get("exclude_paths"))
    exclude_globs = _coerce_candidate_filter_list(filters.get("exclude_globs"))
    return {
        "requested": bool(include_paths or include_globs or exclude_paths or exclude_globs),
        "include_paths": include_paths,
        "include_globs": include_globs,
        "exclude_paths": exclude_paths,
        "exclude_globs": exclude_globs,
    }


def resolve_docs_policy_for_benchmark(
    *,
    policy_docs_enabled: bool,
    benchmark_filter_payload: dict[str, Any],
) -> tuple[bool, str]:
    if not bool(policy_docs_enabled):
        return False, "policy_disabled"
    include_paths = _coerce_candidate_filter_list(benchmark_filter_payload.get("include_paths"))
    if not include_paths:
        return True, "policy_enabled"
    if any(_path_looks_like_docs(path) for path in include_paths):
        return True, "benchmark_include_paths_contains_docs"
    return False, "benchmark_include_paths_code_only"


def resolve_worktree_policy_for_benchmark(
    *,
    worktree_prior_enabled: bool,
    benchmark_filter_payload: dict[str, Any],
) -> tuple[bool, str]:
    if not bool(worktree_prior_enabled):
        return False, "policy_disabled"
    include_paths = _coerce_candidate_filter_list(benchmark_filter_payload.get("include_paths"))
    include_globs = _coerce_candidate_filter_list(benchmark_filter_payload.get("include_globs"))
    if include_paths or include_globs:
        return False, "benchmark_filter_explicit_scope"
    return True, "policy_enabled"


def filter_candidate_rows(
    rows: list[dict[str, Any]],
    *,
    include_paths: list[str],
    include_globs: list[str],
    exclude_paths: list[str],
    exclude_globs: list[str],
) -> tuple[list[dict[str, Any]], int]:
    output: list[dict[str, Any]] = []
    removed = 0
    for item in rows:
        if not _candidate_path_matches_filters(
            item.get("path"),
            include_paths=include_paths,
            include_globs=include_globs,
            exclude_paths=exclude_paths,
            exclude_globs=exclude_globs,
        ):
            removed += 1
            continue
        output.append(item)
    return output, removed


def filter_files_map_for_benchmark(
    files_map: dict[str, Any],
    *,
    include_paths: list[str],
    include_globs: list[str],
    exclude_paths: list[str],
    exclude_globs: list[str],
) -> tuple[dict[str, Any], int]:
    output: dict[str, Any] = {}
    removed = 0
    for path, payload in files_map.items():
        if not _candidate_path_matches_filters(
            path,
            include_paths=include_paths,
            include_globs=include_globs,
            exclude_paths=exclude_paths,
            exclude_globs=exclude_globs,
        ):
            removed += 1
            continue
        output[str(path)] = payload
    return output, removed


__all__ = [
    "filter_candidate_rows",
    "filter_files_map_for_benchmark",
    "resolve_benchmark_candidate_filters",
    "resolve_docs_policy_for_benchmark",
    "resolve_worktree_policy_for_benchmark",
]
