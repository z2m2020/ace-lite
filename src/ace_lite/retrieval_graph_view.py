"""Read-only retrieval graph view builder.

This module produces a top-K candidate subgraph from an already-computed
plan payload. It is intentionally lightweight (no NetworkX, no external
services) and read-only (does not write files or call LLM APIs).

Schema version: ``retrieval_graph_view_v1``

Node sources:
- source_plan.candidate_files
- source_plan.candidate_chunks
- repomap.focused_files
- index.candidate_files

Edge sources:
- file -> chunk (path-based grouping)
- repomap neighbor relationships
- graph_lookup / cochange / SCIP / xref (from subgraph_payload and score_breakdown)

Default limit: 50 nodes. Schema scope field is always emitted.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ace_lite.plan_payload_view import (
    coerce_payload,
    resolve_candidate_chunks,
    resolve_candidate_files,
    resolve_repomap_payload,
    resolve_source_plan_payload,
    resolve_subgraph_payload,
)

__all__ = [
    "RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION",
    "build_retrieval_graph_view",
    "validate_retrieval_graph_view_payload",
]

RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION = "retrieval_graph_view_v1"


def _str(value: Any, default: str = "") -> str:
    return str(value) if value is not None else default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _dedup_label(path: str) -> str:
    return path.split("/")[-1].split("\\")[-1] or path


def _resolve_index_candidate_files(plan_payload: Mapping[str, Any] | Any) -> list[Any]:
    payload = coerce_payload(plan_payload)
    index_payload = _dict(payload.get("index", {}))
    return _list(index_payload.get("candidate_files", []))


def _build_nodes(
    *,
    plan_payload: Mapping[str, Any] | Any,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], set[str], list[str]]:
    """Build nodes from candidate files and chunks."""
    warnings: list[str] = []
    node_map: dict[str, dict[str, Any]] = {}
    chunk_nodes: list[dict[str, Any]] = []
    chunk_node_ids: set[str] = set()

    source_plan = resolve_source_plan_payload(plan_payload)
    candidate_files = resolve_candidate_files(plan_payload, source_plan=source_plan)
    candidate_chunks = resolve_candidate_chunks(plan_payload, source_plan=source_plan)
    index_files = _resolve_index_candidate_files(plan_payload)
    repomap = resolve_repomap_payload(plan_payload, source_plan=source_plan)
    repomap_focused = {
        str(path).strip() for path in _list(repomap.get("focused_files", [])) if str(path).strip()
    }

    for item in candidate_files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path or path in node_map:
            continue
        node_map[path] = {
            "id": path,
            "label": _dedup_label(path),
            "kind": "file",
            "path": path,
            "source": "source_plan",
            "score": _float(item.get("score", 0.0)),
            "chunk_count": 0,
        }

    for item in index_files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path or path in node_map:
            continue
        node_map[path] = {
            "id": path,
            "label": _dedup_label(path),
            "kind": "file",
            "path": path,
            "source": "index",
            "score": _float(item.get("score", 0.0)),
            "chunk_count": 0,
        }

    for chunk in candidate_chunks:
        if not isinstance(chunk, dict):
            continue
        path = str(chunk.get("path") or "").strip()
        qualified_name = str(chunk.get("qualified_name") or "").strip()
        if not path:
            continue

        chunk_id = f"{path}::{qualified_name}" if qualified_name else path
        if path in node_map:
            node_map[path]["chunk_count"] = node_map[path].get("chunk_count", 0) + 1
        if chunk_id in chunk_node_ids:
            continue

        chunk_node_ids.add(chunk_id)
        evidence_confidence = str(chunk.get("evidence_confidence", "")).strip().upper()
        chunk_nodes.append(
            {
                "id": chunk_id,
                "label": qualified_name or _dedup_label(path),
                "kind": str(chunk.get("kind", "chunk")),
                "path": path,
                "source": "source_plan",
                "score": _float(chunk.get("score", 0.0)),
                "lineno": _int(chunk.get("lineno", 0)),
                "end_lineno": _int(chunk.get("end_lineno", chunk.get("lineno", 0))),
                "evidence_confidence": evidence_confidence or None,
                "confidence_score": _float(chunk.get("confidence_score", 0.0))
                if evidence_confidence
                else None,
            }
        )

    for focused_path in repomap_focused:
        if focused_path not in node_map:
            node_map[focused_path] = {
                "id": focused_path,
                "label": _dedup_label(focused_path),
                "kind": "file",
                "path": focused_path,
                "source": "repomap",
                "score": 0.0,
                "chunk_count": 0,
            }
        elif node_map[focused_path]["source"] == "index":
            node_map[focused_path]["source"] = "repomap"

    all_nodes = list(node_map.values()) + chunk_nodes
    all_nodes.sort(key=lambda node: -_float(node.get("score", 0.0)))
    all_nodes = all_nodes[: max(1, _int(limit, 50))]
    node_ids = {node["id"] for node in all_nodes}

    if not all_nodes:
        warnings.append("no_nodes_available: candidate files and chunks are empty")

    return all_nodes, node_ids, warnings


def _build_edges(
    *,
    node_ids: set[str],
    plan_payload: Mapping[str, Any] | Any,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Build edges from file-chunk grouping and graph signals."""
    warnings: list[str] = []
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    source_plan = resolve_source_plan_payload(plan_payload)
    candidate_chunks = resolve_candidate_chunks(plan_payload, source_plan=source_plan)

    chunks_by_path: dict[str, list[dict[str, Any]]] = {}
    for chunk in candidate_chunks:
        if not isinstance(chunk, dict):
            continue
        path = str(chunk.get("path") or "").strip()
        if not path or path not in node_ids:
            continue
        chunks_by_path.setdefault(path, []).append(chunk)

    for path, chunks in chunks_by_path.items():
        for chunk in chunks:
            qualified_name = str(chunk.get("qualified_name") or "").strip()
            chunk_id = f"{path}::{qualified_name}" if qualified_name else path
            if chunk_id not in node_ids:
                continue
            edge_key = (path, chunk_id, "grouping")
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            edges.append(
                {
                    "id": f"{path}->{chunk_id}",
                    "source": path,
                    "target": chunk_id,
                    "kind": "grouping",
                    "predicate": "contains_chunk",
                    "confidence": 1.0,
                }
            )

    subgraph_payload = resolve_subgraph_payload(plan_payload, source_plan=source_plan)
    edge_counts = _dict(subgraph_payload.get("edge_counts", {}))
    seed_paths = _list(subgraph_payload.get("seed_paths", []))
    subgraph_keys: list[str] = []
    has_proxy_graph_signal = False

    for key, count in edge_counts.items():
        count_value = _float(count, 0.0)
        if count_value <= 0:
            continue
        subgraph_keys.append(str(key))
        for seed in seed_paths:
            if seed not in node_ids:
                continue
            has_proxy_graph_signal = True

    if has_proxy_graph_signal:
        warnings.append(
            f"graph_signals_proxy_only: subgraph edge types {subgraph_keys} detected "
            "but no real neighbor paths available - no directed edges created"
        )

    chunk_boost_signal_keys: list[str] = []
    graph_boost_keys = {
        "cochange_boost",
        "graph_closure_bonus",
        "graph_lookup_boost",
        "scip_reference_boost",
        "xref_boost",
        "coverage_boost",
    }
    for chunk in candidate_chunks:
        if not isinstance(chunk, dict):
            continue
        path = str(chunk.get("path") or "").strip()
        if path not in node_ids:
            continue
        score_breakdown = _dict(chunk.get("score_breakdown", {}))
        for boost_key in graph_boost_keys:
            if _float(score_breakdown.get(boost_key, 0.0)) <= 0:
                continue
            chunk_boost_signal_keys.append(f"{path}:{boost_key}")

    if chunk_boost_signal_keys:
        warnings.append(
            f"chunk_graph_signals_proxy_only: {len(chunk_boost_signal_keys)} "
            "chunk boost(s) detected but no real neighbor edges available - "
            f"signals: {chunk_boost_signal_keys[:5]}{'...' if len(chunk_boost_signal_keys) > 5 else ''}"
        )

    if not edges:
        warnings.append("no_edges_available: no stable graph signals found")

    return edges, warnings


