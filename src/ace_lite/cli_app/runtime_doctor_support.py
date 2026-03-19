from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ace_lite.cli_app.runtime_status_support import load_runtime_stats_summary
from ace_lite.config import find_git_root
from ace_lite.stage_artifact_cache_gc import (
    vacuum_stage_artifact_cache,
    verify_stage_artifact_cache,
)
from ace_lite.vcs_history import collect_git_head_snapshot
from ace_lite.vcs_worktree import collect_git_worktree_summary
from ace_lite.version import get_version_info


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


def _classify_git_error(error: str) -> str:
    text = str(error or "").strip().lower()
    if not text:
        return ""
    if (
        "error launching git" in text
        or "not recognized as an internal or external command" in text
        or "no such file or directory" in text
        or "cannot find the file" in text
        or "file not found" in text
        or "winerror 2" in text
    ):
        return "git_unavailable"
    if "timeout" in text:
        return "timeout"
    return "git_error"


def build_runtime_git_doctor_payload(
    *,
    root: str,
    timeout_seconds: float,
    find_git_root_fn: Any = find_git_root,
    collect_git_head_snapshot_fn: Any = collect_git_head_snapshot,
    collect_git_worktree_summary_fn: Any = collect_git_worktree_summary,
) -> dict[str, Any]:
    requested_root = Path(root).resolve()
    repo_root = find_git_root_fn(requested_root) or requested_root
    if not (repo_root / ".git").exists():
        return {
            "ok": True,
            "event": "runtime_doctor_git",
            "enabled": False,
            "requested_root": str(requested_root),
            "repo_root": str(repo_root),
            "reason": "not_git_repo",
            "issue_type": "",
            "git_available": False,
            "recommendations": [],
            "head": {
                "enabled": False,
                "reason": "not_git_repo",
                "head_commit": "",
                "head_ref": "",
                "error": None,
            },
            "worktree": {
                "enabled": False,
                "reason": "not_git_repo",
                "changed_count": 0,
                "entries": [],
                "error": None,
            },
        }

    resolved_timeout = max(0.1, float(timeout_seconds))
    head = collect_git_head_snapshot_fn(
        repo_root=repo_root,
        timeout_seconds=min(1.0, resolved_timeout),
    )
    worktree = collect_git_worktree_summary_fn(
        repo_root=repo_root,
        timeout_seconds=min(1.0, resolved_timeout),
    )

    errors = [
        str(item.get("error") or "").strip()
        for item in (head, worktree)
        if isinstance(item, dict) and str(item.get("error") or "").strip()
    ]
    issue_type = _classify_git_error(errors[0]) if errors else ""
    reasons = {
        str(item.get("reason") or "").strip()
        for item in (head, worktree)
        if isinstance(item, dict)
    }
    recommendations: list[str] = []

    if issue_type == "git_unavailable":
        recommendations.append(
            "Install Git or fix PATH so `git` is launchable from non-interactive subprocesses."
        )
    elif issue_type == "git_error":
        recommendations.append(
            "Run `git status` and `git rev-parse HEAD` manually to inspect the underlying repository error."
        )
    elif issue_type == "timeout" or "timeout" in reasons:
        recommendations.append(
            "Increase git timeout settings or reduce worktree size if runtime git checks are timing out."
        )

    ok = True
    reason = "ok"
    git_available = True
    if issue_type == "git_unavailable":
        ok = False
        reason = "git_unavailable"
        git_available = False
    elif "error" in reasons:
        ok = False
        reason = "error"
    elif "timeout" in reasons:
        ok = False
        reason = "timeout"
    elif "partial" in reasons:
        reason = "partial"

    return {
        "ok": ok,
        "event": "runtime_doctor_git",
        "enabled": True,
        "requested_root": str(requested_root),
        "repo_root": str(repo_root),
        "reason": reason,
        "issue_type": issue_type,
        "git_available": git_available,
        "recommendations": recommendations,
        "head": head,
        "worktree": worktree,
    }


def build_runtime_version_sync_payload(
    *,
    dist_name: str = "ace-lite-engine",
    get_version_info_fn: Any = get_version_info,
) -> dict[str, Any]:
    info = get_version_info_fn(dist_name=dist_name)
    installed_version = str(info.get("installed_version") or "").strip()
    pyproject_version = str(info.get("pyproject_version") or "").strip()
    drifted = bool(info.get("drifted", False))

    if not installed_version:
        reason = "missing_installed_metadata"
        ok = False
        recommendations = ["Run `python -m pip install -e .[dev]` to install editable metadata."]
    elif drifted:
        reason = "install_drift"
        ok = False
        recommendations = ["Run `python -m pip install -e .[dev]` to resync installed metadata."]
    else:
        reason = "ok"
        ok = True
        recommendations = []

    return {
        "ok": ok,
        "event": "runtime_doctor_version_sync",
        "reason": reason,
        "dist_name": str(info.get("dist_name") or dist_name),
        "version": str(info.get("version") or ""),
        "source": str(info.get("source") or ""),
        "pyproject_version": pyproject_version,
        "installed_version": installed_version,
        "drifted": drifted,
        "recommendations": recommendations,
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
    git_payload = build_runtime_git_doctor_payload(
        root=root,
        timeout_seconds=timeout_seconds,
    )
    version_sync = build_runtime_version_sync_payload()
    plugins_payload = (
        resolved.snapshot.get("plan", {}).get("plugins", {})
        if isinstance(resolved.snapshot.get("plan"), dict)
        and isinstance(resolved.snapshot.get("plan", {}).get("plugins"), dict)
        else {}
    )
    return {
        "ok": (
            bool(integration.get("ok"))
            and bool(cache_report.get("ok"))
            and bool(git_payload.get("ok"))
            and bool(version_sync.get("ok"))
        ),
        "event": "runtime_doctor",
        "settings": build_runtime_settings_payload(bundle),
        "stats": runtime_stats,
        "cache": cache_report,
        "git": git_payload,
        "version_sync": version_sync,
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
    "build_runtime_git_doctor_payload",
    "build_runtime_version_sync_payload",
]
