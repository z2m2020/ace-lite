"""Unified graph context provider seam for chunk graph consumers."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from ace_lite.config_sections.runtime_helpers import DEFAULT_SCIP_INDEX_PATH
from ace_lite.index_stage.repo_paths import resolve_repo_relative_path
from ace_lite.repomap.adjacency import (
    _build_symbol_adjacency,
    _build_symbol_graph_context,
)
from ace_lite.scip import load_scip_edges

GRAPH_CONTEXT_PROVIDERS: tuple[str, ...] = (
    "auto",
    "adjacency",
    "scip",
    "scip_lite",
    "xref_json",
    "stack_graphs_json",
)
_SCIP_GRAPH_CONTEXT_PROVIDERS = frozenset(
    {"scip", "scip_lite", "xref_json", "stack_graphs_json"}
)
_GRAPH_CONTEXT_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_GRAPH_CONTEXT_CACHE_CAP = 8


def _normalize_graph_context_provider(value: Any) -> str:
    normalized = str(value or "auto").strip().lower() or "auto"
    return normalized if normalized in GRAPH_CONTEXT_PROVIDERS else "auto"


def _resolve_graph_context_provider(policy: dict[str, Any] | None) -> str:
    if not isinstance(policy, dict):
        return "auto"
    for key in ("chunk_graph_context_provider", "chunk_graph_provider"):
        if key in policy:
            return _normalize_graph_context_provider(policy.get(key))
    return "auto"


def _graph_context_cache_key(*, cache_key: str, provider_requested: str) -> str:
    normalized_key = str(cache_key or "").strip()
    if not normalized_key:
        return ""
    return f"graph_context:v1:{provider_requested}:{normalized_key}"


def _empty_graph_context(
    *,
    provider_requested: str,
    provider_selected: str,
    provider_fallback: bool,
    fallback_reason: str,
    graph_scope: str,
    cache_key: str,
) -> dict[str, Any]:
    return {
        "provider_requested": str(provider_requested or "auto"),
        "provider_selected": str(provider_selected or "adjacency"),
        "provider_fallback": bool(provider_fallback),
        "fallback_reason": str(fallback_reason or ""),
        "graph_scope": str(graph_scope or "symbol"),
        "loaded": False,
        "cache_key": str(cache_key or ""),
        "adjacency": {},
        "inbound_degree": {},
        "file_adjacency": {},
        "file_inbound_degree": {},
        "pagerank": {},
        "degree_centrality": {},
        "source_provider_selected": str(provider_selected or "adjacency"),
        "source_provider_loaded": False,
        "source_graph_scope": str(graph_scope or "symbol"),
        "source_path": "",
        "source_schema_version": "",
        "source_edge_count": 0,
        "source_projection_fallback": False,
        "source_projection_reason": "",
    }


def _build_adjacency_graph_context(
    *,
    files_map: dict[str, dict[str, Any]],
    provider_requested: str,
    cache_key: str,
    provider_fallback: bool = False,
    fallback_reason: str = "",
) -> dict[str, Any]:
    context = _empty_graph_context(
        provider_requested=provider_requested,
        provider_selected="adjacency",
        provider_fallback=provider_fallback,
        fallback_reason=fallback_reason,
        graph_scope="symbol",
        cache_key=cache_key,
    )

    symbol_nodes_by_path, symbol_to_node_ids = _build_symbol_graph_context(files=files_map)
    adjacency = _build_symbol_adjacency(
        files=files_map,
        nodes_by_path=symbol_nodes_by_path,
        symbol_to_node_ids=symbol_to_node_ids,
    )

    inbound_degree: dict[str, int] = {}
    for source_id, targets in adjacency.items():
        if source_id not in inbound_degree:
            inbound_degree[source_id] = 0
        if not isinstance(targets, list):
            continue
        for target_id in targets:
            normalized = str(target_id or "").strip()
            if not normalized:
                continue
            inbound_degree[normalized] = inbound_degree.get(normalized, 0) + 1

    context.update(
        {
            "loaded": True,
            "adjacency": adjacency,
            "inbound_degree": inbound_degree,
            "source_provider_selected": "adjacency",
            "source_provider_loaded": True,
            "source_graph_scope": "symbol",
        }
    )
    return context


def _resolve_scip_index_path(*, root: str, policy: dict[str, Any] | None) -> str:
    configured_path = DEFAULT_SCIP_INDEX_PATH
    if isinstance(policy, dict):
        for key in ("chunk_graph_scip_index_path", "scip_index_path"):
            candidate = str(policy.get(key) or "").strip()
            if candidate:
                configured_path = candidate
                break
    resolved = resolve_repo_relative_path(root=root or ".", configured_path=configured_path)
    return str(resolved)


def _build_file_adjacency(edges: Any) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {}
    if not isinstance(edges, list):
        return adjacency
    for item in edges:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        if not source or not target:
            continue
        adjacency.setdefault(source, [])
        if target not in adjacency[source]:
            adjacency[source].append(target)
    return adjacency


def _build_scip_graph_context(
    *,
    root: str,
    files_map: dict[str, dict[str, Any]],
    provider_requested: str,
    cache_key: str,
    policy: dict[str, Any] | None,
) -> dict[str, Any]:
    scip_index_path = _resolve_scip_index_path(root=root, policy=policy)
    loaded = load_scip_edges(scip_index_path, provider=provider_requested)
    if not bool(loaded.get("loaded", False)):
        context = _build_adjacency_graph_context(
            files_map=files_map,
            provider_requested=provider_requested,
            cache_key=cache_key,
            provider_fallback=True,
            fallback_reason="scip_source_unavailable",
        )
        context["source_path"] = str(scip_index_path)
        return context

    context = _build_adjacency_graph_context(
        files_map=files_map,
        provider_requested=provider_requested,
        cache_key=cache_key,
        provider_fallback=True,
        fallback_reason="file_scope_symbol_projection_pending",
    )
    context.update(
        {
            "file_adjacency": _build_file_adjacency(loaded.get("edges")),
            "file_inbound_degree": (
                dict(loaded.get("inbound_counts"))
                if isinstance(loaded.get("inbound_counts"), dict)
                else {}
            ),
            "pagerank": (
                dict(loaded.get("pagerank"))
                if isinstance(loaded.get("pagerank"), dict)
                else {}
            ),
            "degree_centrality": (
                dict(loaded.get("degree_centrality"))
                if isinstance(loaded.get("degree_centrality"), dict)
                else {}
            ),
            "source_provider_selected": str(
                loaded.get("provider") or provider_requested or "scip"
            ),
            "source_provider_loaded": True,
            "source_graph_scope": "file",
            "source_path": str(loaded.get("path") or scip_index_path),
            "source_schema_version": str(loaded.get("schema_version") or ""),
            "source_edge_count": int(loaded.get("edge_count", 0) or 0),
            "source_projection_fallback": True,
            "source_projection_reason": "file_scope_symbol_projection_pending",
        }
    )
    return context


def _build_graph_context(
    *,
    root: str,
    files_map: dict[str, dict[str, Any]],
    provider_requested: str,
    cache_key: str,
    policy: dict[str, Any] | None,
) -> dict[str, Any]:
    if provider_requested in _SCIP_GRAPH_CONTEXT_PROVIDERS:
        return _build_scip_graph_context(
            root=root,
            files_map=files_map,
            provider_requested=provider_requested,
            cache_key=cache_key,
            policy=policy,
        )
    return _build_adjacency_graph_context(
        files_map=files_map,
        provider_requested=provider_requested,
        cache_key=cache_key,
    )


def get_graph_context(
    *,
    root: str = ".",
    files_map: dict[str, dict[str, Any]],
    cache_key: str,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider_requested = _resolve_graph_context_provider(policy)
    resolved_cache_key = _graph_context_cache_key(
        cache_key=cache_key,
        provider_requested=provider_requested,
    )
    if resolved_cache_key:
        cached = _GRAPH_CONTEXT_CACHE.get(resolved_cache_key)
        if isinstance(cached, dict):
            _GRAPH_CONTEXT_CACHE.move_to_end(resolved_cache_key)
            return cached

    context = _build_graph_context(
        root=root,
        files_map=files_map,
        provider_requested=provider_requested,
        cache_key=resolved_cache_key,
        policy=policy,
    )
    if resolved_cache_key:
        _GRAPH_CONTEXT_CACHE[resolved_cache_key] = context
        _GRAPH_CONTEXT_CACHE.move_to_end(resolved_cache_key)
        while len(_GRAPH_CONTEXT_CACHE) > _GRAPH_CONTEXT_CACHE_CAP:
            _GRAPH_CONTEXT_CACHE.popitem(last=False)
    return context


def build_graph_context_payload(context: dict[str, Any] | None) -> dict[str, Any]:
    payload = context if isinstance(context, dict) else {}
    return {
        "graph_provider_requested": str(payload.get("provider_requested", "auto")),
        "graph_provider_selected": str(payload.get("provider_selected", "adjacency")),
        "graph_provider_fallback": bool(payload.get("provider_fallback", False)),
        "graph_fallback_reason": str(payload.get("fallback_reason", "")),
        "graph_scope": str(payload.get("graph_scope", "symbol")),
        "graph_source_provider_selected": str(
            payload.get("source_provider_selected", "adjacency")
        ),
        "graph_source_provider_loaded": bool(
            payload.get("source_provider_loaded", False)
        ),
        "graph_source_graph_scope": str(
            payload.get("source_graph_scope", "symbol")
        ),
        "graph_source_edge_count": int(payload.get("source_edge_count", 0) or 0),
        "graph_source_projection_fallback": bool(
            payload.get("source_projection_fallback", False)
        ),
        "graph_source_projection_reason": str(
            payload.get("source_projection_reason", "")
        ),
    }


__all__ = ["GRAPH_CONTEXT_PROVIDERS", "build_graph_context_payload", "get_graph_context"]
