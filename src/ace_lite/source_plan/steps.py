"""Step construction helpers for the source_plan stage."""

from __future__ import annotations

from typing import Any

from ace_lite.chunking import build_chunk_step_reason
from ace_lite.prompt_rendering.renderer import build_prompt_rendering_boundary


def build_chunk_steps(
    prioritized_chunks: list[dict[str, Any]],
    *,
    chunk_top_k: int,
) -> list[dict[str, Any]]:
    """Build chunk inspection steps from prioritized chunk candidates."""
    limit = max(1, int(chunk_top_k))
    output: list[dict[str, Any]] = []

    for index, item in enumerate(prioritized_chunks[:limit]):
        if not isinstance(item, dict):
            continue
        lineno = int(item.get("lineno") or 0)
        end_lineno = int(item.get("end_lineno") or lineno)
        output.append(
            {
                "id": index + 1,
                "action": "Inspect chunk before opening full file",
                "chunk_ref": {
                    "path": str(item.get("path") or ""),
                    "qualified_name": str(item.get("qualified_name") or ""),
                    "kind": str(item.get("kind") or ""),
                    "lineno": lineno,
                    "end_lineno": end_lineno,
                    "evidence": dict(item.get("evidence"))
                    if isinstance(item.get("evidence"), dict)
                    else {},
                    "disclosure": str(item.get("disclosure") or "refs"),
                    "skeleton_available": isinstance(item.get("skeleton"), dict),
                },
                "reason": build_chunk_step_reason(item),
                "score": float(item.get("score") or 0.0),
            }
        )

    return output


def build_source_plan_steps(
    *,
    index_stage: dict[str, Any],
    repomap_stage: dict[str, Any],
    augment_stage: dict[str, Any],
    skills_stage: dict[str, Any],
    focused_files: list[str],
    prioritized_chunks: list[dict[str, Any]],
    candidate_chunk_count: int,
    suspicious_chunk_count: int,
    diagnostics: list[Any],
    xref: dict[str, Any],
    tests: dict[str, Any],
    validation_tests: list[str],
    subgraph_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build the high-level stage plan steps list for source_plan output."""
    vcs_history = (
        augment_stage.get("vcs_history", {})
        if isinstance(augment_stage.get("vcs_history"), dict)
        else {}
    )
    vcs_worktree = (
        augment_stage.get("vcs_worktree", {})
        if isinstance(augment_stage.get("vcs_worktree"), dict)
        else {}
    )
    recent_subjects: list[str] = []
    commits = vcs_history.get("commits")
    if isinstance(commits, list):
        for item in commits[:3]:
            if not isinstance(item, dict):
                continue
            subject = str(item.get("subject") or "").strip()
            if subject:
                recent_subjects.append(subject)

    changed_files: list[str] = []
    entries = vcs_worktree.get("entries")
    if isinstance(entries, list):
        for item in entries[:3]:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").strip()
            if path:
                changed_files.append(path)

    return [
        {
            "id": 1,
            "stage": "memory",
            "action": "Collect prior facts and constraints from OpenMemory.",
        },
        {
            "id": 2,
            "stage": "index",
            "action": "Resolve candidate files from the distilled index cache and score symbol chunks.",
            "targets": index_stage.get("targets", []),
            "languages_covered": index_stage.get("languages_covered", []),
            "candidate_chunk_count": int(candidate_chunk_count),
        },
        {
            "id": 3,
            "stage": "repomap",
            "action": "Expand seed files with one-hop import neighbors and skeleton map.",
            "seed_count": int(repomap_stage.get("seed_count", 0) or 0),
            "neighbor_count": int(repomap_stage.get("neighbor_count", 0) or 0),
        },
        {
            "id": 4,
            "stage": "augment",
            "action": "Attach diagnostics, xref summary, and test-failure signals.",
            "diagnostic_count": len(diagnostics) if isinstance(diagnostics, list) else 0,
            "xref_count": int(xref.get("count", 0) or 0) if isinstance(xref, dict) else 0,
            "test_failure_count": len(tests.get("failures", []))
            if isinstance(tests, dict) and isinstance(tests.get("failures"), list)
            else 0,
            "suspicious_chunk_count": int(suspicious_chunk_count),
            "vcs_history_enabled": bool(vcs_history.get("enabled", False)),
            "vcs_commit_count": int(vcs_history.get("commit_count", 0) or 0),
            "vcs_recent_subjects": recent_subjects,
            "vcs_worktree_enabled": bool(vcs_worktree.get("enabled", False)),
            "vcs_worktree_changed_count": int(
                vcs_worktree.get("changed_count", 0) or 0
            ),
            "vcs_worktree_changed_files": changed_files,
            "vcs_worktree_error": bool(str(vcs_worktree.get("error") or "").strip()),
        },
        {
            "id": 5,
            "stage": "skills",
            "action": "Lazy-load markdown skill sections for matched intents.",
            "selected": [item.get("name") for item in skills_stage.get("selected", [])]
            if isinstance(skills_stage.get("selected"), list)
            else [],
        },
        {
            "id": 6,
            "stage": "source_plan",
            "action": "Read repomap skeleton first, then open prioritized symbol chunks before full files.",
            "candidate_files": focused_files,
            "candidate_chunks": prioritized_chunks[:24],
            "subgraph_payload": subgraph_payload,
            "prompt_rendering_boundary": build_prompt_rendering_boundary(),
        },
        {
            "id": 7,
            "stage": "validate",
            "action": "Run the minimal suggested test set to verify the change.",
            "suggested_tests": validation_tests,
        },
    ]


__all__ = ["build_chunk_steps", "build_source_plan_steps"]
