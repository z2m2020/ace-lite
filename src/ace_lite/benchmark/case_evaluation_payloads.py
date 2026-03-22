"""Payload extraction helpers for benchmark case evaluation."""

from __future__ import annotations

from typing import Any


def extract_stage_latency_ms(*, plan_payload: dict[str, Any], stage: str) -> float:
    observability = (
        plan_payload.get("observability", {})
        if isinstance(plan_payload.get("observability"), dict)
        else {}
    )
    stage_metrics = (
        observability.get("stage_metrics", [])
        if isinstance(observability.get("stage_metrics"), list)
        else []
    )
    target = str(stage or "").strip().lower()
    if not target:
        return 0.0

    for item in stage_metrics:
        if not isinstance(item, dict):
            continue
        name = str(item.get("stage") or "").strip().lower()
        if name != target:
            continue
        return max(0.0, float(item.get("elapsed_ms", 0.0) or 0.0))
    return 0.0


def extract_stage_observability(plan_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    observability = (
        plan_payload.get("observability", {})
        if isinstance(plan_payload.get("observability"), dict)
        else {}
    )
    stage_metrics = (
        observability.get("stage_metrics", [])
        if isinstance(observability.get("stage_metrics"), list)
        else []
    )

    stage_data: dict[str, dict[str, Any]] = {}
    for item in stage_metrics:
        if not isinstance(item, dict):
            continue
        stage = str(item.get("stage") or "").strip().lower()
        if not stage:
            continue
        tags_raw = item.get("tags")
        stage_data[stage] = {
            "elapsed_ms": max(0.0, float(item.get("elapsed_ms", 0.0) or 0.0)),
            "tags": tags_raw if isinstance(tags_raw, dict) else {},
        }
    return stage_data


def coerce_chunk_refs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def count_unique_paths(items: list[dict[str, Any]]) -> int:
    paths: set[str] = set()
    for item in items:
        path = str(item.get("path") or "").strip()
        if path:
            paths.add(path)
    return len(paths)


def compute_chunks_per_file_mean(candidate_chunks: list[dict[str, Any]]) -> float:
    counts: dict[str, int] = {}
    for item in candidate_chunks:
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        counts[path] = counts.get(path, 0) + 1
    if not counts:
        return 0.0
    return float(sum(counts.values())) / float(len(counts))


def safe_ratio(numerator: Any, denominator: Any) -> float:
    numerator_value = max(0.0, float(numerator or 0.0))
    denominator_value = float(denominator or 0.0)
    if denominator_value <= 0.0:
        return 0.0
    return numerator_value / denominator_value


def normalize_source_plan_evidence_summary(value: Any) -> dict[str, float]:
    summary = value if isinstance(value, dict) else {}
    return {
        "direct_count": float(summary.get("direct_count", 0.0) or 0.0),
        "neighbor_context_count": float(
            summary.get("neighbor_context_count", 0.0) or 0.0
        ),
        "hint_only_count": float(summary.get("hint_only_count", 0.0) or 0.0),
        "direct_ratio": float(summary.get("direct_ratio", 0.0) or 0.0),
        "neighbor_context_ratio": float(
            summary.get("neighbor_context_ratio", 0.0) or 0.0
        ),
        "hint_only_ratio": float(summary.get("hint_only_ratio", 0.0) or 0.0),
        "symbol_count": float(summary.get("symbol_count", 0.0) or 0.0),
        "signature_count": float(summary.get("signature_count", 0.0) or 0.0),
        "skeleton_count": float(summary.get("skeleton_count", 0.0) or 0.0),
        "robust_signature_count": float(
            summary.get("robust_signature_count", 0.0) or 0.0
        ),
        "symbol_ratio": float(summary.get("symbol_ratio", 0.0) or 0.0),
        "signature_ratio": float(summary.get("signature_ratio", 0.0) or 0.0),
        "skeleton_ratio": float(summary.get("skeleton_ratio", 0.0) or 0.0),
        "robust_signature_ratio": float(
            summary.get("robust_signature_ratio", 0.0) or 0.0
        ),
    }


__all__ = [
    "coerce_chunk_refs",
    "count_unique_paths",
    "compute_chunks_per_file_mean",
    "extract_stage_latency_ms",
    "extract_stage_observability",
    "normalize_source_plan_evidence_summary",
    "safe_ratio",
]
