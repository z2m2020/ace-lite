from __future__ import annotations

import json
from pathlib import Path
from threading import Event

import pytest

import ace_lite.router_reward_store as reward_store
from ace_lite.router_reward_store import (
    SCHEMA_VERSION,
    AsyncRewardLogWriter,
    append_reward_event,
    load_reward_events,
    load_reward_events_for_replay,
    make_reward_event,
    normalize_reward_event_for_replay,
    validate_reward_event,
)


def test_make_reward_event_links_chosen_arm_context_and_delayed_reward() -> None:
    event = make_reward_event(
        query_id="qry-001",
        chosen_arm_id="feature_graph",
        reward_source="ci_test_pass",
        reward_value=1.0,
        observed_at="2026-03-10T00:00:00+00:00",
        reward_observed_at="2026-03-10T00:05:30+00:00",
        context_features={
            "intent": "refactor",
            "top_k_files": 4,
            "non_json": Path("src/app.py"),
        },
        is_exploration=True,
        router_mode="shadow",
        shadow_arm_id="general_hybrid",
        reward_metadata={"suite": "unit"},
    )

    assert event["schema_version"] == SCHEMA_VERSION
    assert event["query_id"] == "qry-001"
    assert event["chosen_arm_id"] == "feature_graph"
    assert event["shadow_arm_id"] == "general_hybrid"
    assert event["router_mode"] == "shadow"
    assert event["is_exploration"] is True
    assert event["reward_source"] == "ci_test_pass"
    assert event["reward_value"] == 1.0
    assert event["reward_delay_seconds"] == pytest.approx(330.0)
    assert event["context_features"]["intent"] == "refactor"
    assert event["context_features"]["non_json"] == "src/app.py"
    assert len(str(event["context_fingerprint"])) == 16
    assert str(event["event_id"]).startswith("rwd_")


def test_make_reward_event_rejects_reward_timestamps_before_decision() -> None:
    with pytest.raises(ValueError, match="reward_observed_at must be on or after observed_at"):
        make_reward_event(
            query_id="qry-002",
            chosen_arm_id="general_hybrid",
            reward_source="implicit_acceptance",
            reward_value=1.0,
            observed_at="2026-03-10T00:05:30+00:00",
            reward_observed_at="2026-03-10T00:00:00+00:00",
        )


def test_append_and_load_reward_events_round_trip_and_skip_invalid_rows(tmp_path: Path) -> None:
    output_path = tmp_path / "context-map" / "router" / "rewards.jsonl"
    first = append_reward_event(
        path=output_path,
        event=make_reward_event(
            query_id="qry-100",
            chosen_arm_id="feature_graph",
            reward_source="implicit_acceptance",
            reward_value=0.5,
            observed_at="2026-03-10T00:00:00+00:00",
            reward_observed_at="2026-03-10T00:00:10+00:00",
            context_features={"intent": "bugfix"},
        ),
    )
    second = append_reward_event(
        path=output_path,
        event=make_reward_event(
            query_id="qry-101",
            chosen_arm_id="general_hybrid",
            reward_source="lsp_syntax_pass",
            reward_value=1.0,
            observed_at="2026-03-10T00:01:00+00:00",
            reward_observed_at="2026-03-10T00:01:01+00:00",
        ),
    )
    with output_path.open("a", encoding="utf-8") as fh:
        fh.write("{not-json}\n")
        fh.write(json.dumps({"schema_version": "0.0", "query_id": "bad"}) + "\n")

    loaded = load_reward_events(path=output_path)

    assert loaded == [validate_reward_event(first), validate_reward_event(second)]


def test_async_reward_log_writer_submit_returns_before_background_write_finishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = Event()
    release = Event()

    def fake_append_reward_event(*, path: Path, event: dict[str, object]) -> dict[str, object]:
        _ = path
        started.set()
        assert release.wait(1.0)
        return event

    monkeypatch.setattr(reward_store, "append_reward_event", fake_append_reward_event)

    writer = AsyncRewardLogWriter(path=tmp_path / "rewards.jsonl")
    writer.submit(
        event=make_reward_event(
            query_id="qry-200",
            chosen_arm_id="feature_graph",
            reward_source="implicit_acceptance",
            reward_value=1.0,
        )
    )

    assert started.wait(1.0)
    release.set()
    stats = writer.close()
    assert stats["written_count"] == 1
    assert stats["error_count"] == 0


def test_normalize_reward_event_for_replay_accepts_legacy_aliases() -> None:
    normalized = normalize_reward_event_for_replay(
        {
            "schema_version": "0.9",
            "event_id": "legacy-1",
            "query": "qry-legacy",
            "arm_id": "feature_graph",
            "shadow_arm": "general_hybrid",
            "mode": "shadow",
            "features": {"policy_profile": "feature"},
            "exploration": True,
            "source": "ci_test_pass",
            "reward": 0.5,
            "logged_at": "2026-03-10T00:00:00+00:00",
            "reward_ts": "2026-03-10T00:00:30+00:00",
            "metadata": {"suite": "legacy"},
        }
    )

    assert normalized["schema_version"] == SCHEMA_VERSION
    assert normalized["source_schema_version"] == "0.9"
    assert normalized["source_event_id"] == "legacy-1"
    assert normalized["query_id"] == "qry-legacy"
    assert normalized["chosen_arm_id"] == "feature_graph"
    assert normalized["shadow_arm_id"] == "general_hybrid"
    assert normalized["router_mode"] == "shadow"
    assert normalized["is_exploration"] is True
    assert normalized["reward_source"] == "ci_test_pass"
    assert normalized["reward_value"] == 0.5
    assert normalized["reward_delay_seconds"] == pytest.approx(30.0)


def test_load_reward_events_for_replay_preserves_mixed_schema_rows_and_counts_skips(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "context-map" / "router" / "rewards.jsonl"
    append_reward_event(
        path=output_path,
        event=make_reward_event(
            query_id="qry-current",
            chosen_arm_id="feature_graph",
            reward_source="implicit_acceptance",
            reward_value=1.0,
            observed_at="2026-03-10T00:00:00+00:00",
            reward_observed_at="2026-03-10T00:00:05+00:00",
        ),
    )
    with output_path.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "schema_version": "0.9",
                    "query": "qry-legacy",
                    "arm_id": "general_hybrid",
                    "source": "ci_test_pass",
                    "reward": 0.5,
                    "logged_at": "2026-03-10T00:00:00+00:00",
                    "reward_ts": "2026-03-10T00:00:10+00:00",
                }
            )
            + "\n"
        )
        fh.write("{not-json}\n")

    payload = load_reward_events_for_replay(path=output_path)

    assert payload["total_row_count"] == 3
    assert payload["skipped_row_count"] == 1
    assert payload["source_schema_versions"] == {"1.0": 1, "0.9": 1}
    assert len(payload["events"]) == 2
    assert payload["events"][0]["source_schema_version"] == "1.0"
    assert payload["events"][1]["source_schema_version"] == "0.9"
