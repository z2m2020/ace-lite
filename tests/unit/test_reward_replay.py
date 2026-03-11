from __future__ import annotations

import json
from pathlib import Path

from ace_lite.benchmark.reward_replay import build_reward_replay_payload
from ace_lite.benchmark.reward_replay import write_reward_replay_artifacts
from ace_lite.router_reward_store import append_reward_event
from ace_lite.router_reward_store import make_reward_event


def test_build_reward_replay_payload_summarizes_reward_events() -> None:
    events = [
        make_reward_event(
            query_id="q1",
            chosen_arm_id="feature",
            shadow_arm_id="feature_graph",
            router_mode="shadow",
            context_features={"policy_profile": "feature"},
            is_exploration=False,
            reward_source="benchmark_task_success",
            reward_value=1.0,
            reward_observed_at="2026-03-10T00:00:10+00:00",
            observed_at="2026-03-10T00:00:00+00:00",
        ),
        make_reward_event(
            query_id="q2",
            chosen_arm_id="general_hybrid",
            shadow_arm_id="feature_graph",
            router_mode="observe",
            context_features={"policy_profile": "general"},
            is_exploration=True,
            reward_source="ci_test_pass",
            reward_value=0.5,
            reward_observed_at="2026-03-10T00:00:20+00:00",
            observed_at="2026-03-10T00:00:00+00:00",
        ),
    ]

    payload = build_reward_replay_payload(
        events=events,
        input_path="context-map/router/rewards.jsonl",
    )

    assert len(payload["events"]) == 2
    assert payload["events"][0]["chosen_arm_id"] == "feature"
    assert payload["events"][1]["reward_source"] == "ci_test_pass"
    assert payload["summary"]["input_path"] == "context-map/router/rewards.jsonl"
    assert payload["summary"]["event_count"] == 2
    assert payload["summary"]["query_count"] == 2
    assert payload["summary"]["context_fingerprint_count"] == 2
    assert payload["summary"]["exploration_event_count"] == 1
    assert payload["summary"]["reward_value_mean"] == 0.75
    assert payload["summary"]["reward_delay_max_seconds"] == 20.0
    assert payload["summary"]["chosen_arms"][0]["arm_id"] == "feature"
    assert payload["summary"]["reward_sources"][0]["reward_source"] == "benchmark_task_success"
    assert payload["summary"]["router_modes"][0]["router_mode"] == "observe"
    assert payload["summary"]["schema_versions"][0]["schema_version"]


def test_write_reward_replay_artifacts_writes_dataset_and_summary(tmp_path: Path) -> None:
    input_path = tmp_path / "context-map" / "router" / "rewards.jsonl"
    append_reward_event(
        path=input_path,
        event=make_reward_event(
            query_id="q1",
            chosen_arm_id="feature",
            reward_source="benchmark_task_success",
            reward_value=1.0,
            observed_at="2026-03-10T00:00:00+00:00",
            reward_observed_at="2026-03-10T00:00:05+00:00",
            context_features={"policy_profile": "feature"},
        ),
    )
    with input_path.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "schema_version": "0.9",
                    "query": "q1",
                    "arm_id": "feature",
                    "source": "ci_test_pass",
                    "reward": 0.5,
                    "logged_at": "2026-03-10T00:00:00+00:00",
                    "reward_ts": "2026-03-10T00:00:30+00:00",
                    "features": {"policy_profile": "feature"},
                }
            )
            + "\n"
        )
        fh.write("{not-json}\n")

    outputs = write_reward_replay_artifacts(
        input_path=input_path,
        output_dir=tmp_path / "artifacts" / "benchmark" / "reward-replay",
    )

    dataset_path = Path(outputs["dataset_jsonl"])
    summary_path = Path(outputs["summary_json"])

    assert outputs["event_count"] == 2
    assert outputs["query_count"] == 1
    assert dataset_path.exists()
    assert summary_path.exists()
    dataset_rows = [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(dataset_rows) == 2
    assert dataset_rows[1]["source_schema_version"] == "0.9"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["event_count"] == 2
    assert summary["total_row_count"] == 3
    assert summary["skipped_row_count"] == 1
    assert summary["query_count"] == 1
    assert summary["reward_sources"][0]["reward_source"] == "benchmark_task_success"
