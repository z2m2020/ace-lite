from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import click

from ace_lite.cli_app.runtime_doctor_support import (
    build_runtime_cache_doctor_payload as build_runtime_cache_doctor_payload,
)
from ace_lite.cli_app.runtime_doctor_support import (
    build_runtime_cache_vacuum_payload as build_runtime_cache_vacuum_payload,
)
from ace_lite.cli_app.runtime_doctor_support import (
    build_runtime_doctor_payload,
    build_runtime_git_doctor_payload,
    build_runtime_version_sync_payload,
)
from ace_lite.cli_app.runtime_mcp_ops import (
    extract_memory_channels,
    load_mcp_env_snapshot,
    mcp_env_snapshot_path,
    memory_channels_disabled,
    memory_config_recommendations,
    probe_mcp_memory_endpoint,
    probe_rest_memory_endpoint,
    run_mcp_self_test,
)
from ace_lite.cli_app.runtime_settings_support import (
    build_runtime_settings_governance_payload,
    build_runtime_settings_payload,
    collect_runtime_settings_persist_payload,
    collect_runtime_settings_show_payload,
    evaluate_runtime_memory_state,
    load_runtime_snapshot,
    resolve_runtime_settings_bundle,
)
from ace_lite.cli_app.runtime_settings_support import (
    resolve_effective_runtime_skills_dir as resolve_effective_runtime_skills_dir,
)
from ace_lite.cli_app.runtime_setup_support import (
    build_codex_mcp_setup_plan,
)
from ace_lite.cli_app.runtime_setup_support import (
    execute_codex_mcp_setup_plan as execute_codex_mcp_setup_plan,
)
from ace_lite.cli_app.runtime_status_support import (
    DEFAULT_RUNTIME_STATS_DB_PATH,
    build_runtime_status_payload,
    build_runtime_status_snapshot,
    load_latest_runtime_stats_match,
    load_runtime_dev_feedback_summary,
    load_runtime_preference_capture_summary,
    load_runtime_stats_summary,
    resolve_user_runtime_stats_path,
)


