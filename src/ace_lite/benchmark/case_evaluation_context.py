"""Context extraction helpers for benchmark case evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ace_lite.benchmark.case_evaluation_filters import (
    coerce_string_list,
    filter_candidate_path_items,
    resolve_candidate_path_filters,
)


@dataclass(frozen=True, slots=True)
class CandidateContext:
    candidate_path_filters: dict[str, list[str]]
    included_candidate_paths: list[str]
    included_candidate_globs: list[str]
    excluded_candidate_paths: list[str]
    excluded_candidate_globs: list[str]
    filters_applied_upstream: bool
    candidate_files: list[Any]
    raw_candidate_chunks: list[dict[str, Any]]
    source_plan_has_candidate_chunks: bool
    source_plan_candidate_chunks: list[dict[str, Any]]
    candidate_chunks: list[dict[str, Any]]


def build_candidate_context(
    *,
    case: dict[str, Any],
    index_payload: dict[str, Any],
    index_benchmark_filters: dict[str, Any],
    source_plan_payload: dict[str, Any],
    coerce_chunk_refs: Any,
) -> CandidateContext:
    candidate_path_filters = (
        {
            "include_paths": coerce_string_list(
                index_benchmark_filters.get("include_paths")
            ),
            "include_globs": coerce_string_list(
                index_benchmark_filters.get("include_globs")
            ),
            "exclude_paths": coerce_string_list(
                index_benchmark_filters.get("exclude_paths")
            ),
            "exclude_globs": coerce_string_list(
                index_benchmark_filters.get("exclude_globs")
            ),
        }
        if bool(index_benchmark_filters.get("requested", False))
        else resolve_candidate_path_filters(case)
    )
    included_candidate_paths = candidate_path_filters["include_paths"]
    included_candidate_globs = candidate_path_filters["include_globs"]
    excluded_candidate_paths = candidate_path_filters["exclude_paths"]
    excluded_candidate_globs = candidate_path_filters["exclude_globs"]
    filters_applied_upstream = bool(index_benchmark_filters.get("requested", False))
    candidate_files = (
        index_payload.get("candidate_files", [])
        if filters_applied_upstream
        else filter_candidate_path_items(
            index_payload.get("candidate_files", []),
            include_paths=included_candidate_paths,
            include_globs=included_candidate_globs,
            exclude_paths=excluded_candidate_paths,
            exclude_globs=excluded_candidate_globs,
        )
    )
    raw_candidate_chunks = (
        coerce_chunk_refs(index_payload.get("candidate_chunks", []))
        if filters_applied_upstream
        else filter_candidate_path_items(
            coerce_chunk_refs(index_payload.get("candidate_chunks", [])),
            include_paths=included_candidate_paths,
            include_globs=included_candidate_globs,
            exclude_paths=excluded_candidate_paths,
            exclude_globs=excluded_candidate_globs,
        )
    )
    source_plan_has_candidate_chunks = isinstance(
        source_plan_payload.get("candidate_chunks"),
        list,
    )
    source_plan_candidate_chunks = (
        coerce_chunk_refs(source_plan_payload.get("candidate_chunks", []))
        if filters_applied_upstream
        else filter_candidate_path_items(
            coerce_chunk_refs(source_plan_payload.get("candidate_chunks", [])),
            include_paths=included_candidate_paths,
            include_globs=included_candidate_globs,
            exclude_paths=excluded_candidate_paths,
            exclude_globs=excluded_candidate_globs,
        )
    )
    candidate_chunks = (
        source_plan_candidate_chunks
        if source_plan_has_candidate_chunks
        else raw_candidate_chunks
    )
    return CandidateContext(
        candidate_path_filters=candidate_path_filters,
        included_candidate_paths=included_candidate_paths,
        included_candidate_globs=included_candidate_globs,
        excluded_candidate_paths=excluded_candidate_paths,
        excluded_candidate_globs=excluded_candidate_globs,
        filters_applied_upstream=filters_applied_upstream,
        candidate_files=list(candidate_files) if isinstance(candidate_files, list) else [],
        raw_candidate_chunks=list(raw_candidate_chunks),
        source_plan_has_candidate_chunks=source_plan_has_candidate_chunks,
        source_plan_candidate_chunks=list(source_plan_candidate_chunks),
        candidate_chunks=list(candidate_chunks),
    )


__all__ = ["CandidateContext", "build_candidate_context"]
