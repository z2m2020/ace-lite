from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ace_lite.dev_feedback_store import DevFeedbackStore
from ace_lite.feedback_store import SelectionFeedbackStore
from ace_lite.preference_capture_store import DurablePreferenceCaptureStore
from ace_lite.runtime_db import connect_runtime_db
from ace_lite.runtime_paths import DEFAULT_USER_RUNTIME_DB_PATH, resolve_user_runtime_db_path
from ace_lite.runtime_stats import RuntimeScopeRollup
from ace_lite.runtime_stats_schema import (
    RUNTIME_STATS_ALL_TIME_SCOPE_KEY,
    RUNTIME_STATS_INVOCATIONS_TABLE,
    build_runtime_stats_migration_bootstrap,
)
from ace_lite.runtime_stats_store import DurableStatsStore


DEFAULT_RUNTIME_STATS_DB_PATH = DEFAULT_USER_RUNTIME_DB_PATH
RUNTIME_MEMORY_REASON_CODES = frozenset(
    {
        "memory_fallback",
        "memory_namespace_fallback",
    }
)


@dataclass(frozen=True)
class RuntimeStatusSections:
    mcp: dict[str, Any]
    plan_index: dict[str, Any]
    plan_embeddings: dict[str, Any]
    plan_replay: dict[str, Any]
    plan_trace: dict[str, Any]
    plan_lsp: dict[str, Any]
    plan_skills: dict[str, Any]
    plan_plugins: dict[str, Any]
    plan_cochange: dict[str, Any]


def resolve_user_runtime_stats_path(
    *,
    home_path: str | Path | None = None,
    configured_path: str | Path | None = None,
) -> Path:
    base = Path(home_path).expanduser() if home_path is not None else Path.home()
    resolved = resolve_user_runtime_db_path(
        home_path=str(base),
        configured_path=configured_path or DEFAULT_RUNTIME_STATS_DB_PATH,
    )
    return Path(str(resolved)).resolve()


