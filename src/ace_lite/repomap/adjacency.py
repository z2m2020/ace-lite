from __future__ import annotations

from collections import defaultdict
from typing import Any

from ace_lite.repomap.resolution import _resolve_import_target, _tail_token

_REFERENCE_EDGE_SCAN_LIMIT = 256
_REFERENCE_EDGE_TARGET_LIMIT = 24
_REFERENCE_EDGE_MAX_DEFINITIONS = 3
_REFERENCE_KIND_WEIGHTS: dict[str, float] = {
    "reference": 1.0,
    "call": 2.0,
    "invoke": 2.0,
    "inherits": 2.5,
    "inheritance": 2.5,
    "extends": 2.5,
    "implements": 2.0,
}


def _reference_kind_weight(kind: str) -> float:
    normalized = str(kind or "").strip().lower()
    if not normalized:
        return 1.0
    return float(_REFERENCE_KIND_WEIGHTS.get(normalized, 1.0))


def _reference_candidate_keys(value: str) -> tuple[str, ...]:
    normalized = str(value or "").strip().lstrip(".")
    if not normalized:
        return ()

    candidates = [normalized]
    tail = _tail_token(normalized)
    if tail and tail not in candidates:
        candidates.append(tail)
    return tuple(candidates)


def _build_symbol_to_paths(*, files: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    symbol_to_paths: dict[str, set[str]] = defaultdict(set)

    for path in sorted(files):
        entry = files.get(path)
        if not isinstance(entry, dict):
            continue

        module = str(entry.get("module") or "").strip().lstrip(".")
        symbols = entry.get("symbols", [])
        if not isinstance(symbols, list):
            continue

        for symbol in symbols:
            if not isinstance(symbol, dict):
                continue

            name = str(symbol.get("name") or "").strip().lstrip(".")
            qualified_name = str(symbol.get("qualified_name") or "").strip().lstrip(".")
            candidates = [
                qualified_name,
                name,
                f"{module}.{name}".lstrip(".") if module and name else "",
            ]
            for candidate in candidates:
                key = str(candidate).strip().lstrip(".")
                if key:
                    symbol_to_paths[key].add(path)

    return dict(symbol_to_paths)


def _normalize_symbol_record(
    *,
    path: str,
    module: str,
    symbol: dict[str, Any],
) -> dict[str, Any] | None:
    name = str(symbol.get("name") or "").strip().lstrip(".")
    qualified_name = str(symbol.get("qualified_name") or "").strip().lstrip(".")
    label = qualified_name or name
    if not label:
        return None

    try:
        lineno = int(symbol.get("lineno") or 0)
    except Exception:
        return None
    if lineno <= 0:
        return None

    try:
        end_lineno = int(symbol.get("end_lineno") or lineno)
    except Exception:
        end_lineno = lineno
    if end_lineno < lineno:
        end_lineno = lineno

    kind = str(symbol.get("kind") or "").strip().lower() or "symbol"
    symbol_id = f"{path}|{lineno}|{end_lineno}|{label}"
    candidates = {
        label,
        name,
        qualified_name,
        f"{module}.{name}".lstrip(".") if module and name else "",
    }

    return {
        "id": symbol_id,
        "path": path,
        "module": module,
        "name": name,
        "qualified_name": qualified_name,
        "kind": kind,
        "lineno": lineno,
        "end_lineno": end_lineno,
        "candidates": tuple(sorted(candidate for candidate in candidates if candidate)),
    }


def _build_symbol_assignment_context(
    *,
    files: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, set[str]]]:
    symbol_records: dict[str, dict[str, Any]] = {}
    path_to_symbols: dict[str, list[dict[str, Any]]] = {}
    symbol_to_ids: dict[str, set[str]] = defaultdict(set)

    for path in sorted(files):
        entry = files.get(path)
        if not isinstance(entry, dict):
            path_to_symbols[path] = []
            continue

        module = str(entry.get("module") or "").strip().lstrip(".")
        raw_symbols = entry.get("symbols", [])
        if not isinstance(raw_symbols, list):
            path_to_symbols[path] = []
            continue

        normalized_symbols: list[dict[str, Any]] = []
        for raw_symbol in raw_symbols:
            if not isinstance(raw_symbol, dict):
                continue
            normalized = _normalize_symbol_record(
                path=path,
                module=module,
                symbol=raw_symbol,
            )
            if normalized is None:
                continue
            normalized_symbols.append(normalized)
            symbol_records[normalized["id"]] = normalized
            for candidate in normalized["candidates"]:
                symbol_to_ids[candidate].add(normalized["id"])

        normalized_symbols.sort(
            key=lambda item: (
                int(item["lineno"]),
                int(item["end_lineno"]),
                str(item["qualified_name"] or item["name"]),
                str(item["kind"]),
                str(item["id"]),
            )
        )
        path_to_symbols[path] = normalized_symbols

    return symbol_records, path_to_symbols, dict(symbol_to_ids)


