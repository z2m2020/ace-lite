from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class OrchestratorAugmentRuntime:
    index_stage: dict[str, Any]
    repomap_stage: dict[str, Any]
    index_files: dict[str, dict[str, Any]]
    candidate_chunks: list[dict[str, Any]]
    vcs_worktree_override: dict[str, Any] | None
    policy_name: str
    policy_version: str


def build_orchestrator_augment_runtime(*, ctx_state: dict[str, Any]) -> OrchestratorAugmentRuntime:
    index_stage = (
        ctx_state.get("index", {})
        if isinstance(ctx_state.get("index"), dict)
        else {}
    )
    repomap_stage = (
        ctx_state.get("repomap", {})
        if isinstance(ctx_state.get("repomap"), dict)
        else {}
    )
    index_files = (
        ctx_state.get("__index_files", {})
        if isinstance(ctx_state.get("__index_files"), dict)
        else {}
    )
    raw_candidate_chunks = (
        index_stage.get("candidate_chunks", []) if isinstance(index_stage, dict) else []
    )
    candidate_chunks = [
        item for item in raw_candidate_chunks if isinstance(item, dict)
    ] if isinstance(raw_candidate_chunks, list) else []
    vcs_worktree_override = ctx_state.get("__vcs_worktree")
    if not isinstance(vcs_worktree_override, dict):
        vcs_worktree_override = None
    policy = (
        ctx_state.get("__policy", {})
        if isinstance(ctx_state.get("__policy"), dict)
        else {}
    )
    return OrchestratorAugmentRuntime(
        index_stage=index_stage,
        repomap_stage=repomap_stage,
        index_files=index_files,
        candidate_chunks=candidate_chunks,
        vcs_worktree_override=vcs_worktree_override,
        policy_name=str(policy.get("name", "general")),
        policy_version=str(policy.get("version", "")),
    )


def resolve_augment_candidates(
    *,
    index_stage: dict[str, Any],
    repomap_stage: dict[str, Any],
    index_files: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    base_candidates = (
        index_stage.get("candidate_files", []) if isinstance(index_stage, dict) else []
    )
    if not isinstance(base_candidates, list):
        base_candidates = []

    focused = (
        repomap_stage.get("focused_files", []) if isinstance(repomap_stage, dict) else []
    )
    if not isinstance(focused, list):
        focused = []
    if not focused:
        return [item for item in base_candidates if isinstance(item, dict)]

    by_path = {
        str(item.get("path", "")): item
        for item in base_candidates
        if isinstance(item, dict) and str(item.get("path", "")).strip()
    }

    resolved: list[dict[str, Any]] = []
    for path in focused:
        relative_path = str(path).strip()
        if not relative_path:
            continue
        if relative_path in by_path:
            resolved.append(by_path[relative_path])
            continue

        entry = index_files.get(relative_path, {}) if isinstance(index_files, dict) else {}
        if not isinstance(entry, dict):
            continue
        resolved.append(
            {
                "path": relative_path,
                "module": entry.get("module", ""),
                "language": entry.get("language", ""),
                "score": 0,
                "symbol_count": len(entry.get("symbols", []))
                if isinstance(entry.get("symbols", []), list)
                else 0,
                "import_count": len(entry.get("imports", []))
                if isinstance(entry.get("imports", []), list)
                else 0,
            }
        )
    return resolved


__all__ = [
    "OrchestratorAugmentRuntime",
    "build_orchestrator_augment_runtime",
    "resolve_augment_candidates",
]
