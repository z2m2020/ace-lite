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

from typing import Any

__all__ = [
    "RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION",
    "build_retrieval_graph_view",
]

RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION = "retrieval_graph_view_v1"

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


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


def _bool(value: Any, default: bool = False) -> bool:
    return bool(value) if isinstance(value, (bool, type(None))) else default


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _dedup_label(path: str) -> str:
    return path.split("/")[-1].split("\\")[-1] or path


# ----------------------------------------------------------------------
# Node builder
# ----------------------------------------------------------------------


def _build_nodes(
    *,
    plan_payload: dict[str, Any],
    limit: int = 50,
) -> tuple[list[dict[str, Any]], set[str], list[str]]:
    """Build nodes from candidate files and chunks.

    Returns (nodes, node_ids_set, warnings).
    """
    warnings: list[str] = []
    node_map: dict[str, dict[str, Any]] = {}
    chunk_nodes: list[dict[str, Any]] = []

    sp = _dict(plan_payload.get("source_plan", {}))
    candidate_files_sp = _list(sp.get("candidate_files", [])) or _list(
        plan_payload.get("candidate_files", [])
    )
    candidate_chunks = _list(sp.get("candidate_chunks", [])) or _list(
        plan_payload.get("candidate_chunks", [])
    )
    index_payload = _dict(plan_payload.get("index", {}))
    index_files = _list(index_payload.get("candidate_files", []))
    repomap = _dict(plan_payload.get("repomap", {}))
    repomap_focused = {
        str(p).strip() for p in _list(repomap.get("focused_files", [])) if str(p).strip()
    }

    # Collect file-level nodes (deduplicated by path)
    for item in candidate_files_sp + index_files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        if path in node_map:
            continue
        score = _float(item.get("score", 0.0))
        source = "source_plan" if item in candidate_files_sp else "index"
        node_map[path] = {
            "id": path,
            "label": _dedup_label(path),
            "kind": "file",
            "path": path,
            "source": source,
            "score": score,
            "chunk_count": 0,
        }

    # Collect chunk-level nodes (deduplicated by path+qualified_name)
    for chunk in candidate_chunks:
        if not isinstance(chunk, dict):
            continue
        path = str(chunk.get("path") or "").strip()
        qualified_name = str(chunk.get("qualified_name") or "").strip()
        chunk_id = f"{path}::{qualified_name}" if qualified_name else path
        if not path:
            continue
        score = _float(chunk.get("score", 0.0))
        lineno = _int(chunk.get("lineno", 0))
        end_lineno = _int(chunk.get("end_lineno", lineno))

        evidence_confidence = str(chunk.get("evidence_confidence", "")).strip().upper()
        confidence_score = _float(chunk.get("confidence_score", 0.0))

        # Track file node chunk_count
        if path in node_map:
            node_map[path]["chunk_count"] = node_map[path].get("chunk_count", 0) + 1

        if chunk_id in {n["id"] for n in chunk_nodes}:
            continue

        chunk_nodes.append(
            {
                "id": chunk_id,
                "label": qualified_name or _dedup_label(path),
                "kind": str(chunk.get("kind", "chunk")),
                "path": path,
                "source": "source_plan",
                "score": score,
                "lineno": lineno,
                "end_lineno": end_lineno,
                "evidence_confidence": evidence_confidence or None,
                "confidence_score": confidence_score if evidence_confidence else None,
            }
        )

    # Add repomap-focused files as separate source if not already present
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

    # Combine file and chunk nodes, sorted by score descending
    all_nodes: list[dict[str, Any]] = list(node_map.values()) + chunk_nodes
    all_nodes.sort(key=lambda n: -n["score"])
    resolved_limit = max(1, _int(limit, 50))
    all_nodes = all_nodes[:resolved_limit]

    node_ids = {n["id"] for n in all_nodes}

    if len(all_nodes) == 0:
        warnings.append("no_nodes_available: candidate files and chunks are empty")

    return all_nodes, node_ids, warnings


# ----------------------------------------------------------------------
# Edge builder
# ----------------------------------------------------------------------


