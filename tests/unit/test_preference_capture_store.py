from __future__ import annotations

from pathlib import Path

from ace_lite.preference_capture_store import (
    DurablePreferenceCaptureStore,
    normalize_preference_capture_event,
)


def test_preference_capture_store_records_and_lists_events(tmp_path: Path) -> None:
    store = DurablePreferenceCaptureStore(
        db_path=tmp_path / "context-map" / "preference-capture.db"
    )

    recorded = store.record(
        {
            "event_id": "event-1",
            "user_id": "bdxx2",
            "repo_key": "ace-lite",
            "profile_key": "bugfix",
            "preference_kind": "selection_feedback",
            "signal_source": "benchmark",
            "signal_key": "case-01",
            "target_path": "./src\\ace_lite\\feedback_store.py",
            "value_text": "prefer benchmark-observed path",
            "weight": 0.75,
            "payload": {"matched_event_count": 3},
            "created_at": "2026-03-18T00:00:00+00:00",
        }
    )

    assert recorded.target_path == "src/ace_lite/feedback_store.py"

    events = store.list_events(user_id="bdxx2", repo_key="ace-lite", profile_key="bugfix")
    assert len(events) == 1
    assert events[0].event_id == "event-1"
    assert events[0].payload == {"matched_event_count": 3}


def test_preference_capture_store_summary_filters_and_aggregates(tmp_path: Path) -> None:
    store = DurablePreferenceCaptureStore(
        db_path=tmp_path / "context-map" / "preference-capture.db"
    )

    store.record(
        {
            "event_id": "event-1",
            "user_id": "bdxx2",
            "repo_key": "ace-lite",
            "profile_key": "bugfix",
            "preference_kind": "selection_feedback",
            "signal_source": "benchmark",
            "signal_key": "case-01",
            "target_path": "src/ace_lite/feedback_store.py",
            "value_text": "prefer feedback store",
            "weight": 0.5,
            "created_at": "2026-03-18T00:00:00+00:00",
        }
    )
    store.record(
        {
            "event_id": "event-2",
            "user_id": "bdxx2",
            "repo_key": "ace-lite",
            "profile_key": "bugfix",
            "preference_kind": "selection_feedback",
            "signal_source": "benchmark",
            "signal_key": "case-02",
            "target_path": "src/ace_lite/runtime_stats_store.py",
            "value_text": "prefer runtime stats store",
            "weight": 1.25,
            "created_at": "2026-03-18T00:01:00+00:00",
        }
    )
    store.record(
        {
            "event_id": "event-3",
            "user_id": "bdxx2",
            "repo_key": "other-repo",
            "profile_key": "refactor",
            "preference_kind": "note_capture",
            "signal_source": "manual",
            "signal_key": "case-03",
            "target_path": "src/ace_lite/profile_store.py",
            "value_text": "manual note",
            "weight": 2.0,
            "created_at": "2026-03-18T00:02:00+00:00",
        }
    )

    summary = store.summarize(
        repo_key="ace-lite",
        profile_key="bugfix",
        preference_kind="selection_feedback",
        signal_source="benchmark",
    )

    assert summary["event_count"] == 2
    assert summary["distinct_target_path_count"] == 2
    assert summary["total_weight"] == 1.75
    assert summary["latest_created_at"] == "2026-03-18T00:01:00+00:00"
    assert summary["by_kind"] == {"selection_feedback": 2}
    assert summary["by_signal_source"] == {"benchmark": 2}


def test_preference_capture_store_user_id_filters_are_respected(tmp_path: Path) -> None:
    store = DurablePreferenceCaptureStore(
        db_path=tmp_path / "context-map" / "preference-capture.db"
    )

    store.record(
        {
            "event_id": "event-u1",
            "user_id": "user-alpha",
            "repo_key": "ace-lite",
            "profile_key": "bugfix",
            "preference_kind": "retrieval_preference",
            "signal_source": "benchmark",
            "signal_key": "case-01",
            "target_path": "src/ace_lite/feedback_store.py",
            "value_text": "alpha",
            "weight": 0.5,
            "created_at": "2026-03-18T00:00:00+00:00",
        }
    )
    store.record(
        {
            "event_id": "event-u2",
            "user_id": "user-beta",
            "repo_key": "ace-lite",
            "profile_key": "bugfix",
            "preference_kind": "retrieval_preference",
            "signal_source": "benchmark",
            "signal_key": "case-02",
            "target_path": "src/ace_lite/runtime_stats_store.py",
            "value_text": "beta",
            "weight": 1.25,
            "created_at": "2026-03-18T00:01:00+00:00",
        }
    )

    events = store.list_events(user_id="user-alpha", limit=10)
    assert [item.event_id for item in events] == ["event-u1"]

    summary = store.summarize(
        user_id="user-beta",
        repo_key="ace-lite",
        profile_key="bugfix",
        preference_kind="retrieval_preference",
        signal_source="benchmark",
    )
    assert summary["event_count"] == 1
    assert summary["distinct_target_path_count"] == 1
    assert summary["total_weight"] == 1.25

    trimmed = store.trim_events(
        keep_latest=0,
        user_id="user-alpha",
        preference_kind="retrieval_preference",
        signal_source="benchmark",
    )
    assert trimmed == 1
    assert [item.event_id for item in store.list_events(limit=10)] == ["event-u2"]


def test_preference_capture_store_defaults_to_user_db_path(tmp_path: Path) -> None:
    store = DurablePreferenceCaptureStore(home_path=tmp_path)

    assert store.db_path == (tmp_path / ".ace-lite" / "preference_capture.db").resolve()


def test_preference_capture_store_trim_and_delete_events(tmp_path: Path) -> None:
    store = DurablePreferenceCaptureStore(
        db_path=tmp_path / "context-map" / "preference-capture.db"
    )

    for index in range(3):
        store.record(
            {
                "event_id": f"event-{index}",
                "repo_key": "ace-lite",
                "preference_kind": "selection_feedback",
                "signal_source": "feedback_store",
                "signal_key": f"case-{index}",
                "target_path": f"src/file_{index}.py",
                "value_text": f"query {index}",
                "created_at": f"2026-03-18T00:0{index}:00+00:00",
            }
        )

    trimmed = store.trim_events(
        keep_latest=2,
        preference_kind="selection_feedback",
        signal_source="feedback_store",
    )
    assert trimmed == 1
    assert [item.event_id for item in store.list_events(limit=10)] == ["event-2", "event-1"]

    deleted = store.delete_events(event_ids=["event-1"])
    assert deleted == 1
    assert [item.event_id for item in store.list_events(limit=10)] == ["event-2"]


def test_preference_capture_event_normalizes_taxonomy_aliases() -> None:
    event = normalize_preference_capture_event(
        {
            "event_id": "event-1",
            "repo_key": "ace-lite",
            "preference_kind": "validation",
            "signal_source": "feedback",
            "signal_key": "case-1",
            "target_path": "src/app.py",
            "value_text": "prefer validated path",
        }
    )

    assert event.preference_kind == "validation_preference"
    assert event.signal_source == "feedback_store"
