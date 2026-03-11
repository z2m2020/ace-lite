from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _compute_pagerank(
    *,
    nodes: list[str],
    edges: list[dict[str, Any]],
    iterations: int = 20,
    damping: float = 0.85,
) -> dict[str, float]:
    if not nodes:
        return {}

    normalized_nodes = [str(node) for node in nodes if str(node).strip()]
    if not normalized_nodes:
        return {}

    n = len(normalized_nodes)
    base_rank = 1.0 / float(n)
    rank: dict[str, float] = {node: base_rank for node in normalized_nodes}

    out_weights: dict[str, float] = {}
    inbound: dict[str, list[tuple[str, float]]] = {node: [] for node in normalized_nodes}

    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if not source or not target or source not in rank or target not in rank:
            continue
        try:
            weight = float(edge.get("weight") or 0.0)
        except Exception:
            weight = 0.0
        if weight <= 0.0:
            continue
        out_weights[source] = float(out_weights.get(source, 0.0)) + weight
        inbound[target].append((source, weight))

    normalized_damping = float(damping)
    if normalized_damping < 0.0:
        normalized_damping = 0.0
    if normalized_damping > 1.0:
        normalized_damping = 1.0
    iterations_effective = max(1, int(iterations))

    base = (1.0 - normalized_damping) / float(n)

    for _ in range(iterations_effective):
        dangling_sum = sum(
            float(rank.get(node, 0.0))
            for node in normalized_nodes
            if float(out_weights.get(node, 0.0)) <= 0.0
        )
        dangling_contrib = normalized_damping * dangling_sum / float(n)

        updated: dict[str, float] = {}
        for node in normalized_nodes:
            incoming = 0.0
            for source, weight in inbound.get(node, []):
                denom = float(out_weights.get(source, 0.0))
                if denom <= 0.0:
                    continue
                incoming += float(rank.get(source, 0.0)) * (float(weight) / denom)
            updated[node] = base + dangling_contrib + normalized_damping * incoming
        rank = updated

    total = sum(rank.values())
    if total > 0.0:
        rank = {node: float(value) / total for node, value in rank.items()}
    return {node: float(rank.get(node, 0.0)) for node in normalized_nodes}


def _symbol_keys(entry: dict[str, Any]) -> list[str]:
    symbols = entry.get("symbols", [])
    if not isinstance(symbols, list):
        return []

    keys: list[str] = []
    for item in symbols:
        if not isinstance(item, dict):
            continue
        qualified_name = str(item.get("qualified_name") or "").strip().lstrip(".")
        name = str(item.get("name") or "").strip().lstrip(".")
        for candidate in (qualified_name, name):
            if candidate and candidate not in keys:
                keys.append(candidate)
    return keys


def _reference_keys(entry: dict[str, Any]) -> list[str]:
    references = entry.get("references", [])
    if not isinstance(references, list):
        return []

    keys: list[str] = []
    for item in references:
        if not isinstance(item, dict):
            continue
        qualified_name = str(item.get("qualified_name") or "").strip().lstrip(".")
        name = str(item.get("name") or "").strip().lstrip(".")
        candidate = qualified_name or name
        if candidate and candidate not in keys:
            keys.append(candidate)
    return keys


def _tail_symbol(value: str) -> str:
    parts = str(value or "").replace("/", ".").split(".")
    for item in reversed(parts):
        token = item.strip()
        if token:
            return token
    return ""


def generate_scip_index(*, index_files: dict[str, dict[str, Any]], output_path: str | Path) -> dict[str, Any]:
    symbol_to_paths: dict[str, set[str]] = {}

    for path, entry in index_files.items():
        if not isinstance(path, str) or not isinstance(entry, dict):
            continue
        for symbol in _symbol_keys(entry):
            symbol_to_paths.setdefault(symbol, set()).add(path)
            tail = _tail_symbol(symbol)
            if tail:
                symbol_to_paths.setdefault(tail, set()).add(path)

    edge_weights: dict[tuple[str, str], float] = {}
    inbound_counts: dict[str, float] = {}

    for source_path, entry in index_files.items():
        if not isinstance(source_path, str) or not isinstance(entry, dict):
            continue
        for reference in _reference_keys(entry):
            candidates = [reference]
            tail = _tail_symbol(reference)
            if tail and tail not in candidates:
                candidates.append(tail)

            matched_targets: set[str] = set()
            for candidate in candidates:
                matched_targets.update(symbol_to_paths.get(candidate, set()))

            for target in sorted(matched_targets):
                if target == source_path:
                    continue
                key = (source_path, target)
                edge_weights[key] = float(edge_weights.get(key, 0.0)) + 1.0
                inbound_counts[target] = float(inbound_counts.get(target, 0.0)) + 1.0

    edges: list[dict[str, Any]] = [
        {
            "source": source,
            "target": target,
            "weight": float(weight),
        }
        for (source, target), weight in sorted(edge_weights.items(), key=lambda item: (item[0][0], item[0][1]))
    ]

    nodes = sorted(
        {
            str(path)
            for path in index_files
            if isinstance(path, str) and path.strip()
        }
    )
    pagerank = _compute_pagerank(nodes=nodes, edges=edges, iterations=20, damping=0.85)
    sorted_pagerank = {path: float(pagerank.get(path, 0.0)) for path in sorted(pagerank)}

    outbound_counts: dict[str, float] = {}
    for edge in edges:
        source = str(edge.get("source") or "").strip()
        if not source:
            continue
        try:
            weight = float(edge.get("weight") or 0.0)
        except Exception:
            weight = 0.0
        outbound_counts[source] = float(outbound_counts.get(source, 0.0)) + weight
    degree_centrality = {
        path: float(inbound_counts.get(path, 0.0)) + float(outbound_counts.get(path, 0.0))
        for path in nodes
    }
    sorted_degree_centrality = {
        path: float(degree_centrality.get(path, 0.0))
        for path in sorted(degree_centrality)
    }

    sorted_inbound_counts = {
        path: float(score)
        for path, score in sorted(inbound_counts.items(), key=lambda item: item[0])
    }
    payload = {
        "schema_version": "scip-lite-2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "edge_count": len(edges),
        "inbound_counts": sorted_inbound_counts,
        "pagerank": sorted_pagerank,
        "degree_centrality": sorted_degree_centrality,
        "edges": edges,
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "path": str(output),
        "edge_count": len(edges),
        "inbound_counts": dict(sorted_inbound_counts),
        "pagerank": dict(sorted_pagerank),
        "degree_centrality": dict(sorted_degree_centrality),
    }


__all__ = ["generate_scip_index"]

