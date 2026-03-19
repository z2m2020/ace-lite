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
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
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
    assert record_payload["configured_path"] == str(profile_path.resolve())
    assert record_payload["store_path"].endswith("preference_capture.db")
    assert record_payload["path"] == record_payload["store_path"]
    assert record_payload["event"]["selected_path"] == "src/demo.py"
    assert record_payload["event"]["user_id"] == "cli-user"
    assert record_payload["event"]["profile_key"] == "bugfix"

    stats = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "stats",
            "--repo",
            "demo",
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
            "--profile-path",
            str(profile_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert stats.exit_code == 0
    stats_payload = json.loads(stats.output)
    assert stats_payload["ok"] is True
    assert stats_payload["configured_path"] == str(profile_path.resolve())
    assert stats_payload["store_path"].endswith("preference_capture.db")
    assert stats_payload["matched_event_count"] == 1
    assert stats_payload["unique_paths"] == 1
    assert stats_payload["user_id_filter"] == "cli-user"
    assert stats_payload["profile_key_filter"] == "bugfix"

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
    assert reset_payload["configured_path"] == str(profile_path.resolve())
    assert reset_payload["store_path"].endswith("preference_capture.db")

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
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
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
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
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
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
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
    assert replay_payload["configured_path"] == str(replay_profile_path.resolve())
    assert replay_payload["store_path"].endswith(".feedback.db")
    assert replay_payload["user_id_override"] == "cli-user"
    assert replay_payload["profile_key_override"] == "bugfix"

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
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
        ],
        env=_cli_env(tmp_path),
    )
    assert stats.exit_code == 0
    stats_payload = json.loads(stats.output)
    assert stats_payload["matched_event_count"] == 1
    assert stats_payload["paths"][0]["selected_path"] == "src/demo.py"
    assert stats_payload["user_id_filter"] == "cli-user"
    assert stats_payload["profile_key_filter"] == "bugfix"


def test_cli_feedback_record_mirrors_to_long_term_memory_when_enabled(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    profile_path = tmp_path / "profile.json"
    selected = tmp_path / "src" / "demo.py"
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text("print('demo')\n", encoding="utf-8")
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "plan:\n"
            "  memory:\n"
            "    long_term:\n"
            "      enabled: true\n"
            "      write_enabled: true\n"
            "      path: context-map/long_term_memory.db\n"
        ),
        encoding="utf-8",
    )

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
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
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
    assert record_payload["long_term_capture"]["ok"] is True
    assert record_payload["long_term_capture"]["stage"] == "selection_feedback"

    long_term_path = tmp_path / "context-map" / "long_term_memory.db"
    assert long_term_path.exists() is True


def test_cli_feedback_issue_report_round_trip(tmp_path: Path) -> None:
    runner = CliRunner()
    selected = tmp_path / "src" / "demo.py"
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text("print('demo')\n", encoding="utf-8")

    recorded = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "report-issue",
            "--title",
            "validation payload missing selected path",
            "--query",
            "validation missing selected path",
            "--repo",
            "demo",
            "--actual-behavior",
            "selected path missing from validation payload",
            "--expected-behavior",
            "selected path should be included",
            "--category",
            "validation",
            "--severity",
            "high",
            "--status",
            "open",
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
            "--selected-path",
            str(selected),
            "--plan-payload-ref",
            "run-123",
            "--repro-step",
            "run ace_plan",
            "--repro-step",
            "inspect output",
            "--attachment",
            "artifact://validation.json",
            "--occurred-at",
            "2026-03-19T00:00:00+00:00",
            "--root",
            str(tmp_path),
        ],
        env=_cli_env(tmp_path),
    )

    assert recorded.exit_code == 0
    recorded_payload = json.loads(recorded.output)
    assert recorded_payload["ok"] is True
    assert recorded_payload["report"]["selected_path"] == "src/demo.py"
    assert recorded_payload["report"]["plan_payload_ref"] == "run-123"

    listed = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "list-issues",
            "--repo",
            "demo",
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
            "--status",
            "open",
            "--category",
            "validation",
            "--severity",
            "high",
            "--root",
            str(tmp_path),
        ],
        env=_cli_env(tmp_path),
    )

    assert listed.exit_code == 0
    listed_payload = json.loads(listed.output)
    assert listed_payload["ok"] is True
    assert listed_payload["count"] == 1
    assert listed_payload["reports"][0]["title"] == "validation payload missing selected path"


