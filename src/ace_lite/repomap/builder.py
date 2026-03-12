"""Repo map builders used by the orchestration pipeline.

These helpers transform the distilled index payload into:

- A compact ranked file list (with Markdown summary).
- A focused skeleton map expanded with one-hop import neighbors.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ace_lite.repomap.adjacency import (
    _build_adjacency,
    _build_reference_adjacency,
    _build_symbol_adjacency,
    _build_symbol_graph_context,
    _build_symbol_to_paths,
    _expand_neighbors,
)
from ace_lite.repomap.ranking import RANKING_PROFILES, rank_index_files
from ace_lite.repomap.resolution import _build_resolution_maps
from ace_lite.repomap.rendering import _file_descriptor, _render_skeleton_markdown
from ace_lite.repomap.stage_support import (
    build_stage_repomap_explainability,
    extract_seed_candidate_paths,
    resolve_seed_paths,
)
from ace_lite.token_estimator import estimate_tokens

SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".sol")


def build_repo_map(
    *,
    index_payload: dict[str, Any],
    budget_tokens: int = 800,
    top_k: int = 40,
    ranking_profile: str = "heuristic",
    signal_weights: dict[str, float] | None = None,
    tokenizer_model: str | None = None,
) -> dict[str, Any]:
    files = index_payload.get("files", {})
    if not isinstance(files, dict):
        files = {}

    normalized_profile = str(ranking_profile or "heuristic").strip().lower()
    if normalized_profile not in RANKING_PROFILES:
        raise ValueError(f"unsupported ranking profile: {ranking_profile}")

    ranked = rank_index_files(files=files, profile=normalized_profile, signal_weights=signal_weights)
    selected: list[dict[str, Any]] = []
    used_tokens = 0

    for item in ranked[: max(0, top_k)]:
        line = f"{item.get('path')} {item.get('module')} {item.get('language')}"
        line_tokens = estimate_tokens(line, model=tokenizer_model)
        if used_tokens + line_tokens > max(1, budget_tokens):
            break
        used_tokens += line_tokens
        selected.append(item)

    markdown_lines = [
        "# Repo Map",
        "",
        f"- Ranking profile: {normalized_profile}",
        f"- Budget tokens: {budget_tokens}",
        f"- Used tokens: {used_tokens}",
        "",
        "## Ranked Files",
        "",
    ]
    for item in selected:
        markdown_lines.append(
            f"- `{item.get('path')}` ({item.get('language')}) score={item.get('score')} symbols={item.get('symbol_count')} imports={item.get('import_count')}"
        )

    return {
        "ranking_profile": normalized_profile,
        "budget_tokens": budget_tokens,
        "used_tokens": used_tokens,
        "selected_count": len(selected),
        "files": selected,
        "markdown": "\n".join(markdown_lines).strip() + "\n",
    }


def build_stage_repo_map(
    *,
    index_files: dict[str, dict[str, Any]],
    seed_candidates: list[dict[str, Any]],
    subgraph_payload: dict[str, Any] | None = None,
    ranking_profile: str = "graph",
    top_k: int = 8,
    neighbor_limit: int = 20,
    neighbor_depth: int = 1,
    budget_tokens: int = 800,
    signal_weights: dict[str, float] | None = None,
    precomputed_payload: dict[str, Any] | None = None,
    tokenizer_model: str | None = None,
) -> dict[str, Any]:
    files = index_files if isinstance(index_files, dict) else {}
    normalized_profile = str(ranking_profile or "graph").strip().lower()
    if normalized_profile not in RANKING_PROFILES:
        raise ValueError(f"unsupported ranking profile: {ranking_profile}")

    top_seed_k = max(1, int(top_k))
    seed_hints = extract_seed_candidate_paths(
        files=files,
        seed_candidates=seed_candidates,
        top_k=top_seed_k,
    )
    normalized_precomputed = _normalize_stage_precomputed_payload(
        payload=precomputed_payload,
        ranking_profile=normalized_profile,
    )
    if normalized_precomputed is None:
        ranked = rank_index_files(
            files=files,
            profile=normalized_profile,
            signal_weights=signal_weights,
            seed_paths=seed_hints,
        )
    else:
        ranked = _rank_from_precomputed(
            ranked_rows=normalized_precomputed.get("ranked", []),
            seed_paths=seed_hints,
            adjacency=normalized_precomputed.get("adjacency", {}),
            profile=normalized_profile,
        )
    seed_paths = resolve_seed_paths(
        files=files,
        seed_candidates=seed_candidates,
        ranked=ranked,
        top_k=top_seed_k,
    )

    if normalized_precomputed is None:
        module_to_path, path_style_to_paths, stem_to_paths = _build_resolution_maps(files)
        adjacency = _build_adjacency(
            files=files,
            module_to_path=module_to_path,
            path_style_to_paths=path_style_to_paths,
            stem_to_paths=stem_to_paths,
        )
        symbol_to_paths = _build_symbol_to_paths(files=files)
        reference_adjacency = _build_reference_adjacency(
            files=files,
            symbol_to_paths=symbol_to_paths,
        )
    else:
        module_to_path = dict(normalized_precomputed.get("module_to_path", {}))
        path_style_to_paths = {
            str(key): {str(item) for item in value if isinstance(item, str)}
            for key, value in normalized_precomputed.get("path_style_to_paths", {}).items()
            if isinstance(key, str) and isinstance(value, list)
        }
        stem_to_paths = {
            str(key): set(value)
            for key, value in normalized_precomputed.get("stem_to_paths", {}).items()
            if isinstance(key, str) and isinstance(value, list)
        }
        adjacency = {
            str(key): [str(item) for item in value if isinstance(item, str)]
            for key, value in normalized_precomputed.get("adjacency", {}).items()
            if isinstance(key, str) and isinstance(value, list)
        }
        reference_adjacency_raw = normalized_precomputed.get("reference_adjacency", {})
        reference_adjacency = (
            {
                str(key): [str(item) for item in value if isinstance(item, str)]
                for key, value in reference_adjacency_raw.items()
                if isinstance(key, str) and isinstance(value, list)
            }
            if isinstance(reference_adjacency_raw, dict)
            else {}
        )
        if not reference_adjacency:
            symbol_to_paths = _build_symbol_to_paths(files=files)
            reference_adjacency = _build_reference_adjacency(
                files=files,
                symbol_to_paths=symbol_to_paths,
            )

    symbol_to_paths = _build_symbol_to_paths(files=files)

    import_neighbors = _expand_neighbors(
        files=files,
        seed_paths=seed_paths,
        module_to_path=module_to_path,
        path_style_to_paths=path_style_to_paths,
        stem_to_paths=stem_to_paths,
        neighbor_limit=max(0, int(neighbor_limit)),
        depth=max(1, int(neighbor_depth)),
        adjacency=adjacency,
    )
    remaining_neighbor_slots = max(0, int(neighbor_limit) - len(import_neighbors))
    reference_neighbors: list[str] = []
    if remaining_neighbor_slots > 0:
        reference_neighbors = _expand_neighbors(
            files=files,
            seed_paths=seed_paths,
            module_to_path=module_to_path,
            path_style_to_paths=path_style_to_paths,
            stem_to_paths=stem_to_paths,
            neighbor_limit=remaining_neighbor_slots,
            depth=1,
            adjacency=reference_adjacency,
        )

    expected_neighbors = list(import_neighbors)
    neighbor_candidates: list[str] = []
    for path in [*import_neighbors, *reference_neighbors]:
        if path not in neighbor_candidates:
            neighbor_candidates.append(path)

    markdown, used_tokens, included_neighbors, render_levels = _render_skeleton_markdown(
        files=files,
        seed_paths=seed_paths,
        neighbor_paths=neighbor_candidates,
        subgraph_payload=subgraph_payload,
        budget_tokens=max(1, int(budget_tokens)),
        neighbor_depth=max(1, int(neighbor_depth)),
        tokenizer_model=tokenizer_model,
        estimate_tokens_fn=estimate_tokens,
    )

    focused_files: list[str] = []
    for path in [*seed_paths, *included_neighbors]:
        if path not in focused_files:
            focused_files.append(path)

    files_payload = [
        _file_descriptor(path=path, role="seed", entry=files.get(path, {}))
        for path in seed_paths
        if path in files
    ]
    files_payload.extend(
        _file_descriptor(path=path, role="neighbor", entry=files.get(path, {}))
        for path in included_neighbors
        if path in files
    )

    expected_set = set(import_neighbors)
    included_set = set(included_neighbors)
    hit_count = len(expected_set & included_set)
    expected_count = len(expected_set)
    hit_rate = (hit_count / expected_count) if expected_count else 1.0
    total_tag_count = sum(
        int(item.get("tag_count", 0) or 0)
        for item in files_payload
        if isinstance(item, dict)
    )
    focused_count = max(1, len(files_payload))
    explainability = build_stage_repomap_explainability(
        seed_paths=seed_paths,
        seed_hints=seed_hints,
        import_neighbors=import_neighbors,
        reference_neighbors=reference_neighbors,
        included_neighbors=included_neighbors,
        neighbor_candidates=neighbor_candidates,
        path_style_to_paths=path_style_to_paths,
        stem_to_paths=stem_to_paths,
        symbol_to_paths=symbol_to_paths,
    )

    return {
        "enabled": True,
        "ranking_profile": normalized_profile,
        "budget_tokens": max(1, int(budget_tokens)),
        "used_tokens": used_tokens,
        "neighbor_depth": max(1, int(neighbor_depth)),
        "seed_count": len(seed_paths),
        "seed_hint_count": len(seed_hints),
        "neighbor_count": len(included_neighbors),
        "seed_paths": seed_paths,
        "neighbor_paths": included_neighbors,
        "expected_neighbor_paths": expected_neighbors,
        "reference_neighbor_paths": reference_neighbors,
        "dependency_recall": {
            "expected_count": expected_count,
            "hit_count": hit_count,
            "hit_rate": round(hit_rate, 6),
        },
        "focused_files": focused_files,
        "files": files_payload,
        "render_levels": render_levels,
        "tag_summary": {
            "total_tags": int(total_tag_count),
            "avg_tags_per_file": round(float(total_tag_count / focused_count), 6),
        },
        "explainability": explainability,
        "markdown": markdown,
    }


def build_stage_precompute_payload(
    *,
    index_files: dict[str, dict[str, Any]],
    ranking_profile: str,
    signal_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    files = index_files if isinstance(index_files, dict) else {}
    normalized_profile = str(ranking_profile or "graph").strip().lower()
    if normalized_profile not in RANKING_PROFILES:
        raise ValueError(f"unsupported ranking profile: {ranking_profile}")

    ranked = rank_index_files(
        files=files,
        profile=normalized_profile,
        signal_weights=signal_weights,
    )
    module_to_path, path_style_to_paths, stem_to_paths = _build_resolution_maps(files)
    adjacency = _build_adjacency(
        files=files,
        module_to_path=module_to_path,
        path_style_to_paths=path_style_to_paths,
        stem_to_paths=stem_to_paths,
    )
    symbol_to_paths = _build_symbol_to_paths(files=files)
    reference_adjacency = _build_reference_adjacency(
        files=files,
        symbol_to_paths=symbol_to_paths,
    )
    symbol_nodes_by_path, symbol_to_node_ids = _build_symbol_graph_context(files=files)
    symbol_adjacency = _build_symbol_adjacency(
        files=files,
        nodes_by_path=symbol_nodes_by_path,
        symbol_to_node_ids=symbol_to_node_ids,
    )
    return {
        "ranking_profile": normalized_profile,
        "ranked": [
            {
                "path": str(item.get("path", "")),
                "score": float(item.get("score", 0.0) or 0.0),
                "symbol_count": int(item.get("symbol_count", 0) or 0),
                "import_count": int(item.get("import_count", 0) or 0),
                "language": str(item.get("language", "")),
                "module": str(item.get("module", "")),
            }
            for item in ranked
            if isinstance(item, dict)
        ],
        "module_to_path": module_to_path,
        "path_style_to_paths": {
            key: sorted(str(value) for value in values)
            for key, values in path_style_to_paths.items()
        },
        "stem_to_paths": {
            key: sorted(str(value) for value in values)
            for key, values in stem_to_paths.items()
        },
        "adjacency": adjacency,
        "reference_adjacency": reference_adjacency,
        "symbol_adjacency": symbol_adjacency,
    }


def _normalize_stage_precomputed_payload(
    *,
    payload: dict[str, Any] | None,
    ranking_profile: str,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if str(payload.get("ranking_profile", "")).strip().lower() != str(ranking_profile):
        return None
    ranked = payload.get("ranked")
    module_to_path = payload.get("module_to_path")
    path_style_to_paths = payload.get("path_style_to_paths")
    legacy_path_style_to_path = payload.get("path_style_to_path")
    stem_to_paths = payload.get("stem_to_paths")
    adjacency = payload.get("adjacency")
    if not isinstance(ranked, list):
        return None
    if not isinstance(module_to_path, dict):
        return None
    if not isinstance(path_style_to_paths, dict):
        if not isinstance(legacy_path_style_to_path, dict):
            return None
        path_style_to_paths = {
            str(key): [str(value)]
            for key, value in legacy_path_style_to_path.items()
            if isinstance(key, str) and isinstance(value, str)
        }
    if not isinstance(stem_to_paths, dict):
        return None
    if not isinstance(adjacency, dict):
        return None
    normalized_payload = dict(payload)
    normalized_payload["path_style_to_paths"] = path_style_to_paths
    return normalized_payload


def _rank_from_precomputed(
    *,
    ranked_rows: list[dict[str, Any]],
    seed_paths: list[str],
    adjacency: dict[str, list[str]] | Any,
    profile: str,
) -> list[dict[str, Any]]:
    rows = [dict(item) for item in ranked_rows if isinstance(item, dict)]
    if not rows:
        return []

    seed_set = {str(path).strip() for path in seed_paths if str(path).strip()}
    if not seed_set or profile != "graph_seeded":
        rows.sort(
            key=lambda item: (
                -float(item.get("score", 0.0) or 0.0),
                -float(item.get("base_score", 0.0) or 0.0),
                -float(item.get("graph_rank", 0.0) or 0.0),
                -float(item.get("import_depth_rank", 0.0) or 0.0),
                str(item.get("path", "")),
            )
        )
        return rows

    adjacency_map = adjacency if isinstance(adjacency, dict) else {}
    inbound_neighbors: dict[str, int] = {}
    for source, targets_raw in adjacency_map.items():
        if not isinstance(source, str):
            continue
        targets = targets_raw if isinstance(targets_raw, list) else []
        for target in targets:
            key = str(target).strip()
            if not key:
                continue
            inbound_neighbors[key] = inbound_neighbors.get(key, 0) + 1

    for row in rows:
        path = str(row.get("path") or "").strip()
        seed_boost = 0.0
        if path in seed_set:
            seed_boost += 0.12
        inbound = int(inbound_neighbors.get(path, 0))
        if inbound > 0:
            seed_boost += min(0.08, float(inbound) * 0.01)
        if seed_boost <= 0.0:
            continue
        row["seed_rank"] = round(float(row.get("seed_rank", 0.0) or 0.0) + seed_boost, 6)
        row["score"] = round(float(row.get("score", 0.0) or 0.0) + seed_boost, 6)
        row["seeded"] = path in seed_set

    rows.sort(
        key=lambda item: (
            -float(item.get("score", 0.0) or 0.0),
            -float(item.get("base_score", 0.0) or 0.0),
            -float(item.get("graph_rank", 0.0) or 0.0),
            -float(item.get("import_depth_rank", 0.0) or 0.0),
            str(item.get("path", "")),
        )
    )
    return rows


def write_repo_map(
    *,
    index_payload: dict[str, Any],
    output_json: str | Path,
    output_md: str | Path,
    budget_tokens: int = 800,
    top_k: int = 40,
    ranking_profile: str = "heuristic",
    signal_weights: dict[str, float] | None = None,
    tokenizer_model: str | None = None,
) -> dict[str, str]:
    repo_map = build_repo_map(
        index_payload=index_payload,
        budget_tokens=budget_tokens,
        top_k=top_k,
        ranking_profile=ranking_profile,
        signal_weights=signal_weights,
        tokenizer_model=tokenizer_model,
    )

    out_json = Path(output_json)
    out_md = Path(output_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    payload = dict(repo_map)
    payload.pop("markdown", None)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(repo_map["markdown"], encoding="utf-8")

    return {
        "repo_map_json": str(out_json),
        "repo_map_md": str(out_md),
    }
__all__ = [
    "build_repo_map",
    "build_stage_precompute_payload",
    "build_stage_repo_map",
    "write_repo_map",
]
