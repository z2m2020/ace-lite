from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from ace_lite.index_stage.cochange import apply_cochange_neighbors
from ace_lite.index_stage.graph_lookup import apply_graph_lookup_rerank
from ace_lite.index_stage.repo_paths import resolve_repo_relative_path
from ace_lite.index_stage.scip_boost import apply_scip_boost
from ace_lite.scip import load_scip_edges

_GRAPH_LOOKUP_GUARD_REASONS = {
    "candidate_count_guarded",
    "query_terms_too_few",
    "query_terms_too_many",
}

_GRAPH_LOOKUP_DEFAULT_WEIGHTS = {
    "scip": 0.0,
    "xref": 0.0,
    "query_xref": 0.0,
    "symbol": 0.0,
    "import": 0.0,
    "coverage": 0.0,
}


def _build_default_graph_lookup_payload(*, candidate_count: int) -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": "disabled",
        "guarded": False,
        "boosted_count": 0,
        "weights": dict(_GRAPH_LOOKUP_DEFAULT_WEIGHTS),
        "query_terms_count": 0,
        "candidate_count": int(candidate_count),
        "pool_size": 0,
        "scip_signal_paths": 0,
        "xref_signal_paths": 0,
        "query_hit_paths": 0,
        "symbol_hit_paths": 0,
        "import_hit_paths": 0,
        "coverage_hit_paths": 0,
        "max_inbound": 0.0,
        "max_xref_count": 0.0,
        "max_query_hits": 0.0,
        "max_symbol_hits": 0.0,
        "max_import_hits": 0.0,
        "max_query_coverage": 0.0,
        "guard_max_candidates": 0,
        "guard_min_query_terms": 0,
        "guard_max_query_terms": 0,
    }


def _merge_graph_lookup_payload(
    base_payload: dict[str, Any],
    applied_payload: dict[str, Any],
) -> dict[str, Any]:
    base_weights_value = base_payload.get("weights")
    base_weights = dict(base_weights_value) if isinstance(base_weights_value, dict) else {}
    applied_weights_value = applied_payload.get("weights")
    applied_weights = (
        dict(applied_weights_value)
        if isinstance(applied_weights_value, dict)
        else {}
    )
    merged = {
        **base_payload,
        **applied_payload,
    }
    merged["weights"] = {
        **_GRAPH_LOOKUP_DEFAULT_WEIGHTS,
        **base_weights,
        **applied_weights,
    }
    return merged


@dataclass(frozen=True, slots=True)
class StructuralRerankResult:
    candidates: list[dict[str, Any]]
    cochange_payload: dict[str, Any]
    scip_payload: dict[str, Any]
    graph_lookup_payload: dict[str, Any]


