"""Chunk ranking utilities for the source_plan stage."""

from __future__ import annotations

from typing import Any

from ace_lite.chunking.types import (
    CONTEXTUAL_CHUNKING_SIDECAR_KEY,
    RETRIEVAL_CONTEXT_SIDECAR_KEY,
)


def _chunk_granularity_signals(item: dict[str, Any]) -> tuple[int, int, int, int, int]:
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    evidence_granularity = (
        evidence.get("granularity") if isinstance(evidence.get("granularity"), list) else []
    )
    granularity = {
        str(value).strip()
        for value in evidence_granularity
        if str(value).strip()
    }

    qualified_name = str(item.get("qualified_name") or "").strip()
    kind = str(item.get("kind") or "").strip().lower()
    if qualified_name or kind in {"function", "method", "class", "heading", "section"}:
        granularity.add("symbol")
    if str(item.get("signature") or "").strip():
        granularity.add("signature")
    if isinstance(item.get("skeleton"), dict) and item.get("skeleton"):
        granularity.add("skeleton")
    robust_signature = (
        item.get("robust_signature_summary")
        if isinstance(item.get("robust_signature_summary"), dict)
        else {}
    )
    if robust_signature and bool(robust_signature.get("available", True)):
        granularity.add("robust_signature")

    return (
        len(granularity),
        1 if "skeleton" in granularity else 0,
        1 if "signature" in granularity else 0,
        1 if "robust_signature" in granularity else 0,
        1 if "symbol" in granularity else 0,
    )


def _chunk_granularity_bias(item: dict[str, Any]) -> float:
    """Return a tiny bias so richer chunks win only within a narrow score margin."""

    signal_count, skeleton, signature, robust_signature, symbol = (
        _chunk_granularity_signals(item)
    )
    return round(
        (signal_count * 0.01)
        + (skeleton * 0.004)
        + (signature * 0.002)
        + (robust_signature * 0.001)
        + (symbol * 0.0005),
        6,
    )


