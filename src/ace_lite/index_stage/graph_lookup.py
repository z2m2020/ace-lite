"""Lookup-style graph signal reranking for index-stage candidates."""

from __future__ import annotations

import math
import re
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def apply_graph_lookup_rerank(
    *,
    candidates: list[dict[str, Any]],
    files_map: dict[str, dict[str, Any]],
    terms: list[str],
    scip_inbound_counts: dict[str, float] | None,
    policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [dict(item) for item in candidates if isinstance(item, dict)]
    if not rows:
        return rows, _empty_payload(enabled=False, reason="no_candidates")

    enabled = bool(policy.get("graph_lookup_enabled", True))
    scip_weight = max(0.0, float(policy.get("graph_lookup_scip_weight", 0.0) or 0.0))
    xref_weight = max(0.0, float(policy.get("graph_lookup_xref_weight", 0.0) or 0.0))
    query_weight = max(
        0.0, float(policy.get("graph_lookup_query_weight", 0.0) or 0.0)
    )
    symbol_weight = max(
        0.0, float(policy.get("graph_lookup_symbol_weight", 0.0) or 0.0)
    )
    import_weight = max(
        0.0, float(policy.get("graph_lookup_import_weight", 0.0) or 0.0)
    )
    coverage_weight = max(
        0.0, float(policy.get("graph_lookup_coverage_weight", 0.0) or 0.0)
    )
    use_log_norm = bool(policy.get("graph_lookup_log_norm", True))
    pool_limit = max(1, int(policy.get("graph_lookup_pool", 24) or 24))
    if (
        (not enabled)
        or (
            scip_weight
            + xref_weight
            + query_weight
            + symbol_weight
            + import_weight
            + coverage_weight
        )
        <= 0.0
    ):
        return rows, _empty_payload(enabled=False, reason="disabled_by_policy")

    pool_size = min(len(rows), pool_limit)
    head = rows[:pool_size]
    tail = rows[pool_size:]

    inbound_raw = (
        scip_inbound_counts if isinstance(scip_inbound_counts, dict) else {}
    )
    inbound_lookup: dict[str, float] = {}
    for path, value in inbound_raw.items():
        normalized_path = _normalize_path(path)
        if not normalized_path:
            continue
        inbound_lookup[normalized_path] = max(
            0.0, float(value if value is not None else 0.0)
        )

    term_set = {
        token
        for token in (str(item or "").strip().lower() for item in terms)
        if token and len(token) >= 3
    }

    candidate_paths: list[str] = []
    inbound_scores: dict[str, float] = {}
    xref_counts: dict[str, float] = {}
    query_hits: dict[str, float] = {}
    symbol_hits: dict[str, float] = {}
    import_hits: dict[str, float] = {}
    coverage_scores: dict[str, float] = {}

    for row in head:
        path = _normalize_path(str(row.get("path") or ""))
        if not path:
            continue
        candidate_paths.append(path)
        inbound_scores[path] = max(0.0, float(inbound_lookup.get(path, 0.0) or 0.0))
        (
            ref_count,
            ref_query_hits,
            reference_matched_terms,
        ) = _collect_reference_signals(
            entry=files_map.get(path, {}),
            terms=term_set,
        )
        symbol_hit_count, symbol_matched_terms = _collect_symbol_signals(
            entry=files_map.get(path, {}),
            terms=term_set,
        )
        import_hit_count, import_matched_terms = _collect_import_signals(
            entry=files_map.get(path, {}),
            terms=term_set,
        )
        xref_counts[path] = float(ref_count)
        query_hits[path] = float(ref_query_hits)
        symbol_hits[path] = float(symbol_hit_count)
        import_hits[path] = float(import_hit_count)
        if term_set:
            matched_terms = set(reference_matched_terms)
            matched_terms.update(symbol_matched_terms)
            matched_terms.update(import_matched_terms)
            coverage_scores[path] = float(len(matched_terms)) / float(len(term_set))
        else:
            coverage_scores[path] = 0.0

    max_inbound = max(inbound_scores.values(), default=0.0)
    max_xref = max(xref_counts.values(), default=0.0)
    max_query = max(query_hits.values(), default=0.0)
    max_symbol_hits = max(symbol_hits.values(), default=0.0)
    max_import_hits = max(import_hits.values(), default=0.0)
    max_coverage = max(coverage_scores.values(), default=0.0)

    boosted_count = 0
    for row in head:
        path = _normalize_path(str(row.get("path") or ""))
        if not path:
            continue
        inbound_norm = _normalize_signal(
            value=float(inbound_scores.get(path, 0.0)),
            max_value=max_inbound,
            use_log=use_log_norm,
        )
        xref_norm = _normalize_signal(
            value=float(xref_counts.get(path, 0.0)),
            max_value=max_xref,
            use_log=use_log_norm,
        )
        query_norm = _normalize_signal(
            value=float(query_hits.get(path, 0.0)),
            max_value=max_query,
            use_log=use_log_norm,
        )
        symbol_norm = _normalize_signal(
            value=float(symbol_hits.get(path, 0.0)),
            max_value=max_symbol_hits,
            use_log=use_log_norm,
        )
        import_norm = _normalize_signal(
            value=float(import_hits.get(path, 0.0)),
            max_value=max_import_hits,
            use_log=use_log_norm,
        )
        coverage_norm = _normalize_signal(
            value=float(coverage_scores.get(path, 0.0)),
            max_value=max_coverage,
            use_log=False,
        )
        boost = (
            scip_weight * inbound_norm
            + xref_weight * xref_norm
            + query_weight * query_norm
            + symbol_weight * symbol_norm
            + import_weight * import_norm
            + coverage_weight * coverage_norm
        )
        if boost <= 0.0:
            continue
        row["score"] = round(float(row.get("score", 0.0) or 0.0) + boost, 6)
        breakdown = row.get("score_breakdown")
        if not isinstance(breakdown, dict):
            breakdown = {}
            row["score_breakdown"] = breakdown
        breakdown["graph_lookup"] = round(
            float(breakdown.get("graph_lookup", 0.0) or 0.0) + boost, 6
        )
        boosted_count += 1

    head.sort(
        key=lambda item: (
            -float(item.get("score", 0.0) or 0.0),
            str(item.get("path") or ""),
        )
    )
    rows = head + tail

    return rows, {
        "enabled": True,
        "reason": "ok",
        "boosted_count": boosted_count,
        "weights": {
            "scip": scip_weight,
            "xref": xref_weight,
            "query_xref": query_weight,
            "symbol": symbol_weight,
            "import": import_weight,
            "coverage": coverage_weight,
        },
        "normalization": "log1p" if use_log_norm else "linear",
        "query_terms_count": len(term_set),
        "candidate_count": len(rows),
        "pool_size": pool_size,
        "scip_signal_paths": sum(
            1 for path in candidate_paths if float(inbound_scores.get(path, 0.0)) > 0.0
        ),
        "xref_signal_paths": sum(
            1 for path in candidate_paths if float(xref_counts.get(path, 0.0)) > 0.0
        ),
        "query_hit_paths": sum(
            1 for path in candidate_paths if float(query_hits.get(path, 0.0)) > 0.0
        ),
        "symbol_hit_paths": sum(
            1 for path in candidate_paths if float(symbol_hits.get(path, 0.0)) > 0.0
        ),
        "import_hit_paths": sum(
            1 for path in candidate_paths if float(import_hits.get(path, 0.0)) > 0.0
        ),
        "coverage_hit_paths": sum(
            1 for path in candidate_paths if float(coverage_scores.get(path, 0.0)) > 0.0
        ),
        "max_inbound": float(max_inbound),
        "max_xref_count": float(max_xref),
        "max_query_hits": float(max_query),
        "max_symbol_hits": float(max_symbol_hits),
        "max_import_hits": float(max_import_hits),
        "max_query_coverage": float(max_coverage),
    }


def _collect_reference_signals(
    *,
    entry: dict[str, Any] | None,
    terms: set[str],
) -> tuple[int, int, set[str]]:
    if not isinstance(entry, dict):
        return 0, 0, set()
    references = entry.get("references")
    if not isinstance(references, list):
        return 0, 0, set()

    count = 0
    query_hits = 0
    matched_terms: set[str] = set()
    for item in references[:128]:
        if not isinstance(item, dict):
            continue
        count += 1
        label = str(item.get("qualified_name") or item.get("name") or "").lower()
        if not label:
            continue
        tokens = set(_TOKEN_RE.findall(label))
        if terms and tokens.intersection(terms):
            query_hits += 1
            matched_terms.update(tokens.intersection(terms))
    return count, query_hits, matched_terms


def _collect_symbol_signals(
    *,
    entry: dict[str, Any] | None,
    terms: set[str],
) -> tuple[int, set[str]]:
    if not terms or not isinstance(entry, dict):
        return 0, set()
    symbols = entry.get("symbols")
    if not isinstance(symbols, list):
        return 0, set()

    hit_count = 0
    matched_terms: set[str] = set()
    for item in symbols[:128]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("qualified_name") or item.get("name") or "").lower()
        if not label:
            continue
        tokens = set(_TOKEN_RE.findall(label))
        overlap = tokens.intersection(terms)
        if overlap:
            hit_count += 1
            matched_terms.update(overlap)
    return hit_count, matched_terms


