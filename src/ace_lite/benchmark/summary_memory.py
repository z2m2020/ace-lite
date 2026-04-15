from __future__ import annotations

from statistics import mean
from typing import Any


def build_ltm_explainability_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    feedback_signal_names = ("helpful", "stale", "harmful")

    def _build_feedback_signal_rows(
        *,
        case_total: float,
        case_counts: dict[str, int],
        total_counts: dict[str, int],
    ) -> list[dict[str, Any]]:
        return [
            {
                "feedback_signal": signal,
                "case_count": int(case_counts.get(signal, 0) or 0),
                "case_rate": (
                    float(case_counts.get(signal, 0) or 0) / case_total
                    if case_total > 0.0
                    else 0.0
                ),
                "total_count": int(total_counts.get(signal, 0) or 0),
                "count_mean": (
                    float(total_counts.get(signal, 0) or 0) / case_total
                    if case_total > 0.0
                    else 0.0
                ),
            }
            for signal in feedback_signal_names
        ]

    def _positive_case_count(values: list[float]) -> int:
        return sum(1 for value in values if value > 0.0)

    case_count = len(case_results)
    if case_count <= 0:
        zero_feedback_case_counts = {signal: 0 for signal in feedback_signal_names}
        zero_feedback_total_counts = {signal: 0 for signal in feedback_signal_names}
        return {
            "case_count": 0,
            "selected_case_count": 0,
            "selected_case_rate": 0.0,
            "selected_count_mean": 0.0,
            "attribution_case_count": 0,
            "attribution_case_rate": 0.0,
            "attribution_count_mean": 0.0,
            "graph_neighbor_case_count": 0,
            "graph_neighbor_case_rate": 0.0,
            "graph_neighbor_count_mean": 0.0,
            "plan_constraint_case_count": 0,
            "plan_constraint_case_rate": 0.0,
            "plan_constraint_count_mean": 0.0,
            "feedback_signal_observed_case_count": 0,
            "feedback_signal_observed_case_rate": 0.0,
            "feedback_signals": _build_feedback_signal_rows(
                case_total=0.0,
                case_counts=zero_feedback_case_counts,
                total_counts=zero_feedback_total_counts,
            ),
            "attribution_scope_count": 0,
            "attribution_scope_observed_case_count": 0,
            "attribution_scope_observed_case_rate": 0.0,
            "attribution_scopes": [],
        }

    selected_counts = [
        float(item.get("ltm_selected_count", 0.0) or 0.0) for item in case_results
    ]
    attribution_counts = [
        float(item.get("ltm_attribution_count", 0.0) or 0.0) for item in case_results
    ]
    graph_neighbor_counts = [
        float(item.get("ltm_graph_neighbor_count", 0.0) or 0.0)
        for item in case_results
    ]
    plan_constraint_counts = [
        float(item.get("ltm_plan_constraint_count", 0.0) or 0.0)
        for item in case_results
    ]

    selected_case_count = _positive_case_count(selected_counts)
    attribution_case_count = _positive_case_count(attribution_counts)
    graph_neighbor_case_count = _positive_case_count(graph_neighbor_counts)
    plan_constraint_case_count = _positive_case_count(plan_constraint_counts)

    feedback_signal_case_counts = {signal: 0 for signal in feedback_signal_names}
    feedback_signal_total_counts = {signal: 0 for signal in feedback_signal_names}
    feedback_signal_observed_case_count = 0
    attribution_scope_case_counts: dict[str, int] = {}
    attribution_scope_total_counts: dict[str, int] = {}
    attribution_scope_observed_case_count = 0

    for item in case_results:
        payload_raw = item.get("ltm_explainability")
        payload: dict[str, Any] = payload_raw if isinstance(payload_raw, dict) else {}

        raw_feedback_counts = payload.get("feedback_signal_counts")
        feedback_counts = {
            signal: max(
                0,
                int(
                    (
                        raw_feedback_counts.get(signal, 0)
                        if isinstance(raw_feedback_counts, dict)
                        else 0
                    )
                    or 0
                ),
            )
            for signal in feedback_signal_names
        }
        if any(feedback_counts.values()):
            feedback_signal_observed_case_count += 1
        for signal in feedback_signal_names:
            count = feedback_counts[signal]
            feedback_signal_total_counts[signal] += count
            if count > 0:
                feedback_signal_case_counts[signal] += 1

        raw_scope_counts = payload.get("attribution_scope_counts")
        scope_counts: dict[str, int] = {}
        if isinstance(raw_scope_counts, dict):
            scope_counts = {
                str(key).strip(): max(0, int(value or 0))
                for key, value in raw_scope_counts.items()
                if str(key).strip()
            }
        if any(count > 0 for count in scope_counts.values()):
            attribution_scope_observed_case_count += 1
        for scope, count in scope_counts.items():
            attribution_scope_total_counts[scope] = (
                int(attribution_scope_total_counts.get(scope, 0) or 0) + count
            )
            if count > 0:
                attribution_scope_case_counts[scope] = (
                    int(attribution_scope_case_counts.get(scope, 0) or 0) + 1
                )

    total = float(case_count)
    return {
        "case_count": case_count,
        "selected_case_count": selected_case_count,
        "selected_case_rate": float(selected_case_count) / total,
        "selected_count_mean": mean(selected_counts),
        "attribution_case_count": attribution_case_count,
        "attribution_case_rate": float(attribution_case_count) / total,
        "attribution_count_mean": mean(attribution_counts),
        "graph_neighbor_case_count": graph_neighbor_case_count,
        "graph_neighbor_case_rate": float(graph_neighbor_case_count) / total,
        "graph_neighbor_count_mean": mean(graph_neighbor_counts),
        "plan_constraint_case_count": plan_constraint_case_count,
        "plan_constraint_case_rate": float(plan_constraint_case_count) / total,
        "plan_constraint_count_mean": mean(plan_constraint_counts),
        "feedback_signal_observed_case_count": feedback_signal_observed_case_count,
        "feedback_signal_observed_case_rate": (
            float(feedback_signal_observed_case_count) / total
        ),
        "feedback_signals": _build_feedback_signal_rows(
            case_total=total,
            case_counts=feedback_signal_case_counts,
            total_counts=feedback_signal_total_counts,
        ),
        "attribution_scope_count": len(attribution_scope_total_counts),
        "attribution_scope_observed_case_count": attribution_scope_observed_case_count,
        "attribution_scope_observed_case_rate": (
            float(attribution_scope_observed_case_count) / total
        ),
        "attribution_scopes": [
            {
                "attribution_scope": scope,
                "case_count": int(attribution_scope_case_counts.get(scope, 0) or 0),
                "case_rate": float(attribution_scope_case_counts.get(scope, 0) or 0)
                / total,
                "total_count": int(attribution_scope_total_counts.get(scope, 0) or 0),
                "count_mean": float(attribution_scope_total_counts.get(scope, 0) or 0)
                / total,
            }
            for scope in sorted(
                attribution_scope_total_counts,
                key=lambda item: (
                    -int(attribution_scope_total_counts.get(item, 0) or 0),
                    -int(attribution_scope_case_counts.get(item, 0) or 0),
                    item,
                ),
            )
        ],
    }


