from __future__ import annotations

from collections import deque
from typing import Any

RANKING_PROFILES = ("heuristic", "graph", "graph_seeded")
DEFAULT_SIGNAL_WEIGHTS: dict[str, dict[str, float]] = {
    "heuristic": {"base": 1.0},
    "graph": {"base": 0.75, "graph": 0.2, "import_depth": 0.05, "reference": 0.1},
    "graph_seeded": {
        "base": 0.70,
        "graph": 0.2,
        "import_depth": 0.05,
        "reference": 0.1,
    },
}
_FLOAT_EPSILON = 1e-12
_REFERENCE_KIND_WEIGHTS: dict[str, float] = {
    "reference": 1.0,
    "call": 2.0,
    "invoke": 2.0,
    "inherits": 2.5,
    "inheritance": 2.5,
    "extends": 2.5,
    "implements": 2.0,
}


def rank_index_files(
    *,
    files: dict[str, dict[str, Any]],
    profile: str = "heuristic",
    signal_weights: dict[str, float] | None = None,
    seed_paths: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    normalized_profile = str(profile or "heuristic").strip().lower()
    if normalized_profile not in RANKING_PROFILES:
        raise ValueError(f"unsupported ranking profile: {profile}")

    stats, module_to_path = _collect_file_stats(files)
    nodes = sorted(stats.keys())

    base_scores = {
        path: _base_score(
            path=path,
            symbol_count=stats[path]["symbol_count"],
            import_count=stats[path]["import_count"],
            generated=bool(stats[path].get("generated")),
            dependency=str(stats[path].get("tier") or "").strip().lower() == "dependency",
        )
        for path in nodes
    }
    base_signals = _normalize_scores(scores={path: float(score) for path, score in base_scores.items()}, nodes=nodes)

    graph_scores: dict[str, float] = {}
    import_depth_scores: dict[str, float] = {}
    reference_scores: dict[str, float] = {}
    graph_signals = {path: 0.0 for path in nodes}
    import_depth_signals = {path: 0.0 for path in nodes}
    reference_signals = {path: 0.0 for path in nodes}
    seed_nodes = _resolve_seed_nodes(nodes=nodes, seed_paths=seed_paths)

    if normalized_profile in {"graph", "graph_seeded"}:
        edges = _build_import_edges(nodes=nodes, stats=stats, module_to_path=module_to_path)
        symbol_to_paths = _build_symbol_to_paths(nodes=nodes, stats=stats)
        reference_edges = _build_reference_edges(nodes=nodes, stats=stats, symbol_to_paths=symbol_to_paths)

        if normalized_profile == "graph_seeded" and seed_nodes:
            graph_scores = _graph_scores_personalized(nodes=nodes, edges=edges, seed_nodes=seed_nodes)
            reference_scores = _graph_scores_personalized(
                nodes=nodes,
                edges=reference_edges,
                seed_nodes=seed_nodes,
            )
        else:
            graph_scores = _graph_scores(nodes=nodes, edges=edges)
            reference_scores = _graph_scores(nodes=nodes, edges=reference_edges)

        import_depth_scores = _import_depth_centrality(nodes=nodes, edges=edges)
        graph_signals = _normalize_scores(scores=graph_scores, nodes=nodes)
        import_depth_signals = _normalize_scores(scores=import_depth_scores, nodes=nodes)
        reference_signals = _normalize_scores(scores=reference_scores, nodes=nodes)

    minimum_base_score = min((float(score) for score in base_scores.values()), default=0.0)
    maximum_base_score = max((float(score) for score in base_scores.values()), default=0.0)
    resolved_weights = _resolve_signal_weights(profile=normalized_profile, signal_weights=signal_weights)
    if normalized_profile in {'graph', 'graph_seeded'}:
        has_references = any(bool(stats[path].get('references')) for path in nodes)
        if not has_references:
            resolved_weights['reference'] = 0.0

    ranked: list[dict[str, Any]] = []
    for path in nodes:
        entry = stats[path]
        base_score = int(base_scores.get(path, 0))
        graph_rank = float(graph_scores.get(path, 0.0))
        import_depth_rank = float(import_depth_scores.get(path, 0.0))
        reference_rank = float(reference_scores.get(path, 0.0))

        score = float(base_score)
        if normalized_profile in {"graph", "graph_seeded"}:
            normalized_score = _weighted_signal_score(
                signal_values={
                    "base": float(base_signals.get(path, 0.0)),
                    "graph": float(graph_signals.get(path, 0.0)),
                    "import_depth": float(import_depth_signals.get(path, 0.0)),
                    'reference': float(reference_signals.get(path, 0.0)),
                },
                signal_weights=resolved_weights,
            )
            score = _scale_normalized_score(
                normalized_score=normalized_score,
                minimum=minimum_base_score,
                maximum=maximum_base_score,
            )

        ranked.append(
            {
                "path": path,
                "language": entry["language"],
                "module": entry["module"],
                "generated": bool(entry.get("generated")),
                "symbol_count": entry["symbol_count"],
                "import_count": entry["import_count"],
                "score": round(score, 6),
                "base_score": base_score,
                "graph_rank": round(graph_rank, 6),
                "import_depth_rank": round(import_depth_rank, 6),
                "ranking_profile": normalized_profile,
                "seed_rank": round(
                    float(graph_scores.get(path, 0.0)) if normalized_profile == "graph_seeded" else 0.0,
                    6,
                ),
            }
        )
        ranked[-1]['reference_rank'] = round(reference_rank, 6)
        ranked[-1]['seeded'] = normalized_profile == "graph_seeded" and path in seed_nodes

    ranked.sort(
        key=lambda item: (
            -float(item.get("score", 0.0)),
            -float(item.get("base_score", 0.0)),
            -float(item.get("graph_rank", 0.0)),
            -float(item.get("import_depth_rank", 0.0)),
            str(item.get("path", "")),
        )
    )
    return ranked


def _collect_file_stats(files: dict[str, dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    stats: dict[str, dict[str, Any]] = {}
    module_to_path: dict[str, str] = {}

    for path in sorted(item for item in files if isinstance(item, str)):
        entry = files.get(path)
        if not isinstance(entry, dict):
            continue

        symbols = entry.get("symbols", [])
        imports = entry.get("imports", [])
        references = entry.get('references', [])
        symbol_count = len(symbols) if isinstance(symbols, list) else 0
        import_count = len(imports) if isinstance(imports, list) else 0
        module = str(entry.get("module") or "")

        import_modules: list[str] = []
        seen_import_modules: set[str] = set()
        if isinstance(imports, list):
            for item in imports:
                if not isinstance(item, dict):
                    continue
                module_name = str(item.get("module") or "").strip().lstrip(".")
                if module_name and module_name not in seen_import_modules:
                    seen_import_modules.add(module_name)
                    import_modules.append(module_name)

        symbol_keys: list[str] = []
        seen_symbol_keys: set[str] = set()
        if isinstance(symbols, list):
            for item in symbols:
                if not isinstance(item, dict):
                    continue

                qualified_name = str(item.get('qualified_name') or '').strip().lstrip('.')
                name = str(item.get('name') or '').strip().lstrip('.')
                if qualified_name and qualified_name not in seen_symbol_keys:
                    seen_symbol_keys.add(qualified_name)
                    symbol_keys.append(qualified_name)

                if module and name:
                    module_symbol = f'{module}.{name}'.lstrip('.')
                    if module_symbol and module_symbol not in seen_symbol_keys:
                        seen_symbol_keys.add(module_symbol)
                        symbol_keys.append(module_symbol)

                if name and name not in seen_symbol_keys:
                    seen_symbol_keys.add(name)
                    symbol_keys.append(name)

        reference_values: list[str] = []
        reference_items: list[dict[str, str]] = []
        seen_reference_values: set[str] = set()
        seen_reference_items: set[tuple[str, str]] = set()
        if isinstance(references, list):
            for item in references:
                if not isinstance(item, dict):
                    continue

                qualified_name = str(item.get('qualified_name') or '').strip().lstrip('.')
                name = str(item.get('name') or '').strip().lstrip('.')
                kind = str(item.get("kind") or "reference").strip().lower() or "reference"
                for candidate in (qualified_name, name):
                    if candidate and candidate not in seen_reference_values:
                        seen_reference_values.add(candidate)
                        reference_values.append(candidate)
                    if not candidate:
                        continue
                    key = (candidate, kind)
                    if key in seen_reference_items:
                        continue
                    seen_reference_items.add(key)
                    reference_items.append({"value": candidate, "kind": kind})

        stats[path] = {
            "path": path,
            "language": str(entry.get("language") or ""),
            "module": module,
            "generated": bool(entry.get("generated")),
            "tier": str(entry.get("tier") or ""),
            "symbol_count": symbol_count,
            "import_count": import_count,
            "import_modules": import_modules,
            'symbol_keys': symbol_keys,
            'references': reference_values,
            "reference_items": reference_items,
        }

        if module and module not in module_to_path:
            module_to_path[module] = path

    return stats, module_to_path


def _base_score(
    *,
    path: str,
    symbol_count: int,
    import_count: int,
    generated: bool = False,
    dependency: bool = False,
) -> int:
    score = symbol_count * 2 + import_count
    if path.startswith("src/"):
        score += 2
    if generated and score > 0:
        score = max(1, round(score * 0.15))
    if dependency and score > 0:
        score = max(1, round(score * 0.35))
    return score


def _resolve_signal_weights(*, profile: str, signal_weights: dict[str, float] | None) -> dict[str, float]:
    defaults = DEFAULT_SIGNAL_WEIGHTS.get(profile, {})
    resolved = dict(defaults)

    if isinstance(signal_weights, dict):
        for signal_name in defaults:
            candidate = signal_weights.get(signal_name)
            if isinstance(candidate, (int, float)):
                resolved[signal_name] = max(0.0, float(candidate))
        if profile == 'graph' and 'reference' not in signal_weights:
            resolved['reference'] = 0.0

    if sum(resolved.values()) <= _FLOAT_EPSILON and defaults:
        return dict(defaults)
    return resolved


def _build_import_edges(
    *,
    nodes: list[str],
    stats: dict[str, dict[str, Any]],
    module_to_path: dict[str, str],
) -> dict[str, tuple[str, ...]]:
    edges: dict[str, tuple[str, ...]] = {}

    for path in nodes:
        entry = stats.get(path, {})
        targets: set[str] = set()
        for module in entry.get("import_modules", []):
            target = module_to_path.get(module)
            if not target or target == path:
                continue
            targets.add(target)
        edges[path] = tuple(sorted(targets))

    return edges


def _build_symbol_to_paths(*, nodes: list[str], stats: dict[str, dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    symbol_to_paths: dict[str, set[str]] = {}

    for path in nodes:
        entry = stats.get(path, {})
        for symbol in entry.get('symbol_keys', []):
            key = str(symbol).strip().lstrip('.')
            if not key:
                continue

            symbol_to_paths.setdefault(key, set()).add(path)
            tail = _tail_symbol(key)
            if tail:
                symbol_to_paths.setdefault(tail, set()).add(path)

    return {
        key: tuple(sorted(paths))
        for key, paths in symbol_to_paths.items()
    }


def _build_reference_edges(
    *,
    nodes: list[str],
    stats: dict[str, dict[str, Any]],
    symbol_to_paths: dict[str, tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    edges: dict[str, tuple[str, ...]] = {}

    for path in nodes:
        entry = stats.get(path, {})
        targets_weighted: list[str] = []
        reference_rows = entry.get("reference_items", [])
        if not isinstance(reference_rows, list) or not reference_rows:
            reference_rows = [
                {"value": str(value), "kind": "reference"}
                for value in entry.get("references", [])
            ]
        for row in reference_rows:
            if not isinstance(row, dict):
                continue
            reference_value = str(row.get("value") or "").strip()
            if not reference_value:
                continue
            kind = str(row.get("kind") or "reference").strip().lower()
            repeat = max(1, round(_reference_kind_weight(kind)))
            for candidate in _reference_candidates(reference_value):
                for target in symbol_to_paths.get(candidate, ()):
                    if target == path:
                        continue
                    for _ in range(repeat):
                        targets_weighted.append(target)
        edges[path] = tuple(sorted(targets_weighted))

    return edges


def _reference_kind_weight(kind: str) -> float:
    normalized = str(kind or "").strip().lower()
    if not normalized:
        return 1.0
    return float(_REFERENCE_KIND_WEIGHTS.get(normalized, 1.0))


def _reference_candidates(reference: str) -> tuple[str, ...]:
    value = str(reference).strip().lstrip('.')
    if not value:
        return ()

    candidates: list[str] = [value]
    seen_candidates: set[str] = {value}
    tail = _tail_symbol(value)
    if tail and tail not in seen_candidates:
        seen_candidates.add(tail)
        candidates.append(tail)
    return tuple(candidates)


def _tail_symbol(value: str) -> str:
    parts = str(value).replace('/', '.').split('.')
    for item in reversed(parts):
        token = item.strip()
        if token:
            return token
    return ''


def _graph_scores(*, nodes: list[str], edges: dict[str, tuple[str, ...]]) -> dict[str, float]:
    if not nodes:
        return {}

    n = len(nodes)
    if n == 1:
        return {nodes[0]: 1.0}

    damping = 0.85
    ranks = {node: 1.0 / n for node in nodes}

    for _ in range(12):
        next_ranks = {node: (1.0 - damping) / n for node in nodes}
        sink_mass = 0.0
        for source in nodes:
            outs = edges.get(source, ())
            if outs:
                shared = (damping * ranks[source]) / len(outs)
                for target in outs:
                    next_ranks[target] += shared
            else:
                sink_mass += ranks[source]

        if sink_mass > 0.0:
            sink_share = (damping * sink_mass) / n
            for target in nodes:
                next_ranks[target] += sink_share
        ranks = next_ranks

    return ranks


def _resolve_seed_nodes(
    *,
    nodes: list[str],
    seed_paths: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    if not nodes or not seed_paths:
        return ()

    node_set = set(nodes)
    ordered: list[str] = []
    for candidate in seed_paths:
        path = str(candidate or "").strip()
        if not path or path not in node_set or path in ordered:
            continue
        ordered.append(path)
    return tuple(ordered)


def _graph_scores_personalized(
    *,
    nodes: list[str],
    edges: dict[str, tuple[str, ...]],
    seed_nodes: tuple[str, ...],
) -> dict[str, float]:
    if not nodes:
        return {}

    n = len(nodes)
    if n == 1:
        return {nodes[0]: 1.0}

    if not seed_nodes:
        return _graph_scores(nodes=nodes, edges=edges)

    damping = 0.85
    teleport_weights = {
        node: (1.0 / float(len(seed_nodes))) if node in seed_nodes else 0.0
        for node in nodes
    }
    fallback_weight = 1.0 / float(n)

    ranks = {node: teleport_weights.get(node, 0.0) for node in nodes}
    if sum(ranks.values()) <= _FLOAT_EPSILON:
        ranks = {node: fallback_weight for node in nodes}

    for _ in range(14):
        next_ranks = {
            node: (1.0 - damping) * teleport_weights.get(node, 0.0)
            for node in nodes
        }
        sink_mass = 0.0
        for source in nodes:
            outs = edges.get(source, ())
            if outs:
                shared = (damping * ranks[source]) / len(outs)
                for target in outs:
                    next_ranks[target] += shared
            else:
                sink_mass += ranks[source]

        if sink_mass > 0.0:
            for target in nodes:
                next_ranks[target] += damping * sink_mass * teleport_weights.get(target, 0.0)

        rank_total = sum(next_ranks.values())
        if rank_total > _FLOAT_EPSILON:
            ranks = {node: value / rank_total for node, value in next_ranks.items()}
        else:
            ranks = {node: fallback_weight for node in nodes}

    return ranks


def _import_depth_centrality(*, nodes: list[str], edges: dict[str, tuple[str, ...]]) -> dict[str, float]:
    centrality = {node: 0.0 for node in nodes}
    if not nodes:
        return centrality

    for source in nodes:
        queue = deque((target, 1) for target in edges.get(source, ()))
        seen_depths: dict[str, int] = {}

        while queue:
            target, depth = queue.popleft()
            if target in seen_depths:
                continue

            seen_depths[target] = depth
            centrality[target] += 1.0 / float(depth)

            for neighbor in edges.get(target, ()):
                if neighbor not in seen_depths:
                    queue.append((neighbor, depth + 1))

    return centrality


def _normalize_scores(*, scores: dict[str, float], nodes: list[str]) -> dict[str, float]:
    if not nodes:
        return {}

    values = [float(scores.get(node, 0.0)) for node in nodes]
    minimum = min(values)
    maximum = max(values)

    if maximum - minimum <= _FLOAT_EPSILON:
        normalized = 1.0 if maximum > 0.0 else 0.0
        return {node: normalized for node in nodes}

    spread = maximum - minimum
    return {
        node: (float(scores.get(node, 0.0)) - minimum) / spread
        for node in nodes
    }


def _weighted_signal_score(*, signal_values: dict[str, float], signal_weights: dict[str, float]) -> float:
    weighted_sum = 0.0
    total_weight = 0.0

    for signal_name, weight in signal_weights.items():
        if weight <= 0.0:
            continue
        total_weight += weight
        weighted_sum += weight * float(signal_values.get(signal_name, 0.0))

    if total_weight <= _FLOAT_EPSILON:
        return float(signal_values.get("base", 0.0))
    return weighted_sum / total_weight


def _scale_normalized_score(*, normalized_score: float, minimum: float, maximum: float) -> float:
    bounded = min(1.0, max(0.0, float(normalized_score)))
    if maximum - minimum <= _FLOAT_EPSILON:
        return minimum + bounded
    return minimum + bounded * (maximum - minimum)


__all__ = ["DEFAULT_SIGNAL_WEIGHTS", "RANKING_PROFILES", "rank_index_files"]

