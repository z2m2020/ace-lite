"""Adaptive-router benchmark summary builders."""

from __future__ import annotations

from statistics import mean
from typing import Any

from ace_lite.benchmark.summary_common import p95


def _build_router_arm_bucket(
    *,
    buckets: dict[str, dict[str, Any]],
    case_count: int,
) -> dict[str, Any]:
    observed_case_count = sum(
        int(bucket.get("case_count", 0) or 0) for bucket in buckets.values()
    )
    arms: list[dict[str, Any]] = []
    for arm_id, bucket in sorted(
        buckets.items(),
        key=lambda item: (-int(item[1].get("case_count", 0) or 0), item[0]),
    ):
        arm_case_count = int(bucket.get("case_count", 0) or 0)
        latency_values = [float(value or 0.0) for value in bucket.get("latency_ms", [])]
        index_latency_values = [
            float(value or 0.0) for value in bucket.get("index_latency_ms", [])
        ]
        arms.append(
            {
                "arm_id": arm_id,
                "case_count": arm_case_count,
                "case_rate": (
                    float(arm_case_count) / float(case_count)
                    if case_count > 0
                    else 0.0
                ),
                "task_success_rate": (
                    float(bucket.get("task_success_total", 0.0) or 0.0)
                    / float(arm_case_count)
                    if arm_case_count > 0
                    else 0.0
                ),
                "mrr": (
                    float(bucket.get("mrr_total", 0.0) or 0.0)
                    / float(arm_case_count)
                    if arm_case_count > 0
                    else 0.0
                ),
                "fallback_case_count": int(bucket.get("fallback_case_count", 0) or 0),
                "fallback_case_rate": (
                    float(bucket.get("fallback_case_count", 0) or 0)
                    / float(arm_case_count)
                    if arm_case_count > 0
                    else 0.0
                ),
                "fallback_event_count": int(bucket.get("fallback_event_count", 0) or 0),
                "fallback_targets": dict(
                    sorted(
                        (bucket.get("fallback_targets", {}) or {}).items(),
                        key=lambda item: (-int(item[1] or 0), str(item[0])),
                    )
                ),
                "downgrade_case_count": int(bucket.get("downgrade_case_count", 0) or 0),
                "downgrade_case_rate": (
                    float(bucket.get("downgrade_case_count", 0) or 0)
                    / float(arm_case_count)
                    if arm_case_count > 0
                    else 0.0
                ),
                "downgrade_event_count": int(bucket.get("downgrade_event_count", 0) or 0),
                "downgrade_targets": dict(
                    sorted(
                        (bucket.get("downgrade_targets", {}) or {}).items(),
                        key=lambda item: (-int(item[1] or 0), str(item[0])),
                    )
                ),
                "latency_mean_ms": (
                    round(mean(latency_values), 6) if latency_values else 0.0
                ),
                "latency_p95_ms": round(p95(latency_values), 6),
                "index_latency_mean_ms": (
                    round(mean(index_latency_values), 6)
                    if index_latency_values
                    else 0.0
                ),
                "index_latency_p95_ms": round(p95(index_latency_values), 6),
            }
        )
    return {
        "arm_count": len(buckets),
        "observed_case_count": observed_case_count,
        "arms": arms,
    }


