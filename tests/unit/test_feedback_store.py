from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ace_lite.feedback_store import (
    FeedbackBoostConfig,
    SelectionFeedbackStore,
    build_feedback_boosts,
)
from ace_lite.profile_store import ProfileStore


def test_feedback_store_records_and_prunes(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    store = SelectionFeedbackStore(profile_path=profile_path, max_entries=2)

    first = store.record(
        query="fix openmemory provider",
        repo="demo",
        user_id="user-a",
        profile_key="bugfix",
        selected_path="src/demo.py",
        captured_at="2026-01-01T00:00:00+00:00",
        position=1,
    )
    assert first["ok"] is True
    assert first["event_count"] == 1
    assert first["configured_path"] == str(profile_path.resolve())
    assert first["store_path"].endswith("preference_capture.db")
    assert first["path"] == first["store_path"]
    assert first["event"]["user_id"] == "user-a"
    assert first["event"]["profile_key"] == "bugfix"

    second = store.record(
        query="fix openmemory provider",
        repo="demo",
        selected_path="src/other.py",
        captured_at="2026-01-02T00:00:00+00:00",
        position=2,
    )
    assert second["event_count"] == 2

    third = store.record(
        query="fix openmemory provider",
        repo="demo",
        selected_path="src/third.py",
        captured_at="2026-01-03T00:00:00+00:00",
        position=3,
    )
    assert third["event_count"] == 2
    assert third["pruned"] == 1

    events = store.load_events()
    assert [event["selected_path"] for event in events] == [
        "src/other.py",
        "src/third.py",
    ]
    assert events[-1]["user_id"] == ""
    assert events[-1]["profile_key"] == ""


def test_build_feedback_boosts_applies_decay_and_caps(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    store = SelectionFeedbackStore(profile_path=profile_path, max_entries=8)

    store.record(
        query="openmemory 405 dimension mismatch",
        repo="demo",
        selected_path="src/memory.py",
        captured_at="2026-01-01T00:00:00+00:00",
        position=1,
    )
    store.record(
        query="openmemory 405 dimension mismatch",
        repo="demo",
        selected_path="src/memory.py",
        captured_at="2026-02-01T00:00:00+00:00",
        position=1,
    )

    events = store.load_events()
    now_ts = datetime(2026, 2, 2, tzinfo=timezone.utc).timestamp()
    boosts, summary = build_feedback_boosts(
        events=events,
        repo="demo",
        query_terms=["openmemory", "405"],
        boost=FeedbackBoostConfig(boost_per_select=0.6, max_boost=0.75, decay_days=30.0),
        now_ts=now_ts,
    )
    assert summary["enabled"] is True
    assert summary["matched_event_count"] == 2
    assert boosts["src/memory.py"] <= 0.75
    assert boosts["src/memory.py"] > 0.0


def test_feedback_store_record_relativizes_absolute_paths_against_root(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    selected = tmp_path / "src" / "demo.py"
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text("print('demo')\n", encoding="utf-8")

    store = SelectionFeedbackStore(profile_path=profile_path, max_entries=8)
    payload = store.record(
        query="record absolute path",
        repo="demo",
        selected_path=str(selected),
        captured_at="2026-02-01T00:00:00+00:00",
        root_path=tmp_path,
    )

    assert payload["event"]["selected_path"] == "src/demo.py"
    assert store.load_events()[0]["selected_path"] == "src/demo.py"


def test_feedback_store_export_and_replay_roundtrip(tmp_path: Path) -> None:
    source_profile = tmp_path / "source.json"
    replay_profile = tmp_path / "replay.json"
    store = SelectionFeedbackStore(profile_path=source_profile, max_entries=8)
    store.record(
        query="validate token",
        repo="demo",
        user_id="bench-user",
        profile_key="bugfix",
        selected_path="src/app/beta.py",
        captured_at="2026-02-14T00:00:00+00:00",
        position=1,
    )
    store.record(
        query="validate token",
        repo="demo",
        selected_path="src/app/alpha.py",
        captured_at="2026-02-15T00:00:00+00:00",
        position=2,
    )

    exported = store.export(repo="demo")
    assert exported["event_count"] == 2
    assert exported["configured_path"] == str(source_profile.resolve())
    assert exported["store_path"].endswith(".feedback.db")
    assert exported["events"][0]["user_id"] == "bench-user"
    assert exported["events"][0]["profile_key"] == "bugfix"

    replay_store = SelectionFeedbackStore(profile_path=replay_profile, max_entries=8)
    replayed = replay_store.replay(
        events=list(exported["events"]),
        repo="demo",
        reset=True,
    )
    assert replayed["imported"] == 2
    assert replayed["skipped"] == 0
    assert replayed["event_count"] == 2
    assert replayed["configured_path"] == str(replay_profile.resolve())
    assert replayed["store_path"].endswith(".feedback.db")
    assert replay_store.export(repo="demo")["events"] == exported["events"]


def test_feedback_store_stats_and_export_support_scope_filters(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    store = SelectionFeedbackStore(profile_path=profile_path, max_entries=8)
    store.record(
        query="scoped feedback",
        repo="demo",
        user_id="user-a",
        profile_key="bugfix",
        selected_path="src/a.py",
        captured_at="2026-02-14T00:00:00+00:00",
    )
    store.record(
        query="scoped feedback",
        repo="demo",
        user_id="user-b",
        profile_key="docs",
        selected_path="src/b.py",
        captured_at="2026-02-15T00:00:00+00:00",
    )

    exported = store.export(repo="demo", user_id="user-a", profile_key="bugfix")
    assert exported["event_count"] == 1
    assert exported["events"][0]["selected_path"] == "src/a.py"

    stats = store.stats(
        repo="demo",
        user_id="user-b",
        profile_key="docs",
        query_terms=["scoped"],
        boost=FeedbackBoostConfig(boost_per_select=0.2, max_boost=0.5, decay_days=30.0),
        top_n=5,
    )
    assert stats["matched_event_count"] == 1
    assert stats["paths"][0]["selected_path"] == "src/b.py"


def test_feedback_store_reads_legacy_profile_payload_when_durable_store_is_empty(
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "profile.json"
    ProfileStore(path=profile_path).save(
        {
            "preferences": {
                "selection_feedback": {
                    "version": 1,
                    "events": [
                        {
                            "query": "legacy feedback",
                            "repo": "demo",
                            "selected_path": "src/legacy.py",
                            "position": 1,
                            "captured_at": "2026-02-01T00:00:00+00:00",
                            "terms": ["legacy", "feedback"],
                        }
                    ],
                }
            }
        }
    )

    store = SelectionFeedbackStore(profile_path=profile_path, max_entries=8)
    events = store.load_events()

    assert len(events) == 1
    assert events[0]["selected_path"] == "src/legacy.py"
    assert events[0]["query"] == "legacy feedback"


def test_feedback_store_reset_clears_durable_and_legacy_payload(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    store = SelectionFeedbackStore(profile_path=profile_path, max_entries=8)
    store.record(
        query="reset durable event",
        repo="demo",
        selected_path="src/demo.py",
        captured_at="2026-02-14T00:00:00+00:00",
    )
    ProfileStore(path=profile_path).save(
        {
            "preferences": {
                "selection_feedback": {
                    "version": 1,
                    "events": [
                        {
                            "query": "legacy feedback",
                            "repo": "demo",
                            "selected_path": "src/legacy.py",
                            "position": 1,
                            "captured_at": "2026-02-01T00:00:00+00:00",
                            "terms": ["legacy", "feedback"],
                        }
                    ],
                }
            }
        }
    )

    payload = store.reset()

    assert payload["ok"] is True
    assert payload["configured_path"] == str(profile_path.resolve())
    assert payload["store_path"].endswith("preference_capture.db")
    assert store.load_events() == []
    assert ProfileStore(path=profile_path).load().get("preferences", {}) == {}
