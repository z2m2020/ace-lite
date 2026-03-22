from __future__ import annotations

from typing import Any

from ace_lite.dev_feedback_taxonomy import describe_dev_feedback_reason
from ace_lite.dev_feedback_taxonomy import normalize_dev_feedback_reason_code


RUNTIME_MEMORY_REASON_CODES = frozenset(
    {
        "memory_fallback",
        "memory_namespace_fallback",
    }
)


def resolve_reason_details(reason_code: Any) -> dict[str, str]:
    canonical = normalize_dev_feedback_reason_code(reason_code, default="")
    if not canonical:
        return {"reason_code": "", "reason_family": "", "capture_class": ""}
    return describe_dev_feedback_reason(canonical)


def build_runtime_top_pain_summary(
    *,
    runtime_scope_map: dict[str, dict[str, Any] | None],
    dev_feedback_summary: dict[str, Any],
) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    preferred_scope = None
    for scope_name in ("repo_profile", "repo", "profile", "session", "all_time"):
        candidate = runtime_scope_map.get(scope_name)
        if isinstance(candidate, dict):
            preferred_scope = candidate
            break
    degraded_states = (
        preferred_scope.get("degraded_states", [])
        if isinstance(preferred_scope, dict)
        else []
    )
    for item in degraded_states if isinstance(degraded_states, list) else []:
        reason_details = resolve_reason_details(item.get("reason_code"))
        reason_code = str(reason_details.get("reason_code") or "").strip()
        if not reason_code:
            continue
        bucket = merged.setdefault(
            reason_code,
            {
                "reason_code": reason_code,
                "reason_family": str(reason_details.get("reason_family") or ""),
                "capture_class": str(reason_details.get("capture_class") or ""),
                "runtime_event_count": 0,
                "manual_issue_count": 0,
                "open_issue_count": 0,
                "resolved_issue_count": 0,
                "fix_count": 0,
                "linked_fix_issue_count": 0,
                "issue_time_to_fix_case_count": 0,
                "issue_time_to_fix_hours_total": 0.0,
                "last_seen_at": "",
            },
        )
        bucket["runtime_event_count"] += int(item.get("event_count", 0) or 0)
        bucket["last_seen_at"] = max(
            str(bucket["last_seen_at"]),
            str(item.get("last_seen_at") or ""),
        )

    by_reason_code = dev_feedback_summary.get("by_reason_code", [])
    for item in by_reason_code if isinstance(by_reason_code, list) else []:
        if not isinstance(item, dict):
            continue
        reason_details = resolve_reason_details(item.get("reason_code"))
        reason_code = str(reason_details.get("reason_code") or "").strip()
        if not reason_code:
            continue
        bucket = merged.setdefault(
            reason_code,
            {
                "reason_code": reason_code,
                "reason_family": str(reason_details.get("reason_family") or ""),
                "capture_class": str(reason_details.get("capture_class") or ""),
                "runtime_event_count": 0,
                "manual_issue_count": 0,
                "open_issue_count": 0,
                "resolved_issue_count": 0,
                "fix_count": 0,
                "linked_fix_issue_count": 0,
                "issue_time_to_fix_case_count": 0,
                "issue_time_to_fix_hours_total": 0.0,
                "last_seen_at": "",
            },
        )
        bucket["manual_issue_count"] += int(item.get("issue_count", 0) or 0)
        bucket["open_issue_count"] += int(item.get("open_issue_count", 0) or 0)
        bucket["resolved_issue_count"] += int(item.get("resolved_issue_count", 0) or 0)
        bucket["fix_count"] += int(item.get("fix_count", 0) or 0)
        bucket["linked_fix_issue_count"] += int(
            item.get("linked_fix_issue_count", 0) or 0
        )
        issue_time_to_fix_case_count = int(
            item.get("issue_time_to_fix_case_count", 0) or 0
        )
        bucket["issue_time_to_fix_case_count"] += issue_time_to_fix_case_count
        bucket["issue_time_to_fix_hours_total"] += float(
            item.get("issue_time_to_fix_hours_mean", 0.0) or 0.0
        ) * float(issue_time_to_fix_case_count)
        bucket["last_seen_at"] = max(
            str(bucket["last_seen_at"]),
            str(item.get("last_seen_at") or ""),
        )

    rows: list[dict[str, Any]] = []
    for bucket in merged.values():
        issue_count = int(bucket["manual_issue_count"])
        issue_time_to_fix_case_count = int(bucket["issue_time_to_fix_case_count"])
        total_count = (
            int(bucket["runtime_event_count"])
            + issue_count
            + int(bucket["open_issue_count"])
        )
        rows.append(
            {
                **bucket,
                "dev_issue_to_fix_rate": (
                    float(bucket["linked_fix_issue_count"]) / float(issue_count)
                    if issue_count > 0
                    else 0.0
                ),
                "issue_time_to_fix_hours_mean": (
                    float(bucket["issue_time_to_fix_hours_total"])
                    / float(issue_time_to_fix_case_count)
                    if issue_time_to_fix_case_count > 0
                    else 0.0
                ),
                "total_count": total_count,
            }
        )
    rows.sort(
        key=lambda item: (
            -int(item.get("total_count", 0) or 0),
            -int(item.get("fix_count", 0) or 0),
            str(item.get("reason_code") or ""),
        )
    )
    for item in rows:
        item.pop("issue_time_to_fix_hours_total", None)
    return {"count": len(rows), "items": rows[:10]}


