from __future__ import annotations

from typing import Any

from ace_lite.runtime_stats import RuntimeScopeRollup
from ace_lite.runtime_stats_schema import (
    RUNTIME_STATS_ALL_TIME_SCOPE_KEY,
    RUNTIME_STATS_COUNTER_FIELDS,
)


def _counter_delta_for_invocation(stats: Any) -> dict[str, int]:
    normalized_status = str(getattr(stats, "status", "") or "").strip().lower()
    return {
        "invocation_count": 1,
        "success_count": 1 if normalized_status == "succeeded" else 0,
        "degraded_count": 1 if normalized_status == "degraded" else 0,
        "failure_count": 1 if normalized_status == "failed" else 0,
        "contract_error_count": (
            1 if str(getattr(stats, "contract_error_code", "") or "").strip() else 0
        ),
        "plan_replay_hit_count": 1 if bool(getattr(stats, "plan_replay_hit", False)) else 0,
        "plan_replay_safe_hit_count": (
            1 if bool(getattr(stats, "plan_replay_safe_hit", False)) else 0
        ),
        "plan_replay_store_count": (
            1 if bool(getattr(stats, "plan_replay_store_written", False)) else 0
        ),
        "trace_export_count": 1 if bool(getattr(stats, "trace_exported", False)) else 0,
        "trace_export_failure_count": (
            1 if bool(getattr(stats, "trace_export_failed", False)) else 0
        ),
    }


def build_scope_rollup_from_invocations(
    *,
    scope_kind: str,
    scope_key: str,
    repo_key: str = "",
    profile_key: str = "",
    invocations: tuple[Any, ...],
) -> RuntimeScopeRollup | None:
    if not invocations:
        return None
    counters = {field: 0 for field in RUNTIME_STATS_COUNTER_FIELDS}
    latency_sum = 0.0
    latency_min: float | None = None
    latency_max = 0.0
    latency_last = 0.0
    updated_at = ""
    stage_rollups: dict[str, dict[str, Any]] = {}
    degraded_rollups: dict[str, dict[str, Any]] = {}
    for stats in invocations:
        for key, value in _counter_delta_for_invocation(stats).items():
            counters[key] += int(value)
        total_latency = float(getattr(stats, "total_latency_ms", 0.0) or 0.0)
        latency_sum += total_latency
        latency_min = total_latency if latency_min is None else min(latency_min, total_latency)
        latency_max = max(latency_max, total_latency)
        latency_last = total_latency
        finished_at = str(getattr(stats, "finished_at", "") or "")
        if finished_at:
            updated_at = max(updated_at, finished_at)
        for stage in getattr(stats, "stage_latencies", ()) or ():
            stage_name = str(getattr(stage, "stage_name", "") or "").strip()
            if not stage_name:
                continue
            elapsed_ms = float(getattr(stage, "elapsed_ms", 0.0) or 0.0)
            current = stage_rollups.get(stage_name)
            if current is None:
                stage_rollups[stage_name] = {
                    "stage_name": stage_name,
                    "invocation_count": 1,
                    "latency_ms_sum": elapsed_ms,
                    "latency_ms_min": elapsed_ms,
                    "latency_ms_max": elapsed_ms,
                    "latency_ms_last": elapsed_ms,
                    "updated_at": finished_at,
                }
                continue
            current["invocation_count"] += 1
            current["latency_ms_sum"] += elapsed_ms
            current["latency_ms_min"] = min(float(current["latency_ms_min"]), elapsed_ms)
            current["latency_ms_max"] = max(float(current["latency_ms_max"]), elapsed_ms)
            current["latency_ms_last"] = elapsed_ms
            current["updated_at"] = max(str(current["updated_at"]), finished_at)
        for reason_code in getattr(stats, "degraded_reason_codes", ()) or ():
            normalized_reason = str(reason_code or "").strip()
            if not normalized_reason:
                continue
            current_reason = degraded_rollups.get(normalized_reason)
            if current_reason is None:
                degraded_rollups[normalized_reason] = {
                    "reason_code": normalized_reason,
                    "event_count": 1,
                    "last_seen_at": finished_at,
                }
                continue
            current_reason["event_count"] += 1
            current_reason["last_seen_at"] = max(
                str(current_reason["last_seen_at"]),
                finished_at,
            )
    return RuntimeScopeRollup(
        scope_kind=scope_kind,
        scope_key=scope_key,
        repo_key=repo_key,
        profile_key=profile_key,
        counters=counters,
        latency={
            "latency_ms_sum": round(latency_sum, 6),
            "latency_ms_min": round(latency_min or 0.0, 6),
            "latency_ms_max": round(latency_max, 6),
            "latency_ms_last": round(latency_last, 6),
        },
        updated_at=updated_at,
        stage_latencies=tuple(stage_rollups[name] for name in sorted(stage_rollups)),
        degraded_states=tuple(
            degraded_rollups[name] for name in sorted(degraded_rollups)
        ),
    )


