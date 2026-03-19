from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from ace_lite.feedback_store import FeedbackBoostConfig, SelectionFeedbackStore
from ace_lite.index_stage.terms import extract_terms
from ace_lite.memory_long_term import build_long_term_capture_service_from_runtime


class FeedbackRecordResponse(TypedDict):
    ok: bool
    root: str
    repo: str
    profile_path: str
    configured_path: str
    store_path: str
    recorded: dict[str, Any]


class FeedbackStatsResponse(TypedDict):
    ok: bool
    root: str
    repo: str
    profile_path: str
    configured_path: str
    store_path: str
    stats: dict[str, Any]


def resolve_feedback_profile_path(
    *,
    root_path: Path,
    profile_path: str | None,
) -> Path:
    profile = (
        Path(profile_path).expanduser()
        if profile_path
        else Path("~/.ace-lite/profile.json").expanduser()
    )
    if not profile.is_absolute():
        return (root_path / profile).resolve()
    return profile.resolve()


def handle_feedback_record_request(
    *,
    query: str,
    selected_path: str,
    repo: str | None,
    user_id: str | None,
    profile_key: str | None,
    root_path: Path,
    default_repo: str,
    profile_path: str | None,
    position: int | None,
    max_entries: int,
) -> FeedbackRecordResponse:
    normalized_query = str(query or "").strip()
    if not normalized_query:
        raise ValueError("query cannot be empty")
    normalized_selected_path = str(selected_path or "").strip()
    if not normalized_selected_path:
        raise ValueError("selected_path cannot be empty")

    resolved_repo = str(repo or default_repo).strip() or default_repo
    profile = resolve_feedback_profile_path(
        root_path=root_path,
        profile_path=profile_path,
    )
    long_term_capture_service = None
    try:
        long_term_capture_service = build_long_term_capture_service_from_runtime(
            root=root_path,
        )
    except Exception:
        long_term_capture_service = None
    store = SelectionFeedbackStore(
        profile_path=profile,
        max_entries=max(0, int(max_entries)),
        long_term_capture_service=long_term_capture_service,
    )
    recorded = store.record(
        query=normalized_query,
        repo=resolved_repo,
        user_id=user_id,
        profile_key=profile_key,
        selected_path=normalized_selected_path,
        position=position,
        root_path=root_path,
    )
    return {
        "ok": True,
        "root": str(root_path),
        "repo": resolved_repo,
        "profile_path": str(store.path),
        "configured_path": str(store.configured_path),
        "store_path": str(store.path),
        "recorded": recorded,
    }


def handle_feedback_stats_request(
    *,
    repo: str | None,
    user_id: str | None,
    profile_key: str | None,
    root_path: Path,
    default_repo: str,
    profile_path: str | None,
    query: str | None,
    boost_per_select: float,
    max_boost: float,
    decay_days: float,
    top_n: int,
    max_entries: int,
) -> FeedbackStatsResponse:
    resolved_repo = str(repo or default_repo).strip() or default_repo
    profile = resolve_feedback_profile_path(
        root_path=root_path,
        profile_path=profile_path,
    )
    store = SelectionFeedbackStore(
        profile_path=profile,
        max_entries=max(0, int(max_entries)),
    )
    query_terms: list[str] | None = None
    normalized_query = str(query or "").strip()
    if normalized_query:
        query_terms = extract_terms(query=normalized_query, memory_stage={})
    stats = store.stats(
        repo=resolved_repo if repo is not None else None,
        user_id=user_id,
        profile_key=profile_key,
        query_terms=query_terms,
        boost=FeedbackBoostConfig(
            boost_per_select=max(0.0, float(boost_per_select)),
            max_boost=max(0.0, float(max_boost)),
            decay_days=max(0.0, float(decay_days)),
        ),
        top_n=max(1, int(top_n)),
    )
    return {
        "ok": True,
        "root": str(root_path),
        "repo": resolved_repo,
        "profile_path": str(store.path),
        "configured_path": str(store.configured_path),
        "store_path": str(store.path),
        "stats": stats,
    }


handle_feedback_record = handle_feedback_record_request
handle_feedback_stats = handle_feedback_stats_request


__all__ = [
    "FeedbackRecordResponse",
    "FeedbackStatsResponse",
    "handle_feedback_record",
    "handle_feedback_record_request",
    "handle_feedback_stats",
    "handle_feedback_stats_request",
    "resolve_feedback_profile_path",
]
