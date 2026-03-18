from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ace_lite.cli_app.runtime_status_support import load_runtime_stats_summary
from ace_lite.stage_artifact_cache_gc import (
    vacuum_stage_artifact_cache,
    verify_stage_artifact_cache,
)


def build_runtime_cache_doctor_payload(
    *,
    root: str,
    db_path: str,
    payload_root: str,
    temp_root: str,
) -> dict[str, Any]:
    report = verify_stage_artifact_cache(
        repo_root=root,
        db_path=db_path or None,
        payload_root=payload_root or None,
        temp_root=temp_root or None,
    )
    severe_issue_count = int(report.get("severe_issue_count", 0) or 0)
    warning_issue_count = int(report.get("warning_issue_count", 0) or 0)
    return {
        "ok": severe_issue_count == 0,
        "event": "runtime_doctor_cache",
        "summary": {
            "severe_issue_count": severe_issue_count,
            "warning_issue_count": warning_issue_count,
        },
        **report,
    }


def build_runtime_cache_vacuum_payload(
    *,
    root: str,
    db_path: str,
    payload_root: str,
    temp_root: str,
    apply: bool,
) -> dict[str, Any]:
    result = vacuum_stage_artifact_cache(
        repo_root=root,
        db_path=db_path or None,
        payload_root=payload_root or None,
        temp_root=temp_root or None,
        apply=apply,
    )
    return {
        "ok": bool(result.get("ok", False)),
        "event": "runtime_cache_vacuum",
        **result,
    }


def build_runtime_doctor_payload(
    *,
    root: str,
    config_file: str,
    skills_dir: str,
    python_executable: str,
    timeout_seconds: float,
    mcp_name: str,
    runtime_profile: str | None,
    use_snapshot: bool,
    require_memory: bool,
    probe_endpoints: bool,
    current_path: str,
    last_known_good_path: str,
    stats_db_path: str,
    user_id: str | None = None,
    cache_db_path: str,
    payload_root: str,
    temp_root: str,
) -> dict[str, Any]:
    from ace_lite.cli_app.runtime_settings_support import (
        build_runtime_settings_payload,
        resolve_effective_runtime_skills_dir,
        resolve_runtime_settings_bundle,
    )
    from ace_lite.cli_app.runtime_command_support import collect_runtime_mcp_doctor_payload

    bundle = resolve_runtime_settings_bundle(
        root=root,
        config_file=config_file,
        mcp_name=mcp_name,
        runtime_profile=runtime_profile,
        use_snapshot=use_snapshot,
        current_path=current_path,
        last_known_good_path=last_known_good_path,
    )
    resolved = bundle["resolved"]
    runtime_stats = load_runtime_stats_summary(
        db_path=stats_db_path,
        user_id=user_id,
        home_path=os.environ.get("HOME")
        or os.environ.get("USERPROFILE")
        or Path.home(),
    )
    cache_report = verify_stage_artifact_cache(
        repo_root=root,
        db_path=cache_db_path or None,
        payload_root=payload_root or None,
        temp_root=temp_root or None,
    )
    effective_skills_dir = resolve_effective_runtime_skills_dir(
        resolved.snapshot,
        skills_dir=skills_dir,
    )
    integration = collect_runtime_mcp_doctor_payload(
        root=root,
        skills_dir=effective_skills_dir,
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
        mcp_name=mcp_name,
        use_snapshot=use_snapshot,
        require_memory=require_memory,
        probe_endpoints=probe_endpoints,
    )
    plugins_payload = (
        resolved.snapshot.get("plan", {}).get("plugins", {})
        if isinstance(resolved.snapshot.get("plan"), dict)
        and isinstance(resolved.snapshot.get("plan", {}).get("plugins"), dict)
        else {}
    )
    return {
        "ok": bool(integration.get("ok")) and bool(cache_report.get("ok")),
        "event": "runtime_doctor",
        "settings": build_runtime_settings_payload(bundle),
        "stats": runtime_stats,
        "cache": cache_report,
        "integration": {
            **integration,
            "plugin_policy": {
                "remote_slot_policy_mode": plugins_payload.get("remote_slot_policy_mode"),
                "remote_slot_allowlist": plugins_payload.get("remote_slot_allowlist"),
            },
        },
    }


__all__ = [
    "build_runtime_cache_doctor_payload",
    "build_runtime_cache_vacuum_payload",
    "build_runtime_doctor_payload",
]