def apply_structural_rerank(
    *,
    root: str,
    files_map: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    memory_paths: list[str],
    terms: list[str],
    policy: dict[str, Any],
    cochange_enabled: bool,
    cochange_cache_path: str,
    cochange_lookback_commits: int,
    cochange_half_life_days: float,
    cochange_neighbor_cap: int,
    top_k_files: int,
    cochange_top_neighbors: int,
    cochange_boost_weight: float,
    cochange_min_neighbor_score: float,
    cochange_max_boost: float,
    scip_enabled: bool,
    scip_index_path: str,
    scip_provider: str,
    scip_generate_fallback: bool,
    scip_base_weight: float = 0.5,
    mark_timing: Callable[[str, float], None],
    perf_counter_fn: Callable[[], float] = perf_counter,
    cochange_fn: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]] = apply_cochange_neighbors,
    scip_fn: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]] = apply_scip_boost,
    graph_lookup_fn: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]] = apply_graph_lookup_rerank,
    load_graph_fn: Callable[..., dict[str, Any]] = load_scip_edges,
) -> StructuralRerankResult:
    cochange_payload: dict[str, Any] = {
        "enabled": False,
        "cache_hit": False,
        "cache_mode": "disabled",
        "neighbors_added": 0,
        "boost_applied": 0,
        "lookback_commits": int(cochange_lookback_commits),
        "half_life_days": float(cochange_half_life_days),
    }
    timing_started = perf_counter_fn()
    if cochange_enabled and bool(policy.get("cochange_enabled", True)) and files_map:
        cache_path = resolve_repo_relative_path(
            root=root, configured_path=cochange_cache_path
        )
        candidates, cochange_payload = cochange_fn(
            repo_root=root,
            cache_path=cache_path,
            files_map=files_map,
            candidates=candidates,
            memory_paths=memory_paths,
            policy=policy,
            lookback_commits=int(cochange_lookback_commits),
            half_life_days=float(cochange_half_life_days),
            neighbor_cap=int(cochange_neighbor_cap),
            top_k_files=int(top_k_files),
            top_neighbors=int(cochange_top_neighbors),
            boost_weight=float(cochange_boost_weight),
            min_neighbor_score=float(cochange_min_neighbor_score),
            max_boost=float(cochange_max_boost),
        )
    elif cochange_enabled and files_map:
        cochange_payload["cache_mode"] = "policy_disabled"
        cochange_payload["enabled"] = False
    mark_timing("cochange", timing_started)

    scip_payload: dict[str, Any] = {
        "enabled": bool(scip_enabled),
        "loaded": False,
        "edge_count": 0,
        "boost_applied": 0,
        "path": "",
        "provider": str(scip_provider),
        "generate_fallback": bool(scip_generate_fallback),
        "fallback_generated": False,
        "weights": {"base_weight": float(scip_base_weight)},
    }
    resolved_scip_index_path = resolve_repo_relative_path(
        root=root, configured_path=scip_index_path
    )
    timing_started = perf_counter_fn()
    if scip_enabled and files_map:
        candidates, scip_payload = scip_fn(
            index_path=resolved_scip_index_path,
            provider=str(scip_provider),
            generate_fallback=bool(scip_generate_fallback),
            files_map=files_map,
            candidates=candidates,
            policy=policy,
            scoring_config={"base_weight": float(scip_base_weight)},
        )
    mark_timing("scip_boost", timing_started)

    graph_lookup_payload = _build_default_graph_lookup_payload(
        candidate_count=len(candidates)
    )
    scip_inbound_counts: dict[str, float] = {}
    timing_started = perf_counter_fn()
    graph_lookup_max_candidates = max(
        1, int(policy.get("graph_lookup_max_candidates", 64) or 64)
    )
    graph_lookup_min_query_terms = max(
        0, int(policy.get("graph_lookup_min_query_terms", 0) or 0)
    )
    graph_lookup_max_query_terms = max(
        graph_lookup_min_query_terms,
        int(policy.get("graph_lookup_max_query_terms", 64) or 64),
    )
    graph_lookup_payload["guard_max_candidates"] = graph_lookup_max_candidates
    graph_lookup_payload["guard_min_query_terms"] = graph_lookup_min_query_terms
    graph_lookup_payload["guard_max_query_terms"] = graph_lookup_max_query_terms
    graph_lookup_enabled = bool(policy.get("graph_lookup_enabled", True))
    if not graph_lookup_enabled:
        graph_lookup_payload["reason"] = "disabled_by_policy"
    elif not files_map:
        graph_lookup_payload["reason"] = "no_files_map"
    elif len(candidates) > graph_lookup_max_candidates:
        graph_lookup_payload["reason"] = "candidate_count_guarded"
    elif len(terms) < graph_lookup_min_query_terms:
        graph_lookup_payload["reason"] = "query_terms_too_few"
    elif len(terms) > graph_lookup_max_query_terms:
        graph_lookup_payload["reason"] = "query_terms_too_many"
    else:
        if bool(scip_payload.get("loaded", False)):
            loaded_graph = load_graph_fn(
                resolved_scip_index_path,
                provider=str(scip_payload.get("provider") or scip_provider),
            )
            inbound_raw = (
                loaded_graph.get("inbound_counts")
                if isinstance(loaded_graph, dict)
                else {}
            )
            if isinstance(inbound_raw, dict):
                scip_inbound_counts = {
                    str(path): max(0.0, float(value or 0.0))
                    for path, value in inbound_raw.items()
                    if str(path).strip()
                }
        candidates, applied_graph_lookup_payload = graph_lookup_fn(
            candidates=candidates,
            files_map=files_map,
            terms=terms,
            scip_inbound_counts=scip_inbound_counts,
            policy=policy,
        )
        graph_lookup_payload = _merge_graph_lookup_payload(
            graph_lookup_payload,
            applied_graph_lookup_payload,
        )
    graph_lookup_payload["guarded"] = (
        str(graph_lookup_payload.get("reason", "") or "").strip()
        in _GRAPH_LOOKUP_GUARD_REASONS
    )
    mark_timing("graph_lookup", timing_started)

    return StructuralRerankResult(
        candidates=list(candidates),
        cochange_payload=cochange_payload,
        scip_payload=scip_payload,
        graph_lookup_payload=graph_lookup_payload,
    )
