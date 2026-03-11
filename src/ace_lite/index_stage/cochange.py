"""Co-change (temporal coupling) boosting for index-stage candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.cochange import load_or_build_cochange_matrix, query_cochange_neighbors


def apply_cochange_neighbors(
    *,
    repo_root: str,
    cache_path: Path,
    files_map: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    memory_paths: list[str],
    policy: dict[str, Any],
    lookback_commits: int,
    half_life_days: float,
    neighbor_cap: int,
    top_k_files: int,
    top_neighbors: int,
    boost_weight: float,
    min_neighbor_score: float,
    max_boost: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply co-change neighbors as boosts and/or extra candidates."""
    try:
        matrix, info = load_or_build_cochange_matrix(
            repo_root=repo_root,
            cache_path=cache_path,
            lookback_commits=lookback_commits,
            half_life_days=half_life_days,
            neighbor_cap=neighbor_cap,
        )
    except Exception as exc:
        return candidates, {
            "enabled": False,
            "cache_hit": False,
            "cache_mode": "error",
            "neighbors_added": 0,
            "boost_applied": 0,
            "error": str(exc),
            "lookback_commits": lookback_commits,
            "half_life_days": half_life_days,
            "neighbor_cap": neighbor_cap,
            "expand_candidates": False,
            "min_neighbor_score": float(min_neighbor_score),
            "max_boost": float(max_boost),
        }

    seed_paths = [
        str(item.get("path") or "")
        for item in candidates[: max(1, int(top_k_files))]
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    ]
    for path in memory_paths:
        normalized = str(path or "").strip()
        if normalized and normalized not in seed_paths:
            seed_paths.append(normalized)

    neighbors = query_cochange_neighbors(matrix=matrix, seed_paths=seed_paths, top_n=top_neighbors)
    policy_weight = float(policy.get("cochange_weight", 1.0) or 1.0)
    effective_boost_weight = max(0.0, float(boost_weight) * policy_weight)
    expand_candidates = bool(policy.get("cochange_expand_candidates", False))

    ranked = [item for item in candidates if isinstance(item, dict)]
    by_path = {
        str(item.get("path") or ""): item
        for item in ranked
        if str(item.get("path") or "").strip()
    }

    max_raw_score = max((float(item.get("score") or 0.0) for item in neighbors), default=0.0)
    neighbors_added = 0
    boost_applied = 0

    for neighbor in neighbors:
        path = str(neighbor.get("path") or "").strip()
        if not path:
            continue
        try:
            raw_score = float(neighbor.get("score") or 0.0)
        except Exception:
            raw_score = 0.0
        if raw_score < float(min_neighbor_score):
            continue

        normalized_raw = (raw_score / max_raw_score) if max_raw_score > 0.0 else 0.0
        boost = min(float(max_boost), normalized_raw * effective_boost_weight)
        if boost <= 0.0:
            continue

        if path in by_path:
            entry = by_path[path]
            entry["score"] = round(float(entry.get("score") or 0.0) + boost, 6)
            breakdown = entry.get("score_breakdown")
            if isinstance(breakdown, dict):
                breakdown["cochange"] = round(float(breakdown.get("cochange", 0.0)) + boost, 6)
            else:
                entry["score_breakdown"] = {"cochange": round(boost, 6)}
            boost_applied += 1
            continue

        if not expand_candidates:
            continue

        index_entry = files_map.get(path)
        if not isinstance(index_entry, dict):
            continue

        symbols = index_entry.get("symbols", [])
        imports = index_entry.get("imports", [])
        created = {
            "path": path,
            "module": str(index_entry.get("module") or ""),
            "language": index_entry.get("language", ""),
            "score": round(boost, 6),
            "symbol_count": len(symbols) if isinstance(symbols, list) else 0,
            "import_count": len(imports) if isinstance(imports, list) else 0,
            "score_breakdown": {"cochange": round(boost, 6)},
        }
        ranked.append(created)
        by_path[path] = created
        neighbors_added += 1
        boost_applied += 1

    ranked.sort(
        key=lambda item: (-float(item.get("score") or 0.0), str(item.get("path") or "")),
    )

    return ranked, {
        "enabled": bool(info.get("enabled", True)),
        "cache_hit": bool(info.get("cache_hit", False)),
        "cache_mode": str(info.get("mode", "unknown")),
        "neighbors_added": neighbors_added,
        "boost_applied": boost_applied,
        "lookback_commits": lookback_commits,
        "half_life_days": half_life_days,
        "cache_path": str(info.get("cache_path") or cache_path),
        "edge_count": int(info.get("edge_count", 0) or 0),
        "neighbor_cap": int(info.get("neighbor_cap", neighbor_cap) or neighbor_cap),
        "expand_candidates": expand_candidates,
        "min_neighbor_score": float(min_neighbor_score),
        "max_boost": float(max_boost),
    }


__all__ = ["apply_cochange_neighbors"]