def build_chunk_cache_contract_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "present_case_count": 0,
            "present_case_rate": 0.0,
            "fingerprint_present_case_count": 0,
            "fingerprint_present_case_rate": 0.0,
            "metadata_aligned_case_count": 0,
            "metadata_aligned_case_rate": 0.0,
            "file_count_mean": 0.0,
            "chunk_count_mean": 0.0,
        }

    present_case_count = 0
    fingerprint_present_case_count = 0
    metadata_aligned_case_count = 0
    file_counts: list[float] = []
    chunk_counts: list[float] = []
    for item in case_results:
        if not isinstance(item, dict):
            continue
        if float(item.get("chunk_cache_contract_present", 0.0) or 0.0) > 0.0:
            present_case_count += 1
        if (
            float(item.get("chunk_cache_contract_fingerprint_present", 0.0) or 0.0)
            > 0.0
        ):
            fingerprint_present_case_count += 1
        if (
            float(item.get("chunk_cache_contract_metadata_aligned", 0.0) or 0.0)
            > 0.0
        ):
            metadata_aligned_case_count += 1
        file_counts.append(float(item.get("chunk_cache_contract_file_count", 0.0) or 0.0))
        chunk_counts.append(
            float(item.get("chunk_cache_contract_chunk_count", 0.0) or 0.0)
        )

    return {
        "case_count": case_count,
        "present_case_count": present_case_count,
        "present_case_rate": float(present_case_count) / float(case_count),
        "fingerprint_present_case_count": fingerprint_present_case_count,
        "fingerprint_present_case_rate": (
            float(fingerprint_present_case_count) / float(case_count)
        ),
        "metadata_aligned_case_count": metadata_aligned_case_count,
        "metadata_aligned_case_rate": (
            float(metadata_aligned_case_count) / float(case_count)
        ),
        "file_count_mean": mean(file_counts),
        "chunk_count_mean": mean(chunk_counts),
    }


__all__ = [
    "build_chunk_cache_contract_summary",
    "build_ltm_explainability_summary",
]