def _normalize_filter_value(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _summarize_scope(scope: RuntimeScopeRollup | None) -> dict[str, Any] | None:
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


def _connect_runtime_stats_db(db_path: Path) -> Any:
    return connect_runtime_db(
        db_path=db_path,
        row_factory=sqlite3.Row,
        migration_bootstrap=build_runtime_stats_migration_bootstrap(),
    )


def load_latest_runtime_stats_match(
    *,
    db_path: str | Path,
    session_id: str | None = None,
    repo_key: str | None = None,
    profile_key: str | None = None,
) -> dict[str, Any] | None:
    resolved_path = Path(db_path).resolve()
    normalized_session = _normalize_filter_value(session_id)
    normalized_repo = _normalize_filter_value(repo_key)
    normalized_profile = _normalize_filter_value(profile_key)
    conn = _connect_runtime_stats_db(resolved_path)
    try:
        clauses: list[str] = []
        params: list[str] = []
        if normalized_session is not None:
            clauses.append("session_id = ?")
            params.append(normalized_session)
        if normalized_repo is not None:
            clauses.append("repo_key = ?")
            params.append(normalized_repo)
        if normalized_profile is not None:
            clauses.append("profile_key = ?")
            params.append(normalized_profile)
        sql = (
            f"SELECT invocation_id, session_id, repo_key, profile_key, finished_at "
            f"FROM {RUNTIME_STATS_INVOCATIONS_TABLE}"
        )
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY finished_at DESC, invocation_id DESC LIMIT 1"
        row = conn.execute(sql, tuple(params)).fetchone()
        if row is None:
            return None
        return {
            "invocation_id": str(row["invocation_id"]),
            "session_id": str(row["session_id"]),
            "repo_key": str(row["repo_key"]),
            "profile_key": str(row["profile_key"]),
            "finished_at": str(row["finished_at"]),
        }
    finally:
        conn.close()


def load_runtime_preference_capture_summary(
    *,
    feedback_path: str | Path | None = None,
    repo_key: str | None = None,
    user_id: str | None = None,
    profile_key: str | None = None,
    home_path: str | Path | None = None,
) -> dict[str, Any]:
    if feedback_path is None:
        base = Path(home_path).expanduser() if home_path is not None else Path.home()
        configured_path = str(base / ".ace-lite" / "profile.json")
    else:
        configured_path = str(feedback_path)
    feedback_store = SelectionFeedbackStore(
        profile_path=configured_path,
        max_entries=512,
    )
    durable_store = DurablePreferenceCaptureStore(db_path=feedback_store.path)
    summary = durable_store.summarize(
        user_id=_normalize_filter_value(user_id),
        repo_key=_normalize_filter_value(repo_key),
        profile_key=_normalize_filter_value(profile_key),
        preference_kind="selection_feedback",
        signal_source="feedback_store",
    )
    payload = dict(summary)
    payload.update(
        {
            "configured_path": str(configured_path),
            "store_path": str(feedback_store.path),
            "user_id": _normalize_filter_value(user_id),
            "repo_key": _normalize_filter_value(repo_key),
            "profile_key": _normalize_filter_value(profile_key),
            "preference_kind": "selection_feedback",
            "signal_source": "feedback_store",
        }
    )
    return payload


def load_runtime_dev_feedback_summary(
    *,
    dev_feedback_path: str | Path | None = None,
    repo_key: str | None = None,
    user_id: str | None = None,
    profile_key: str | None = None,
    home_path: str | Path | None = None,
) -> dict[str, Any]:
    store = DevFeedbackStore(
        db_path=dev_feedback_path,
        home_path=home_path,
    )
    payload = store.summarize(
        repo=_normalize_filter_value(repo_key),
        user_id=_normalize_filter_value(user_id),
        profile_key=_normalize_filter_value(profile_key),
    )
    payload.update(
        {
            "repo_key": _normalize_filter_value(repo_key),
            "user_id": _normalize_filter_value(user_id),
            "profile_key": _normalize_filter_value(profile_key),
        }
    )
    return payload


def _build_runtime_top_pain_summary(
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
        reason_code = str(item.get("reason_code") or "").strip()
        if not reason_code:
            continue
        bucket = merged.setdefault(
            reason_code,
            {
                "reason_code": reason_code,
                "runtime_event_count": 0,
                "manual_issue_count": 0,
                "open_issue_count": 0,
                "fix_count": 0,
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
        reason_code = str(item.get("reason_code") or "").strip()
        if not reason_code:
            continue
        bucket = merged.setdefault(
            reason_code,
            {
                "reason_code": reason_code,
                "runtime_event_count": 0,
                "manual_issue_count": 0,
                "open_issue_count": 0,
                "fix_count": 0,
                "last_seen_at": "",
            },
        )
        bucket["manual_issue_count"] += int(item.get("issue_count", 0) or 0)
        bucket["open_issue_count"] += int(item.get("open_issue_count", 0) or 0)
        bucket["fix_count"] += int(item.get("fix_count", 0) or 0)
        bucket["last_seen_at"] = max(
            str(bucket["last_seen_at"]),
            str(item.get("last_seen_at") or ""),
        )

    rows: list[dict[str, Any]] = []
    for bucket in merged.values():
        total_count = (
            int(bucket["runtime_event_count"])
            + int(bucket["manual_issue_count"])
            + int(bucket["open_issue_count"])
        )
        rows.append({**bucket, "total_count": total_count})
    rows.sort(
        key=lambda item: (
            -int(item.get("total_count", 0) or 0),
            -int(item.get("fix_count", 0) or 0),
            str(item.get("reason_code") or ""),
        )
    )
    return {"count": len(rows), "items": rows[:10]}


def _build_runtime_memory_health_summary(
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
        reason_code = str(item.get("reason_code") or "").strip()
        if reason_code not in RUNTIME_MEMORY_REASON_CODES:
            continue
        memory_items.append(
            {
                "reason_code": reason_code,
                "runtime_event_count": int(item.get("runtime_event_count", 0) or 0),
                "manual_issue_count": int(item.get("manual_issue_count", 0) or 0),
                "open_issue_count": int(item.get("open_issue_count", 0) or 0),
                "fix_count": int(item.get("fix_count", 0) or 0),
                "last_seen_at": str(item.get("last_seen_at") or ""),
            }
        )

    runtime_event_count = sum(
        int(item.get("runtime_event_count", 0) or 0) for item in memory_items
    )
    issue_count = sum(int(item.get("manual_issue_count", 0) or 0) for item in memory_items)
    open_issue_count = sum(int(item.get("open_issue_count", 0) or 0) for item in memory_items)
    fix_count = sum(int(item.get("fix_count", 0) or 0) for item in memory_items)

    return {
        "scope_kind": preferred_scope_name,
        "reason_count": len(memory_items),
        "runtime_event_count": runtime_event_count,
        "issue_count": issue_count,
        "open_issue_count": open_issue_count,
        "fix_count": fix_count,
        "resolution_rate": (
            float(fix_count) / float(issue_count) if issue_count > 0 else 0.0
        ),
        "open_issue_rate": (
            float(open_issue_count) / float(issue_count) if issue_count > 0 else 0.0
        ),
        "memory_stage_latency_ms_avg": latency_mean,
        "reasons": memory_items,
    }


def load_runtime_stats_summary(
    *,
    db_path: str | Path | None = None,
    session_id: str | None = None,
    repo_key: str | None = None,
    user_id: str | None = None,
    profile_key: str | None = None,
    feedback_path: str | Path | None = None,
    dev_feedback_path: str | Path | None = None,
    home_path: str | Path | None = None,
) -> dict[str, Any]:
    resolved_path = resolve_user_runtime_stats_path(
        home_path=home_path,
        configured_path=db_path or DEFAULT_RUNTIME_STATS_DB_PATH,
    )
    normalized_repo = _normalize_filter_value(repo_key)
    normalized_user_id = _normalize_filter_value(user_id)
    normalized_profile = _normalize_filter_value(profile_key)
    store = DurableStatsStore(db_path=resolved_path)
    latest_match = load_latest_runtime_stats_match(
        db_path=resolved_path,
        session_id=session_id,
        repo_key=normalized_repo,
        profile_key=normalized_profile,
    )
    scope_map: dict[str, dict[str, Any] | None] = {
        "session": None,
        "all_time": _summarize_scope(
            store.read_scope(
                scope_kind="all_time",
                scope_key=RUNTIME_STATS_ALL_TIME_SCOPE_KEY,
            )
        ),
        "repo": None,
        "profile": None,
        "repo_profile": None,
    }
    if latest_match is not None:
        snapshot = store.read_snapshot(
            session_id=str(latest_match["session_id"]),
            repo_key=str(latest_match["repo_key"]),
            profile_key=str(latest_match["profile_key"]) or None,
        )
        for scope in snapshot.scopes:
            scope_map[scope.scope_kind] = _summarize_scope(scope)
    scopes = [
        scope_map[name]
        for name in ("session", "all_time", "repo", "profile", "repo_profile")
        if scope_map[name] is not None
    ]
    preference_capture_summary = load_runtime_preference_capture_summary(
        feedback_path=feedback_path,
        repo_key=normalized_repo,
        user_id=normalized_user_id,
        profile_key=normalized_profile,
        home_path=home_path,
    )
    dev_feedback_summary = load_runtime_dev_feedback_summary(
        dev_feedback_path=dev_feedback_path,
        repo_key=normalized_repo,
        user_id=normalized_user_id,
        profile_key=normalized_profile,
        home_path=home_path,
    )
    top_pain_summary = _build_runtime_top_pain_summary(
        runtime_scope_map=scope_map,
        dev_feedback_summary=dev_feedback_summary,
    )
    memory_health_summary = _build_runtime_memory_health_summary(
        runtime_scope_map=scope_map,
        top_pain_summary=top_pain_summary,
    )
    filters = {
        "repo": normalized_repo,
        "profile": normalized_profile,
    }
    if normalized_user_id is not None:
        filters["user_id"] = normalized_user_id
    return {
        "db_path": str(resolved_path),
        "filters": filters,
        "latest_match": latest_match,
        "summary": scope_map,
        "scopes": scopes,
        "preference_capture_summary": preference_capture_summary,
        "dev_feedback_summary": dev_feedback_summary,
        "top_pain_summary": top_pain_summary,
        "memory_health_summary": memory_health_summary,
    }


def _resolve_repo_relative_path(*, root: str | Path, configured_path: str | Path | None) -> str | None:
    if configured_path is None:
        return None
    raw = str(configured_path).strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = Path(root).resolve() / path
    return str(path.resolve())


def _resolve_runtime_feedback_path_from_settings(settings: dict[str, Any]) -> str | None:
    top_level_memory = settings.get("memory")
    if isinstance(top_level_memory, dict):
        feedback = top_level_memory.get("feedback")
        if isinstance(feedback, dict):
            path = str(feedback.get("path") or "").strip()
            if path:
                return path
    for namespace in ("plan", "benchmark"):
        section = settings.get(namespace)
        if not isinstance(section, dict):
            continue
        memory = section.get("memory")
        if not isinstance(memory, dict):
            continue
        feedback = memory.get("feedback")
        if not isinstance(feedback, dict):
            continue
        path = str(feedback.get("path") or "").strip()
        if path:
            return path
    return None


def _resolve_runtime_status_sections(settings: dict[str, Any]) -> RuntimeStatusSections:
    plan = settings.get("plan", {}) if isinstance(settings.get("plan"), dict) else {}
    mcp = settings.get("mcp", {}) if isinstance(settings.get("mcp"), dict) else {}
    return RuntimeStatusSections(
        mcp=mcp,
        plan_index=plan.get("index", {}) if isinstance(plan.get("index"), dict) else {},
        plan_embeddings=(
            plan.get("embeddings", {})
            if isinstance(plan.get("embeddings"), dict)
            else {}
        ),
        plan_replay=(
            plan.get("plan_replay_cache", {})
            if isinstance(plan.get("plan_replay_cache"), dict)
            else {}
        ),
        plan_trace=plan.get("trace", {}) if isinstance(plan.get("trace"), dict) else {},
        plan_lsp=plan.get("lsp", {}) if isinstance(plan.get("lsp"), dict) else {},
        plan_skills=(
            plan.get("skills", {}) if isinstance(plan.get("skills"), dict) else {}
        ),
        plan_plugins=(
            plan.get("plugins", {}) if isinstance(plan.get("plugins"), dict) else {}
        ),
        plan_cochange=(
            plan.get("cochange", {}) if isinstance(plan.get("cochange"), dict) else {}
        ),
    )


def _build_runtime_status_cache_paths(
    *,
    root_path: Path,
    sections: RuntimeStatusSections,
    runtime_stats: dict[str, Any],
) -> dict[str, str | None]:
    return {
        "index": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_index.get("cache_path"),
        ),
        "embeddings": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_embeddings.get("index_path"),
        ),
        "plan_replay_cache": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_replay.get("cache_path"),
        ),
        "trace_export": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_trace.get("export_path"),
        )
        if bool(sections.plan_trace.get("export_enabled"))
        else None,
        "memory_notes": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.mcp.get("notes_path"),
        ),
        "cochange": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_cochange.get("cache_path"),
        ),
        "runtime_stats_db": str(Path(runtime_stats.get("db_path", "")).resolve()),
        "skills_dir": _resolve_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_skills.get("dir"),
        ),
    }


