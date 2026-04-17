from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from ace_lite.config import resolve_repo_identity
from ace_lite.mcp_server.config import AceLiteMcpConfig
from ace_lite.runtime_fingerprint import (
    build_git_fast_fingerprint,
    build_git_fast_fingerprint_observability,
)
from ace_lite.version import build_repair_steps


class RuntimeIdentityPayload(TypedDict):
    pid: int
    parent_pid: int
    process_started_at: str
    process_uptime_seconds: float
    current_working_directory: str
    python_executable: str
    command_line: list[str]
    source_root: str
    pyproject_path: str
    module_path: str
    startup_head_commit: str
    startup_head_ref: str
    startup_head_reason: str
    current_head_commit: str
    current_head_ref: str
    current_head_reason: str
    git_repo_available: bool
    head_changed_since_start: bool
    stale_process_suspected: bool
    stale_reason: str


class HealthPayload(TypedDict):
    ok: bool
    server_name: str
    version: str
    version_info: dict[str, Any]
    default_root: str
    default_repo: str
    repo_identity: dict[str, Any]
    default_skills_dir: str
    default_languages: str
    default_config_pack: str
    memory_primary: str
    memory_secondary: str
    memory_ready: bool
    plan_timeout_seconds: float
    mcp_base_url: str
    rest_base_url: str
    embedding_enabled: bool
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embedding_index_path: str
    ollama_base_url: str
    user_id: str | None
    app: str
    runtime_identity: RuntimeIdentityPayload
    runtime_fingerprint: dict[str, Any]
    stdio_session_health: dict[str, Any]
    staleness_warning: dict[str, Any] | None
    runtime_sync_warning: dict[str, Any] | None
    request_stats: dict[str, Any]
    settings_governance: dict[str, Any]
    warnings: list[str]
    recommendations: list[str]
    timestamp: str


