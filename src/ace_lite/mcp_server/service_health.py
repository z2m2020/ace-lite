from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, TypedDict

from ace_lite.mcp_server.config import AceLiteMcpConfig


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
    request_stats: dict[str, Any]
    warnings: list[str]
    recommendations: list[str]
    timestamp: str


def build_health_response_payload(
    *,
    config: AceLiteMcpConfig,
    request_stats: dict[str, Any],
    version: str,
    version_info: dict[str, Any],
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
        "request_stats": request_stats,
        "warnings": warnings,
        "recommendations": recommendations,
        "timestamp": timestamp,
    }


build_health_payload = build_health_response_payload


__all__ = [
    "HealthPayload",
    "build_health_payload",
    "build_health_response_payload",
]