def rank_source_plan_chunks(
    *,
    suspicious_chunks: list[dict[str, Any]],
    candidate_chunks: list[dict[str, Any]],
    test_signal_weight: float = 1.0,
) -> list[dict[str, Any]]:
    """Merge candidate chunks with test signal chunks and rank them.

    The merge key is (path, lineno, end_lineno, qualified_name). Scores from
    both sources are accumulated into a combined score with breakdown.

    Args:
        suspicious_chunks: Chunk refs from test signals (SBFL/coverage/stacktrace).
        candidate_chunks: Chunk refs emitted by index stage.
        test_signal_weight: Multiplicative weight applied to suspicious chunk scores.

    Returns:
        Ranked merged chunk list.
    """
    merged: dict[tuple[str, int, int, str], dict[str, Any]] = {}
    normalized_test_weight = max(0.0, float(test_signal_weight))

    def _coerce_breakdown(value: Any) -> dict[str, float]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, float] = {}
        for raw_key, raw_score in value.items():
            key = str(raw_key or "").strip()
            if not key:
                continue
            try:
                normalized[key] = float(raw_score or 0.0)
            except Exception:
                continue
        return normalized

    def merge_item(item: dict[str, Any], *, source_key: str, weight: float) -> None:
        if not isinstance(item, dict):
            return

        path = str(item.get("path") or "").strip()
        if not path:
            return

        try:
            lineno = int(item.get("lineno") or 0)
            end_lineno = int(item.get("end_lineno") or lineno)
        except Exception:
            return

        if lineno <= 0:
            return
        if end_lineno < lineno:
            end_lineno = lineno

        qualified_name = str(item.get("qualified_name") or "").strip()
        key = (path, lineno, end_lineno, qualified_name)

        def _copy_contract_fields(target: dict[str, Any], source: dict[str, Any]) -> None:
            for field in (
                "disclosure",
                "disclosure_requested",
                "disclosure_fallback_reason",
                "skeleton",
                "robust_signature_summary",
                RETRIEVAL_CONTEXT_SIDECAR_KEY,
                CONTEXTUAL_CHUNKING_SIDECAR_KEY,
            ):
                value = source.get(field)
                if field == "skeleton":
                    if isinstance(value, dict):
                        target[field] = dict(value)
                elif field == "robust_signature_summary":
                    if isinstance(value, dict):
                        target[field] = dict(value)
                elif field == CONTEXTUAL_CHUNKING_SIDECAR_KEY:
                    if isinstance(value, dict):
                        target[field] = dict(value)
                elif field == RETRIEVAL_CONTEXT_SIDECAR_KEY:
                    if isinstance(value, str) and value.strip():
                        target[field] = value
                elif isinstance(value, str) and value.strip():
                    target[field] = value

        entry = merged.get(key)
        if entry is None:
            preserved_breakdown = _coerce_breakdown(item.get("score_breakdown"))
            entry = {
                "path": path,
                "qualified_name": qualified_name,
                "kind": str(item.get("kind") or "").strip(),
                "lineno": lineno,
                "end_lineno": end_lineno,
                "score": 0.0,
                "score_breakdown": {
                    **preserved_breakdown,
                    "candidate": 0.0,
                    "test_signal": 0.0,
                },
            }
            signature = str(item.get("signature") or "").strip()
            if signature:
                entry["signature"] = signature
            _copy_contract_fields(entry, item)
            merged[key] = entry
        else:
            if not str(entry.get("kind") or "").strip():
                entry["kind"] = str(item.get("kind") or "").strip()
            signature = str(item.get("signature") or "").strip()
            if signature and not str(entry.get("signature") or "").strip():
                entry["signature"] = signature
            _copy_contract_fields(entry, item)
            breakdown = entry.get("score_breakdown")
            if isinstance(breakdown, dict):
                for name, value in _coerce_breakdown(item.get("score_breakdown")).items():
                    if name in {"candidate", "test_signal"}:
                        continue
                    breakdown[name] = max(float(breakdown.get(name, 0.0) or 0.0), value)

        try:
            raw_score = max(0.0, float(item.get("score") or 0.0))
        except Exception:
            raw_score = 0.0

        contribution = raw_score * max(0.0, float(weight))
        if contribution <= 0.0:
            return

        entry["score"] = round(
            float(entry.get("score") or 0.0) + contribution,
            6,
        )

        breakdown = entry.get("score_breakdown")
        if isinstance(breakdown, dict):
            breakdown[source_key] = round(
                float(breakdown.get(source_key, 0.0) or 0.0) + contribution,
                6,
            )

    for item in candidate_chunks:
        if isinstance(item, dict):
            merge_item(item, source_key="candidate", weight=1.0)

    for item in suspicious_chunks:
        if isinstance(item, dict):
            merge_item(item, source_key="test_signal", weight=normalized_test_weight)

    ranked = [item for item in merged.values() if float(item.get("score") or 0.0) > 0.0]
    ranked.sort(
        key=lambda item: (
            -(float(item.get("score") or 0.0) + _chunk_granularity_bias(item)),
            tuple(-value for value in _chunk_granularity_signals(item)),
            str(item.get("path") or ""),
            int(item.get("lineno") or 0),
            str(item.get("qualified_name") or ""),
        )
    )
    return ranked


