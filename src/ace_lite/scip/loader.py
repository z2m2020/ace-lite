from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCIP_PROVIDERS: tuple[str, ...] = (
    "auto",
    "scip",
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
        "document_count": 0,
        "definition_occurrence_count": 0,
        "reference_occurrence_count": 0,
        "symbol_definition_count": 0,
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


def _coerce_symbol_roles(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _is_definition_occurrence(symbol_roles: int) -> bool:
    # Mirrors SCIP SymbolRole bit flags for Definition and ForwardDefinition.
    return bool(symbol_roles & 0x1) or bool(symbol_roles & 0x40)


def _extract_document_path(document: dict[str, Any]) -> str:
    return _extract_path(
        document.get("relative_path")
        or document.get("path")
        or document.get("document")
        or document.get("uri")
    )


def _extract_document_symbols(document: dict[str, Any]) -> list[str]:
    symbols_raw = document.get("symbols")
    symbols = symbols_raw if isinstance(symbols_raw, list) else []
    collected: list[str] = []
    for item in symbols:
        if isinstance(item, str):
            symbol = item.strip()
        elif isinstance(item, dict):
            symbol = str(item.get("symbol") or "").strip()
        else:
            symbol = ""
        if symbol:
            collected.append(symbol)
    return collected


def _parse_scip(payload: dict[str, Any], *, path: Path) -> dict[str, Any] | None:
    documents_raw = payload.get("documents")
    documents = documents_raw if isinstance(documents_raw, list) else []
    if not documents:
        return None

    schema = str(payload.get("schema_version") or payload.get("protocol") or "scip").strip().lower()
    symbol_to_paths: dict[str, set[str]] = {}
    document_paths: list[str] = []
    definition_occurrence_count = 0
    reference_occurrence_count = 0

    for item in documents:
        if not isinstance(item, dict):
            continue
        document_path = _extract_document_path(item)
        if not document_path:
            continue
        document_paths.append(document_path)
        occurrences_raw = item.get("occurrences")
        occurrences = occurrences_raw if isinstance(occurrences_raw, list) else []

        for occurrence in occurrences:
            if not isinstance(occurrence, dict):
                continue
            symbol = str(occurrence.get("symbol") or "").strip()
            if not symbol:
                continue
            symbol_roles = _coerce_symbol_roles(occurrence.get("symbol_roles"))
            if not _is_definition_occurrence(symbol_roles):
                continue
            definition_occurrence_count += 1
            symbol_to_paths.setdefault(symbol, set()).add(document_path)

    if not symbol_to_paths:
        for item in documents:
            if not isinstance(item, dict):
                continue
            document_path = _extract_document_path(item)
            if not document_path:
                continue
            for symbol in _extract_document_symbols(item):
                symbol_to_paths.setdefault(symbol, set()).add(document_path)

    edge_weights: dict[tuple[str, str], float] = {}
    for item in documents:
        if not isinstance(item, dict):
            continue
        source_path = _extract_document_path(item)
        if not source_path:
            continue
        occurrences_raw = item.get("occurrences")
        occurrences = occurrences_raw if isinstance(occurrences_raw, list) else []
        for occurrence in occurrences:
            if not isinstance(occurrence, dict):
                continue
            symbol = str(occurrence.get("symbol") or "").strip()
            if not symbol:
                continue
            symbol_roles = _coerce_symbol_roles(occurrence.get("symbol_roles"))
            if _is_definition_occurrence(symbol_roles):
                continue
            reference_occurrence_count += 1
            for target_path in sorted(symbol_to_paths.get(symbol, ())):
                if not target_path or target_path == source_path:
                    continue
                edge_key = (source_path, target_path)
                edge_weights[edge_key] = float(edge_weights.get(edge_key, 0.0)) + 1.0

    edges = [
        {"source": source, "target": target, "weight": weight}
        for (source, target), weight in sorted(edge_weights.items())
    ]
    inbound_counts = _compute_inbound_from_edges(edges) if edges else {}

    if not symbol_to_paths and not document_paths:
        return None

    return {
        "edge_count": len(edges),
        "inbound_counts": inbound_counts,
        "pagerank": {},
        "degree_centrality": {},
        "edges": edges,
        "document_count": len(document_paths),
        "definition_occurrence_count": definition_occurrence_count,
        "reference_occurrence_count": reference_occurrence_count,
        "symbol_definition_count": len(symbol_to_paths),
        "loaded": True,
        "path": str(path),
        "provider": "scip",
        "schema_version": schema or "scip",
    }


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
        "document_count": 0,
        "definition_occurrence_count": 0,
        "reference_occurrence_count": 0,
        "symbol_definition_count": 0,
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
        "document_count": 0,
        "definition_occurrence_count": 0,
        "reference_occurrence_count": 0,
        "symbol_definition_count": 0,
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
        "document_count": 0,
        "definition_occurrence_count": 0,
        "reference_occurrence_count": 0,
        "symbol_definition_count": 0,
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
        "scip": _parse_scip,
        "scip_lite": _parse_scip_lite,
        "xref_json": _parse_xref_json,
        "stack_graphs_json": _parse_stack_graphs,
    }

    parser_order: list[str]
    if selected_provider == "auto":
        parser_order = ["scip", "scip_lite", "xref_json", "stack_graphs_json"]
    else:
        parser_order = [selected_provider]

    for parser_key in parser_order:
        parser = parsers[parser_key]
        parsed = parser(payload, path=source)
        if parsed is not None:
            return parsed

    return _empty_payload(path=source, provider=selected_provider)


__all__ = ["SCIP_PROVIDERS", "load_scip_edges"]
