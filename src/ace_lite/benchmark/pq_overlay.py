from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ace_lite.benchmark.problem_surface_reader import PQ_SURFACE_SPECS
from ace_lite.plan_payload_view import resolve_confidence_summary


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _round(value: float) -> float:
    return round(float(value), 6)


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return _round(float(numerator) / float(denominator))


def _coerce_confidence_summary(summary: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload = _dict(summary)
    extracted_count = max(0, _int(payload.get("extracted_count", 0)))
    inferred_count = max(0, _int(payload.get("inferred_count", 0)))
    ambiguous_count = max(0, _int(payload.get("ambiguous_count", 0)))
    unknown_count = max(0, _int(payload.get("unknown_count", 0)))
    total_candidates = max(
        0,
        _int(
            payload.get("total_candidates", payload.get("total_count")),
            extracted_count + inferred_count + ambiguous_count + unknown_count,
        ),
    )
    if total_candidates <= 0:
        total_candidates = extracted_count + inferred_count + ambiguous_count + unknown_count

    low_confidence_chunks = [
        str(item).strip()
        for item in _list(payload.get("low_confidence_chunks"))
        if str(item).strip()
    ]

    return {
        "extracted_count": extracted_count,
        "inferred_count": inferred_count,
        "ambiguous_count": ambiguous_count,
        "unknown_count": unknown_count,
        "total_candidates": total_candidates,
        "low_confidence_chunks": low_confidence_chunks,
    }


def _aggregate_confidence_summaries(
    summaries: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not summaries:
        return None

    extracted_count = 0
    inferred_count = 0
    ambiguous_count = 0
    unknown_count = 0
    total_candidates = 0
    low_confidence_chunks: list[str] = []
    seen_chunks: set[str] = set()

    for summary in summaries:
        normalized = _coerce_confidence_summary(summary)
        extracted_count += normalized["extracted_count"]
        inferred_count += normalized["inferred_count"]
        ambiguous_count += normalized["ambiguous_count"]
        unknown_count += normalized["unknown_count"]
        total_candidates += normalized["total_candidates"]
        for chunk_id in normalized["low_confidence_chunks"]:
            if chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk_id)
            low_confidence_chunks.append(chunk_id)

    if total_candidates <= 0:
        return None

    return {
        "extracted_count": extracted_count,
        "inferred_count": inferred_count,
        "ambiguous_count": ambiguous_count,
        "unknown_count": unknown_count,
        "total_candidates": total_candidates,
        "low_confidence_chunks": low_confidence_chunks,
    }


def _build_confidence_breakdown(summary: dict[str, Any]) -> dict[str, Any]:
    total_candidates = max(0, _int(summary.get("total_candidates", 0)))
    extracted_count = max(0, _int(summary.get("extracted_count", 0)))
    inferred_count = max(0, _int(summary.get("inferred_count", 0)))
    ambiguous_count = max(0, _int(summary.get("ambiguous_count", 0)))
    unknown_count = max(0, _int(summary.get("unknown_count", 0)))

    return {
        "total_candidates": total_candidates,
        "extracted_count": extracted_count,
        "inferred_count": inferred_count,
        "ambiguous_count": ambiguous_count,
        "unknown_count": unknown_count,
        "extracted_ratio": _safe_ratio(extracted_count, total_candidates),
        "inferred_ratio": _safe_ratio(inferred_count, total_candidates),
        "ambiguous_ratio": _safe_ratio(ambiguous_count, total_candidates),
        "unknown_ratio": _safe_ratio(unknown_count, total_candidates),
    }


def build_pq_003_overlay(
    *,
    confidence_summary: Mapping[str, Any] | Any,
    metrics: Mapping[str, Any] | Any = None,
    generated_at: str = "",
    git_sha: str = "",
    phase: str = "phase1",
) -> dict[str, Any] | None:
    normalized_summary = _coerce_confidence_summary(confidence_summary)
    if normalized_summary["total_candidates"] <= 0:
        return None

    breakdown = _build_confidence_breakdown(normalized_summary)
    metric_source = _dict(metrics)
    pq_spec = _dict(PQ_SURFACE_SPECS.get("PQ-003"))
    metric_names = tuple(pq_spec.get("metric_names", ()))

    evidence_strength_score = _round(
        breakdown["extracted_ratio"] * 1.0
        + breakdown["inferred_ratio"] * 0.75
        + breakdown["ambiguous_ratio"] * 0.25
        + breakdown["unknown_ratio"] * 0.0
    )
    derived_metrics: dict[str, Any] = {
        "evidence_strength_score": evidence_strength_score,
    }
    for metric_name in metric_names:
        if metric_name == "evidence_strength_score":
            continue
        if metric_name in metric_source:
            derived_metrics[metric_name] = _round(_float(metric_source.get(metric_name), 0.0))

    return {
        "schema_version": "pq_003_evidence_overlay_v1",
        "generated_at": str(generated_at or ""),
        "git_sha": str(git_sha or ""),
        "phase": str(phase or "phase1"),
        "source": "source_plan/evidence_confidence.py",
        "pq_id": "PQ-003",
        "pq_title": str(pq_spec.get("title") or "evidence_strength_interpretability"),
        "confidence_breakdown": breakdown,
        "derived_metrics": derived_metrics,
        "ratios": {
            "hint_only_ratio": breakdown["ambiguous_ratio"],
            "ambiguous_ratio": breakdown["ambiguous_ratio"],
            "unknown_ratio": breakdown["unknown_ratio"],
            "grounded_ratio": _round(breakdown["extracted_ratio"] + breakdown["inferred_ratio"]),
        },
        "low_confidence_chunks": list(normalized_summary.get("low_confidence_chunks", [])),
        "warnings": [],
        "gate_mode": "report_only",
    }


def resolve_benchmark_pq_003_overlay(results: Mapping[str, Any] | Any) -> dict[str, Any] | None:
    payload = _dict(results)
    summaries: list[dict[str, Any]] = []

    top_level_summary = resolve_confidence_summary(payload)
    if top_level_summary:
        summaries.append(top_level_summary)

    for case in _list(payload.get("cases")):
        case_payload = _dict(case)
        plan_payload = _dict(case_payload.get("plan"))
        if not plan_payload:
            continue
        confidence_summary = resolve_confidence_summary(plan_payload)
        if confidence_summary:
            summaries.append(confidence_summary)

    aggregated = _aggregate_confidence_summaries(summaries)
    if not aggregated:
        return None

    return build_pq_003_overlay(
        confidence_summary=aggregated,
        metrics=_dict(payload.get("metrics")),
        generated_at=str(payload.get("generated_at") or ""),
        git_sha=str(payload.get("git_sha") or ""),
        phase=str(payload.get("phase") or "phase1"),
    )


def resolve_freeze_pq_003_overlay(payload: Mapping[str, Any] | Any) -> dict[str, Any] | None:
    report_payload = _dict(payload)

    confidence_summary = resolve_confidence_summary(report_payload)
    if not confidence_summary:
        validation_rich = _dict(report_payload.get("validation_rich_benchmark"))
        confidence_summary = _dict(validation_rich.get("confidence_summary"))
    if confidence_summary:
        validation_rich = _dict(report_payload.get("validation_rich_benchmark"))
        frontier = _dict(validation_rich.get("retrieval_frontier_gate_summary"))
        deep_symbol = _dict(validation_rich.get("deep_symbol_summary"))
        native_scip = _dict(validation_rich.get("native_scip_summary"))
        metrics = {
            "deep_symbol_case_recall": _float(
                frontier.get("deep_symbol_case_recall", deep_symbol.get("recall", 0.0)),
                0.0,
            ),
            "native_scip_loaded_rate": _float(
                frontier.get("native_scip_loaded_rate", native_scip.get("loaded_rate", 0.0)),
                0.0,
            ),
        }
        return build_pq_003_overlay(
            confidence_summary=confidence_summary,
            metrics=metrics,
            generated_at=str(report_payload.get("generated_at") or ""),
            git_sha=str(report_payload.get("git_sha") or ""),
            phase=str(report_payload.get("phase") or "phase1"),
        )

    existing_overlay = _dict(report_payload.get("pq_003_overlay"))
    return existing_overlay or None


__all__ = [
    "build_pq_003_overlay",
    "resolve_benchmark_pq_003_overlay",
    "resolve_freeze_pq_003_overlay",
]
