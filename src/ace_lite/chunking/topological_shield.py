"""Report-only topological shield diagnostics for chunk diversity."""

from __future__ import annotations

from typing import Any

from ace_lite.chunking.graph_prior import _chunk_symbol_id, _get_graph_context


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


def _has_graph_attestation(row: dict[str, Any]) -> bool:
    breakdown = row.get("score_breakdown")
    if not isinstance(breakdown, dict):
        return False
    graph_prior = max(0.0, float(breakdown.get("graph_prior", 0.0) or 0.0))
    graph_seeded = max(0.0, float(breakdown.get("graph_seeded", 0.0) or 0.0))
    graph_transfer_count = max(
        0.0, float(breakdown.get("graph_transfer_count", 0.0) or 0.0)
    )
    return graph_prior > 0.0 or graph_seeded > 0.0 or graph_transfer_count > 0.0


def compute_topological_shield(
    *,
    candidate: dict[str, Any],
    selected: list[dict[str, Any]],
    files_map: dict[str, dict[str, Any]],
    cache_key: str,
    base_penalty: float,
    base_score: float,
    enabled: bool,
    mode: str,
    max_attenuation: float,
    shared_parent_attenuation: float,
    adjacency_attenuation: float,
) -> dict[str, Any]:
    """Compute additive report-only topological shield diagnostics."""

    normalized_mode = str(mode or "off").strip().lower() or "off"
    report_only = normalized_mode != "enforce"
    payload: dict[str, Any] = {
        "enabled": bool(enabled),
        "mode": normalized_mode,
        "report_only": bool(report_only),
        "reason": "disabled",
        "base_penalty": round(max(0.0, float(base_penalty)), 6),
        "attenuation": 0.0,
        "penalty_delta": 0.0,
        "adjusted_penalty": round(max(0.0, float(base_penalty)), 6),
        "adjusted_score": round(max(0.0, float(base_score - base_penalty)), 6),
        "evidence_count": 0,
        "adjacency_evidence_count": 0,
        "shared_parent_evidence_count": 0,
        "graph_attested": False,
    }
    if not enabled or normalized_mode == "off":
        return payload
    if not selected:
        payload["reason"] = "no_selected_chunks"
        return payload

    adjacency: dict[str, list[str]] = {}
    if isinstance(files_map, dict) and files_map:
        try:
            context = _get_graph_context(files_map=files_map, cache_key=cache_key)
        except Exception:
            context = {}
        resolved_adjacency = context.get("adjacency", {})
        if isinstance(resolved_adjacency, dict):
            adjacency = resolved_adjacency

    candidate_id = _chunk_symbol_id(candidate)
    candidate_parent = _parent_namespace(str(candidate.get("qualified_name") or ""))
    candidate_graph_attested = _has_graph_attestation(candidate)

    pair_weights: list[float] = []
    adjacency_evidence_count = 0
    shared_parent_evidence_count = 0
    graph_attested = candidate_graph_attested

    for item in selected:
        if not isinstance(item, dict):
            continue
        pair_weight = 0.0
        selected_parent = _parent_namespace(str(item.get("qualified_name") or ""))
        selected_id = _chunk_symbol_id(item)
        pair_adjacency = False
        if candidate_id and selected_id:
            candidate_neighbors = adjacency.get(candidate_id, [])
            selected_neighbors = adjacency.get(selected_id, [])
            pair_adjacency = (
                isinstance(candidate_neighbors, list)
                and selected_id in candidate_neighbors
            ) or (
                isinstance(selected_neighbors, list)
                and candidate_id in selected_neighbors
            )
        if pair_adjacency:
            adjacency_evidence_count += 1
            pair_weight = max(pair_weight, max(0.0, float(adjacency_attenuation)))

        pair_shared_parent = bool(candidate_parent and candidate_parent == selected_parent)
        if pair_shared_parent:
            shared_parent_evidence_count += 1
            pair_weight = max(
                pair_weight, max(0.0, float(shared_parent_attenuation))
            )

        if pair_weight <= 0.0:
            continue
        if candidate_graph_attested or _has_graph_attestation(item):
            graph_attested = True
            pair_weight = min(float(max_attenuation), pair_weight + 0.1)
        pair_weights.append(pair_weight)

    evidence_count = adjacency_evidence_count + shared_parent_evidence_count
    payload.update(
        {
            "reason": "ok" if evidence_count > 0 else "no_structural_evidence",
            "evidence_count": int(evidence_count),
            "adjacency_evidence_count": int(adjacency_evidence_count),
            "shared_parent_evidence_count": int(shared_parent_evidence_count),
            "graph_attested": bool(graph_attested),
        }
    )
    if evidence_count <= 0:
        return payload

    attenuation = min(float(max_attenuation), sum(pair_weights))
    base_penalty = max(0.0, float(base_penalty))
    penalty_delta = min(base_penalty, base_penalty * attenuation)
    adjusted_penalty = max(0.0, base_penalty - penalty_delta)
    adjusted_score = max(0.0, float(base_score) - adjusted_penalty)
    payload.update(
        {
            "attenuation": round(float(attenuation), 6),
            "penalty_delta": round(float(penalty_delta), 6),
            "adjusted_penalty": round(float(adjusted_penalty), 6),
            "adjusted_score": round(float(adjusted_score), 6),
        }
    )
    return payload


__all__ = ["compute_topological_shield"]
