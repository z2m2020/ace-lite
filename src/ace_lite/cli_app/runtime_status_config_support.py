from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


def resolve_runtime_status_repo_relative_path(
    *,
    root: str | Path,
    configured_path: str | Path | None,
) -> str | None:
    if configured_path is None:
        return None
    raw = str(configured_path).strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path(root).resolve() / path
    return str(path.resolve())


def resolve_runtime_feedback_path_from_settings(settings: dict[str, Any]) -> str | None:
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


def resolve_runtime_status_sections(settings: dict[str, Any]) -> RuntimeStatusSections:
    plan = settings.get("plan", {}) if isinstance(settings.get("plan"), dict) else {}
    mcp = settings.get("mcp", {}) if isinstance(settings.get("mcp"), dict) else {}
    return RuntimeStatusSections(
        mcp=mcp,
        plan_index=plan.get("index", {}) if isinstance(plan.get("index"), dict) else {},
        plan_embeddings=(
            plan.get("embeddings", {}) if isinstance(plan.get("embeddings"), dict) else {}
        ),
        plan_replay=(
            plan.get("plan_replay_cache", {})
            if isinstance(plan.get("plan_replay_cache"), dict)
            else {}
        ),
        plan_trace=plan.get("trace", {}) if isinstance(plan.get("trace"), dict) else {},
        plan_lsp=plan.get("lsp", {}) if isinstance(plan.get("lsp"), dict) else {},
        plan_skills=plan.get("skills", {}) if isinstance(plan.get("skills"), dict) else {},
        plan_plugins=(
            plan.get("plugins", {}) if isinstance(plan.get("plugins"), dict) else {}
        ),
        plan_cochange=(
            plan.get("cochange", {}) if isinstance(plan.get("cochange"), dict) else {}
        ),
    )


def build_runtime_status_cache_paths(
    *,
    root_path: Path,
    sections: RuntimeStatusSections,
    runtime_stats: dict[str, Any],
) -> dict[str, str | None]:
    return {
        "index": resolve_runtime_status_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_index.get("cache_path"),
        ),
        "embeddings": resolve_runtime_status_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_embeddings.get("index_path"),
        ),
        "plan_replay_cache": resolve_runtime_status_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_replay.get("cache_path"),
        ),
        "trace_export": resolve_runtime_status_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_trace.get("export_path"),
        )
        if bool(sections.plan_trace.get("export_enabled"))
        else None,
        "memory_notes": resolve_runtime_status_repo_relative_path(
            root=root_path,
            configured_path=sections.mcp.get("notes_path"),
        ),
        "cochange": resolve_runtime_status_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_cochange.get("cache_path"),
        ),
        "runtime_stats_db": str(Path(runtime_stats.get("db_path", "")).resolve()),
        "skills_dir": resolve_runtime_status_repo_relative_path(
            root=root_path,
            configured_path=sections.plan_skills.get("dir"),
        ),
    }


__all__ = [
    "RuntimeStatusSections",
    "build_runtime_status_cache_paths",
    "resolve_runtime_feedback_path_from_settings",
    "resolve_runtime_status_repo_relative_path",
    "resolve_runtime_status_sections",
]
