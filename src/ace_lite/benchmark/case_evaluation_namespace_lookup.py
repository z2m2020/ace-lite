"""Shared namespace lookup helpers for case-evaluation entry seams."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def lookup_case_evaluation_value(
    namespace: Mapping[str, Any],
    key: str,
    *,
    error_prefix: str,
) -> Any:
    if key in namespace:
        return namespace[key]

    for source_name in ("metrics", "diagnostics", "candidate_context"):
        source = namespace.get(source_name)
        if source is not None and hasattr(source, key):
            return getattr(source, key)

    for source_name in ("candidate_match_details", "chunk_match_details"):
        source = namespace.get(source_name)
        if isinstance(source, dict) and key in source:
            return source[key]

    raise KeyError(f"missing {error_prefix}: {key}")


__all__ = ["lookup_case_evaluation_value"]
