from __future__ import annotations

from typing import Any

from ace_lite.agent_loop.contracts import (
    AGENT_LOOP_ACTION_TYPES,
    AGENT_LOOP_RERUN_POLICY_SCHEMA_VERSION,
)
from ace_lite.agent_loop.controller import AGENT_LOOP_STOP_REASONS
from ace_lite.dev_feedback_taxonomy import describe_dev_feedback_reason
from ace_lite.dev_feedback_taxonomy import normalize_dev_feedback_reason_code


RUNTIME_MEMORY_REASON_CODES = frozenset(
    {
        "memory_fallback",
        "memory_namespace_fallback",
    }
)
RUNTIME_MEMORY_LTM_FEEDBACK_SIGNALS = ("helpful", "stale", "harmful")


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


def build_runtime_memory_ltm_signal_summary(
    *,
    ltm_explainability_summary: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(ltm_explainability_summary, dict) or not ltm_explainability_summary:
        return {}

    case_count = max(0, int(ltm_explainability_summary.get("case_count", 0) or 0))
    feedback_rows_raw = ltm_explainability_summary.get("feedback_signals")
    feedback_rows_input = feedback_rows_raw if isinstance(feedback_rows_raw, list) else []
    feedback_rows: list[dict[str, Any]] = []
    for signal in RUNTIME_MEMORY_LTM_FEEDBACK_SIGNALS:
        candidate = next(
            (
                item
                for item in feedback_rows_input
                if isinstance(item, dict)
                and str(item.get("feedback_signal") or "").strip().lower() == signal
            ),
            {},
        )
        feedback_rows.append(
            {
                "feedback_signal": signal,
                "case_count": max(0, int(candidate.get("case_count", 0) or 0)),
                "case_rate": float(candidate.get("case_rate", 0.0) or 0.0),
                "total_count": max(0, int(candidate.get("total_count", 0) or 0)),
                "count_mean": float(candidate.get("count_mean", 0.0) or 0.0),
            }
        )

    attribution_rows_raw = ltm_explainability_summary.get("attribution_scopes")
    attribution_rows_input = (
        attribution_rows_raw if isinstance(attribution_rows_raw, list) else []
    )
    attribution_rows: list[dict[str, Any]] = []
    for item in attribution_rows_input:
        if not isinstance(item, dict):
            continue
        scope = str(item.get("attribution_scope") or "").strip()
        if not scope:
            continue
        attribution_rows.append(
            {
                "attribution_scope": scope,
                "case_count": max(0, int(item.get("case_count", 0) or 0)),
                "case_rate": float(item.get("case_rate", 0.0) or 0.0),
                "total_count": max(0, int(item.get("total_count", 0) or 0)),
                "count_mean": float(item.get("count_mean", 0.0) or 0.0),
            }
        )

    observed_feedback_case_count = max(
        0,
        int(ltm_explainability_summary.get("feedback_signal_observed_case_count", 0) or 0),
    )
    observed_attribution_case_count = max(
        0,
        int(
            ltm_explainability_summary.get("attribution_scope_observed_case_count", 0)
            or 0
        ),
    )
    if (
        case_count <= 0
        and observed_feedback_case_count <= 0
        and observed_attribution_case_count <= 0
        and not any(int(item.get("total_count", 0) or 0) > 0 for item in feedback_rows)
        and not attribution_rows
    ):
        return {}

    return {
        "case_count": case_count,
        "feedback_signal_observed_case_count": observed_feedback_case_count,
        "feedback_signal_observed_case_rate": float(
            ltm_explainability_summary.get("feedback_signal_observed_case_rate", 0.0)
            or 0.0
        ),
        "feedback_signals": feedback_rows,
        "attribution_scope_count": max(
            0, int(ltm_explainability_summary.get("attribution_scope_count", 0) or 0)
        ),
        "attribution_scope_observed_case_count": observed_attribution_case_count,
        "attribution_scope_observed_case_rate": float(
            ltm_explainability_summary.get("attribution_scope_observed_case_rate", 0.0)
            or 0.0
        ),
        "attribution_scopes": attribution_rows,
    }


def attach_runtime_memory_ltm_signal_summary(
    *,
    memory_health_summary: dict[str, Any],
    ltm_explainability_summary: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(memory_health_summary, dict) or not memory_health_summary:
        return {}
    payload = dict(memory_health_summary)
    ltm_signal_summary = build_runtime_memory_ltm_signal_summary(
        ltm_explainability_summary=ltm_explainability_summary,
    )
    if ltm_signal_summary:
        payload["ltm_signal_summary"] = ltm_signal_summary
    return payload


def build_runtime_agent_loop_control_plane_summary(
    *,
    runtime_scope_map: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    preferred_scope_name = "all_time"
    preferred_scope: dict[str, Any] | None = None
    for scope_name in ("repo_profile", "repo", "profile", "session", "all_time"):
        candidate = runtime_scope_map.get(scope_name)
        if isinstance(candidate, dict):
            preferred_scope_name = scope_name
            preferred_scope = candidate
            break

    agent_loop_stage: dict[str, Any] = {}
    if isinstance(preferred_scope, dict):
        for item in preferred_scope.get("stage_latencies", []):
            if not isinstance(item, dict):
                continue
            if str(item.get("stage_name") or "").strip() != "agent_loop":
                continue
            agent_loop_stage = item
            break

    request_more_context_rerun_stages = [
        "index",
        "repomap",
        "augment",
        "skills",
        "source_plan",
        "validation",
    ]
    source_plan_retry_rerun_stages = ["source_plan", "validation"]
    validation_retry_rerun_stages = ["validation"]

    return {
        "scope_kind": preferred_scope_name,
        "supported_action_types": list(AGENT_LOOP_ACTION_TYPES),
        "supported_stop_reasons": list(AGENT_LOOP_STOP_REASONS),
        "rerun_policy_schema_version": AGENT_LOOP_RERUN_POLICY_SCHEMA_VERSION,
        "rerun_policy_supported": True,
        "preferred_execution_scope": "post_source_runtime",
        "request_more_context_supported": "request_more_context"
        in AGENT_LOOP_ACTION_TYPES,
        "source_plan_retry_supported": "request_source_plan_retry"
        in AGENT_LOOP_ACTION_TYPES,
        "validation_retry_supported": "request_validation_retry"
        in AGENT_LOOP_ACTION_TYPES,
        "request_more_context_rerun_stages": request_more_context_rerun_stages,
        "source_plan_retry_rerun_stages": source_plan_retry_rerun_stages,
        "validation_retry_rerun_stages": validation_retry_rerun_stages,
        "observed_stage": bool(agent_loop_stage),
        "agent_loop_stage_invocation_count": int(
            agent_loop_stage.get("invocation_count", 0) or 0
        ),
        "agent_loop_stage_latency_ms_avg": float(
            agent_loop_stage.get("latency_ms_avg", 0.0) or 0.0
        ),
    }


def _build_next_cycle_action_hint(
    *,
    reason_code: str,
    reason_family: str,
    capture_class: str,
) -> str:
    family = str(reason_family or "").strip().lower()
    capture = str(capture_class or "").strip().lower()
    if capture == "memory" or family == "memory":
        return "Stabilize memory fallback and capture quality before expanding retrieval breadth."
    if capture == "budget":
        return "Tune budget and gating defaults before increasing candidate or skills scope."
    if capture == "validation":
        return "Prioritize validation feedback and branch diagnostics hardening in the next cycle."
    if capture == "retrieval" or family == "retrieval":
        return "Reduce retrieval misses/noise and keep structured refinement evidence stable."
    if reason_code == "install_drift":
        return "Resync editable install metadata before using runtime health as a release signal."
    if reason_code == "git_unavailable":
        return "Restore Git availability for runtime diagnostics before widening automation scope."
    if reason_code == "stage_artifact_cache_corrupt":
        return "Repair stage artifact cache integrity before relying on replay or branch evidence."
    return "Prioritize the highest-frequency degraded reason as the next cycle maintenance stream."


def build_runtime_next_cycle_input_summary(
    *,
    top_pain_summary: dict[str, Any],
    memory_health_summary: dict[str, Any],
    degraded_services: list[dict[str, Any]] | None = None,
    doctor_reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    top_pain_items_raw = top_pain_summary.get("items")
    top_pain_items = top_pain_items_raw if isinstance(top_pain_items_raw, list) else []
    priorities: list[dict[str, Any]] = []
    seen_reason_codes: set[str] = set()
    for item in top_pain_items:
        if not isinstance(item, dict):
            continue
        reason_details = resolve_reason_details(item.get("reason_code"))
        reason_code = str(reason_details.get("reason_code") or "").strip()
        if not reason_code or reason_code in seen_reason_codes:
            continue
        total_count = int(item.get("total_count", 0) or 0)
        runtime_event_count = int(item.get("runtime_event_count", 0) or 0)
        manual_issue_count = int(item.get("manual_issue_count", 0) or 0)
        open_issue_count = int(item.get("open_issue_count", 0) or 0)
        if max(total_count, runtime_event_count, manual_issue_count, open_issue_count) <= 0:
            continue
        seen_reason_codes.add(reason_code)
        reason_family = str(reason_details.get("reason_family") or "").strip()
        capture_class = str(reason_details.get("capture_class") or "").strip()
        priorities.append(
            {
                "reason_code": reason_code,
                "reason_family": reason_family,
                "capture_class": capture_class,
                "total_count": total_count,
                "runtime_event_count": runtime_event_count,
                "manual_issue_count": manual_issue_count,
                "open_issue_count": open_issue_count,
                "fix_count": int(item.get("fix_count", 0) or 0),
                "last_seen_at": str(item.get("last_seen_at") or "").strip(),
                "action_hint": _build_next_cycle_action_hint(
                    reason_code=reason_code,
                    reason_family=reason_family,
                    capture_class=capture_class,
                ),
            }
        )
        if len(priorities) >= 3:
            break

    degraded_service_names: list[str] = []
    seen_services: set[str] = set()
    for item in degraded_services if isinstance(degraded_services, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name or name in seen_services:
            continue
        seen_services.add(name)
        degraded_service_names.append(name)

    normalized_doctor_reasons: list[str] = []
    seen_doctor_reasons: set[str] = set()
    for item in doctor_reason_codes if isinstance(doctor_reason_codes, list) else []:
        normalized = normalize_dev_feedback_reason_code(item, default="")
        if not normalized or normalized in seen_doctor_reasons:
            continue
        seen_doctor_reasons.add(normalized)
        normalized_doctor_reasons.append(normalized)

    memory_focus = {
        "reason_count": int(memory_health_summary.get("reason_count", 0) or 0),
        "runtime_event_count": int(
            memory_health_summary.get("runtime_event_count", 0) or 0
        ),
        "issue_count": int(memory_health_summary.get("issue_count", 0) or 0),
        "open_issue_count": int(memory_health_summary.get("open_issue_count", 0) or 0),
        "fix_count": int(memory_health_summary.get("fix_count", 0) or 0),
        "resolution_rate": float(
            memory_health_summary.get("resolution_rate", 0.0) or 0.0
        ),
        "action_hint": _build_next_cycle_action_hint(
            reason_code="memory_fallback",
            reason_family="memory",
            capture_class="memory",
        ),
    }
    memory_focus_enabled = any(
        float(memory_focus.get(key, 0) or 0) > 0.0
        for key in (
            "reason_count",
            "runtime_event_count",
            "issue_count",
            "open_issue_count",
            "fix_count",
        )
    )

    if not priorities and not memory_focus_enabled and not degraded_service_names and not normalized_doctor_reasons:
        return {}

    primary_stream = ""
    if priorities:
        primary_stream = str(priorities[0].get("capture_class") or "").strip()
        if not primary_stream:
            primary_stream = str(priorities[0].get("reason_family") or "").strip()
    if not primary_stream and memory_focus_enabled:
        primary_stream = "memory"
    if not primary_stream and degraded_service_names:
        primary_stream = degraded_service_names[0]
    if not primary_stream and normalized_doctor_reasons:
        primary_stream = normalized_doctor_reasons[0]

    return {
        "priority_count": len(priorities),
        "primary_stream": primary_stream,
        "priorities": priorities,
        "memory_focus": memory_focus if memory_focus_enabled else {},
        "degraded_service_names": degraded_service_names,
        "doctor_reason_codes": normalized_doctor_reasons,
    }


__all__ = [
    "RUNTIME_MEMORY_REASON_CODES",
    "RUNTIME_MEMORY_LTM_FEEDBACK_SIGNALS",
    "build_runtime_agent_loop_control_plane_summary",
    "build_runtime_memory_health_summary",
    "build_runtime_memory_ltm_signal_summary",
    "build_runtime_next_cycle_input_summary",
    "build_runtime_top_pain_summary",
    "attach_runtime_memory_ltm_signal_summary",
    "resolve_reason_details",
]