def pack_source_plan_chunks(
    *,
    prioritized_chunks: list[dict[str, Any]],
    focused_files: list[str],
    chunk_top_k: int,
    graph_closure_preference_enabled: bool = True,
    return_metadata: bool = False,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pack prioritized chunks to preserve file coverage under a tight limit.

    The source-plan stage already receives score-ranked chunks from the index stage.
    This helper keeps that ranking, but promotes the first chunk from each focused file
    before taking additional chunks from the same file. The goal is to improve
    multi-file context sufficiency without introducing new budget logic or
    nondeterministic packing heuristics.
    """

    limit = max(1, int(chunk_top_k))
    enabled = bool(graph_closure_preference_enabled)
    empty_metadata = {
        "graph_closure_preference_enabled": enabled,
        "graph_closure_bonus_candidate_count": 0,
        "graph_closure_preferred_count": 0,
        "granularity_preferred_count": 0,
        "focused_file_promoted_count": 0,
        "packed_path_count": 0,
        "reason": "no_candidates",
    }
    if not isinstance(prioritized_chunks, list) or not prioritized_chunks:
        if return_metadata:
            return [], empty_metadata
        return []

    def chunk_key(item: dict[str, Any]) -> tuple[str, int, int, str]:
        lineno = int(item.get("lineno") or 0)
        end_lineno = int(item.get("end_lineno") or lineno)
        return (
            str(item.get("path") or "").strip(),
            lineno,
            end_lineno,
            str(item.get("qualified_name") or "").strip(),
        )

    focused_rank: dict[str, int] = {}
    for path in focused_files:
        normalized = str(path or "").strip()
        if not normalized or normalized in focused_rank:
            continue
        focused_rank[normalized] = len(focused_rank)

    def closure_bonus(item: dict[str, Any]) -> float:
        breakdown = (
            item.get("score_breakdown")
            if isinstance(item.get("score_breakdown"), dict)
            else {}
        )
        return max(0.0, float(breakdown.get("graph_closure_bonus", 0.0) or 0.0))

    graph_closure_bonus_candidate_count = sum(
        1
        for item in prioritized_chunks
        if isinstance(item, dict) and closure_bonus(item) > 0.0
    )
    packed: list[dict[str, Any]] = []
    used: set[tuple[str, int, int, str]] = set()
    packed_paths: set[str] = set()
    graph_closure_preferred_count = 0
    granularity_preferred_count = 0
    focused_file_promoted_count = 0

    while len(packed) < limit:
        best_item: dict[str, Any] | None = None
        best_sort_key: tuple[float, float, int, float, tuple[int, int, int, int, int], str, int, str] | None = None
        best_closure_pack = False
        best_focused_uncovered = False
        best_priority_identity: tuple[float, float, int] | None = None
        for item in prioritized_chunks:
            if not isinstance(item, dict):
                continue
            key = chunk_key(item)
            if key in used:
                continue
            path = str(item.get("path") or "").strip()
            if not path:
                continue
            closure_pack = (
                1.0
                if enabled and packed and path in packed_paths and closure_bonus(item) > 0.0
                else 0.0
            )
            focused_uncovered = (
                1.0 if path in focused_rank and path not in packed_paths else 0.0
            )
            granularity_signals = _chunk_granularity_signals(item)
            sort_key = (
                -closure_pack,
                -focused_uncovered,
                focused_rank.get(path, len(focused_rank) + 1024),
                -(float(item.get("score") or 0.0) + _chunk_granularity_bias(item)),
                tuple(-value for value in granularity_signals),
                path,
                int(item.get("lineno") or 0),
                str(item.get("qualified_name") or ""),
            )
            if best_sort_key is None or sort_key < best_sort_key:
                best_sort_key = sort_key
                best_item = item
                best_closure_pack = closure_pack > 0.0
                best_focused_uncovered = focused_uncovered > 0.0
                best_priority_identity = (
                    closure_pack,
                    focused_uncovered,
                    focused_rank.get(path, len(focused_rank) + 1024),
                )
        if best_item is None:
            break
        if (
            best_priority_identity is not None
            and _chunk_granularity_bias(best_item) > 0.0
        ):
            best_raw_score = float(best_item.get("score") or 0.0)
            best_adjusted_score = best_raw_score + _chunk_granularity_bias(best_item)
            for candidate in prioritized_chunks:
                if not isinstance(candidate, dict):
                    continue
                candidate_key = chunk_key(candidate)
                if candidate_key in used or candidate is best_item:
                    continue
                candidate_path = str(candidate.get("path") or "").strip()
                if not candidate_path:
                    continue
                candidate_priority_identity = (
                    1.0
                    if enabled
                    and packed
                    and candidate_path in packed_paths
                    and closure_bonus(candidate) > 0.0
                    else 0.0,
                    1.0
                    if candidate_path in focused_rank and candidate_path not in packed_paths
                    else 0.0,
                    focused_rank.get(candidate_path, len(focused_rank) + 1024),
                )
                candidate_raw_score = float(candidate.get("score") or 0.0)
                candidate_adjusted_score = (
                    candidate_raw_score + _chunk_granularity_bias(candidate)
                )
                if (
                    candidate_priority_identity == best_priority_identity
                    and candidate_raw_score > best_raw_score
                    and candidate_adjusted_score < best_adjusted_score
                ):
                    granularity_preferred_count += 1
                    break
        key = chunk_key(best_item)
        packed.append(best_item)
        used.add(key)
        packed_paths.add(str(best_item.get("path") or "").strip())
        if best_closure_pack:
            graph_closure_preferred_count += 1
        elif best_focused_uncovered:
            focused_file_promoted_count += 1

    metadata = {
        "graph_closure_preference_enabled": enabled,
        "graph_closure_bonus_candidate_count": int(graph_closure_bonus_candidate_count),
        "graph_closure_preferred_count": int(graph_closure_preferred_count),
        "granularity_preferred_count": int(granularity_preferred_count),
        "focused_file_promoted_count": int(focused_file_promoted_count),
        "packed_path_count": int(len(packed_paths)),
        "reason": (
            "disabled_by_policy"
            if not enabled
            else (
                "no_graph_closure_bonus_candidates"
                if graph_closure_bonus_candidate_count <= 0
                else "ok"
            )
        ),
    }
    if return_metadata:
        return packed, metadata
    return packed


__all__ = ["pack_source_plan_chunks", "rank_source_plan_chunks"]
