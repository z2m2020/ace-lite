from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ace_lite.cli_app.runtime_status_config_support import (
    RuntimeStatusSections,
    build_runtime_status_cache_paths,
    resolve_runtime_feedback_path_from_settings,
    resolve_runtime_status_repo_relative_path,
    resolve_runtime_status_sections,
)
from ace_lite.cli_app.runtime_status_health_support import (
    build_runtime_degraded_services,
    build_runtime_service_health,
)
from ace_lite.cli_app.runtime_stats_query_support import load_latest_runtime_stats_match
from ace_lite.dev_feedback_taxonomy import get_dev_feedback_reason_family
from ace_lite.cli_app.runtime_stats_data_support import (
    load_runtime_dev_feedback_summary,
    load_runtime_preference_capture_summary,
    normalize_runtime_stats_filter_value,
)
from ace_lite.cli_app.runtime_stats_enrichment_support import (
    build_runtime_memory_health_summary,
    build_runtime_top_pain_summary,
)
from ace_lite.runtime_paths import DEFAULT_USER_RUNTIME_DB_PATH, resolve_user_runtime_db_path
from ace_lite.cli_app.runtime_stats_summary_support import build_runtime_scope_map
from ace_lite.runtime_stats_schema import (
    RUNTIME_STATS_DOCTOR_EVENT_CLASS,
)
from ace_lite.runtime_stats_store import DurableStatsStore


DEFAULT_RUNTIME_STATS_DB_PATH = DEFAULT_USER_RUNTIME_DB_PATH


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
    return normalize_runtime_stats_filter_value(value)


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
    excluded_event_classes = (RUNTIME_STATS_DOCTOR_EVENT_CLASS,)
    latest_match = load_latest_runtime_stats_match(
        db_path=resolved_path,
        session_id=session_id,
        repo_key=normalized_repo,
        profile_key=normalized_profile,
    )
    scope_map = build_runtime_scope_map(
        store=store,
        latest_match=latest_match,
        excluded_event_classes=excluded_event_classes,
    )
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
    top_pain_summary = build_runtime_top_pain_summary(
        runtime_scope_map=scope_map,
        dev_feedback_summary=dev_feedback_summary,
    )
    memory_health_summary = build_runtime_memory_health_summary(
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
    sections = resolve_runtime_status_sections(settings)
    cache_paths = build_runtime_status_cache_paths(
        root_path=root_path,
        sections=sections,
        runtime_stats=runtime_stats,
    )
    service_health = build_runtime_service_health(
        cache_paths=cache_paths,
        sections=sections,
        memory_state=memory_state,
        runtime_stats=runtime_stats,
    )
    degraded_services = build_runtime_degraded_services(
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
            "memory_health_summary": runtime_stats.get("memory_health_summary"),
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
    feedback_path = resolve_runtime_status_repo_relative_path(
        root=root_path,
        configured_path=resolve_runtime_feedback_path_from_settings(settings),
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
