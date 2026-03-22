"""Machine-readable grounding semantics for source-plan chunk payloads."""

from __future__ import annotations

from typing import Any


def _chunk_key(item: dict[str, Any]) -> tuple[str, int, int, str]:
    lineno = int(item.get("lineno") or 0)
    end_lineno = int(item.get("end_lineno") or lineno)
    if end_lineno < lineno:
        end_lineno = lineno
    return (
        str(item.get("path") or "").strip(),
        lineno,
        end_lineno,
        str(item.get("qualified_name") or "").strip(),
    )


def _positive_breakdown_value(score_breakdown: dict[str, Any], key: str) -> bool:
    try:
        return float(score_breakdown.get(key, 0.0) or 0.0) > 0.0
    except Exception:
        return False


def _build_granularity_evidence(item: dict[str, Any]) -> list[str]:
    granularity: list[str] = []
    qualified_name = str(item.get("qualified_name") or "").strip()
    kind = str(item.get("kind") or "").strip().lower()

    if qualified_name or kind in {"function", "method", "class", "heading", "section"}:
        granularity.append("symbol")

    if str(item.get("signature") or "").strip():
        granularity.append("signature")

    skeleton = item.get("skeleton")
    if isinstance(skeleton, dict) and skeleton:
        granularity.append("skeleton")

    robust_signature = item.get("robust_signature_summary")
    if isinstance(robust_signature, dict) and (
        robust_signature
        and bool(robust_signature.get("available", True))
    ):
        granularity.append("robust_signature")

    return granularity


def annotate_source_plan_grounding(
    *,
    prioritized_chunks: list[dict[str, Any]],
    direct_candidate_files: list[str],
    direct_candidate_chunks: list[dict[str, Any]],
    focused_files: list[str],
) -> list[dict[str, Any]]:
    """Annotate prioritized chunks with additive grounding metadata."""

    direct_file_set = {
        str(path or "").strip()
        for path in direct_candidate_files
        if str(path or "").strip()
    }
    focused_file_set = {
        str(path or "").strip() for path in focused_files if str(path or "").strip()
    }
    direct_chunk_keys = {
        _chunk_key(item)
        for item in direct_candidate_chunks
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    }

    annotated: list[dict[str, Any]] = []
    for item in prioritized_chunks:
        if not isinstance(item, dict):
            continue

        payload = dict(item)
        path = str(payload.get("path") or "").strip()
        score_breakdown = (
            payload.get("score_breakdown")
            if isinstance(payload.get("score_breakdown"), dict)
            else {}
        )
        key = _chunk_key(payload)

        has_direct_chunk_match = key in direct_chunk_keys
        has_candidate_support = has_direct_chunk_match or _positive_breakdown_value(
            score_breakdown,
            "candidate",
        )
        has_test_hint = _positive_breakdown_value(score_breakdown, "test_signal")

        direct_retrieval = bool(has_candidate_support and path in direct_file_set)
        neighbor_context = bool(path in focused_file_set and path not in direct_file_set)

        if direct_retrieval:
            role = "direct"
        elif has_test_hint and not has_candidate_support:
            role = "hint_only"
        elif neighbor_context:
            role = "neighbor_context"
        elif has_candidate_support:
            role = "direct"
        else:
            role = "hint_only"

        sources: list[str] = []
        if has_candidate_support:
            sources.append("direct_candidate")
        if neighbor_context:
            sources.append("focused_neighbor")
        if has_test_hint:
            sources.append("test_hint")

        granularity = _build_granularity_evidence(payload)
        payload["evidence"] = {
            "role": role,
            "direct_retrieval": bool(direct_retrieval),
            "neighbor_context": bool(neighbor_context),
            "hint_only": role == "hint_only",
            "hint_support": bool(has_test_hint),
            "sources": sources,
            "granularity": granularity,
        }
        annotated.append(payload)

    return annotated


def summarize_source_plan_grounding(chunks: list[dict[str, Any]]) -> dict[str, float]:
    total = max(1, len(chunks))
    direct_count = 0
    neighbor_count = 0
    hint_only_count = 0
    symbol_count = 0
    signature_count = 0
    skeleton_count = 0
    robust_signature_count = 0

    for item in chunks:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            continue
        role = str(evidence.get("role") or "").strip().lower()
        if role == "direct":
            direct_count += 1
        elif role == "neighbor_context":
            neighbor_count += 1
        elif role == "hint_only":
            hint_only_count += 1
        granularity = (
            evidence.get("granularity") if isinstance(evidence.get("granularity"), list) else []
        )
        normalized_granularity = {
            str(value).strip()
            for value in granularity
            if str(value).strip()
        }
        if "symbol" in normalized_granularity:
            symbol_count += 1
        if "signature" in normalized_granularity:
            signature_count += 1
        if "skeleton" in normalized_granularity:
            skeleton_count += 1
        if "robust_signature" in normalized_granularity:
            robust_signature_count += 1

    return {
        "direct_count": float(direct_count),
        "neighbor_context_count": float(neighbor_count),
        "hint_only_count": float(hint_only_count),
        "direct_ratio": float(direct_count) / float(total),
        "neighbor_context_ratio": float(neighbor_count) / float(total),
        "hint_only_ratio": float(hint_only_count) / float(total),
        "symbol_count": float(symbol_count),
        "signature_count": float(signature_count),
        "skeleton_count": float(skeleton_count),
        "robust_signature_count": float(robust_signature_count),
        "symbol_ratio": float(symbol_count) / float(total),
        "signature_ratio": float(signature_count) / float(total),
        "skeleton_ratio": float(skeleton_count) / float(total),
        "robust_signature_ratio": float(robust_signature_count) / float(total),
    }


__all__ = [
    "annotate_source_plan_grounding",
    "summarize_source_plan_grounding",
]
