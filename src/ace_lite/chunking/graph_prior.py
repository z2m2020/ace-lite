"""Query-aware graph priors for chunk candidates."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from ace_lite.repomap.adjacency import (
    _build_symbol_adjacency,
    _build_symbol_graph_context,
)

_GRAPH_CONTEXT_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_GRAPH_CONTEXT_CACHE_CAP = 8


def _build_graph_context(*, files_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    symbol_nodes_by_path, symbol_to_node_ids = _build_symbol_graph_context(files=files_map)
    adjacency = _build_symbol_adjacency(
        files=files_map,
        nodes_by_path=symbol_nodes_by_path,
        symbol_to_node_ids=symbol_to_node_ids,
    )

    inbound_degree: dict[str, int] = {}
    for source_id, targets in adjacency.items():
        if source_id not in inbound_degree:
            inbound_degree[source_id] = 0
        if not isinstance(targets, list):
            continue
        for target_id in targets:
            normalized = str(target_id or "").strip()
            if not normalized:
                continue
            inbound_degree[normalized] = inbound_degree.get(normalized, 0) + 1

    return {
        "adjacency": adjacency,
        "inbound_degree": inbound_degree,
    }


def _get_graph_context(
    *,
    files_map: dict[str, dict[str, Any]],
    cache_key: str,
) -> dict[str, Any]:
    normalized_key = str(cache_key or "").strip()
    if normalized_key:
        cached = _GRAPH_CONTEXT_CACHE.get(normalized_key)
        if isinstance(cached, dict):
            _GRAPH_CONTEXT_CACHE.move_to_end(normalized_key)
            return cached

    context = _build_graph_context(files_map=files_map)
    if normalized_key:
        _GRAPH_CONTEXT_CACHE[normalized_key] = context
        _GRAPH_CONTEXT_CACHE.move_to_end(normalized_key)
        while len(_GRAPH_CONTEXT_CACHE) > _GRAPH_CONTEXT_CACHE_CAP:
            _GRAPH_CONTEXT_CACHE.popitem(last=False)
    return context


def _chunk_symbol_id(chunk: dict[str, Any]) -> str:
    path = str(chunk.get("path") or "").strip()
    qualified_name = str(chunk.get("qualified_name") or chunk.get("name") or "").strip()
    try:
        lineno = int(chunk.get("lineno") or 0)
    except Exception:
        lineno = 0
    try:
        end_lineno = int(chunk.get("end_lineno") or lineno)
    except Exception:
        end_lineno = lineno
    if not path or not qualified_name or lineno <= 0 or end_lineno < lineno:
        return ""
    return f"{path}|{lineno}|{end_lineno}|{qualified_name}"


def _seed_strength(
    *,
    breakdown: dict[str, Any],
    min_lexical: float,
    min_file_prior: float,
) -> tuple[bool, float]:
    lexical_signal = 0.0
    for key in ("path", "module", "symbol", "signature"):
        try:
            lexical_signal += max(0.0, float(breakdown.get(key, 0.0) or 0.0))
        except Exception:
            continue

    try:
        file_prior = max(0.0, float(breakdown.get("file_prior", 0.0) or 0.0))
    except Exception:
        file_prior = 0.0

    lexical_ready = lexical_signal >= min_lexical if min_lexical > 0.0 else lexical_signal > 0.0
    file_ready = file_prior >= min_file_prior if min_file_prior > 0.0 else file_prior > 0.0
    if not lexical_ready and not file_ready:
        return False, 0.0

    lexical_norm = (lexical_signal / min_lexical) if min_lexical > 0.0 else lexical_signal
    file_norm = (file_prior / min_file_prior) if min_file_prior > 0.0 else file_prior
    strength = min(1.0, max(lexical_norm, file_norm * 0.6))
    return True, max(0.0, float(strength))


def apply_query_aware_graph_prior(
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

    enabled = bool(policy.get("chunk_graph_prior_enabled", True))
    seed_limit = max(1, int(policy.get("chunk_graph_seed_limit", 8) or 8))
    neighbor_limit = max(1, int(policy.get("chunk_graph_neighbor_limit", 4) or 4))
    max_candidates = max(1, int(policy.get("chunk_graph_max_candidates", 192) or 192))
    edge_weight = max(0.0, float(policy.get("chunk_graph_edge_weight", 0.18) or 0.0))
    prior_cap = max(0.0, float(policy.get("chunk_graph_prior_cap", 0.45) or 0.0))
    seed_min_lexical = max(
        0.0, float(policy.get("chunk_graph_seed_min_lexical", 1.0) or 0.0)
    )
    seed_min_file_prior = max(
        0.0, float(policy.get("chunk_graph_seed_min_file_prior", 2.0) or 0.0)
    )
    hub_soft_cap = max(1, int(policy.get("chunk_graph_hub_soft_cap", 3) or 3))
    hub_penalty_weight = max(
        0.0, float(policy.get("chunk_graph_hub_penalty_weight", 0.04) or 0.0)
    )
    max_hub_penalty = max(
        0.0,
        float(policy.get("chunk_graph_max_hub_penalty", max(0.0, prior_cap * 0.8)) or 0.0),
    )

    payload = _empty_payload(reason="disabled")
    payload["enabled"] = enabled
    payload["seed_limit"] = seed_limit
    payload["neighbor_limit"] = neighbor_limit
    payload["candidate_count"] = len(rows)
    payload["max_candidates"] = max_candidates
    payload["prior_cap"] = float(prior_cap)
    if not enabled:
        payload["reason"] = "disabled_by_policy"
        return rows, payload
    if edge_weight <= 0.0 or prior_cap <= 0.0:
        payload["reason"] = "zero_weight_or_cap"
        return rows, payload
    if len(rows) > max_candidates:
        payload["reason"] = "candidate_count_guarded"
        return rows, payload

    context = _get_graph_context(files_map=files_map, cache_key=cache_key)
    adjacency = context.get("adjacency", {})
    inbound_degree = context.get("inbound_degree", {})
    if not isinstance(adjacency, dict) or not adjacency:
        payload["reason"] = "no_graph_context"
        return rows, payload

    by_symbol_id: dict[str, dict[str, Any]] = {}
    seeds: list[tuple[float, str]] = []
    seeded_chunk_count = 0

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
        breakdown["graph_seeded"] = round(strength, 6)
        seeds.append((float(row.get("score", 0.0) or 0.0), symbol_id))
        seeded_chunk_count += 1

    if not seeds:
        payload["reason"] = "no_seed_chunks"
        return rows, payload

    seeds.sort(key=lambda item: (-float(item[0]), str(item[1])))
    transfer_count: dict[str, int] = {}
    graph_additions: dict[str, float] = {}
    hub_penalties: dict[str, float] = {}

    for _, source_id in seeds[:seed_limit]:
        source_row = by_symbol_id.get(source_id)
        if not isinstance(source_row, dict):
            continue
        source_breakdown = (
            source_row.get("score_breakdown")
            if isinstance(source_row.get("score_breakdown"), dict)
            else {}
        )
        seed_strength = max(
            0.0, float(source_breakdown.get("graph_seeded", 0.0) or 0.0)
        )
        base_transfer = edge_weight * max(0.5, seed_strength)
        neighbors = adjacency.get(source_id, [])
        if not isinstance(neighbors, list):
            continue
        for target_id in neighbors[:neighbor_limit]:
            normalized_target = str(target_id or "").strip()
            if not normalized_target or normalized_target == source_id:
                continue
            target_row = by_symbol_id.get(normalized_target)
            if not isinstance(target_row, dict):
                continue
            target_inbound_degree = max(
                0, int(inbound_degree.get(normalized_target, 0) or 0)
            )
            hub_overflow = max(0, target_inbound_degree - hub_soft_cap)
            hub_penalty = min(
                max_hub_penalty,
                float(hub_overflow) * hub_penalty_weight,
            )
            transfer_count[normalized_target] = int(
                transfer_count.get(normalized_target, 0)
            ) + 1
            if hub_penalty > 0.0:
                hub_penalties[normalized_target] = float(
                    hub_penalties.get(normalized_target, 0.0) or 0.0
                ) + hub_penalty
            transfer = max(0.0, base_transfer - hub_penalty)
            if transfer <= 0.0:
                continue
            graph_additions[normalized_target] = min(
                prior_cap,
                float(graph_additions.get(normalized_target, 0.0) or 0.0) + transfer,
            )

    boosted_chunk_count = 0
    hub_suppressed_chunk_count = 0
    total_graph_prior = 0.0
    total_hub_penalty = 0.0
    total_transfers = 0
    affected_symbol_ids = set(graph_additions)
    affected_symbol_ids.update(transfer_count)
    affected_symbol_ids.update(hub_penalties)
    for symbol_id in sorted(affected_symbol_ids):
        row = by_symbol_id.get(symbol_id)
        if not isinstance(row, dict):
            continue
        boost = float(graph_additions.get(symbol_id, 0.0) or 0.0)
        if boost > 0.0:
            row["score"] = round(float(row.get("score", 0.0) or 0.0) + boost, 6)
        breakdown = row.get("score_breakdown")
        if not isinstance(breakdown, dict):
            breakdown = {}
            row["score_breakdown"] = breakdown
        transfers = int(transfer_count.get(symbol_id, 0) or 0)
        if transfers > 0:
            breakdown["graph_transfer_count"] = float(transfers)
            total_transfers += transfers
        penalty = float(hub_penalties.get(symbol_id, 0.0) or 0.0)
        if penalty > 0.0:
            breakdown["graph_hub_penalty"] = round(-penalty, 6)
            hub_suppressed_chunk_count += 1
            total_hub_penalty += penalty
        if boost > 0.0:
            breakdown["graph_prior"] = round(
                float(breakdown.get("graph_prior", 0.0) or 0.0) + boost,
                6,
            )
            boosted_chunk_count += 1
            total_graph_prior += boost

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
            "seeded_chunk_count": seeded_chunk_count,
            "boosted_chunk_count": boosted_chunk_count,
            "hub_suppressed_chunk_count": hub_suppressed_chunk_count,
            "graph_prior_total": round(total_graph_prior, 6),
            "graph_hub_penalty_total": round(total_hub_penalty, 6),
            "graph_transfer_count": int(total_transfers),
            "cache_key": str(cache_key or ""),
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
        "prior_cap": 0.0,
        "seeded_chunk_count": 0,
        "boosted_chunk_count": 0,
        "hub_suppressed_chunk_count": 0,
        "graph_prior_total": 0.0,
        "graph_hub_penalty_total": 0.0,
        "graph_transfer_count": 0,
        "cache_key": "",
    }


__all__ = ["apply_query_aware_graph_prior"]
