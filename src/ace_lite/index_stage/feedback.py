"""Feedback-driven deterministic rerank helpers for the index stage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ace_lite.feedback_store import (
    FeedbackBoostConfig,
    SelectionFeedbackStore,
    build_feedback_boosts,
)
from ace_lite.index_stage.repo_paths import normalize_repo_path


def _resolve_profile_path(*, root: str | Path, configured_path: str | Path) -> Path:
    path = Path(str(configured_path or "").strip() or "~/.ace-lite/profile.json").expanduser()
    if path.is_absolute():
        return path
    return Path(root) / path
def apply_feedback_boost(
    *,
    candidates: list[dict[str, Any]],
    repo: str,
    root: str | Path,
    enabled: bool,
    configured_path: str | Path,
    max_entries: int,
    boost_per_select: float,
    max_boost: float,
    decay_days: float,
    query_terms: list[str],
    policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload: dict[str, Any] = {
        "enabled": bool(enabled),
        "reason": "disabled",
        "path": "",
        "event_count": 0,
        "matched_event_count": 0,
        "boosted_candidate_count": 0,
        "boosted_unique_paths": 0,
        "boost_config": {
            "boost_per_select": float(boost_per_select),
            "max_boost": float(max_boost),
            "decay_days": float(decay_days),
        },
    }

    if not enabled:
        return candidates, payload

    if not bool(policy.get("feedback_enabled", True)):
        payload["reason"] = "disabled_by_policy"
        return candidates, payload

    rows = [dict(item) for item in candidates if isinstance(item, dict)]
    if not rows:
        payload["reason"] = "no_candidates"
        return rows, payload

    if not query_terms:
        payload["reason"] = "empty_query_terms"
        return rows, payload

    profile_path = _resolve_profile_path(root=root, configured_path=configured_path)
    payload["path"] = str(profile_path)
    try:
        store = SelectionFeedbackStore(
            profile_path=profile_path,
            max_entries=max(0, int(max_entries)),
        )
        events = store.load_events()
    except Exception as exc:
        payload["reason"] = "load_error"
        payload["error"] = f"{exc.__class__.__name__}:{exc}"
        return rows, payload

    payload["event_count"] = len(events)
    if not events:
        payload["reason"] = "no_events"
        return rows, payload

    boost_cfg = FeedbackBoostConfig(
        boost_per_select=float(boost_per_select),
        max_boost=float(max_boost),
        decay_days=float(decay_days),
    )
    boosts_by_path, summary = build_feedback_boosts(
        events=events,
        repo=str(repo or "").strip(),
        query_terms=list(query_terms),
        boost=boost_cfg,
    )
    payload["matched_event_count"] = int(summary.get("matched_event_count", 0) or 0)

    if not boosts_by_path:
        payload["reason"] = str(summary.get("reason", "no_boosts"))
        return rows, payload

    boosted_count = 0
    boosted_paths: set[str] = set()
    for row in rows:
        path = normalize_repo_path(row.get("path"), strip_leading_slash=True)
        if not path:
            continue
        boost = float(boosts_by_path.get(path, 0.0) or 0.0)
        if boost <= 0.0:
            continue
        row["score"] = round(float(row.get("score", 0.0) or 0.0) + boost, 6)
        breakdown = row.get("score_breakdown")
        if not isinstance(breakdown, dict):
            breakdown = {}
            row["score_breakdown"] = breakdown
        breakdown["prior_feedback"] = round(
            float(breakdown.get("prior_feedback", 0.0) or 0.0) + boost,
            6,
        )
        boosted_count += 1
        boosted_paths.add(path)

    payload["boosted_candidate_count"] = boosted_count
    payload["boosted_unique_paths"] = len(boosted_paths)
    if boosted_count <= 0:
        payload["reason"] = "no_matching_candidates"
        return rows, payload

    rows.sort(
        key=lambda item: (
            -float(item.get("score", 0.0) or 0.0),
            str(item.get("path") or ""),
        )
    )
    payload["reason"] = "ok"
    return rows, payload


__all__ = ["apply_feedback_boost"]
