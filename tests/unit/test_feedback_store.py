from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ace_lite.feedback_store import (
    FeedbackBoostConfig,
    SelectionFeedbackStore,
    build_feedback_boosts,
)


def test_feedback_store_records_and_prunes(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    store = SelectionFeedbackStore(profile_path=profile_path, max_entries=2)

    first = store.record(
        query="fix openmemory provider",
        repo="demo",
        selected_path="src/demo.py",
        captured_at="2026-01-01T00:00:00+00:00",
        position=1,
    )
    assert first["ok"] is True
    assert first["event_count"] == 1

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

    replay_store = SelectionFeedbackStore(profile_path=replay_profile, max_entries=8)
    replayed = replay_store.replay(
        events=list(exported["events"]),
        repo="demo",
        reset=True,
    )
    assert replayed["imported"] == 2
    assert replayed["skipped"] == 0
    assert replayed["event_count"] == 2
    assert replay_store.export(repo="demo")["events"] == exported["events"]
