"""Report-only history_channel stage.

This stage upgrades the raw ``augment.vcs_history`` git summary into a stable
stage payload that downstream stages can consume without depending on the
augment-stage internals. The output is additive and must not change ranking or
gating decisions.
"""

from __future__ import annotations

from typing import Any

from ace_lite.pipeline.types import StageContext
from ace_lite.source_plan.report_only import build_history_hits


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _str(value: Any) -> str:
    return str(value) if value is not None else ""


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_path(value: Any) -> str:
    return _str(value).strip().replace("\\", "/").lstrip("./")


def _resolve_focused_files(
    *, repomap_stage: dict[str, Any], index_stage: dict[str, Any]
) -> list[str]:
    focused = repomap_stage.get("focused_files")
    if isinstance(focused, list) and focused:
        return [_normalize_path(item) for item in focused if _normalize_path(item)]

    candidates = index_stage.get("candidate_files")
    if not isinstance(candidates, list):
        return []
    return [
        _normalize_path(item.get("path"))
        for item in candidates
        if isinstance(item, dict) and _normalize_path(item.get("path"))
    ]


def _build_recommendations(
    *,
    history_hits: dict[str, Any],
    focused_files: list[str],
) -> list[str]:
    hit_count = _int(history_hits.get("hit_count", 0))
    commit_count = _int(history_hits.get("commit_count", 0))

    recommendations: list[str] = []
    if not focused_files:
        recommendations.append(
            "Establish at least one focus path before trusting history guidance."
        )
    if hit_count > 0:
        recommendations.append(
            "Review the recent matching commits before repeating the same change pattern."
        )
    elif commit_count > 0:
        recommendations.append(
            "Recent commits were found, but none match the current focus paths closely."
        )
    else:
        recommendations.append("No recent commit history matched the current candidate set.")
    if not recommendations:
        recommendations.append(
            "History context is neutral; proceed with direct code evidence first."
        )
    return recommendations[:4]


def run_history_channel(*, ctx: StageContext) -> dict[str, Any]:
    index_stage = _dict(ctx.state.get("index"))
    repomap_stage = _dict(ctx.state.get("repomap"))
    augment_stage = _dict(ctx.state.get("augment"))

    vcs_history = _dict(augment_stage.get("vcs_history"))
    focused_files = _resolve_focused_files(
        repomap_stage=repomap_stage,
        index_stage=index_stage,
    )[:8]
    history_hits = build_history_hits(
        vcs_history=vcs_history,
        focused_files=focused_files,
    )
    policy_name = _str(index_stage.get("policy_name")).strip() or "general"
    policy_version = _str(index_stage.get("policy_version")).strip() or "1"

    enabled = bool(vcs_history.get("enabled", False))
    reason = _str(vcs_history.get("reason")).strip() or "disabled"
    if enabled and _int(history_hits.get("hit_count", 0)) > 0:
        reason = "matched"

    return {
        "schema_version": "history_channel_v1",
        "enabled": enabled,
        "reason": reason,
        "focused_files": list(focused_files),
        "commit_count": _int(history_hits.get("commit_count", 0)),
        "path_count": _int(history_hits.get("path_count", 0)),
        "hit_count": _int(history_hits.get("hit_count", 0)),
        "history_hits": history_hits,
        "recommendations": _build_recommendations(
            history_hits=history_hits,
            focused_files=focused_files,
        ),
        "policy_name": policy_name,
        "policy_version": policy_version,
    }


__all__ = ["run_history_channel"]