@dataclass(frozen=True)
class RuntimeCommandDomainDescriptor:
    name: str
    handlers: tuple[str, ...]


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _merge_unique_messages(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            normalized = str(item or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
    return merged


def _build_mcp_session_summary(payload: dict[str, Any]) -> dict[str, Any]:
    session_health = _coerce_mapping(payload.get("stdio_session_health"))
    runtime_identity = _coerce_mapping(payload.get("runtime_identity"))
    request_stats = _coerce_mapping(payload.get("request_stats"))
    return {
        "status": str(session_health.get("status") or "unknown"),
        "scope": str(session_health.get("scope") or ""),
        "transport": str(session_health.get("transport") or ""),
        "message": str(session_health.get("message") or ""),
        "restart_recommended": bool(session_health.get("restart_recommended")),
        "reason_codes": list(session_health.get("reason_codes", []))
        if isinstance(session_health.get("reason_codes"), list)
        else [],
        "pid": int(runtime_identity.get("pid") or 0),
        "parent_pid": int(runtime_identity.get("parent_pid") or 0),
        "python_executable": str(runtime_identity.get("python_executable") or ""),
        "cwd": str(runtime_identity.get("current_working_directory") or ""),
        "active_request_count": int(request_stats.get("active_request_count") or 0),
        "current_request_runtime_ms": float(
            request_stats.get("current_request_runtime_ms") or 0.0
        ),
    }


def collect_runtime_mcp_doctor_payload(
    *,
    root: str,
    skills_dir: str,
    python_executable: str,
    timeout_seconds: float,
    mcp_name: str,
    use_snapshot: bool,
    require_memory: bool,
    probe_endpoints: bool,
) -> dict[str, Any]:
    snapshot_env, snapshot_path = load_runtime_snapshot(
        root=root,
        mcp_name=mcp_name,
        use_snapshot=use_snapshot,
        snapshot_path_fn=mcp_env_snapshot_path,
        load_snapshot_fn=load_mcp_env_snapshot,
    )
    payload = run_mcp_self_test(
        root=root,
        skills_dir=skills_dir,
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
        env_overrides=snapshot_env if snapshot_env else None,
    )
    memory_state = evaluate_runtime_memory_state(
        payload=payload,
        root=root,
        skills_dir=skills_dir,
        extract_memory_channels_fn=extract_memory_channels,
        memory_channels_disabled_fn=memory_channels_disabled,
        memory_config_recommendations_fn=memory_config_recommendations,
    )
    primary = str(memory_state["primary"])
    secondary = str(memory_state["secondary"])
    memory_disabled = bool(memory_state["memory_disabled"])

    checks: list[dict[str, Any]] = [
        {
            "name": "self_test",
            "ok": True,
        }
    ]
    warnings = _merge_unique_messages(
        list(memory_state["warnings"]),
        list(payload.get("warnings", [])) if isinstance(payload.get("warnings"), list) else [],
    )
    recommendations = _merge_unique_messages(
        list(memory_state["recommendations"]),
        list(payload.get("recommendations", []))
        if isinstance(payload.get("recommendations"), list)
        else [],
    )
    session_summary = _build_mcp_session_summary(payload)
    checks.append(
        {
            "name": "session_health",
            "ok": str(session_summary.get("status") or "") == "ok",
            "detail": str(session_summary.get("message") or ""),
            "scope": session_summary.get("scope"),
            "transport": session_summary.get("transport"),
        }
    )
    endpoint_checks: list[dict[str, Any]] = []
    ok = True

    if memory_disabled:
        checks.append(
            {
                "name": "memory_configured",
                "ok": False,
                "detail": "memory_primary and memory_secondary are both none",
            }
        )
        warnings.append("Remote memory is disabled (none/none).")
        if require_memory:
            ok = False
    else:
        checks.append(
            {
                "name": "memory_configured",
                "ok": True,
                "primary": primary,
                "secondary": secondary,
            }
        )

    if probe_endpoints and not memory_disabled:
        timeout = max(0.5, float(timeout_seconds))
        channels = {primary, secondary}
        if "mcp" in channels:
            mcp_result = probe_mcp_memory_endpoint(
                base_url=str(payload.get("mcp_base_url") or "http://localhost:8765"),
                timeout_seconds=timeout,
            )
            endpoint_checks.append({"name": "mcp_endpoint", **mcp_result})
        if "rest" in channels:
            rest_result = probe_rest_memory_endpoint(
                base_url=str(payload.get("rest_base_url") or "http://localhost:8765"),
                timeout_seconds=timeout,
                user_id=str(payload.get("user_id") or "codex"),
                app=str(payload.get("app") or "ace-lite"),
            )
            endpoint_checks.append({"name": "rest_endpoint", **rest_result})

        checks.extend(endpoint_checks)
        if (
            require_memory
            and endpoint_checks
            and not any(bool(item.get("ok")) for item in endpoint_checks)
        ):
            ok = False
            warnings.append(
                "All configured memory endpoints failed probing in require-memory mode."
            )
        for item in endpoint_checks:
            if not bool(item.get("ok")):
                warnings.append(
                    f"{item.get('name')}: probe failed ({item.get('error') or item.get('fallback_error') or item.get('primary_error') or 'unknown'})"
                )

    return {
        "ok": ok,
        "event": "mcp_doctor",
        "self_test": payload,
        "session_summary": session_summary,
        "checks": checks,
        "warnings": warnings,
        "recommendations": recommendations,
        "snapshot_loaded": bool(snapshot_env),
        "snapshot_path": str(snapshot_path),
    }


def collect_runtime_mcp_self_test_payload(
    *,
    root: str,
    skills_dir: str,
    python_executable: str,
    timeout_seconds: float,
    mcp_name: str,
    use_snapshot: bool,
    require_memory: bool,
    extract_memory_channels_fn: Any,
    memory_channels_disabled_fn: Any,
    memory_config_recommendations_fn: Any,
    run_mcp_self_test_fn: Any = run_mcp_self_test,
    snapshot_path_fn: Any = mcp_env_snapshot_path,
    load_snapshot_fn: Any = load_mcp_env_snapshot,
) -> dict[str, Any]:
    snapshot_env, snapshot_path = load_runtime_snapshot(
        root=root,
        mcp_name=mcp_name,
        use_snapshot=use_snapshot,
        snapshot_path_fn=snapshot_path_fn,
        load_snapshot_fn=load_snapshot_fn,
    )
    payload = run_mcp_self_test_fn(
        root=root,
        skills_dir=skills_dir,
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
        env_overrides=snapshot_env if snapshot_env else None,
    )
    memory_state = evaluate_runtime_memory_state(
        payload=payload,
        root=root,
        skills_dir=skills_dir,
        extract_memory_channels_fn=extract_memory_channels_fn,
        memory_channels_disabled_fn=memory_channels_disabled_fn,
        memory_config_recommendations_fn=memory_config_recommendations_fn,
    )
    if memory_state["memory_disabled"] and require_memory:
        raise click.ClickException(
            "Memory providers are disabled; rerun with configured Mem0/OpenMemory env vars."
        )
    session_summary = _build_mcp_session_summary(payload)
    return {
        "ok": True,
        "event": "mcp_self_test",
        "payload": payload,
        "session_summary": session_summary,
        "warnings": _merge_unique_messages(
            list(memory_state["warnings"]),
            list(payload.get("warnings", [])) if isinstance(payload.get("warnings"), list) else [],
        ),
        "recommendations": _merge_unique_messages(
            list(memory_state["recommendations"]),
            list(payload.get("recommendations", []))
            if isinstance(payload.get("recommendations"), list)
            else [],
        ),
        "snapshot_loaded": bool(snapshot_env),
        "snapshot_path": str(snapshot_path),
    }


def collect_runtime_status_payload(
    *,
    root: str,
    config_file: str,
    mcp_name: str,
    runtime_profile: str | None,
    use_snapshot: bool,
    current_path: str,
    last_known_good_path: str,
    db_path: str,
    user_id: str | None = None,
    extract_memory_channels_fn: Any,
    memory_channels_disabled_fn: Any,
    memory_config_recommendations_fn: Any,
    snapshot_path_fn: Any = mcp_env_snapshot_path,
    load_snapshot_fn: Any = load_mcp_env_snapshot,
) -> dict[str, Any]:
    bundle = resolve_runtime_settings_bundle(
        root=root,
        config_file=config_file,
        mcp_name=mcp_name,
        runtime_profile=runtime_profile,
        use_snapshot=use_snapshot,
        current_path=current_path,
        last_known_good_path=last_known_good_path,
        snapshot_path_fn=snapshot_path_fn,
        load_snapshot_fn=load_snapshot_fn,
    )
    return {
        "ok": True,
        "event": "runtime_status",
        **build_runtime_status_snapshot(
            root=root,
            bundle=bundle,
            db_path=db_path,
            user_id=user_id,
            extract_memory_channels_fn=extract_memory_channels_fn,
            memory_channels_disabled_fn=memory_channels_disabled_fn,
            memory_config_recommendations_fn=memory_config_recommendations_fn,
        ),
    }

def _build_runtime_command_domain_registry() -> dict[str, RuntimeCommandDomainDescriptor]:
    descriptors = (
        RuntimeCommandDomainDescriptor(
            name="settings",
            handlers=(
                "resolve_runtime_settings_bundle",
                "build_runtime_settings_governance_payload",
                "build_runtime_settings_payload",
                "collect_runtime_settings_persist_payload",
                "collect_runtime_settings_show_payload",
            ),
        ),
        RuntimeCommandDomainDescriptor(
            name="doctor",
            handlers=(
                "collect_runtime_mcp_doctor_payload",
                "collect_runtime_mcp_self_test_payload",
                "build_runtime_cache_doctor_payload",
                "build_runtime_cache_vacuum_payload",
                "build_runtime_git_doctor_payload",
                "build_runtime_version_sync_payload",
                "build_runtime_doctor_payload",
            ),
        ),
        RuntimeCommandDomainDescriptor(
            name="status",
            handlers=(
                "collect_runtime_status_payload",
                "build_runtime_status_snapshot",
                "build_runtime_status_payload",
                "load_runtime_stats_summary",
                "load_latest_runtime_stats_match",
            ),
        ),
        RuntimeCommandDomainDescriptor(
            name="setup",
            handlers=(
                "build_codex_mcp_setup_plan",
                "execute_codex_mcp_setup_plan",
            ),
        ),
    )
    return {descriptor.name: descriptor for descriptor in descriptors}


RUNTIME_COMMAND_DOMAIN_REGISTRY = MappingProxyType(
    _build_runtime_command_domain_registry()
)


def iter_runtime_command_domains() -> tuple[RuntimeCommandDomainDescriptor, ...]:
    return tuple(RUNTIME_COMMAND_DOMAIN_REGISTRY.values())


__all__ = [
    "DEFAULT_RUNTIME_STATS_DB_PATH",
    "RUNTIME_COMMAND_DOMAIN_REGISTRY",
    "build_codex_mcp_setup_plan",
    "build_runtime_doctor_payload",
    "build_runtime_git_doctor_payload",
    "build_runtime_settings_governance_payload",
    "build_runtime_settings_payload",
    "build_runtime_status_payload",
    "build_runtime_status_snapshot",
    "build_runtime_version_sync_payload",
    "collect_runtime_mcp_self_test_payload",
    "collect_runtime_settings_persist_payload",
    "collect_runtime_settings_show_payload",
    "collect_runtime_status_payload",
    "evaluate_runtime_memory_state",
    "iter_runtime_command_domains",
    "load_latest_runtime_stats_match",
    "load_runtime_dev_feedback_summary",
    "load_runtime_preference_capture_summary",
    "load_runtime_snapshot",
    "load_runtime_stats_summary",
    "resolve_runtime_settings_bundle",
    "resolve_user_runtime_stats_path",
]
