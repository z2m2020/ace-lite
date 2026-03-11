from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCIP_PROVIDERS: tuple[str, ...] = (
    "auto",
    "scip_lite",
    "xref_json",
    "stack_graphs_json",
)


def _empty_payload(*, path: Path, provider: str, error: str = "") -> dict[str, Any]:
    payload = {
        "edge_count": 0,
        "inbound_counts": {},
        "pagerank": {},
        "degree_centrality": {},
        "edges": [],
        "loaded": False,
        "path": str(path),
        "provider": provider,
        "schema_version": "",
    }
    if error:
        payload["error"] = error
    return payload


def _normalize_provider(value: str) -> str:
    normalized = str(value or "auto").strip().lower() or "auto"
    return normalized if normalized in SCIP_PROVIDERS else "auto"


def _extract_path(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("path", "file", "uri", "document", "module"):
            candidate = str(value.get(key) or "").strip()
            if candidate:
                return candidate
    return ""


def _to_weight(value: Any) -> float:
    try:
        return max(0.0, float(value))
    except Exception:
        return 1.0


def _compute_inbound_from_edges(edges: list[dict[str, Any]]) -> dict[str, float]:
    inbound: dict[str, float] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        target = str(edge.get("target") or "").strip()
        if not target:
            continue
        inbound[target] = float(inbound.get(target, 0.0)) + _to_weight(
            edge.get("weight", 1.0)
        )
    return inbound


def _coerce_edges(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    edges: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue

        source = _extract_path(item.get("source"))
        if not source:
            source = _extract_path(item.get("from"))
        if not source:
            source = _extract_path(item.get("src"))
        if not source:
            source = _extract_path(item.get("source_path"))

        target = _extract_path(item.get("target"))
        if not target:
            target = _extract_path(item.get("to"))
        if not target:
            target = _extract_path(item.get("dst"))
        if not target:
            target = _extract_path(item.get("target_path"))

        if not source or not target:
            continue

        edges.append(
            {
                "source": source,
                "target": target,
                "weight": _to_weight(item.get("weight", 1.0)),
            }
        )
    return edges


def _coerce_inbound_counts(raw: Any) -> dict[str, float]:
    inbound: dict[str, float] = {}
    if not isinstance(raw, dict):
        return inbound

    for key, value in raw.items():
        name = str(key).strip()
        if not name:
            continue
        parsed: float | None
        try:
            parsed = float(value)
        except Exception:
            parsed = None
        if parsed is None:
            continue
        inbound[name] = max(0.0, parsed)
    return inbound


def _parse_scip_lite(payload: dict[str, Any], *, path: Path) -> dict[str, Any] | None:
    schema = str(payload.get("schema_version") or "").strip().lower()
    inbound_counts = _coerce_inbound_counts(payload.get("inbound_counts"))
    pagerank = _coerce_inbound_counts(payload.get("pagerank"))
    degree_centrality = _coerce_inbound_counts(
        payload.get("degree_centrality", payload.get("centrality"))
    )
    edges = _coerce_edges(payload.get("edges"))

    if not (schema.startswith("scip-lite") or inbound_counts or pagerank or degree_centrality or edges):
        return None

    if not inbound_counts and edges:
        inbound_counts = _compute_inbound_from_edges(edges)

    return {
        "edge_count": int(payload.get("edge_count", len(edges)) or 0),
        "inbound_counts": inbound_counts,
        "pagerank": pagerank,
        "degree_centrality": degree_centrality,
        "edges": edges,
        "loaded": True,
        "path": str(path),
        "provider": "scip_lite",
        "schema_version": schema or "scip-lite-unknown",
    }


def _parse_xref_json(payload: dict[str, Any], *, path: Path) -> dict[str, Any] | None:
    schema = str(payload.get("schema_version") or payload.get("protocol") or "").strip().lower()
    edges_raw = payload.get("edges", payload.get("references", []))
    edges = _coerce_edges(edges_raw)
    inbound_counts = _coerce_inbound_counts(payload.get("inbound_counts"))
    pagerank = _coerce_inbound_counts(payload.get("pagerank"))
    degree_centrality = _coerce_inbound_counts(
        payload.get("degree_centrality", payload.get("centrality"))
    )

    looks_like_xref = schema.startswith("xref") or schema.startswith("xrepo")
    if not (looks_like_xref or edges or inbound_counts or pagerank or degree_centrality):
        return None

    if not inbound_counts and edges:
        inbound_counts = _compute_inbound_from_edges(edges)

    return {
        "edge_count": int(payload.get("edge_count", len(edges)) or 0),
        "inbound_counts": inbound_counts,
        "pagerank": pagerank,
        "degree_centrality": degree_centrality,
        "edges": edges,
        "loaded": True,
        "path": str(path),
        "provider": "xref_json",
        "schema_version": schema or "xref-json-unknown",
    }


def _parse_stack_graphs(payload: dict[str, Any], *, path: Path) -> dict[str, Any] | None:
    schema = str(payload.get("schema_version") or payload.get("protocol") or "").strip().lower()
    graph_edges = payload.get("graph_edges", payload.get("edges", []))
    edges = _coerce_edges(graph_edges)
    inbound_counts = _coerce_inbound_counts(payload.get("inbound_counts"))
    pagerank = _coerce_inbound_counts(payload.get("pagerank"))
    degree_centrality = _coerce_inbound_counts(
        payload.get("degree_centrality", payload.get("centrality"))
    )

    looks_like_stack = "stack" in schema
    if not (looks_like_stack or edges or inbound_counts or pagerank or degree_centrality):
        return None

    if not inbound_counts and edges:
        inbound_counts = _compute_inbound_from_edges(edges)

    return {
        "edge_count": int(payload.get("edge_count", len(edges)) or 0),
        "inbound_counts": inbound_counts,
        "pagerank": pagerank,
        "degree_centrality": degree_centrality,
        "edges": edges,
        "loaded": True,
        "path": str(path),
        "provider": "stack_graphs_json",
        "schema_version": schema or "stack-graphs-json-unknown",
    }


def load_scip_edges(path: str | Path, *, provider: str = "auto") -> dict[str, Any]:
    source = Path(path)
    selected_provider = _normalize_provider(provider)

    if not source.exists() or not source.is_file():
        return _empty_payload(path=source, provider=selected_provider)

    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return _empty_payload(path=source, provider=selected_provider)

    if not isinstance(payload, dict):
        return _empty_payload(path=source, provider=selected_provider)

    parsers = {
        "scip_lite": _parse_scip_lite,
        "xref_json": _parse_xref_json,
        "stack_graphs_json": _parse_stack_graphs,
    }

    parser_order: list[str]
    if selected_provider == "auto":
        parser_order = ["scip_lite", "xref_json", "stack_graphs_json"]
    else:
        parser_order = [selected_provider]

    for parser_key in parser_order:
        parser = parsers[parser_key]
        parsed = parser(payload, path=source)
        if parsed is not None:
            return parsed

    return _empty_payload(path=source, provider=selected_provider)


__all__ = ["SCIP_PROVIDERS", "load_scip_edges"]