def build_adaptive_router_arm_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        empty_bucket = {"arm_count": 0, "observed_case_count": 0, "arms": []}
        return {
            "case_count": 0,
            "enabled_case_count": 0,
            "enabled_case_rate": 0.0,
            "executed": dict(empty_bucket),
            "shadow": dict(empty_bucket),
        }

    enabled_case_count = 0
    executed_buckets: dict[str, dict[str, Any]] = {}
    shadow_buckets: dict[str, dict[str, Any]] = {}

    for item in case_results:
        if not isinstance(item, dict):
            continue
        if bool(item.get("router_enabled", False)):
            enabled_case_count += 1
        task_success_hit = float(
            item.get("task_success_hit", item.get("utility_hit", 0.0)) or 0.0
        )
        reciprocal_rank = float(item.get("reciprocal_rank", 0.0) or 0.0)
        latency_ms = float(item.get("latency_ms", 0.0) or 0.0)
        index_latency_ms = float(item.get("index_latency_ms", 0.0) or 0.0)
        decision_trace_raw = item.get("decision_trace", [])
        decision_trace = (
            decision_trace_raw if isinstance(decision_trace_raw, list) else []
        )
        fallback_events = [
            event
            for event in decision_trace
            if isinstance(event, dict) and str(event.get("action") or "").strip() == "fallback"
        ]
        downgrade_events = [
            event
            for event in decision_trace
            if isinstance(event, dict) and str(event.get("action") or "").strip() == "downgrade"
        ]
        executed_arm_id = str(item.get("router_arm_id") or "").strip()
        if executed_arm_id:
            bucket = executed_buckets.setdefault(
                executed_arm_id,
                {
                    "case_count": 0,
                    "task_success_total": 0.0,
                    "mrr_total": 0.0,
                    "fallback_case_count": 0,
                    "fallback_event_count": 0,
                    "fallback_targets": {},
                    "downgrade_case_count": 0,
                    "downgrade_event_count": 0,
                    "downgrade_targets": {},
                    "latency_ms": [],
                    "index_latency_ms": [],
                },
            )
            bucket["case_count"] += 1
            bucket["task_success_total"] += task_success_hit
            bucket["mrr_total"] += reciprocal_rank
            if fallback_events:
                bucket["fallback_case_count"] += 1
                bucket["fallback_event_count"] += len(fallback_events)
                for event in fallback_events:
                    target = str(event.get("target") or "").strip() or "(unknown)"
                    fallback_targets = bucket["fallback_targets"]
                    fallback_targets[target] = fallback_targets.get(target, 0) + 1
            if downgrade_events:
                bucket["downgrade_case_count"] += 1
                bucket["downgrade_event_count"] += len(downgrade_events)
                for event in downgrade_events:
                    target = str(event.get("target") or "").strip() or "(unknown)"
                    downgrade_targets = bucket["downgrade_targets"]
                    downgrade_targets[target] = downgrade_targets.get(target, 0) + 1
            bucket["latency_ms"].append(latency_ms)
            bucket["index_latency_ms"].append(index_latency_ms)
        shadow_arm_id = str(item.get("router_shadow_arm_id") or "").strip()
        if shadow_arm_id:
            bucket = shadow_buckets.setdefault(
                shadow_arm_id,
                {
                    "case_count": 0,
                    "task_success_total": 0.0,
                    "mrr_total": 0.0,
                    "fallback_case_count": 0,
                    "fallback_event_count": 0,
                    "fallback_targets": {},
                    "downgrade_case_count": 0,
                    "downgrade_event_count": 0,
                    "downgrade_targets": {},
                    "latency_ms": [],
                    "index_latency_ms": [],
                },
            )
            bucket["case_count"] += 1
            bucket["task_success_total"] += task_success_hit
            bucket["mrr_total"] += reciprocal_rank
            if fallback_events:
                bucket["fallback_case_count"] += 1
                bucket["fallback_event_count"] += len(fallback_events)
                for event in fallback_events:
                    target = str(event.get("target") or "").strip() or "(unknown)"
                    fallback_targets = bucket["fallback_targets"]
                    fallback_targets[target] = fallback_targets.get(target, 0) + 1
            if downgrade_events:
                bucket["downgrade_case_count"] += 1
                bucket["downgrade_event_count"] += len(downgrade_events)
                for event in downgrade_events:
                    target = str(event.get("target") or "").strip() or "(unknown)"
                    downgrade_targets = bucket["downgrade_targets"]
                    downgrade_targets[target] = downgrade_targets.get(target, 0) + 1
            bucket["latency_ms"].append(latency_ms)
            bucket["index_latency_ms"].append(index_latency_ms)

    return {
        "case_count": case_count,
        "enabled_case_count": enabled_case_count,
        "enabled_case_rate": (
            float(enabled_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "executed": _build_router_arm_bucket(
            buckets=executed_buckets,
            case_count=case_count,
        ),
        "shadow": _build_router_arm_bucket(
            buckets=shadow_buckets,
            case_count=case_count,
        ),
    }


def build_adaptive_router_pair_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    case_count = len(case_results)
    if case_count <= 0:
        return {
            "case_count": 0,
            "comparable_case_count": 0,
            "comparable_case_rate": 0.0,
            "disagreement_case_count": 0,
            "disagreement_rate": 0.0,
            "pairs": [],
        }

    comparable_case_count = 0
    disagreement_case_count = 0
    pair_buckets: dict[tuple[str, str], dict[str, Any]] = {}

    for item in case_results:
        if not isinstance(item, dict):
            continue
        executed_arm_id = str(item.get("router_arm_id") or "").strip()
        shadow_arm_id = str(item.get("router_shadow_arm_id") or "").strip()
        if not executed_arm_id or not shadow_arm_id:
            continue
        comparable_case_count += 1
        disagrees = executed_arm_id != shadow_arm_id
        if disagrees:
            disagreement_case_count += 1
        bucket = pair_buckets.setdefault(
            (executed_arm_id, shadow_arm_id),
            {
                "case_count": 0,
                "disagreement_case_count": 0,
                "latency_ms": [],
                "index_latency_ms": [],
            },
        )
        bucket["case_count"] += 1
        if disagrees:
            bucket["disagreement_case_count"] += 1
        bucket["latency_ms"].append(float(item.get("latency_ms", 0.0) or 0.0))
        bucket["index_latency_ms"].append(float(item.get("index_latency_ms", 0.0) or 0.0))

    pairs: list[dict[str, Any]] = []
    for executed_arm_id, shadow_arm_id in sorted(
        pair_buckets,
        key=lambda item: (-int(pair_buckets[item]["case_count"]), item[0], item[1]),
    ):
        bucket = pair_buckets[(executed_arm_id, shadow_arm_id)]
        pair_case_count = int(bucket["case_count"] or 0)
        latency_values = [float(value or 0.0) for value in bucket["latency_ms"]]
        index_latency_values = [float(value or 0.0) for value in bucket["index_latency_ms"]]
        disagreement_count = int(bucket["disagreement_case_count"] or 0)
        pairs.append(
            {
                "executed_arm_id": executed_arm_id,
                "shadow_arm_id": shadow_arm_id,
                "case_count": pair_case_count,
                "case_rate": (
                    float(pair_case_count) / float(comparable_case_count)
                    if comparable_case_count > 0
                    else 0.0
                ),
                "disagreement_case_count": disagreement_count,
                "disagreement_rate": (
                    float(disagreement_count) / float(pair_case_count)
                    if pair_case_count > 0
                    else 0.0
                ),
                "latency_mean_ms": (
                    round(mean(latency_values), 6) if latency_values else 0.0
                ),
                "latency_p95_ms": round(p95(latency_values), 6),
                "index_latency_mean_ms": (
                    round(mean(index_latency_values), 6)
                    if index_latency_values
                    else 0.0
                ),
                "index_latency_p95_ms": round(p95(index_latency_values), 6),
            }
        )

    return {
        "case_count": case_count,
        "comparable_case_count": comparable_case_count,
        "comparable_case_rate": (
            float(comparable_case_count) / float(case_count)
            if case_count > 0
            else 0.0
        ),
        "disagreement_case_count": disagreement_case_count,
        "disagreement_rate": (
            float(disagreement_case_count) / float(comparable_case_count)
            if comparable_case_count > 0
            else 0.0
        ),
        "pairs": pairs,
    }


def build_adaptive_router_observability_summary(
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    arm_summary = build_adaptive_router_arm_summary(case_results)
    pair_summary = build_adaptive_router_pair_summary(case_results)
    comparable_case_count = int(pair_summary.get("comparable_case_count", 0) or 0)
    disagreement_case_count = int(pair_summary.get("disagreement_case_count", 0) or 0)
    agreement_case_count = max(0, comparable_case_count - disagreement_case_count)

    executed = arm_summary.get("executed", {})
    shadow = arm_summary.get("shadow", {})
    return {
        "case_count": int(arm_summary.get("case_count", 0) or 0),
        "enabled_case_count": int(arm_summary.get("enabled_case_count", 0) or 0),
        "enabled_case_rate": float(arm_summary.get("enabled_case_rate", 0.0) or 0.0),
        "comparable_case_count": comparable_case_count,
        "comparable_case_rate": float(pair_summary.get("comparable_case_rate", 0.0) or 0.0),
        "agreement_case_count": agreement_case_count,
        "agreement_rate": (
            float(agreement_case_count) / float(comparable_case_count)
            if comparable_case_count > 0
            else 0.0
        ),
        "disagreement_case_count": disagreement_case_count,
        "disagreement_rate": float(pair_summary.get("disagreement_rate", 0.0) or 0.0),
        "executed_arm_count": int(executed.get("arm_count", 0) or 0),
        "shadow_arm_count": int(shadow.get("arm_count", 0) or 0),
        "executed_arms": list(executed.get("arms", []))
        if isinstance(executed.get("arms"), list)
        else [],
        "shadow_arms": list(shadow.get("arms", []))
        if isinstance(shadow.get("arms"), list)
        else [],
    }


__all__ = [
    "build_adaptive_router_arm_summary",
    "build_adaptive_router_observability_summary",
    "build_adaptive_router_pair_summary",
]