def _build_symbol_graph_context(
    *,
    files: dict[str, dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, set[str]]]:
    _, path_to_symbols, symbol_to_ids = _build_symbol_assignment_context(files=files)
    return path_to_symbols, symbol_to_ids


def _select_enclosing_symbol(
    *,
    path_symbols: list[dict[str, Any]],
    lineno: int,
) -> dict[str, Any] | None:
    candidates = [
        symbol
        for symbol in path_symbols
        if int(symbol.get("lineno") or 0) <= lineno <= int(symbol.get("end_lineno") or 0)
    ]
    if not candidates:
        return None

    return min(
        candidates,
        key=lambda item: (
            int(item["end_lineno"]) - int(item["lineno"]),
            -int(item["lineno"]),
            int(item["end_lineno"]),
            str(item["qualified_name"] or item["name"]),
            str(item["kind"]),
            str(item["id"]),
        ),
    )


def _assign_references_to_enclosing_symbols(
    *,
    files: dict[str, dict[str, Any]],
    nodes_by_path: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if nodes_by_path is None:
        _, path_to_symbols, _ = _build_symbol_assignment_context(files=files)
    else:
        path_to_symbols = nodes_by_path
    assignments: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for path in sorted(files):
        entry = files.get(path)
        if not isinstance(entry, dict):
            continue

        path_symbols = path_to_symbols.get(path, [])
        if not path_symbols:
            continue

        references = entry.get("references", [])
        if not isinstance(references, list) or not references:
            continue

        for reference in references[:_REFERENCE_EDGE_SCAN_LIMIT]:
            if not isinstance(reference, dict):
                continue
            try:
                lineno = int(reference.get("lineno") or 0)
            except Exception:
                continue
            if lineno <= 0:
                continue

            owner = _select_enclosing_symbol(path_symbols=path_symbols, lineno=lineno)
            if owner is None:
                continue

            assignments[owner["id"]].append(
                {
                    "path": path,
                    "lineno": lineno,
                    "name": str(reference.get("name") or "").strip().lstrip("."),
                    "qualified_name": str(reference.get("qualified_name") or "")
                    .strip()
                    .lstrip("."),
                    "kind": str(reference.get("kind") or "reference").strip().lower()
                    or "reference",
                }
            )

    ordered_assignments: dict[str, list[dict[str, Any]]] = {}
    for symbol_id in sorted(assignments):
        ordered_assignments[symbol_id] = sorted(
            assignments[symbol_id],
            key=lambda item: (
                int(item["lineno"]),
                str(item["qualified_name"] or item["name"]),
                str(item["kind"]),
            ),
        )
    return ordered_assignments


def _build_symbol_adjacency(
    *,
    files: dict[str, dict[str, Any]],
    nodes_by_path: dict[str, list[dict[str, Any]]] | None = None,
    symbol_to_node_ids: dict[str, set[str]] | None = None,
) -> dict[str, list[str]]:
    symbol_records, computed_nodes_by_path, computed_symbol_to_ids = (
        _build_symbol_assignment_context(files=files)
    )
    resolved_nodes_by_path = nodes_by_path or computed_nodes_by_path
    resolved_symbol_to_ids = symbol_to_node_ids or computed_symbol_to_ids
    assignments = _assign_references_to_enclosing_symbols(
        files=files,
        nodes_by_path=resolved_nodes_by_path,
    )
    adjacency: dict[str, list[str]] = {}

    for source_id in sorted(symbol_records):
        weights: dict[str, float] = defaultdict(float)
        for reference in assignments.get(source_id, []):
            weight = _reference_kind_weight(str(reference.get("kind") or "reference"))
            for raw in (reference.get("qualified_name"), reference.get("name")):
                candidate = str(raw or "").strip()
                if not candidate:
                    continue
                for key in _reference_candidate_keys(candidate):
                    targets = resolved_symbol_to_ids.get(key)
                    if not targets:
                        continue
                    if len(targets) > _REFERENCE_EDGE_MAX_DEFINITIONS:
                        continue
                    for target_id in targets:
                        if target_id == source_id:
                            continue
                        weights[target_id] += weight

        ranked = sorted(weights.items(), key=lambda item: (-float(item[1]), item[0]))
        adjacency[source_id] = [
            target_id for target_id, _ in ranked[:_REFERENCE_EDGE_TARGET_LIMIT]
        ]

    return adjacency


def _build_symbol_node_id(
    *,
    path: str,
    lineno: int,
    end_lineno: int,
    qualified_name: str,
    name: str,
) -> str:
    symbol_key = qualified_name or name
    if not path or not symbol_key or lineno <= 0:
        return ""
    return f"{path}|{lineno}|{end_lineno}|{symbol_key}"


def _normalize_symbol_node(
    *,
    path: str,
    module: str,
    symbol: dict[str, Any],
) -> dict[str, Any] | None:
    lineno = int(symbol.get("lineno") or 0)
    if lineno <= 0:
        return None

    end_lineno = int(symbol.get("end_lineno") or lineno)
    if end_lineno < lineno:
        end_lineno = lineno

    name = str(symbol.get("name") or "").strip().lstrip(".")
    qualified_name = str(symbol.get("qualified_name") or "").strip().lstrip(".")
    node_id = _build_symbol_node_id(
        path=path,
        lineno=lineno,
        end_lineno=end_lineno,
        qualified_name=qualified_name,
        name=name,
    )
    if not node_id:
        return None

    candidates = [qualified_name, name]
    if module and name:
        candidates.append(f"{module}.{name}".lstrip("."))

    return {
        "id": node_id,
        "path": path,
        "name": name,
        "qualified_name": qualified_name,
        "lineno": lineno,
        "end_lineno": end_lineno,
        "candidates": tuple(
            candidate for candidate in candidates if str(candidate).strip().lstrip(".")
        ),
    }


def _build_symbol_graph_context(
    *,
    files: dict[str, dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, set[str]]]:
    nodes_by_path: dict[str, list[dict[str, Any]]] = {}
    symbol_to_node_ids: dict[str, set[str]] = defaultdict(set)

    for path in sorted(files):
        entry = files.get(path)
        if not isinstance(entry, dict):
            continue

        module = str(entry.get("module") or "").strip().lstrip(".")
        symbols = entry.get("symbols", [])
        if not isinstance(symbols, list) or not symbols:
            continue

        normalized_nodes: list[dict[str, Any]] = []
        for symbol in symbols:
            if not isinstance(symbol, dict):
                continue
            node = _normalize_symbol_node(path=path, module=module, symbol=symbol)
            if not isinstance(node, dict):
                continue
            normalized_nodes.append(node)
            for candidate in node.get("candidates", ()):
                key = str(candidate).strip().lstrip(".")
                if key:
                    symbol_to_node_ids[key].add(str(node["id"]))

        if not normalized_nodes:
            continue

        normalized_nodes.sort(
            key=lambda item: (
                int(item.get("lineno") or 0),
                int(item.get("end_lineno") or 0),
                str(item.get("qualified_name") or ""),
                str(item.get("name") or ""),
                str(item.get("id") or ""),
            )
        )
        nodes_by_path[path] = normalized_nodes

    return nodes_by_path, dict(symbol_to_node_ids)


def _find_enclosing_symbol_node(
    *,
    symbol_nodes: list[dict[str, Any]],
    lineno: int,
) -> dict[str, Any] | None:
    if lineno <= 0:
        return None

    candidates = [
        item
        for item in symbol_nodes
        if int(item.get("lineno") or 0) <= lineno <= int(item.get("end_lineno") or 0)
    ]
    if not candidates:
        return None

    return min(
        candidates,
        key=lambda item: (
            int(item.get("end_lineno") or 0) - int(item.get("lineno") or 0),
            -int(item.get("lineno") or 0),
            int(item.get("end_lineno") or 0),
            str(item.get("qualified_name") or ""),
            str(item.get("name") or ""),
            str(item.get("id") or ""),
        ),
    )


def _assign_references_to_enclosing_symbols(
    *,
    files: dict[str, dict[str, Any]],
    nodes_by_path: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    symbol_nodes = nodes_by_path or _build_symbol_graph_context(files=files)[0]
    assignments: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for path in sorted(files):
        entry = files.get(path)
        if not isinstance(entry, dict):
            continue

        references = entry.get("references", [])
        path_nodes = symbol_nodes.get(path, [])
        if (
            not isinstance(references, list)
            or not references
            or not isinstance(path_nodes, list)
            or not path_nodes
        ):
            continue

        for reference in references[:_REFERENCE_EDGE_SCAN_LIMIT]:
            if not isinstance(reference, dict):
                continue

            try:
                lineno = int(reference.get("lineno") or 0)
            except (TypeError, ValueError):
                continue
            if lineno <= 0:
                continue

            source_node = _find_enclosing_symbol_node(
                symbol_nodes=path_nodes,
                lineno=lineno,
            )
            if not isinstance(source_node, dict):
                continue

            assignments[str(source_node["id"])].append(
                {
                    "path": path,
                    "lineno": lineno,
                    "kind": str(reference.get("kind") or "reference"),
                    "name": str(reference.get("name") or "").strip().lstrip("."),
                    "qualified_name": str(reference.get("qualified_name") or "")
                    .strip()
                    .lstrip("."),
                }
            )

    return {key: value for key, value in sorted(assignments.items())}


def _build_symbol_adjacency(
    *,
    files: dict[str, dict[str, Any]],
    nodes_by_path: dict[str, list[dict[str, Any]]] | None = None,
    symbol_to_node_ids: dict[str, set[str]] | None = None,
    assignments: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, list[str]]:
    resolved_nodes_by_path = nodes_by_path
    resolved_symbol_to_node_ids = symbol_to_node_ids
    if resolved_nodes_by_path is None or resolved_symbol_to_node_ids is None:
        (
            resolved_nodes_by_path,
            resolved_symbol_to_node_ids,
        ) = _build_symbol_graph_context(files=files)

    resolved_assignments = assignments or _assign_references_to_enclosing_symbols(
        files=files,
        nodes_by_path=resolved_nodes_by_path,
    )
    weights: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for source_node_id in sorted(resolved_assignments):
        reference_rows = resolved_assignments.get(source_node_id, [])
        if not isinstance(reference_rows, list):
            continue

        for reference in reference_rows:
            if not isinstance(reference, dict):
                continue

            weight = _reference_kind_weight(str(reference.get("kind") or "reference"))
            for raw in (reference.get("qualified_name"), reference.get("name")):
                candidate = str(raw or "").strip()
                if not candidate:
                    continue
                for key in _reference_candidate_keys(candidate):
                    targets = resolved_symbol_to_node_ids.get(key)
                    if not targets:
                        continue
                    if len(targets) > _REFERENCE_EDGE_MAX_DEFINITIONS:
                        continue
                    for target_node_id in sorted(str(item) for item in targets):
                        if target_node_id == source_node_id:
                            continue
                        weights[source_node_id][target_node_id] += weight

    adjacency: dict[str, list[str]] = {}
    for path in sorted(resolved_nodes_by_path):
        for node in resolved_nodes_by_path[path]:
            node_id = str(node.get("id") or "")
            ranked = sorted(
                weights.get(node_id, {}).items(),
                key=lambda item: (-float(item[1]), item[0]),
            )
            adjacency[node_id] = [
                target_node_id
                for target_node_id, _ in ranked[:_REFERENCE_EDGE_TARGET_LIMIT]
            ]

    return adjacency


def _build_reference_adjacency(
    *,
    files: dict[str, dict[str, Any]],
    symbol_to_paths: dict[str, set[str]],
) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {}

    for source_path in sorted(files):
        entry = files.get(source_path)
        if not isinstance(entry, dict):
            adjacency[source_path] = []
            continue

        references = entry.get("references", [])
        if not isinstance(references, list) or not references:
            adjacency[source_path] = []
            continue

        weights: dict[str, float] = defaultdict(float)
        for reference in references[:_REFERENCE_EDGE_SCAN_LIMIT]:
            if not isinstance(reference, dict):
                continue

            kind = str(reference.get("kind") or "reference")
            weight = _reference_kind_weight(kind)
            for raw in (reference.get("qualified_name"), reference.get("name")):
                candidate = str(raw or "").strip()
                if not candidate:
                    continue
                for key in _reference_candidate_keys(candidate):
                    targets = symbol_to_paths.get(key)
                    if not targets:
                        continue
                    if len(targets) > _REFERENCE_EDGE_MAX_DEFINITIONS:
                        continue
                    for target in targets:
                        if target == source_path:
                            continue
                        weights[target] += weight

        ranked = sorted(weights.items(), key=lambda item: (-float(item[1]), item[0]))
        adjacency[source_path] = [
            path for path, _ in ranked[:_REFERENCE_EDGE_TARGET_LIMIT]
        ]

    return adjacency


def _expand_neighbors(
    *,
    files: dict[str, dict[str, Any]],
    seed_paths: list[str],
    module_to_path: dict[str, str],
    path_style_to_paths: dict[str, set[str]],
    stem_to_paths: dict[str, set[str]],
    neighbor_limit: int,
    depth: int,
    adjacency: dict[str, list[str]] | None = None,
) -> list[str]:
    neighbors: list[str] = []
    seed_set = set(seed_paths)
    max_depth = max(1, int(depth))
    if neighbor_limit <= 0:
        return neighbors

    if adjacency is None:
        adjacency = _build_adjacency(
            files=files,
            module_to_path=module_to_path,
            path_style_to_paths=path_style_to_paths,
            stem_to_paths=stem_to_paths,
        )

    frontier = [path for path in seed_paths if path in files]
    visited = set(seed_paths)

    for _ in range(max_depth):
        next_frontier: list[str] = []
        for source_path in frontier:
            for target in adjacency.get(source_path, []):
                if target in seed_set or target in visited:
                    continue
                visited.add(target)
                neighbors.append(target)
                next_frontier.append(target)
                if len(neighbors) >= neighbor_limit:
                    return neighbors
        if not next_frontier:
            break
        frontier = next_frontier

    return neighbors


def _build_adjacency(
    *,
    files: dict[str, dict[str, Any]],
    module_to_path: dict[str, str],
    path_style_to_paths: dict[str, set[str]],
    stem_to_paths: dict[str, set[str]],
) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {}

    for source_path in sorted(files):
        source_entry = files.get(source_path, {})
        imports = (
            source_entry.get("imports", []) if isinstance(source_entry, dict) else []
        )
        import_items = imports if isinstance(imports, list) else []

        targets: list[str] = []
        for item in import_items:
            if not isinstance(item, dict):
                continue
            target = _resolve_import_target(
                seed_path=source_path,
                seed_entry=source_entry,
                import_module=str(item.get("module") or "").strip(),
                import_name=str(item.get("name") or "").strip(),
                files=files,
                module_to_path=module_to_path,
                path_style_to_paths=path_style_to_paths,
                stem_to_paths=stem_to_paths,
            )
            if not target or target == source_path or target in targets:
                continue
            targets.append(target)
        adjacency[source_path] = targets
    return adjacency
