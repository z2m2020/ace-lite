from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

import ace_lite.cli as cli_module


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def test_cli_feedback_record_stats_and_reset(tmp_path: Path) -> None:
    runner = CliRunner()
    profile_path = tmp_path / "profile.json"
    selected = tmp_path / "src" / "demo.py"
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text("print('demo')\n", encoding="utf-8")

    record = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "record",
            str(selected),
            "--query",
            "openmemory 405 dimension mismatch",
            "--repo",
            "demo",
            "--position",
            "1",
            "--root",
            str(tmp_path),
            "--profile-path",
            str(profile_path),
            "--max-entries",
            "8",
        ],
        env=_cli_env(tmp_path),
    )
    assert record.exit_code == 0
    record_payload = json.loads(record.output)
    assert record_payload["ok"] is True
    assert record_payload["event_count"] == 1
    assert record_payload["event"]["selected_path"] == "src/demo.py"

    stats = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "stats",
            "--repo",
            "demo",
            "--profile-path",
            str(profile_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert stats.exit_code == 0
    stats_payload = json.loads(stats.output)
    assert stats_payload["ok"] is True
    assert stats_payload["matched_event_count"] == 1
    assert stats_payload["unique_paths"] == 1

    reset = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "reset",
            "--profile-path",
            str(profile_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert reset.exit_code == 0
    reset_payload = json.loads(reset.output)
    assert reset_payload["ok"] is True

    after = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "stats",
            "--repo",
            "demo",
            "--profile-path",
            str(profile_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert after.exit_code == 0
    after_payload = json.loads(after.output)
    assert after_payload["matched_event_count"] == 0


def test_cli_feedback_export_and_replay_roundtrip(tmp_path: Path) -> None:
    runner = CliRunner()
    profile_path = tmp_path / "profile.json"
    replay_profile_path = tmp_path / "replay.json"
    export_path = tmp_path / "events.jsonl"
    selected = tmp_path / "src" / "demo.py"
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text("print('demo')\n", encoding="utf-8")

    record = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "record",
            str(selected),
            "--query",
            "feedback replay roundtrip",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--profile-path",
            str(profile_path),
            "--max-entries",
            "8",
        ],
        env=_cli_env(tmp_path),
    )
    assert record.exit_code == 0

    export = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "export",
            "--repo",
            "demo",
            "--output",
            str(export_path),
            "--profile-path",
            str(profile_path),
            "--max-entries",
            "8",
        ],
        env=_cli_env(tmp_path),
    )
    assert export.exit_code == 0
    export_payload = json.loads(export.output)
    assert export_payload["event_count"] == 1
    assert export_path.exists() is True

    replay = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "replay",
            "--input",
            str(export_path),
            "--repo",
            "demo",
            "--reset",
            "--profile-path",
            str(replay_profile_path),
            "--max-entries",
            "8",
        ],
        env=_cli_env(tmp_path),
    )
    assert replay.exit_code == 0
    replay_payload = json.loads(replay.output)
    assert replay_payload["imported"] == 1
    assert replay_payload["skipped"] == 0
    assert replay_payload["event_count"] == 1

    stats = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "stats",
            "--repo",
            "demo",
            "--profile-path",
            str(replay_profile_path),
            "--query",
            "feedback replay roundtrip",
        ],
        env=_cli_env(tmp_path),
    )
    assert stats.exit_code == 0
    stats_payload = json.loads(stats.output)
    assert stats_payload["matched_event_count"] == 1
    assert stats_payload["paths"][0]["selected_path"] == "src/demo.py"