def _build_runtime_service_health(
    *,
    cache_paths: dict[str, str | None],
    sections: RuntimeStatusSections,
    memory_state: dict[str, Any],
    runtime_stats: dict[str, Any],
) -> list[dict[str, Any]]:
    skills_dir_path = (
        Path(cache_paths["skills_dir"])
        if isinstance(cache_paths["skills_dir"], str)
        else None
    )
    lsp_commands = sections.plan_lsp.get("commands")
    lsp_xref_commands = sections.plan_lsp.get("xref_commands")
    lsp_has_commands = bool(lsp_commands) or bool(lsp_xref_commands)
    return [
        {
            "name": "memory",
            "status": "disabled" if bool(memory_state.get("memory_disabled")) else "ok",
            "primary": memory_state.get("primary"),
            "secondary": memory_state.get("secondary"),
            "warnings": list(memory_state.get("warnings", [])),
            "recommendations": list(memory_state.get("recommendations", [])),
        },
        {
            "name": "embeddings",
            "status": "ok" if bool(sections.mcp.get("embedding_enabled")) else "disabled",
            "provider": sections.mcp.get("embedding_provider"),
            "model": sections.mcp.get("embedding_model"),
            "index_path": cache_paths["embeddings"],
        },
        {
            "name": "plugins",
            "status": (
                "ok" if bool(sections.plan_plugins.get("enabled", True)) else "disabled"
            ),
            "remote_slot_policy_mode": sections.plan_plugins.get(
                "remote_slot_policy_mode"
            ),
        },
        {
            "name": "lsp",
            "status": (
                "disabled"
                if not bool(sections.plan_lsp.get("enabled"))
                else ("ok" if lsp_has_commands else "degraded")
            ),
            "enabled": bool(sections.plan_lsp.get("enabled")),
            "commands_configured": lsp_has_commands,
            "reason": "enabled_without_commands"
            if bool(sections.plan_lsp.get("enabled")) and not lsp_has_commands
            else "",
        },
        {
            "name": "skills",
            "status": (
                "ok"
                if skills_dir_path is not None and skills_dir_path.exists()
                else "degraded"
            ),
            "skills_dir": cache_paths["skills_dir"],
            "precomputed_routing_enabled": bool(
                sections.plan_skills.get("precomputed_routing_enabled")
            ),
            "reason": ""
            if skills_dir_path is not None and skills_dir_path.exists()
            else "skills_dir_missing",
        },
        {
            "name": "trace_export",
            "status": (
                "ok"
                if bool(
                    sections.plan_trace.get("export_enabled")
                    or sections.plan_trace.get("otlp_enabled")
                )
                else "disabled"
            ),
            "export_enabled": bool(sections.plan_trace.get("export_enabled")),
            "otlp_enabled": bool(sections.plan_trace.get("otlp_enabled")),
            "export_path": cache_paths["trace_export"],
            "otlp_endpoint": sections.plan_trace.get("otlp_endpoint"),
        },
        {
            "name": "plan_replay_cache",
            "status": "ok" if bool(sections.plan_replay.get("enabled")) else "disabled",
            "enabled": bool(sections.plan_replay.get("enabled")),
            "cache_path": cache_paths["plan_replay_cache"],
        },
        {
            "name": "durable_stats",
            "status": (
                "ok"
                if runtime_stats.get("latest_match") is not None
                or Path(runtime_stats.get("db_path", "")).exists()
                else "idle"
            ),
            "db_path": runtime_stats.get("db_path"),
            "latest_session_id": (
                runtime_stats.get("latest_match", {}) or {}
            ).get("session_id"),
        },
        {
            "name": "preference_capture",
            "status": (
                "ok"
                if int(
                    (
                        runtime_stats.get("preference_capture_summary", {}) or {}
                    ).get("event_count", 0)
                    or 0
                )
                > 0
                else "idle"
            ),
            "store_path": (
                runtime_stats.get("preference_capture_summary", {}) or {}
            ).get("store_path"),
            "event_count": int(
                (
                    runtime_stats.get("preference_capture_summary", {}) or {}
                ).get("event_count", 0)
                or 0
            ),
        },
    ]