def build_retrieval_graph_view(
    plan_payload: Mapping[str, Any] | Any,
    *,
    limit: int = 50,
    max_hops: int = 1,
    repo: str | None = None,
    root: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """Build a top-K retrieval subgraph from a plan payload."""
    payload = coerce_payload(plan_payload)
    resolved_repo = _str(repo or payload.get("repo", ""))
    resolved_root = _str(root or payload.get("root", ""))
    resolved_query = _str(query or payload.get("query", ""))
    resolved_limit = max(1, min(200, _int(limit, 50)))
    resolved_max_hops = max(1, min(3, _int(max_hops, 1)))

    source_plan = resolve_source_plan_payload(payload)
    candidate_files = resolve_candidate_files(payload, source_plan=source_plan)
    candidate_chunks = resolve_candidate_chunks(payload, source_plan=source_plan)
    index_files = _resolve_index_candidate_files(payload)
    repomap = resolve_repomap_payload(payload, source_plan=source_plan)
    repomap_focused = _list(repomap.get("focused_files", []))
    has_any_candidates = bool(candidate_files or candidate_chunks or index_files or repomap_focused)

    if not has_any_candidates:
        return {
            "ok": False,
            "schema_version": RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION,
            "repo": resolved_repo,
            "root": resolved_root,
            "query": resolved_query,
            "scope": {
                "repo": resolved_repo,
                "root": resolved_root,
                "limit": resolved_limit,
                "max_hops": resolved_max_hops,
            },
            "summary": {
                "node_count": 0,
                "edge_count": 0,
                "node_limit_applied": False,
                "max_hops": resolved_max_hops,
                "limit": resolved_limit,
            },
            "nodes": [],
            "edges": [],
            "warnings": ["empty_payload: no candidate files or chunks available"],
        }

    nodes, node_ids, node_warnings = _build_nodes(plan_payload=payload, limit=resolved_limit)
    edges, edge_warnings = _build_edges(node_ids=node_ids, plan_payload=payload)
    node_limit_applied = (
        len(candidate_files) + len(candidate_chunks) + len(index_files) > resolved_limit
    )

    warnings = [*node_warnings, *edge_warnings]
    if node_limit_applied:
        warnings.append(
            f"node_limit_applied: truncated from "
            f"{len(candidate_files) + len(candidate_chunks) + len(index_files)} "
            f"to {resolved_limit} nodes"
        )
    if resolved_max_hops < _int(max_hops, 1):
        warnings.append(f"max_hops_capped: requested {max_hops}, capped at {resolved_max_hops}")

    return {
        "ok": True,
        "schema_version": RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION,
        "repo": resolved_repo,
        "root": resolved_root,
        "query": resolved_query,
        "scope": {
            "repo": resolved_repo,
            "root": resolved_root,
            "limit": resolved_limit,
            "max_hops": resolved_max_hops,
        },
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "node_limit_applied": node_limit_applied,
            "max_hops": resolved_max_hops,
            "limit": resolved_limit,
        },
        "nodes": nodes,
        "edges": edges,
        "warnings": warnings,
    }