def _build_edges(
    *,
    nodes: list[dict[str, Any]],
    node_ids: set[str],
    plan_payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Build edges from file-chunk grouping and graph signals.

    Returns (edges, warnings).
    """
    warnings: list[str] = []
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    # 1. File -> chunk grouping edges
    chunks_by_path: dict[str, list[dict[str, Any]]] = {}
    sp = _dict(plan_payload.get("source_plan", {}))
    candidate_chunks = _list(sp.get("candidate_chunks", [])) or _list(
        plan_payload.get("candidate_chunks", [])
    )
    for chunk in candidate_chunks:
        if not isinstance(chunk, dict):
            continue
        path = str(chunk.get("path") or "").strip()
        if not path or path not in node_ids:
            continue
        if path not in chunks_by_path:
            chunks_by_path[path] = []
        chunks_by_path[path].append(chunk)

    for path, chunks in chunks_by_path.items():
        file_node_id = path
        for chunk in chunks:
            qualified_name = str(chunk.get("qualified_name") or "").strip()
            chunk_id = f"{path}::{qualified_name}" if qualified_name else path
            if chunk_id not in node_ids:
                continue
            edge_key = (file_node_id, chunk_id, "grouping")
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            edges.append(
                {
                    "id": f"{file_node_id}->{chunk_id}",
                    "source": file_node_id,
                    "target": chunk_id,
                    "kind": "grouping",
                    "predicate": "contains_chunk",
                    "confidence": 1.0,
                }
            )

    # 2. Subgraph payload edges (repomap neighbors)
    subgraph_payload = _dict(sp.get("subgraph_payload", {})) or _dict(
        plan_payload.get("subgraph_payload", {})
    )
    edge_counts = _dict(subgraph_payload.get("edge_counts", {}))
    seed_paths = _list(subgraph_payload.get("seed_paths", []))
    has_valid_subgraph_edges = False
    subgraph_keys: list[str] = []
    for key, count in edge_counts.items():
        count_value = _float(count, 0.0)
        if count_value <= 0:
            continue
        subgraph_keys.append(str(key))
        key_label = key.replace("_edges", "").replace("_", "-")
        for seed in seed_paths:
            if seed not in node_ids:
                continue
            # We only have seed paths (query anchors), not actual neighbor paths,
            # so we cannot create valid directed edges without fabricating them.
            # Do NOT create self-loop proxy edges — they misrepresent graph structure.
            has_valid_subgraph_edges = True
            _ = (seed, key_label, count_value)
    if has_valid_subgraph_edges:
        warnings.append(
            f"graph_signals_proxy_only: subgraph edge types {subgraph_keys} detected "
            "but no real neighbor paths available — no directed edges created"
        )

    # 3. Score breakdown graph signals in chunks (cochange, graph_closure, etc.)
    # Do NOT create self-loop edges (source == target) for chunk boosts —
    # they misrepresent graph connectivity. Chunk boosts are informational signals
    # stored on the node itself, not actual edges.
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
            boost_val = _float(score_breakdown.get(boost_key, 0.0))
            if boost_val <= 0:
                continue
            # Collect boost keys for informational signal only; do NOT create
            # self-loop edges — they misrepresent graph connectivity.
            chunk_boost_signal_keys.append(f"{path}:{boost_key}")

    if chunk_boost_signal_keys:
        warnings.append(
            f"chunk_graph_signals_proxy_only: {len(chunk_boost_signal_keys)} "
            "chunk boost(s) detected but no real neighbor edges available — "
            f"signals: {chunk_boost_signal_keys[:5]}{'...' if len(chunk_boost_signal_keys) > 5 else ''}"
        )

    if not edges:
        warnings.append("no_edges_available: no stable graph signals found")

    return edges, warnings


# ----------------------------------------------------------------------
# Main builder
# ----------------------------------------------------------------------


def build_retrieval_graph_view(
    plan_payload: dict[str, Any],
    *,
    limit: int = 50,
    max_hops: int = 1,
    repo: str | None = None,
    root: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """Build a top-K retrieval subgraph from a plan payload.

    This function is read-only and does not modify the input payload.

    Args:
        plan_payload: A plan output dict (must contain at least
            candidate_files or candidate_chunks).
        limit: Maximum number of nodes to emit (default 50).
        max_hops: Maximum graph traversal depth (default 1; higher values
            are accepted but effectively capped by node limit).
        repo: Override repo name (defaults to plan_payload.repo).
        root: Override root path (defaults to plan_payload.root).
        query: Override query string (defaults to plan_payload.query).

    Returns:
        A dict conforming to the ``retrieval_graph_view_v1`` schema:
        - ok: bool
        - schema_version: "retrieval_graph_view_v1"
        - repo, root, query, scope
        - summary: node_count, edge_count, node_limit_applied
        - nodes: list[dict]
        - edges: list[dict]
        - warnings: list[str]
    """
    resolved_repo = _str(repo or plan_payload.get("repo", ""))
    resolved_root = _str(root or plan_payload.get("root", ""))
    resolved_query = _str(query or plan_payload.get("query", ""))
    resolved_limit = max(1, min(200, _int(limit, 50)))
    resolved_max_hops = max(1, min(3, _int(max_hops, 1)))

    # Graceful empty handling
    sp = _dict(plan_payload.get("source_plan", {}))
    candidate_files = _list(sp.get("candidate_files", [])) or _list(
        plan_payload.get("candidate_files", [])
    )
    index_files = _list(_dict(plan_payload.get("index", {})).get("candidate_files", []))
    candidate_chunks = _list(sp.get("candidate_chunks", [])) or _list(
        plan_payload.get("candidate_chunks", [])
    )
    repomap_focused = _list(_dict(plan_payload.get("repomap", {})).get("focused_files", []))
    has_any_candidates = bool(candidate_files or index_files or candidate_chunks or repomap_focused)

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

    nodes, node_ids, node_warnings = _build_nodes(
        plan_payload=plan_payload,
        limit=resolved_limit,
    )
    edges, edge_warnings = _build_edges(
        nodes=nodes,
        node_ids=node_ids,
        plan_payload=plan_payload,
    )

    all_warnings = list(node_warnings)
    all_warnings.extend(edge_warnings)

    node_limit_applied = (
        len(candidate_files) + len(index_files) + len(candidate_chunks) > resolved_limit
    )

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
        "warnings": all_warnings,
    }
