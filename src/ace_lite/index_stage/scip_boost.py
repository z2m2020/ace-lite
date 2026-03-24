"""SCIP graph boosting for index-stage file candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.scip import generate_scip_index, load_scip_edges
from ace_lite.scoring_config import resolve_scip_scoring_config


def apply_scip_boost(
    *,
    index_path: Path,
    provider: str,
    generate_fallback: bool,
    files_map: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    policy: dict[str, Any],
    scoring_config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply inbound-reference boosts from a SCIP edge index."""
    generated: dict[str, Any] | None = None
    fallback_generated = False
    scip_scoring = resolve_scip_scoring_config(scoring_config)
    base_weight = float(scip_scoring["base_weight"])

    loaded = load_scip_edges(index_path, provider=provider)
    if not bool(loaded.get("loaded", False)) and generate_fallback:
        try:
            generated = generate_scip_index(index_files=files_map, output_path=index_path)
            fallback_generated = True
            loaded = load_scip_edges(index_path, provider="scip_lite")
        except Exception as exc:
            return candidates, {
                "enabled": True,
                "loaded": False,
                "edge_count": 0,
                "boost_applied": 0,
                "path": str(index_path),
                "provider": str(provider),
                "generate_fallback": bool(generate_fallback),
                "fallback_generated": fallback_generated,
                "error": str(exc),
            }

    if not bool(loaded.get("loaded", False)):
        return candidates, {
            "enabled": True,
            "loaded": False,
            "edge_count": 0,
            "boost_applied": 0,
            "path": str(index_path),
            "provider": str(provider),
            "generate_fallback": bool(generate_fallback),
            "fallback_generated": fallback_generated,
        }

    inbound = (
        loaded.get("inbound_counts", {})
        if isinstance(loaded.get("inbound_counts"), dict)
        else {}
    )
    pagerank = loaded.get("pagerank", {}) if isinstance(loaded.get("pagerank"), dict) else {}
    degree_centrality = (
        loaded.get("degree_centrality", {})
        if isinstance(loaded.get("degree_centrality"), dict)
        else {}
    )

    ranked = [item for item in candidates if isinstance(item, dict)]
    by_path = {
        str(item.get("path") or ""): item
        for item in ranked
        if str(item.get("path") or "").strip()
    }

    max_inbound = max((float(value) for value in inbound.values()), default=0.0)
    max_pagerank = max((float(value) for value in pagerank.values()), default=0.0)
    max_degree = max((float(value) for value in degree_centrality.values()), default=0.0)

    inbound_weight = max(
        0.0, base_weight * float(policy.get("scip_weight", 1.0) or 1.0)
    )
    pagerank_weight = max(
        0.0,
        base_weight * float(policy.get("scip_pagerank_weight", 0.0) or 0.0),
    )
    centrality_weight = max(
        0.0,
        base_weight
        * float(
            policy.get(
                "scip_centrality_weight",
                policy.get("scip_degree_weight", 0.0),
            )
            or 0.0
        ),
    )

    boost_applied = 0
    boost_applied_inbound = 0
    boost_applied_pagerank = 0
    boost_applied_centrality = 0
    boosted_paths: set[str] = set()

    for path, entry in by_path.items():
        if not isinstance(entry, dict):
            continue
        boost_total = 0.0

        if inbound_weight > 0.0 and max_inbound > 0.0:
            inbound_value = float(inbound.get(path, 0.0) or 0.0)
            if inbound_value > 0.0:
                boost_total += (inbound_value / max_inbound) * inbound_weight
                boost_applied_inbound += 1

        if pagerank_weight > 0.0 and max_pagerank > 0.0:
            pagerank_value = float(pagerank.get(path, 0.0) or 0.0)
            if pagerank_value > 0.0:
                boost_total += (pagerank_value / max_pagerank) * pagerank_weight
                boost_applied_pagerank += 1

        if centrality_weight > 0.0 and max_degree > 0.0:
            centrality_value = float(degree_centrality.get(path, 0.0) or 0.0)
            if centrality_value > 0.0:
                boost_total += (centrality_value / max_degree) * centrality_weight
                boost_applied_centrality += 1

        if boost_total <= 0.0:
            continue

        entry["score"] = round(float(entry.get("score") or 0.0) + boost_total, 6)
        breakdown = entry.get("score_breakdown")
        if not isinstance(breakdown, dict):
            breakdown = {}
            entry["score_breakdown"] = breakdown

        if inbound_weight > 0.0 and max_inbound > 0.0:
            inbound_value = float(inbound.get(path, 0.0) or 0.0)
            if inbound_value > 0.0:
                inbound_boost = (inbound_value / max_inbound) * inbound_weight
                breakdown["scip"] = round(
                    float(breakdown.get("scip", 0.0)) + inbound_boost, 6
                )

        if pagerank_weight > 0.0 and max_pagerank > 0.0:
            pagerank_value = float(pagerank.get(path, 0.0) or 0.0)
            if pagerank_value > 0.0:
                pagerank_boost = (pagerank_value / max_pagerank) * pagerank_weight
                breakdown["scip_pagerank"] = round(
                    float(breakdown.get("scip_pagerank", 0.0)) + pagerank_boost, 6
                )

        if centrality_weight > 0.0 and max_degree > 0.0:
            centrality_value = float(degree_centrality.get(path, 0.0) or 0.0)
            if centrality_value > 0.0:
                centrality_boost = (centrality_value / max_degree) * centrality_weight
                breakdown["scip_centrality"] = round(
                    float(breakdown.get("scip_centrality", 0.0)) + centrality_boost, 6
                )

        boosted_paths.add(path)

    ranked.sort(key=lambda item: (-float(item.get("score") or 0.0), str(item.get("path") or "")))
    boost_applied = len(boosted_paths)
    return ranked, {
        "enabled": True,
        "loaded": bool(loaded.get("loaded", False)),
        "edge_count": int(loaded.get("edge_count", (generated or {}).get("edge_count", 0)) or 0),
        "document_count": int(loaded.get("document_count", 0) or 0),
        "definition_occurrence_count": int(
            loaded.get("definition_occurrence_count", 0) or 0
        ),
        "reference_occurrence_count": int(
            loaded.get("reference_occurrence_count", 0) or 0
        ),
        "symbol_definition_count": int(loaded.get("symbol_definition_count", 0) or 0),
        "boost_applied": boost_applied,
        "boost_applied_inbound": boost_applied_inbound,
        "boost_applied_pagerank": boost_applied_pagerank,
        "boost_applied_centrality": boost_applied_centrality,
        "path": str(index_path),
        "provider": str(loaded.get("provider") or provider),
        "schema_version": str(loaded.get("schema_version") or ""),
        "generate_fallback": bool(generate_fallback),
        "fallback_generated": fallback_generated,
        "weights": {
            "base_weight": base_weight,
            "inbound": float(inbound_weight),
            "pagerank": float(pagerank_weight),
            "centrality": float(centrality_weight),
        },
    }


__all__ = ["apply_scip_boost"]