# ----------------------------------------------------------------------
# Schema guard
# ----------------------------------------------------------------------


def validate_retrieval_graph_view_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a retrieval_graph_view_v1 payload against required keys and types.

    Args:
        payload: A dict conforming (or claimed to conform) to retrieval_graph_view_v1.

    Returns:
        The validated payload as a dict.

    Raises:
        ValueError: if a required key is missing or has an invalid type.
    """
    if not isinstance(payload, dict):
        raise ValueError("retrieval_graph_view payload must be a dictionary")

    if payload.get("schema_version") != RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be '{RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION}'; "
            f"got {payload.get('schema_version')!r}"
        )

    _required_str_fields = ("repo", "root", "query")
    for field in _required_str_fields:
        value = payload.get(field)
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string; got {type(value).__name__}")

    for key in ("scope", "summary", "nodes", "edges", "warnings"):
        if key not in payload:
            raise ValueError(f"{key} is required")
        if key in ("scope", "summary") and not isinstance(payload[key], dict):
            raise ValueError(f"{key} must be a dict")
        if key in ("nodes", "edges", "warnings") and not isinstance(payload[key], list):
            raise ValueError(f"{key} must be a list")

    for key in ("limit", "max_hops"):
        if key not in payload.get("scope", {}):
            raise ValueError(f"scope.{key} is required")
    for key in ("node_count", "edge_count", "node_limit_applied"):
        if key not in payload.get("summary", {}):
            raise ValueError(f"summary.{key} is required")

    return dict(payload)