def build_runtime_memory_health_summary(
    *,
    runtime_scope_map: dict[str, dict[str, Any] | None],
    top_pain_summary: dict[str, Any],
) -> dict[str, Any]:
    preferred_scope_name = "all_time"
    preferred_scope: dict[str, Any] | None = None
    for scope_name in ("repo_profile", "repo", "profile", "session", "all_time"):
        candidate = runtime_scope_map.get(scope_name)
        if isinstance(candidate, dict):
            preferred_scope_name = scope_name
            preferred_scope = candidate
            break

    latency_mean = 0.0
    if isinstance(preferred_scope, dict):
        for item in preferred_scope.get("stage_latencies", []):
            if not isinstance(item, dict):
                continue
            if str(item.get("stage_name") or "").strip() != "memory":
                continue
            latency_mean = float(item.get("latency_ms_avg", 0.0) or 0.0)
            break

    reason_items_raw = top_pain_summary.get("items")
    reason_items = reason_items_raw if isinstance(reason_items_raw, list) else []
    memory_items: list[dict[str, Any]] = []
    for item in reason_items:
        if not isinstance(item, dict):
            continue
        reason_details = resolve_reason_details(item.get("reason_code"))
        reason_code = str(reason_details.get("reason_code") or "").strip()
        if reason_code not in RUNTIME_MEMORY_REASON_CODES:
            continue
        memory_items.append(
            {
                "reason_code": reason_code,
                "reason_family": str(reason_details.get("reason_family") or ""),
                "capture_class": str(reason_details.get("capture_class") or ""),
                "runtime_event_count": int(item.get("runtime_event_count", 0) or 0),
                "manual_issue_count": int(item.get("manual_issue_count", 0) or 0),
                "open_issue_count": int(item.get("open_issue_count", 0) or 0),
                "resolved_issue_count": int(item.get("resolved_issue_count", 0) or 0),
                "fix_count": int(item.get("fix_count", 0) or 0),
                "linked_fix_issue_count": int(item.get("linked_fix_issue_count", 0) or 0),
                "dev_issue_to_fix_rate": float(
                    item.get("dev_issue_to_fix_rate", 0.0) or 0.0
                ),
                "issue_time_to_fix_case_count": int(
                    item.get("issue_time_to_fix_case_count", 0) or 0
                ),
                "issue_time_to_fix_hours_mean": float(
                    item.get("issue_time_to_fix_hours_mean", 0.0) or 0.0
                ),
                "last_seen_at": str(item.get("last_seen_at") or ""),
            }
        )

    runtime_event_count = sum(
        int(item.get("runtime_event_count", 0) or 0) for item in memory_items
    )
    issue_count = sum(int(item.get("manual_issue_count", 0) or 0) for item in memory_items)
    open_issue_count = sum(int(item.get("open_issue_count", 0) or 0) for item in memory_items)
    resolved_issue_count = sum(
        int(item.get("resolved_issue_count", 0) or 0) for item in memory_items
    )
    fix_count = sum(int(item.get("fix_count", 0) or 0) for item in memory_items)
    linked_fix_issue_count = sum(
        int(item.get("linked_fix_issue_count", 0) or 0) for item in memory_items
    )
    issue_time_to_fix_case_count = sum(
        int(item.get("issue_time_to_fix_case_count", 0) or 0) for item in memory_items
    )
    issue_time_to_fix_hours_total = sum(
        float(item.get("issue_time_to_fix_hours_mean", 0.0) or 0.0)
        * float(item.get("issue_time_to_fix_case_count", 0) or 0)
        for item in memory_items
    )

    return {
        "scope_kind": preferred_scope_name,
        "reason_count": len(memory_items),
        "runtime_event_count": runtime_event_count,
        "issue_count": issue_count,
        "open_issue_count": open_issue_count,
        "resolved_issue_count": resolved_issue_count,
        "fix_count": fix_count,
        "linked_fix_issue_count": linked_fix_issue_count,
        "resolution_rate": (
            float(fix_count) / float(issue_count) if issue_count > 0 else 0.0
        ),
        "dev_issue_to_fix_rate": (
            float(linked_fix_issue_count) / float(issue_count)
            if issue_count > 0
            else 0.0
        ),
        "open_issue_rate": (
            float(open_issue_count) / float(issue_count) if issue_count > 0 else 0.0
        ),
        "issue_time_to_fix_case_count": issue_time_to_fix_case_count,
        "issue_time_to_fix_hours_mean": (
            float(issue_time_to_fix_hours_total) / float(issue_time_to_fix_case_count)
            if issue_time_to_fix_case_count > 0
            else 0.0
        ),
        "memory_stage_latency_ms_avg": latency_mean,
        "reasons": memory_items,
    }


__all__ = [
    "RUNTIME_MEMORY_REASON_CODES",
    "build_runtime_memory_health_summary",
    "build_runtime_top_pain_summary",
    "resolve_reason_details",
]
