from __future__ import annotations

from pathlib import Path

from ace_lite.dev_feedback_store import DevFeedbackStore
from ace_lite.feedback_store import SelectionFeedbackStore
from ace_lite.preference_capture_store import DurablePreferenceCaptureStore


def normalize_runtime_stats_filter_value(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def load_runtime_preference_capture_summary(
    *,
    feedback_path: str | Path | None = None,
    repo_key: str | None = None,
    user_id: str | None = None,
    profile_key: str | None = None,
    home_path: str | Path | None = None,
) -> dict[str, object]:
    if feedback_path is None:
        base = Path(home_path).expanduser() if home_path is not None else Path.home()
        configured_path = str(base / ".ace-lite" / "profile.json")
    else:
        configured_path = str(feedback_path)
    feedback_store = SelectionFeedbackStore(
        profile_path=configured_path,
        max_entries=512,
    )
    durable_store = DurablePreferenceCaptureStore(db_path=feedback_store.path)
    summary = durable_store.summarize(
        user_id=normalize_runtime_stats_filter_value(user_id),
        repo_key=normalize_runtime_stats_filter_value(repo_key),
        profile_key=normalize_runtime_stats_filter_value(profile_key),
        preference_kind="selection_feedback",
        signal_source="feedback_store",
    )
    payload = dict(summary)
    payload.update(
        {
            "configured_path": str(configured_path),
            "store_path": str(feedback_store.path),
            "user_id": normalize_runtime_stats_filter_value(user_id),
            "repo_key": normalize_runtime_stats_filter_value(repo_key),
            "profile_key": normalize_runtime_stats_filter_value(profile_key),
            "preference_kind": "selection_feedback",
            "signal_source": "feedback_store",
        }
    )
    return payload


def load_runtime_dev_feedback_summary(
    *,
    dev_feedback_path: str | Path | None = None,
    repo_key: str | None = None,
    user_id: str | None = None,
    profile_key: str | None = None,
    home_path: str | Path | None = None,
) -> dict[str, object]:
    store = DevFeedbackStore(
        db_path=dev_feedback_path,
        home_path=home_path,
    )
    payload = store.summarize(
        repo=normalize_runtime_stats_filter_value(repo_key),
        user_id=normalize_runtime_stats_filter_value(user_id),
        profile_key=normalize_runtime_stats_filter_value(profile_key),
    )
    payload.update(
        {
            "repo_key": normalize_runtime_stats_filter_value(repo_key),
            "user_id": normalize_runtime_stats_filter_value(user_id),
            "profile_key": normalize_runtime_stats_filter_value(profile_key),
        }
    )
    return payload


__all__ = [
    "load_runtime_dev_feedback_summary",
    "load_runtime_preference_capture_summary",
    "normalize_runtime_stats_filter_value",
]