def test_cli_feedback_dev_issue_fix_and_summary_round_trip(tmp_path: Path) -> None:
    runner = CliRunner()
    store_path = tmp_path / "dev-feedback.db"

    recorded_issue = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "report-dev-issue",
            "--title",
            "Memory fallback while planning",
            "--reason-code",
            "memory_fallback",
            "--repo",
            "demo",
            "--status",
            "open",
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
            "--query",
            "why did memory fallback",
            "--selected-path",
            "src/planner.py",
            "--related-invocation-id",
            "inv-123",
            "--notes",
            "first report",
            "--created-at",
            "2026-03-19T00:00:00+00:00",
            "--updated-at",
            "2026-03-19T00:00:00+00:00",
            "--issue-id",
            "devi_memory_fallback",
            "--store-path",
            str(store_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert recorded_issue.exit_code == 0
    recorded_issue_payload = json.loads(recorded_issue.output)
    assert recorded_issue_payload["ok"] is True
    assert recorded_issue_payload["issue"]["reason_code"] == "memory_fallback"
    assert recorded_issue_payload["issue"]["selected_path"] == "src/planner.py"

    recorded_fix = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "report-dev-fix",
            "--reason-code",
            "memory_fallback",
            "--repo",
            "demo",
            "--resolution-note",
            "added fallback diagnostics",
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
            "--issue-id",
            "devi_memory_fallback",
            "--query",
            "why did memory fallback",
            "--selected-path",
            "src/planner.py",
            "--related-invocation-id",
            "inv-123",
            "--created-at",
            "2026-03-19T00:05:00+00:00",
            "--fix-id",
            "devf_memory_fallback",
            "--store-path",
            str(store_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert recorded_fix.exit_code == 0
    recorded_fix_payload = json.loads(recorded_fix.output)
    assert recorded_fix_payload["ok"] is True
    assert recorded_fix_payload["fix"]["issue_id"] == "devi_memory_fallback"

    summary = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "dev-feedback-summary",
            "--repo",
            "demo",
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
            "--store-path",
            str(store_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert summary.exit_code == 0
    summary_payload = json.loads(summary.output)
    assert summary_payload["ok"] is True
    assert summary_payload["summary"]["issue_count"] == 1
    assert summary_payload["summary"]["open_issue_count"] == 1
    assert summary_payload["summary"]["fix_count"] == 1
    assert summary_payload["summary"]["by_reason_code"][0]["reason_code"] == "memory_fallback"


def test_cli_feedback_issue_export_case_and_apply_fix_round_trip(tmp_path: Path) -> None:
    runner = CliRunner()
    selected = tmp_path / "src" / "demo.py"
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text("print('demo')\n", encoding="utf-8")
    issue_store_path = tmp_path / "context-map" / "issue_reports.db"
    dev_feedback_path = tmp_path / "context-map" / "dev_feedback.db"
    output_path = tmp_path / "benchmark" / "cases" / "feedback_issue_reports.yaml"

    recorded_issue = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "report-issue",
            "--title",
            "validation payload missing selected path",
            "--query",
            "validation missing selected path",
            "--repo",
            "demo",
            "--actual-behavior",
            "selected path missing from validation payload",
            "--expected-behavior",
            "selected path should be included",
            "--category",
            "validation",
            "--severity",
            "high",
            "--status",
            "open",
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
            "--selected-path",
            str(selected),
            "--plan-payload-ref",
            "run-123",
            "--issue-id",
            "iss_demo1234",
            "--root",
            str(tmp_path),
            "--store-path",
            str(issue_store_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert recorded_issue.exit_code == 0

    exported_case = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "issue-to-benchmark-case",
            "--issue-id",
            "iss_demo1234",
            "--root",
            str(tmp_path),
            "--store-path",
            str(issue_store_path),
            "--output",
            str(output_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert exported_case.exit_code == 0
    exported_payload = json.loads(exported_case.output)
    assert exported_payload["ok"] is True
    assert exported_payload["case"]["case_id"] == "issue-report-iss-demo1234"
    assert output_path.exists() is True

    recorded_fix = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "report-dev-fix",
            "--reason-code",
            "memory_fallback",
            "--repo",
            "demo",
            "--resolution-note",
            "patched validation payload",
            "--user-id",
            "cli-user",
            "--profile-key",
            "bugfix",
            "--issue-id",
            "iss_demo1234",
            "--query",
            "validation missing selected path",
            "--selected-path",
            "src/demo.py",
            "--created-at",
            "2026-03-19T00:05:00+00:00",
            "--fix-id",
            "devf_demo1234",
            "--store-path",
            str(dev_feedback_path),
        ],
        env=_cli_env(tmp_path),
    )
    assert recorded_fix.exit_code == 0

    resolved_issue = runner.invoke(
        cli_module.cli,
        [
            "feedback",
            "resolve-issue-from-dev-fix",
            "--issue-id",
            "iss_demo1234",
            "--fix-id",
            "devf_demo1234",
            "--root",
            str(tmp_path),
            "--issue-store-path",
            str(issue_store_path),
            "--dev-feedback-path",
            str(dev_feedback_path),
        ],
        env=_cli_env(tmp_path),
    )

    assert resolved_issue.exit_code == 0
    resolved_payload = json.loads(resolved_issue.output)
    assert resolved_payload["ok"] is True
    assert resolved_payload["report"]["status"] == "resolved"
    assert resolved_payload["report"]["resolution_note"] == "patched validation payload"
    assert "dev-fix://devf_demo1234" in resolved_payload["report"]["attachments"]
