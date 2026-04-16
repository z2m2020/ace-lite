from __future__ import annotations

from typing import Any


def extract_seed_candidate_paths(
    *,
    files: dict[str, dict[str, Any]],
    seed_candidates: list[dict[str, Any]],
    top_k: int,
) -> list[str]:
    seeds: list[str] = []
    seen: set[str] = set()
    for item in seed_candidates:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        if not path or path not in files or path in seen:
            continue
        seeds.append(path)
        seen.add(path)
        if len(seeds) >= top_k:
            break
    return seeds


def resolve_seed_paths(
    *,
    files: dict[str, dict[str, Any]],
    seed_candidates: list[dict[str, Any]],
    ranked: list[dict[str, Any]],
    top_k: int,
) -> list[str]:
    seeds = extract_seed_candidate_paths(
        files=files,
        seed_candidates=seed_candidates,
        top_k=top_k,
    )
    if seeds:
        return seeds

    for item in ranked:
        path = str(item.get("path", "")).strip()
        if not path or path not in files or path in seeds:
            continue
        seeds.append(path)
        if len(seeds) >= top_k:
            break
    return seeds


def build_stage_repomap_explainability(
    *,
    seed_paths: list[str],
    seed_hints: list[str],
    subgraph_seed_paths: list[str] | None = None,
    import_neighbors: list[str],
    reference_neighbors: list[str],
    included_neighbors: list[str],
    neighbor_candidates: list[str],
    path_style_to_paths: dict[str, set[str]],
    stem_to_paths: dict[str, set[str]],
    symbol_to_paths: dict[str, set[str]],
) -> dict[str, Any]:
    seed_hint_set = {str(path).strip() for path in seed_hints if str(path).strip()}
    subgraph_seed_set = {
        str(path).strip() for path in (subgraph_seed_paths or []) if str(path).strip()
    }
    if seed_hint_set:
        seed_strategy = "seed_candidates"
    elif subgraph_seed_set:
        seed_strategy = "subgraph_payload"
    else:
        seed_strategy = "ranked_fallback"
    seed_sources = [
        {
            "path": str(path),
            "source": (
                "seed_candidate"
                if str(path).strip() in seed_hint_set
                else (
                    "subgraph_seed" if str(path).strip() in subgraph_seed_set else "ranked_fallback"
                )
            ),
        }
        for path in seed_paths
        if str(path).strip()
    ]
    import_set = {str(path).strip() for path in import_neighbors if str(path).strip()}
    reference_set = {str(path).strip() for path in reference_neighbors if str(path).strip()}
    included_import_count = sum(1 for path in included_neighbors if path in import_set)
    included_reference_count = sum(1 for path in included_neighbors if path in reference_set)
    ambiguity = {
        "path_style_collision_count": sum(
            1 for values in path_style_to_paths.values() if len(values) > 1
        ),
        "stem_collision_count": sum(1 for values in stem_to_paths.values() if len(values) > 1),
        "reference_multi_definition_symbol_count": sum(
            1 for values in symbol_to_paths.values() if len(values) > 1
        ),
        "budget_trimmed_neighbor_count": max(0, len(neighbor_candidates) - len(included_neighbors)),
    }
    notes: list[str] = []
    for note in (
        f"seed_strategy:{seed_strategy}",
        "subgraph_seed_paths_present" if subgraph_seed_set else "",
        "import_neighbors_present" if import_neighbors else "",
        "reference_neighbors_present" if reference_neighbors else "",
        ("budget_trimmed_neighbors" if int(ambiguity["budget_trimmed_neighbor_count"]) > 0 else ""),
        (
            f"path_style_collisions:{int(ambiguity['path_style_collision_count'])}"
            if int(ambiguity["path_style_collision_count"]) > 0
            else ""
        ),
        (
            f"stem_collisions:{int(ambiguity['stem_collision_count'])}"
            if int(ambiguity["stem_collision_count"]) > 0
            else ""
        ),
        (
            f"reference_symbol_collisions:{int(ambiguity['reference_multi_definition_symbol_count'])}"
            if int(ambiguity["reference_multi_definition_symbol_count"]) > 0
            else ""
        ),
    ):
        normalized = str(note or "").strip()
        if normalized and normalized not in notes:
            notes.append(normalized)

    return {
        "seed_strategy": seed_strategy,
        "seed_sources": seed_sources,
        "neighbor_sources": {
            "import_candidate_count": len(import_neighbors),
            "reference_candidate_count": len(reference_neighbors),
            "included_import_count": int(included_import_count),
            "included_reference_count": int(included_reference_count),
        },
        "ambiguity": ambiguity,
        "selection_notes": notes,
    }


__all__ = [
    "build_stage_repomap_explainability",
    "extract_seed_candidate_paths",
    "resolve_seed_paths",
]