def _build_runtime_degraded_services(
    *,
    service_health: list[dict[str, Any]],
    runtime_stats: dict[str, Any],
) -> list[dict[str, Any]]:
    degraded_services = [
        {
            "name": item["name"],
            "reason": item.get("reason") or item.get("status"),
            "source": "service_health",
        }
        for item in service_health
        if item.get("status") == "degraded"
    ]
    latest_session = runtime_stats.get("summary", {}).get("session")
    if not isinstance(latest_session, dict):
        return degraded_services
    degraded_states = latest_session.get("degraded_states", [])
    reason_map = {
        "memory_fallback": "memory",
        "memory_namespace_fallback": "memory",
        "trace_export_failed": "trace_export",
        "plan_replay_invalid_cached_payload": "plan_replay_cache",
        "plan_replay_store_failed": "plan_replay_cache",
        "candidate_ranker_fallback": "retrieval",
        "embedding_time_budget_exceeded": "embeddings",
        "embedding_fallback": "embeddings",
    }
    for item in degraded_states if isinstance(degraded_states, list) else []:
        reason_code = str(item.get("reason_code", "")).strip()
        if not reason_code:
            continue
        degraded_services.append(
            {
                "name": reason_map.get(reason_code, "runtime"),
                "reason": reason_code,
                "source": "latest_runtime_stats",
            }
        )
    return degraded_services


