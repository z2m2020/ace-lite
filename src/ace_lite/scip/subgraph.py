from __future__ import annotations

from typing import Any

SUBGRAPH_PAYLOAD_VERSION = "subgraph_payload_v1"
SUBGRAPH_EDGE_TAXONOMY_VERSION = "subgraph_edge_taxonomy_v1"
_EDGE_KEYS = ("graph_lookup", "graph_prior", "graph_closure_bonus")


def _coerce_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [item for item in rows if isinstance(item, dict)]


def _positive_breakdown_value(item: dict[str, Any], key: str) -> bool:
    breakdown = item.get("score_breakdown")
    if not isinstance(breakdown, dict):
        return False
    try:
        return float(breakdown.get(key, 0.0) or 0.0) > 0.0
    except Exception:
        return False


def _collect_edge_paths(rows: list[dict[str, Any]], key: str) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for item in rows:
        if not _positive_breakdown_value(item, key):
            continue
        path = str(item.get("path") or "").strip()
        if not path or path in seen:
            continue
        seen.add(path)
        paths.append(path)
    return paths


def build_subgraph_payload(
    *,
    candidate_files: list[dict[str, Any]] | None,
    candidate_chunks: list[dict[str, Any]] | None,
    graph_lookup_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    file_rows = _coerce_rows(candidate_files)
    chunk_rows = _coerce_rows(candidate_chunks)
    combined_rows = [*file_rows, *chunk_rows]
    graph_payload = graph_lookup_payload if isinstance(graph_lookup_payload, dict) else {}

    edge_counts: dict[str, int] = {}
    seed_paths: list[str] = []
    seen_paths: set[str] = set()
    for key in _EDGE_KEYS:
        paths = _collect_edge_paths(combined_rows, key)
        if paths:
            edge_counts[key] = len(paths)
        for path in paths:
            if path in seen_paths:
                continue
            seen_paths.add(path)
            seed_paths.append(path)

    enabled = bool(graph_payload.get("enabled", False)) or bool(edge_counts)
    reason = str(graph_payload.get("reason") or "").strip()
    if not reason:
        reason = "ok" if edge_counts else "disabled"

    return {
        "payload_version": SUBGRAPH_PAYLOAD_VERSION,
        "taxonomy_version": SUBGRAPH_EDGE_TAXONOMY_VERSION,
        "enabled": bool(enabled),
        "reason": reason,
        "seed_paths": seed_paths,
        "edge_counts": edge_counts,
    }


__all__ = [
    "SUBGRAPH_EDGE_TAXONOMY_VERSION",
    "SUBGRAPH_PAYLOAD_VERSION",
    "build_subgraph_payload",
]
