"""Bounded graph-aware closure bonus for retrieval-time chunk scoring."""

from __future__ import annotations

from typing import Any

from ace_lite.chunking.graph_prior import _chunk_symbol_id, _get_graph_context, _seed_strength


def _parent_namespace(value: str) -> str:
    normalized = str(value or "").strip().replace("::", ".").replace("/", ".")
    if not normalized:
        return ""
    parts = [part.strip().lower() for part in normalized.split(".") if part.strip()]
    if len(parts) <= 1:
        return ""
    tail = parts[-1]
    if "(" in tail:
        tail = tail.split("(", 1)[0].strip()
    return ".".join(parts[:-1])


def apply_graph_closure_bonus(
    *,
    candidate_chunks: list[dict[str, Any]],
    files_map: dict[str, dict[str, Any]],
    policy: dict[str, Any],
    cache_key: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [dict(item) for item in candidate_chunks if isinstance(item, dict)]
    if not rows:
        return rows, _empty_payload(reason="no_candidates")
    if not isinstance(files_map, dict) or not files_map:
        return rows, _empty_payload(reason="no_files_map")

    enabled = bool(policy.get("chunk_graph_closure_enabled", False))
    seed_limit = max(1, int(policy.get("chunk_graph_closure_seed_limit", 6) or 6))
    neighbor_limit = max(
        1,
        int(
            policy.get(
                "chunk_graph_closure_neighbor_limit",
                policy.get("chunk_graph_neighbor_limit", 4),
            )
            or 4
        ),
    )
    max_candidates = max(
        1,
        int(
            policy.get(
                "chunk_graph_closure_max_candidates",
                policy.get("chunk_graph_max_candidates", 192),
            )
            or 192
        ),
    )
    bonus_weight = max(
        0.0,
        float(policy.get("chunk_graph_closure_bonus_weight", 0.0) or 0.0),
    )
    bonus_cap = max(
        0.0,
        float(policy.get("chunk_graph_closure_bonus_cap", 0.0) or 0.0),
    )
    seed_min_lexical = max(
        0.0,
        float(
            policy.get(
                "chunk_graph_closure_seed_min_lexical",
                policy.get("chunk_graph_seed_min_lexical", 1.0),
            )
            or 0.0
        ),
    )
    seed_min_file_prior = max(
        0.0,
        float(
            policy.get(
                "chunk_graph_closure_seed_min_file_prior",
                policy.get("chunk_graph_seed_min_file_prior", 2.0),
            )
            or 0.0
        ),
    )

    payload = _empty_payload(reason="disabled")
    payload["enabled"] = enabled
    payload["seed_limit"] = seed_limit
    payload["neighbor_limit"] = neighbor_limit
    payload["candidate_count"] = len(rows)
    payload["max_candidates"] = max_candidates
    payload["bonus_cap"] = float(bonus_cap)
    if not enabled:
        payload["reason"] = "disabled_by_policy"
        return rows, payload
    if bonus_weight <= 0.0 or bonus_cap <= 0.0:
        payload["reason"] = "zero_weight_or_cap"
        return rows, payload
    if len(rows) > max_candidates:
        payload["reason"] = "candidate_count_guarded"
        return rows, payload

    context = _get_graph_context(files_map=files_map, cache_key=cache_key)
    adjacency = context.get("adjacency", {})
    if not isinstance(adjacency, dict) or not adjacency:
        payload["reason"] = "no_graph_context"
        return rows, payload

    by_symbol_id: dict[str, dict[str, Any]] = {}
    anchors: list[tuple[float, str]] = []
    for row in rows:
        symbol_id = _chunk_symbol_id(row)
        if not symbol_id:
            continue
        by_symbol_id[symbol_id] = row
        breakdown = row.get("score_breakdown")
        if not isinstance(breakdown, dict):
            breakdown = {}
            row["score_breakdown"] = breakdown
        seeded, strength = _seed_strength(
            breakdown=breakdown,
            min_lexical=seed_min_lexical,
            min_file_prior=seed_min_file_prior,
        )
        if not seeded:
            continue
        breakdown["graph_closure_seeded"] = round(strength, 6)
        anchors.append((float(row.get("score", 0.0) or 0.0), symbol_id))

    if not anchors:
        payload["reason"] = "no_anchor_chunks"
        return rows, payload

    anchors.sort(key=lambda item: (-float(item[0]), str(item[1])))
    anchor_ids = [symbol_id for _, symbol_id in anchors[:seed_limit]]
    support_counts: dict[str, int] = {}
    bonuses: dict[str, float] = {}

    for anchor_id in anchor_ids:
        anchor = by_symbol_id.get(anchor_id)
        if not isinstance(anchor, dict):
            continue
        anchor_path = str(anchor.get("path") or "").strip()
        anchor_parent = _parent_namespace(str(anchor.get("qualified_name") or ""))
        neighbors = adjacency.get(anchor_id, [])
        if not isinstance(neighbors, list):
            continue
        for target_id in neighbors[:neighbor_limit]:
            normalized_target = str(target_id or "").strip()
            if (
                not normalized_target
                or normalized_target == anchor_id
                or normalized_target not in by_symbol_id
            ):
                continue
            target = by_symbol_id[normalized_target]
            target_path = str(target.get("path") or "").strip()
            target_parent = _parent_namespace(str(target.get("qualified_name") or ""))
            if target_path != anchor_path and (
                not anchor_parent or anchor_parent != target_parent
            ):
                continue
            support_counts[normalized_target] = int(
                support_counts.get(normalized_target, 0)
            ) + 1
            bonuses[normalized_target] = min(
                bonus_cap,
                float(bonuses.get(normalized_target, 0.0) or 0.0) + bonus_weight,
            )

    boosted_chunk_count = 0
    total_bonus = 0.0
    support_edge_count = 0
    for symbol_id in sorted(set(support_counts) | set(bonuses)):
        row = by_symbol_id.get(symbol_id)
        if not isinstance(row, dict):
            continue
        breakdown = row.get("score_breakdown")
        if not isinstance(breakdown, dict):
            breakdown = {}
            row["score_breakdown"] = breakdown
        support_count = int(support_counts.get(symbol_id, 0) or 0)
        if support_count > 0:
            breakdown["graph_closure_support_count"] = float(support_count)
            support_edge_count += support_count
        bonus = float(bonuses.get(symbol_id, 0.0) or 0.0)
        if bonus <= 0.0:
            continue
        row["score"] = round(float(row.get("score", 0.0) or 0.0) + bonus, 6)
        breakdown["graph_closure_bonus"] = round(
            float(breakdown.get("graph_closure_bonus", 0.0) or 0.0) + bonus,
            6,
        )
        boosted_chunk_count += 1
        total_bonus += bonus

    rows.sort(
        key=lambda item: (
            -float(item.get("score", 0.0) or 0.0),
            str(item.get("path") or ""),
            int(item.get("lineno") or 0),
            str(item.get("qualified_name") or ""),
        )
    )
    payload.update(
        {
            "enabled": True,
            "reason": "ok",
            "anchor_count": len(anchor_ids),
            "boosted_chunk_count": boosted_chunk_count,
            "support_edge_count": support_edge_count,
            "graph_closure_total": round(total_bonus, 6),
        }
    )
    return rows, payload


def _empty_payload(*, reason: str) -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": str(reason),
        "candidate_count": 0,
        "max_candidates": 0,
        "seed_limit": 0,
        "neighbor_limit": 0,
        "bonus_cap": 0.0,
        "anchor_count": 0,
        "boosted_chunk_count": 0,
        "support_edge_count": 0,
        "graph_closure_total": 0.0,
    }


__all__ = ["apply_graph_closure_bonus"]