def build_runtime_status_payload(
    *,
    root: str | Path,
    settings: dict[str, Any],
    fingerprint: str,
    selected_profile: str | None,
    stats_tags: dict[str, Any] | None,
    snapshot_loaded: bool,
    snapshot_path: str | Path,
    memory_state: dict[str, Any],
    runtime_stats: dict[str, Any],
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    sections = _resolve_runtime_status_sections(settings)
    cache_paths = _build_runtime_status_cache_paths(
        root_path=root_path,
        sections=sections,
        runtime_stats=runtime_stats,
    )
    service_health = _build_runtime_service_health(
        cache_paths=cache_paths,
        sections=sections,
        memory_state=memory_state,
        runtime_stats=runtime_stats,
    )
    degraded_services = _build_runtime_degraded_services(
        service_health=service_health,
        runtime_stats=runtime_stats,
    )

    return {
        "settings_fingerprint": fingerprint,
        "selected_profile": selected_profile,
        "stats_tags": dict(stats_tags or {}),
        "snapshot_loaded": bool(snapshot_loaded),
        "snapshot_path": str(snapshot_path),
        "cache_paths": cache_paths,
        "service_health": service_health,
        "degraded_services": degraded_services,
        "latest_runtime": {
            "filters": runtime_stats.get("filters"),
            "latest_match": runtime_stats.get("latest_match"),
            "session": runtime_stats.get("summary", {}).get("session"),
            "all_time": runtime_stats.get("summary", {}).get("all_time"),
            "preference_capture_summary": runtime_stats.get(
                "preference_capture_summary"
            ),
            "dev_feedback_summary": runtime_stats.get("dev_feedback_summary"),
            "top_pain_summary": runtime_stats.get("top_pain_summary"),
        },
    }


def build_runtime_status_snapshot(
    *,
    root: str,
    bundle: dict[str, Any],
    db_path: str,
    user_id: str | None = None,
    extract_memory_channels_fn: Any,
    memory_channels_disabled_fn: Any,
    memory_config_recommendations_fn: Any,
) -> dict[str, Any]:
    from ace_lite.cli_app.runtime_settings_support import (
        evaluate_runtime_memory_state,
        resolve_effective_runtime_skills_dir,
    )

    resolved = bundle["resolved"]
    stats_tags = (
        resolved.metadata.get("stats_tags", {})
        if isinstance(resolved.metadata.get("stats_tags", {}), dict)
        else {}
    )
    root_path = Path(root).resolve()
    settings = resolved.snapshot
    skills_dir = resolve_effective_runtime_skills_dir(settings)
    feedback_path = _resolve_repo_relative_path(
        root=root_path,
        configured_path=_resolve_runtime_feedback_path_from_settings(settings),
    )
    memory_state = evaluate_runtime_memory_state(
        payload=settings.get("mcp", {}) if isinstance(settings.get("mcp"), dict) else {},
        root=root,
        skills_dir=skills_dir,
        extract_memory_channels_fn=extract_memory_channels_fn,
        memory_channels_disabled_fn=memory_channels_disabled_fn,
        memory_config_recommendations_fn=memory_config_recommendations_fn,
    )
    runtime_stats = load_runtime_stats_summary(
        db_path=db_path,
        user_id=user_id,
        profile_key=str(stats_tags.get("profile_key") or "").strip() or None,
        feedback_path=feedback_path,
        home_path=os.environ.get("HOME")
        or os.environ.get("USERPROFILE")
        or Path.home(),
    )
    return build_runtime_status_payload(
        root=root,
        settings=settings,
        fingerprint=resolved.fingerprint,
        selected_profile=bundle["selected_profile"],
        stats_tags=stats_tags,
        snapshot_loaded=bool(bundle["snapshot_env"]),
        snapshot_path=bundle["snapshot_path"],
        memory_state=memory_state,
        runtime_stats=runtime_stats,
    )


__all__ = [
    "DEFAULT_RUNTIME_STATS_DB_PATH",
    "RuntimeStatusSections",
    "build_runtime_status_payload",
    "build_runtime_status_snapshot",
    "load_latest_runtime_stats_match",
    "load_runtime_dev_feedback_summary",
    "load_runtime_preference_capture_summary",
    "load_runtime_stats_summary",
    "resolve_user_runtime_stats_path",
]