def _collect_import_signals(
    *,
    entry: dict[str, Any] | None,
    terms: set[str],
) -> tuple[int, set[str]]:
    if not terms or not isinstance(entry, dict):
        return 0, set()
    imports = entry.get("imports")
    if not isinstance(imports, list):
        return 0, set()

    hit_count = 0
    matched_terms: set[str] = set()
    for item in imports[:96]:
        if not isinstance(item, dict):
            continue
        parts = (
            str(item.get("module") or ""),
            str(item.get("name") or ""),
        )
        label = ".".join(part for part in parts if part).lower()
        if not label:
            continue
        tokens = set(_TOKEN_RE.findall(label))
        overlap = tokens.intersection(terms)
        if overlap:
            hit_count += 1
            matched_terms.update(overlap)
    return hit_count, matched_terms


def _normalize_signal(*, value: float, max_value: float, use_log: bool) -> float:
    normalized_value = max(0.0, float(value))
    normalized_max = max(0.0, float(max_value))
    if normalized_max <= 0.0:
        return 0.0
    if not use_log:
        return normalized_value / normalized_max
    denominator = math.log1p(normalized_max)
    if denominator <= 0.0:
        return 0.0
    return math.log1p(normalized_value) / denominator


def _normalize_path(value: str) -> str:
    path = str(value or "").strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def _empty_payload(*, enabled: bool, reason: str) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "reason": reason,
        "boosted_count": 0,
        "weights": {
            "scip": 0.0,
            "xref": 0.0,
            "query_xref": 0.0,
            "symbol": 0.0,
            "import": 0.0,
            "coverage": 0.0,
        },
        "normalization": "linear",
        "query_terms_count": 0,
        "candidate_count": 0,
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
    }


__all__ = ["apply_graph_lookup_rerank"]
