from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.cli_app.runtime_status_config_support import RuntimeStatusSections
from ace_lite.dev_feedback_taxonomy import describe_dev_feedback_reason


def build_runtime_service_health(
    *,
    cache_paths: dict[str, str | None],
    sections: RuntimeStatusSections,
    memory_state: dict[str, Any],
    runtime_stats: dict[str, Any],
) -> list[dict[str, Any]]:
    skills_dir_path = (
        Path(cache_paths["skills_dir"]) if isinstance(cache_paths["skills_dir"], str) else None
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
            "status": "ok" if bool(sections.plan_plugins.get("enabled", True)) else "disabled",
            "remote_slot_policy_mode": sections.plan_plugins.get("remote_slot_policy_mode"),
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
            "reason": (
                "enabled_without_commands"
                if bool(sections.plan_lsp.get("enabled")) and not lsp_has_commands
                else ""
            ),
        },
        {
            "name": "skills",
            "status": "ok" if skills_dir_path is not None and skills_dir_path.exists() else "degraded",
            "skills_dir": cache_paths["skills_dir"],
            "precomputed_routing_enabled": bool(
                sections.plan_skills.get("precomputed_routing_enabled")
            ),
            "reason": "" if skills_dir_path is not None and skills_dir_path.exists() else "skills_dir_missing",
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
            "latest_session_id": (runtime_stats.get("latest_match", {}) or {}).get("session_id"),
        },
        {
            "name": "preference_capture",
            "status": (
                "ok"
                if int(((runtime_stats.get("preference_capture_summary", {}) or {}).get("event_count", 0) or 0)) > 0
                else "idle"
            ),
            "store_path": (runtime_stats.get("preference_capture_summary", {}) or {}).get("store_path"),
            "event_count": int(
                ((runtime_stats.get("preference_capture_summary", {}) or {}).get("event_count", 0) or 0)
            ),
        },
    ]


def build_runtime_degraded_services(
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
    for item in degraded_states if isinstance(degraded_states, list) else []:
        reason_code = str(item.get("reason_code", "")).strip()
        if not reason_code:
            continue
        reason_details = describe_dev_feedback_reason(reason_code)
        degraded_services.append(
            {
                "name": reason_details["reason_family"],
                "reason": reason_details["reason_code"],
                "capture_class": reason_details["capture_class"],
                "source": "latest_runtime_stats",
            }
        )
    return degraded_services


__all__ = [
    "build_runtime_degraded_services",
    "build_runtime_service_health",
]