def summarize_scope_rollup(scope: RuntimeScopeRollup | None) -> dict[str, Any] | None:
    if scope is None:
        return None
    payload = scope.to_payload()
    counters = payload.get("counters", {})
    invocation_count = max(0, int(counters.get("invocation_count", 0) or 0))
    latency = dict(payload.get("latency", {}))
    latency_sum = float(latency.get("latency_ms_sum", 0.0) or 0.0)
    latency["latency_ms_avg"] = (
        round(latency_sum / invocation_count, 6) if invocation_count else 0.0
    )
    payload["latency"] = latency
    payload["stage_latencies"] = [
        {
            **dict(item),
            "latency_ms_avg": (
                round(
                    float(item.get("latency_ms_sum", 0.0) or 0.0)
                    / max(1, int(item.get("invocation_count", 0) or 0)),
                    6,
                )
                if int(item.get("invocation_count", 0) or 0) > 0
                else 0.0
            ),
        }
        for item in payload.get("stage_latencies", [])
    ]
    return payload


def build_runtime_scope_map(
    *,
    store: Any,
    latest_match: dict[str, Any] | None,
    excluded_event_classes: tuple[str, ...] = (),
) -> dict[str, dict[str, Any] | None]:
    scope_map: dict[str, dict[str, Any] | None] = {
        "session": None,
        "all_time": summarize_scope_rollup(
            build_scope_rollup_from_invocations(
                scope_kind="all_time",
                scope_key=RUNTIME_STATS_ALL_TIME_SCOPE_KEY,
                invocations=store.list_invocations(
                    exclude_event_classes=excluded_event_classes,
                ),
            )
        ),
        "repo": None,
        "profile": None,
        "repo_profile": None,
    }
    if latest_match is None:
        return scope_map
    match_session = str(latest_match["session_id"])
    match_repo = str(latest_match["repo_key"])
    match_profile = str(latest_match["profile_key"]) or ""
    scope_map["session"] = summarize_scope_rollup(
        build_scope_rollup_from_invocations(
            scope_kind="session",
            scope_key=match_session,
            repo_key=match_repo,
            profile_key=match_profile,
            invocations=store.list_invocations(session_id=match_session),
        )
    )
    scope_map["repo"] = summarize_scope_rollup(
        build_scope_rollup_from_invocations(
            scope_kind="repo",
            scope_key=match_repo,
            repo_key=match_repo,
            profile_key="",
            invocations=store.list_invocations(
                repo_key=match_repo,
                exclude_event_classes=excluded_event_classes,
            ),
        )
    )
    if match_profile:
        scope_map["profile"] = summarize_scope_rollup(
            build_scope_rollup_from_invocations(
                scope_kind="profile",
                scope_key=match_profile,
                repo_key="",
                profile_key=match_profile,
                invocations=store.list_invocations(
                    profile_key=match_profile,
                    exclude_event_classes=excluded_event_classes,
                ),
            )
        )
        scope_map["repo_profile"] = summarize_scope_rollup(
            build_scope_rollup_from_invocations(
                scope_kind="repo_profile",
                scope_key=f"{match_repo}::{match_profile}",
                repo_key=match_repo,
                profile_key=match_profile,
                invocations=store.list_invocations(
                    repo_key=match_repo,
                    profile_key=match_profile,
                    exclude_event_classes=excluded_event_classes,
                ),
            )
        )
    return scope_map


__all__ = [
    "build_runtime_scope_map",
    "build_scope_rollup_from_invocations",
    "summarize_scope_rollup",
]
