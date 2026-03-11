from __future__ import annotations

import json
from pathlib import Path

import pytest

from ace_lite import friction


def test_make_event_requires_stage_expected_actual() -> None:
    with pytest.raises(ValueError):
        friction.make_event(stage="", expected="ok", actual="bad")
    with pytest.raises(ValueError):
        friction.make_event(stage="index", expected="", actual="bad")
    with pytest.raises(ValueError):
        friction.make_event(stage="index", expected="ok", actual="")


def test_make_event_normalizes_tags_and_values() -> None:
    event = friction.make_event(
        stage=" quality ",
        expected=" expected ",
        actual=" actual ",
        query=" query text ",
        manual_fix=" fix ",
        severity="High",
        status="Open",
        source=" manual ",
        root_cause=" retrieval-noise ",
        time_cost_min=-3.5,
        tags=["MCP", "mcp", "retrieval", "  "],
        context={"a": 1, "b": {"x": 2}},
        created_at="2026-02-14T00:00:00+00:00",
    )

    assert event["stage"] == "quality"
    assert event["expected"] == "expected"
    assert event["actual"] == "actual"
    assert event["severity"] == "high"
    assert event["status"] == "open"
    assert event["source"] == "manual"
    assert event["time_cost_min"] == 0.0
    assert event["tags"] == ["mcp", "retrieval"]
    assert event["event_id"].startswith("fric_")
    assert len(event["fingerprint"]) == 16


def test_append_load_and_aggregate_roundtrip(tmp_path: Path) -> None:
    log_path = tmp_path / "friction.jsonl"
    event_a = friction.make_event(
        stage="quality_gate",
        expected="pass",
        actual="fail",
        severity="high",
        status="open",
        root_cause="quality_gate_command_failure",
        time_cost_min=6.0,
    )
    event_b = friction.make_event(
        stage="planning",
        expected="focused files",
        actual="noisy files",
        severity="medium",
        status="resolved",
        root_cause="retrieval_noise",
        time_cost_min=3.0,
    )
    friction.append_event(path=log_path, event=event_a)
    friction.append_event(path=log_path, event=event_b)
    log_path.write_text(log_path.read_text(encoding="utf-8") + "{bad\n", encoding="utf-8")

    loaded = friction.load_events(path=log_path)
    summary = friction.aggregate_events(events=loaded, top_n=5)

    assert len(loaded) == 2
    assert summary["event_count"] == 2
    assert summary["open_count"] == 1
    assert summary["severity_counts"]["high"] == 1
    assert summary["severity_counts"]["medium"] == 1
    assert summary["stage_counts"]["planning"] == 1
    assert summary["stage_counts"]["quality_gate"] == 1
    assert summary["mean_time_cost_min"] == 4.5
    assert summary["p95_time_cost_min"] == 6.0

    rows = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line and line.startswith("{\"")
    ]
    assert rows
