from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from ace_lite.mcp_server.config import AceLiteMcpConfig


class RuntimeIdentityPayload(TypedDict):
    pid: int
    process_started_at: str
    process_uptime_seconds: float
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
    staleness_warning: dict[str, Any] | None
    request_stats: dict[str, Any]
    warnings: list[str]
    recommendations: list[str]
    timestamp: str


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
    process_started_at: str,
    process_uptime_seconds: float,
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
        startup_head_commit
        and current_head_commit
        and startup_head_commit != current_head_commit
    )
    stale_reason = "git_head_changed_since_start" if head_changed_since_start else ""
    git_repo_available = bool(startup.get("enabled") or current.get("enabled"))
    return {
        "pid": max(0, int(pid)),
        "process_started_at": str(process_started_at or "").strip(),
        "process_uptime_seconds": max(0.0, round(float(process_uptime_seconds), 3)),
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
    now_iso_fn: Callable[[], str] | None = None,
) -> HealthPayload:
    memory_primary = str(config.memory_primary or "none").strip().lower() or "none"
    memory_secondary = str(config.memory_secondary or "none").strip().lower() or "none"
    memory_disabled = memory_primary == "none" and memory_secondary == "none"
    warnings: list[str] = []
    recommendations: list[str] = []
    if bool(version_info.get("drifted")):
        warnings.append(
            "Version drift detected: pyproject.toml="
            f"{version_info.get('pyproject_version')} but installed metadata="
            f"{version_info.get('installed_version')} (dist={version_info.get('dist_name')}). "
            "Run: python -m pip install -e .[dev]"
        )
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
    if bool(runtime_identity.get("stale_process_suspected")):
        warnings.append(
            "Runtime code appears stale: the git HEAD visible at process start differs from the current source tree. "
            "Restart the long-lived stdio MCP process to load the latest code."
        )
        recommendations.append(
            "Restart the stdio MCP server/session after git pull or pip install -e updates."
        )
    staleness_warning = (
        {
            "triggered": True,
            "reason": str(runtime_identity.get("stale_reason") or "").strip()
            or "git_head_changed_since_start",
            "message": (
                "The source tree visible to this process changed after startup. "
                "Restart the long-lived stdio MCP process to load the latest code."
            ),
            "startup_head_commit": str(runtime_identity.get("startup_head_commit") or "").strip(),
            "current_head_commit": str(runtime_identity.get("current_head_commit") or "").strip(),
        }
        if bool(runtime_identity.get("stale_process_suspected"))
        else None
    )
    timestamp = (
        now_iso_fn()
        if now_iso_fn is not None
        else datetime.now(timezone.utc).isoformat()
    )
    return {
        "ok": True,
        "server_name": config.server_name,
        "version": version,
        "version_info": version_info,
        "default_root": str(config.default_root),
        "default_repo": config.default_repo,
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
        "embedding_provider": str(config.embedding_provider or "hash").strip().lower()
        or "hash",
        "embedding_model": str(config.embedding_model or "hash-v1").strip() or "hash-v1",
        "embedding_dimension": max(1, int(config.embedding_dimension)),
        "embedding_index_path": str(config.embedding_index_path or "").strip()
        or "context-map/embeddings/index.json",
        "ollama_base_url": str(config.ollama_base_url or "").strip()
        or "http://localhost:11434",
        "user_id": config.user_id,
        "app": config.app,
        "runtime_identity": runtime_identity,
        "staleness_warning": staleness_warning,
        "request_stats": request_stats,
        "warnings": warnings,
        "recommendations": recommendations,
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
