from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from ace_lite.cli_app.runtime_stats_enrichment_support import (
    build_runtime_next_cycle_input_summary,
)
from ace_lite.cli_app.runtime_status_support import load_runtime_stats_summary
from ace_lite.config import find_git_root
from ace_lite.dev_feedback_taxonomy import normalize_dev_feedback_reason_code
from ace_lite.runtime_stats import RuntimeInvocationStats, utc_now_iso
from ace_lite.runtime_stats_schema import RUNTIME_STATS_DOCTOR_EVENT_CLASS
from ace_lite.runtime_stats_store import DurableStatsStore
from ace_lite.stage_artifact_cache_gc import (
    vacuum_stage_artifact_cache,
    verify_stage_artifact_cache,
)
from ace_lite.vcs_history import collect_git_head_snapshot
from ace_lite.vcs_worktree import collect_git_worktree_summary
from ace_lite.version import get_version_info


def _collect_runtime_doctor_degraded_reason_codes(
    *,
    cache_report: dict[str, Any],
    git_payload: dict[str, Any],
    version_sync: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if int(cache_report.get("severe_issue_count", 0) or 0) > 0:
        reasons.append("stage_artifact_cache_corrupt")
    if str(git_payload.get("issue_type") or "").strip() == "git_unavailable":
        reasons.append("git_unavailable")
    if str(version_sync.get("reason") or "").strip() == "install_drift":
        reasons.append("install_drift")
    normalized: list[str] = []
    for item in reasons:
        canonical = normalize_dev_feedback_reason_code(item, default="")
        if canonical and canonical not in normalized:
            normalized.append(canonical)
    return normalized


def _resolve_runtime_doctor_repo_key(root: str) -> str:
    requested_root = Path(root).resolve()
    repo_root = find_git_root(requested_root) or requested_root
    return str(repo_root.name or str(repo_root))


def persist_runtime_doctor_invocation(
    *,
    root: str,
    payload: dict[str, Any],
    stats_db_path: str,
    profile_key: str | None = None,
) -> dict[str, Any]:
    degraded_reason_codes = [
        normalize_dev_feedback_reason_code(item, default="")
        for item in payload.get("degraded_reason_codes", [])
        if str(item).strip()
    ]
    degraded_reason_codes = [item for item in degraded_reason_codes if item]
    if not degraded_reason_codes:
        return {
            "enabled": True,
            "recorded": False,
            "reason": "no_degraded_reasons",
            "stats_db_path": str(Path(stats_db_path).expanduser().resolve()),
            "invocation_id": "",
        }

    occurred_at = utc_now_iso()
    repo_key = _resolve_runtime_doctor_repo_key(root)
    normalized_profile = " ".join(str(profile_key or "").strip().split())
    invocation_seed = "|".join(
        (
            "runtime_doctor",
            repo_key,
            normalized_profile,
            occurred_at,
            ",".join(degraded_reason_codes),
        )
    )
    invocation_id = hashlib.sha256(invocation_seed.encode("utf-8")).hexdigest()[:24]
    session_id = f"runtime-doctor::{repo_key}"
    store = DurableStatsStore(db_path=stats_db_path)
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id=invocation_id,
            session_id=session_id,
            repo_key=repo_key,
            profile_key=normalized_profile,
            event_class=RUNTIME_STATS_DOCTOR_EVENT_CLASS,
            settings_fingerprint=str(
                (payload.get("settings", {}) or {}).get("fingerprint") or ""
            ).strip(),
            status="degraded",
            total_latency_ms=0.0,
            started_at=occurred_at,
            finished_at=occurred_at,
            degraded_reason_codes=tuple(degraded_reason_codes),
        )
    )
    return {
        "enabled": True,
        "recorded": True,
        "reason": "recorded",
        "stats_db_path": str(store.db_path),
        "invocation_id": invocation_id,
        "session_id": session_id,
        "repo_key": repo_key,
        "profile_key": normalized_profile,
        "event_class": RUNTIME_STATS_DOCTOR_EVENT_CLASS,
        "degraded_reason_codes": degraded_reason_codes,
    }


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
        str(item.get("reason") or "").strip() for item in (head, worktree) if isinstance(item, dict)
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

    repair_steps = ["python -m pip install -e .[dev]"] if not ok else []

    return {
        "ok": ok,
        "event": "runtime_doctor_version_sync",
        "reason": reason,
        "reason_code": reason,
        "dist_name": str(info.get("dist_name") or dist_name),
        "version": str(info.get("version") or ""),
        "source": str(info.get("source") or ""),
        "pyproject_version": pyproject_version,
        "installed_version": installed_version,
        "drifted": drifted,
        "recommendations": recommendations,
        "repair_steps": repair_steps,
        "修复步骤": repair_steps,
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
    from ace_lite.cli_app.runtime_command_support import collect_runtime_mcp_doctor_payload
    from ace_lite.cli_app.runtime_settings_support import (
        build_runtime_settings_payload,
        resolve_effective_runtime_skills_dir,
        resolve_runtime_settings_bundle,
    )

    requested_root = Path(root).resolve()
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
        home_path=os.environ.get("HOME") or os.environ.get("USERPROFILE") or Path.home(),
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
    if requested_root.exists() and not (requested_root / "pyproject.toml").exists():
        version_sync = {
            **version_sync,
            "ok": True,
            "reason": "not_python_project",
            "reason_code": "not_python_project",
            "recommendations": [],
            "repair_steps": [],
            "淇姝ラ": [],
        }
    plugins_payload = (
        resolved.snapshot.get("plan", {}).get("plugins", {})
        if isinstance(resolved.snapshot.get("plan"), dict)
        and isinstance(resolved.snapshot.get("plan", {}).get("plugins"), dict)
        else {}
    )
    degraded_reason_codes = _collect_runtime_doctor_degraded_reason_codes(
        cache_report=cache_report,
        git_payload=git_payload,
        version_sync=version_sync,
    )
    next_cycle_input = build_runtime_next_cycle_input_summary(
        top_pain_summary=(
            runtime_stats.get("top_pain_summary", {})
            if isinstance(runtime_stats.get("top_pain_summary"), dict)
            else {}
        ),
        memory_health_summary=(
            runtime_stats.get("memory_health_summary", {})
            if isinstance(runtime_stats.get("memory_health_summary"), dict)
            else {}
        ),
        doctor_reason_codes=degraded_reason_codes,
    )
    return {
        "ok": (
            bool(integration.get("ok"))
            and bool(cache_report.get("ok"))
            and bool(git_payload.get("ok"))
            and bool(version_sync.get("ok"))
        ),
        "event": "runtime_doctor",
        "degraded_reason_codes": degraded_reason_codes,
        "settings": build_runtime_settings_payload(bundle),
        "stats": runtime_stats,
        "next_cycle_input": next_cycle_input,
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
    "_collect_runtime_doctor_degraded_reason_codes",
    "build_runtime_cache_doctor_payload",
    "build_runtime_cache_vacuum_payload",
    "build_runtime_doctor_payload",
    "build_runtime_git_doctor_payload",
    "build_runtime_version_sync_payload",
    "persist_runtime_doctor_invocation",
]