def _dedupe_non_empty(items: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _safe_resolved_path(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) >= 3 and text[1] == ":" and text[2] in {"/", "\\"}:
        return text
    try:
        return str(Path(text).resolve())
    except Exception:
        return text


def _runtime_sync_requires_restart(runtime_version_info: dict[str, Any]) -> bool:
    sync_state = str(runtime_version_info.get("sync_state") or "").strip()
    if sync_state == "stale_process":
        return True
    mismatch_facts = runtime_version_info.get("mismatch_facts")
    if not isinstance(mismatch_facts, list):
        return False
    mismatch_set = {str(item or "").strip() for item in mismatch_facts}
    return bool(
        {
            "runtime_source_root_mismatch",
            "runtime_pyproject_missing",
        }
        & mismatch_set
    )


def _build_runtime_version_info(
    *,
    version: str,
    version_info: dict[str, Any],
    runtime_identity: RuntimeIdentityPayload,
) -> dict[str, Any]:
    normalized_reason = str(version_info.get("reason_code") or "").strip() or "ok"
    install_mode = str(version_info.get("install_mode") or "").strip() or "unknown"
    install_source_root = str(version_info.get("source_root") or "").strip()
    runtime_source_root = str(runtime_identity.get("source_root") or "").strip()
    runtime_pyproject_path = str(runtime_identity.get("pyproject_path") or "").strip()
    runtime_module_path = str(runtime_identity.get("module_path") or "").strip()
    stale_process = bool(runtime_identity.get("stale_process_suspected"))
    mismatch_facts: list[str] = []

    declared_source_root = _safe_resolved_path(install_source_root)
    effective_runtime_root = _safe_resolved_path(runtime_source_root)
    if install_mode in {"editable", "source_checkout"} and not runtime_pyproject_path:
        mismatch_facts.append("runtime_pyproject_missing")
    if (
        install_mode in {"editable", "source_checkout"}
        and declared_source_root
        and effective_runtime_root
        and declared_source_root != effective_runtime_root
    ):
        mismatch_facts.append("runtime_source_root_mismatch")

    sync_state = "clean"
    if normalized_reason in {"install_drift", "missing_installed_metadata"}:
        sync_state = normalized_reason
    if stale_process:
        sync_state = "mixed_mode" if sync_state != "clean" else "stale_process"
    elif mismatch_facts:
        sync_state = "mixed_mode"

    repair_reason = normalized_reason if normalized_reason != "ok" else sync_state
    repair_steps = build_repair_steps(
        dist_name=str(version_info.get("dist_name") or "ace-lite-engine"),
        install_mode=install_mode,
        source_root=install_source_root or runtime_source_root,
        python_executable=str(runtime_identity.get("python_executable") or "").strip() or None,
        reason_code=repair_reason if repair_reason != "clean" else "ok",
    )
    if stale_process or _runtime_sync_requires_restart(
        {
            "sync_state": sync_state,
            "mismatch_facts": mismatch_facts,
        }
    ):
        repair_steps = _dedupe_non_empty(
            [
                "Restart the long-lived stdio MCP process so it reloads the current checkout.",
                *repair_steps,
            ]
        )

    return {
        "sync_state": sync_state,
        "reason_code": "ok" if sync_state == "clean" else sync_state,
        "runtime_loaded_version": str(version or "").strip(),
        "source_tree_version": str(version_info.get("pyproject_version") or "").strip() or None,
        "installed_metadata_version": (
            str(version_info.get("installed_version") or "").strip() or None
        ),
        "install_mode": install_mode,
        "install_source_root": install_source_root,
        "runtime_source_root": runtime_source_root,
        "runtime_pyproject_path": runtime_pyproject_path,
        "runtime_module_path": runtime_module_path,
        "stale_process_suspected": stale_process,
        "mismatch_facts": mismatch_facts,
        "repair_steps": repair_steps,
        "修复步骤": repair_steps,
    }


def _build_install_drift_guidance(
    version_info: dict[str, Any],
    *,
    runtime_version_info: dict[str, Any],
) -> dict[str, Any] | None:
    reason_code = str(version_info.get("reason_code") or "").strip()
    if reason_code != "install_drift":
        return None
    repair_steps = _dedupe_non_empty(
        [
            *(
                list(runtime_version_info.get("repair_steps", []))
                if isinstance(runtime_version_info.get("repair_steps"), list)
                else []
            ),
            *(
                list(version_info.get("repair_steps", []))
                if isinstance(version_info.get("repair_steps"), list)
                else []
            ),
        ]
    )
    return {
        "triggered": True,
        "reason_code": reason_code,
        "message": (
            "Installed package metadata does not match pyproject.toml. "
            "Reinstall the editable package to resync entry points and metadata."
        ),
        "pyproject_version": str(version_info.get("pyproject_version") or "").strip(),
        "installed_version": str(version_info.get("installed_version") or "").strip(),
        "sync_state": str(runtime_version_info.get("sync_state") or "").strip() or reason_code,
        "runtime_source_root": str(runtime_version_info.get("runtime_source_root") or "").strip(),
        "repair_steps": repair_steps,
        "修复步骤": repair_steps,
    }


def _build_runtime_sync_warning(runtime_version_info: dict[str, Any]) -> dict[str, Any] | None:
    sync_state = str(runtime_version_info.get("sync_state") or "").strip()
    if not sync_state or sync_state == "clean":
        return None
    repair_steps = (
        list(runtime_version_info.get("repair_steps", []))
        if isinstance(runtime_version_info.get("repair_steps"), list)
        else []
    )
    if sync_state == "install_drift":
        message = (
            "Installed metadata and source-tree version are out of sync for this runtime. "
            "Refresh the local install before trusting version-sensitive diagnostics."
        )
    elif sync_state == "missing_installed_metadata":
        message = (
            "Installed package metadata is missing, so this runtime cannot prove its install state. "
            "Reinstall the local package before relying on upgrade validation."
        )
    elif sync_state == "stale_process":
        message = (
            "The long-lived stdio MCP process loaded an older source tree than the current checkout. "
            "Restart it before continuing."
        )
    elif _runtime_sync_requires_restart(runtime_version_info):
        message = (
            "The live MCP process is not loading the editable source tree declared by the current install. "
            "Restart it before trusting plan or health results."
        )
    else:
        message = (
            "The runtime install, source tree, and live process identity do not describe a single clean state. "
            "Resolve the mismatch before treating health results as authoritative."
        )
    return {
        "triggered": True,
        "sync_state": sync_state,
        "reason_code": str(runtime_version_info.get("reason_code") or "").strip() or sync_state,
        "message": message,
        "runtime_loaded_version": runtime_version_info.get("runtime_loaded_version"),
        "source_tree_version": runtime_version_info.get("source_tree_version"),
        "installed_metadata_version": runtime_version_info.get("installed_metadata_version"),
        "mismatch_facts": list(runtime_version_info.get("mismatch_facts", []))
        if isinstance(runtime_version_info.get("mismatch_facts"), list)
        else [],
        "repair_steps": repair_steps,
        "修复步骤": repair_steps,
    }


def _build_runtime_fingerprint_payload(
    *,
    config: AceLiteMcpConfig,
    runtime_identity: RuntimeIdentityPayload,
    settings_governance: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized_settings_governance = (
        dict(settings_governance) if isinstance(settings_governance, dict) else {}
    )
    settings_fingerprint = str(
        normalized_settings_governance.get("resolved_fingerprint") or ""
    ).strip()
    root_path = _safe_resolved_path(str(config.default_root))
    runtime_source_root = _safe_resolved_path(str(runtime_identity.get("source_root") or ""))
    fingerprint = build_git_fast_fingerprint_observability(
        build_git_fast_fingerprint(
            repo_root=root_path or ".",
            settings_fingerprint=settings_fingerprint,
            latency_budget_ms=50.0,
        )
    )
    return {
        "source": "default_root",
        "root_path": root_path,
        "runtime_source_root": runtime_source_root,
        "runtime_source_matches_default_root": bool(
            root_path and runtime_source_root and root_path == runtime_source_root
        ),
        **fingerprint,
    }


def resolve_runtime_source_tree(*, module_path: str | Path) -> dict[str, str]:
    resolved_module_path = Path(module_path).resolve()
    current = resolved_module_path.parent
    for _ in range(10):
        candidate = current / "pyproject.toml"
        if candidate.exists() and candidate.is_file():
            return {
                "source_root": str(current),
                "pyproject_path": str(candidate),
                "module_path": str(resolved_module_path),
            }
        if current.parent == current:
            break
        current = current.parent
    return {
        "source_root": str(resolved_module_path.parent),
        "pyproject_path": "",
        "module_path": str(resolved_module_path),
    }


def build_runtime_identity_payload(
    *,
    pid: int,
    parent_pid: int,
    process_started_at: str,
    process_uptime_seconds: float,
    current_working_directory: str,
    python_executable: str,
    command_line: list[str] | tuple[str, ...],
    source_root: str,
    pyproject_path: str,
    module_path: str,
    startup_head_snapshot: dict[str, Any] | None,
    current_head_snapshot: dict[str, Any] | None,
) -> RuntimeIdentityPayload:
    startup = dict(startup_head_snapshot or {})
    current = dict(current_head_snapshot or {})
    startup_head_commit = str(startup.get("head_commit") or "").strip()
    current_head_commit = str(current.get("head_commit") or "").strip()
    head_changed_since_start = bool(
        startup_head_commit and current_head_commit and startup_head_commit != current_head_commit
    )
    stale_reason = "git_head_changed_since_start" if head_changed_since_start else ""
    git_repo_available = bool(startup.get("enabled") or current.get("enabled"))
    return {
        "pid": max(0, int(pid)),
        "parent_pid": max(0, int(parent_pid)),
        "process_started_at": str(process_started_at or "").strip(),
        "process_uptime_seconds": max(0.0, round(float(process_uptime_seconds), 3)),
        "current_working_directory": str(current_working_directory or "").strip(),
        "python_executable": str(python_executable or "").strip(),
        "command_line": [str(item) for item in command_line if str(item).strip()],
        "source_root": str(source_root or "").strip(),
        "pyproject_path": str(pyproject_path or "").strip(),
        "module_path": str(module_path or "").strip(),
        "startup_head_commit": startup_head_commit,
        "startup_head_ref": str(startup.get("head_ref") or "").strip(),
        "startup_head_reason": str(startup.get("reason") or "").strip(),
        "current_head_commit": current_head_commit,
        "current_head_ref": str(current.get("head_ref") or "").strip(),
        "current_head_reason": str(current.get("reason") or "").strip(),
        "git_repo_available": git_repo_available,
        "head_changed_since_start": head_changed_since_start,
        "stale_process_suspected": head_changed_since_start,
        "stale_reason": stale_reason,
    }


def build_health_response_payload(
    *,
    config: AceLiteMcpConfig,
    request_stats: dict[str, Any],
    version: str,
    version_info: dict[str, Any],
    runtime_identity: RuntimeIdentityPayload,
    settings_governance: dict[str, Any] | None = None,
    now_iso_fn: Callable[[], str] | None = None,
) -> HealthPayload:
    memory_primary = str(config.memory_primary or "none").strip().lower() or "none"
    memory_secondary = str(config.memory_secondary or "none").strip().lower() or "none"
    memory_disabled = memory_primary == "none" and memory_secondary == "none"
    normalized_version_info = dict(version_info or {})
    if (
        bool(normalized_version_info.get("drifted"))
        and not str(normalized_version_info.get("reason_code") or "").strip()
    ):
        normalized_version_info["reason_code"] = "install_drift"
    runtime_version_info = _build_runtime_version_info(
        version=version,
        version_info=normalized_version_info,
        runtime_identity=runtime_identity,
    )
    normalized_version_info["sync_state"] = str(
        runtime_version_info.get("sync_state") or normalized_version_info.get("sync_state") or "clean"
    )
    normalized_version_info["runtime_version_info"] = runtime_version_info
    install_drift_guidance = _build_install_drift_guidance(
        normalized_version_info,
        runtime_version_info=runtime_version_info,
    )
    runtime_sync_warning = _build_runtime_sync_warning(runtime_version_info)
    stale_repair_steps = [
        "Restart the long-lived stdio MCP process so it reloads the current checkout.",
    ]
    warnings: list[str] = []
    recommendations: list[str] = []
    normalized_settings_governance = (
        dict(settings_governance) if isinstance(settings_governance, dict) else {}
    )
    runtime_fingerprint = _build_runtime_fingerprint_payload(
        config=config,
        runtime_identity=runtime_identity,
        settings_governance=normalized_settings_governance,
    )
    config_warnings = (
        list(normalized_settings_governance.get("config_warnings", []))
        if isinstance(normalized_settings_governance.get("config_warnings"), list)
        else []
    )
    runtime_repair_steps = (
        list(runtime_version_info.get("repair_steps", []))
        if isinstance(runtime_version_info.get("repair_steps"), list)
        else []
    )
    if bool(normalized_version_info.get("drifted")):
        recommended_fix = runtime_repair_steps[0] if runtime_repair_steps else "python -m pip install -e .[dev]"
        warnings.append(
            "Version drift detected: pyproject.toml="
            f"{normalized_version_info.get('pyproject_version')} but installed metadata="
            f"{normalized_version_info.get('installed_version')} (dist={normalized_version_info.get('dist_name')}). "
            f"Run: {recommended_fix}"
        )
        recommendations.extend(runtime_repair_steps or [recommended_fix])
    if memory_disabled:
        warnings.append(
            "Memory providers are disabled (ACE_LITE_MEMORY_PRIMARY/SECONDARY are none)."
        )
        recommendations.extend(
            [
                "Set ACE_LITE_MEMORY_PRIMARY=mcp",
                "Set ACE_LITE_MEMORY_SECONDARY=rest",
                "Set ACE_LITE_MCP_BASE_URL / ACE_LITE_REST_BASE_URL to your OpenMemory endpoint",
            ]
        )
    for item in config_warnings:
        if not isinstance(item, dict):
            continue
        message = str(item.get("message") or "").strip()
        code = str(item.get("code") or "").strip()
        if not message:
            continue
        prefix = f"Config consistency warning ({code})" if code else "Config consistency warning"
        warnings.append(f"{prefix}: {message}")
    if config_warnings:
        recommendations.append(
            "Review health.settings_governance.config_warnings to reconcile inactive or conflicting runtime settings."
        )
    if bool(runtime_identity.get("stale_process_suspected")):
        warnings.append(
            "Runtime code appears stale: the git HEAD visible at process start differs from the current source tree. "
            "Restart the long-lived stdio MCP process to load the latest code."
        )
        recommendations.append(
            "Restart the stdio MCP server/session after git pull or pip install -e updates."
        )
    if runtime_sync_warning is not None:
        message = str(runtime_sync_warning.get("message") or "").strip()
        if message:
            warnings.append(message)
        recommendations.extend(
            list(runtime_sync_warning.get("repair_steps", []))
            if isinstance(runtime_sync_warning.get("repair_steps"), list)
            else []
        )
    current_request_runtime_ms = float(request_stats.get("current_request_runtime_ms") or 0.0)
    active_request_count = int(request_stats.get("active_request_count") or 0)
    runtime_sync_requires_restart = (
        runtime_sync_warning is not None
        and _runtime_sync_requires_restart(runtime_version_info)
    )
    if active_request_count > 0 and current_request_runtime_ms >= 30000.0:
        warnings.append(
            "A MCP request has been running for over 30s inside the current process. "
            "This usually indicates a blocked stdio/session or a slow local operation."
        )
        recommendations.append(
            "Inspect health.request_stats.recent_requests and restart the stdio MCP server/session if the request remains stuck."
        )
    command_line = runtime_identity.get("command_line")
    argv = [str(item) for item in command_line] if isinstance(command_line, list) else []
    scope = "self_test_probe" if "--self-test" in argv else "live_process"
    transport = "stdio(default)"
    if "--transport" in argv:
        try:
            transport_value = str(argv[argv.index("--transport") + 1]).strip()
            if transport_value:
                transport = transport_value
        except (IndexError, ValueError):
            transport = "unknown"
    reason_codes: list[str] = []
    if bool(runtime_identity.get("stale_process_suspected")):
        reason_codes.append("stale_process")
    elif runtime_sync_requires_restart:
        reason_codes.append("runtime_sync_mismatch")
    if active_request_count > 0 and current_request_runtime_ms >= 30000.0:
        reason_codes.append("long_running_request")
    stdio_session_health = {
        "scope": scope,
        "transport": transport,
        "status": "warning" if reason_codes else "ok",
        "reason_codes": reason_codes,
        "restart_recommended": bool(reason_codes),
        "active_request_count": active_request_count,
        "current_request_runtime_ms": current_request_runtime_ms,
        "message": (
            "Self-test probe process started cleanly. This probe does not inspect an already-running long-lived stdio MCP session."
            if scope == "self_test_probe" and not reason_codes
            else (
                "No stale-process or stuck-request signal detected for the current MCP process."
                if not reason_codes
                else (
                    "Current MCP process appears stale and should be restarted."
                    if reason_codes == ["stale_process"]
                    else (
                        "Current MCP process is not loading the expected editable source tree and should be restarted."
                        if reason_codes == ["runtime_sync_mismatch"]
                        else (
                            "Current MCP process has a request that appears stuck for over 30s."
                            if reason_codes == ["long_running_request"]
                            else (
                                "Current MCP process appears stale, is loading the wrong source tree, and also has a long-running in-flight request."
                                if "stale_process" in reason_codes
                                and "runtime_sync_mismatch" in reason_codes
                                and "long_running_request" in reason_codes
                                else (
                                    "Current MCP process appears stale and also has a long-running in-flight request."
                                    if reason_codes == ["stale_process", "long_running_request"]
                                    else (
                                        "Current MCP process is loading the wrong source tree and also has a long-running in-flight request."
                                        if reason_codes == ["runtime_sync_mismatch", "long_running_request"]
                                        else "Current MCP process has restart-required runtime sync issues."
                                    )
                                )
                            )
                        )
                    )
                )
            )
        ),
    }
    staleness_warning = (
        {
            "triggered": True,
            "stale_reason": str(runtime_identity.get("stale_reason") or "").strip()
            or "git_head_changed_since_start",
            "reason": str(runtime_identity.get("stale_reason") or "").strip()
            or "git_head_changed_since_start",
            "reason_code": "stale_process",
            "message": (
                "The source tree visible to this process changed after startup. "
                "Restart the long-lived stdio MCP process to load the latest code."
            ),
            "startup_head_commit": str(runtime_identity.get("startup_head_commit") or "").strip(),
            "current_head_commit": str(runtime_identity.get("current_head_commit") or "").strip(),
            "repair_steps": stale_repair_steps,
            "修复步骤": stale_repair_steps,
        }
        if bool(runtime_identity.get("stale_process_suspected"))
        else None
    )
    timestamp = now_iso_fn() if now_iso_fn is not None else datetime.now(timezone.utc).isoformat()
    repo_identity = resolve_repo_identity(
        root=config.default_root,
        repo=config.default_repo,
    )
    return {
        "ok": True,
        "server_name": config.server_name,
        "version": version,
        "version_info": {
            **normalized_version_info,
            "install_drift_guidance": install_drift_guidance,
        },
        "default_root": str(config.default_root),
        "default_repo": config.default_repo,
        "repo_identity": repo_identity,
        "default_skills_dir": str(config.default_skills_dir),
        "default_languages": config.default_languages,
        "default_config_pack": str(config.config_pack or ""),
        "memory_primary": memory_primary,
        "memory_secondary": memory_secondary,
        "memory_ready": not memory_disabled,
        "plan_timeout_seconds": float(config.plan_timeout_seconds),
        "mcp_base_url": config.mcp_base_url,
        "rest_base_url": config.rest_base_url,
        "embedding_enabled": bool(config.embedding_enabled),
        "embedding_provider": str(config.embedding_provider or "hash").strip().lower() or "hash",
        "embedding_model": str(config.embedding_model or "hash-v1").strip() or "hash-v1",
        "embedding_dimension": max(1, int(config.embedding_dimension)),
        "embedding_index_path": str(config.embedding_index_path or "").strip()
        or "context-map/embeddings/index.json",
        "ollama_base_url": str(config.ollama_base_url or "").strip() or "http://localhost:11434",
        "user_id": config.user_id,
        "app": config.app,
        "runtime_identity": runtime_identity,
        "runtime_fingerprint": runtime_fingerprint,
        "stdio_session_health": stdio_session_health,
        "staleness_warning": staleness_warning,
        "runtime_sync_warning": runtime_sync_warning,
        "request_stats": request_stats,
        "settings_governance": normalized_settings_governance,
        "warnings": _dedupe_non_empty(warnings),
        "recommendations": _dedupe_non_empty(recommendations),
        "timestamp": timestamp,
    }


build_health_payload = build_health_response_payload


__all__ = [
    "HealthPayload",
    "RuntimeIdentityPayload",
    "build_health_payload",
    "build_health_response_payload",
    "build_runtime_identity_payload",
    "resolve_runtime_source_tree",
]
