from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

from click.testing import CliRunner

import ace_lite.cli as cli_module
from ace_lite.cli_app.commands import runtime as runtime_module
from ace_lite.dev_feedback_store import DevFeedbackStore
from ace_lite.feedback_store import SelectionFeedbackStore
from ace_lite.runtime_stats import RuntimeInvocationStats
from ace_lite.runtime_stats_schema import RUNTIME_STATS_DOCTOR_EVENT_CLASS
from ace_lite.runtime_stats_store import DurableStatsStore
from ace_lite.runtime_settings import RuntimeSettingsManager
from ace_lite.runtime_settings_store import (
    build_runtime_settings_record,
    persist_runtime_settings_record,
)
from ace_lite.stage_artifact_cache import StageArtifactCache


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def _seed_runtime_stats_db(db_path: Path) -> None:
    store = DurableStatsStore(db_path=db_path)
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-a1",
            session_id="session-alpha",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="succeeded",
            total_latency_ms=120.0,
            started_at="2026-03-11T00:00:00+00:00",
            finished_at="2026-03-11T00:00:01+00:00",
            stage_latencies=(
                {"stage_name": "memory", "elapsed_ms": 20.0},
                {"stage_name": "total", "elapsed_ms": 120.0},
            ),
        )
    )
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-a2",
            session_id="session-beta",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=80.0,
            started_at="2026-03-11T00:01:00+00:00",
            finished_at="2026-03-11T00:01:01+00:00",
            degraded_reason_codes=("memory_fallback",),
            stage_latencies=(
                {"stage_name": "index", "elapsed_ms": 15.0},
                {"stage_name": "total", "elapsed_ms": 80.0},
            ),
        )
    )
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-b1",
            session_id="session-gamma",
            repo_key="repo-beta",
            profile_key="docs",
            status="failed",
            total_latency_ms=60.0,
            started_at="2026-03-11T00:02:00+00:00",
            finished_at="2026-03-11T00:02:01+00:00",
            contract_error_code="contract_error",
            stage_latencies=(
                {"stage_name": "skills", "elapsed_ms": 12.0},
                {"stage_name": "total", "elapsed_ms": 60.0},
            ),
        )
    )


def _seed_runtime_stats_db_with_alias_reason(db_path: Path) -> None:
    store = DurableStatsStore(db_path=db_path)
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-alias",
            session_id="session-alias",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=40.0,
            started_at="2026-03-19T00:10:00+00:00",
            finished_at="2026-03-19T00:10:01+00:00",
            degraded_reason_codes=("budget_exceeded",),
            stage_latencies=(
                {"stage_name": "memory", "elapsed_ms": 10.0},
                {"stage_name": "total", "elapsed_ms": 40.0},
            ),
        )
    )


def _seed_runtime_stats_db_with_skills_budget_reason(db_path: Path) -> None:
    store = DurableStatsStore(db_path=db_path)
    store.record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-skills-budget",
            session_id="session-skills-budget",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=35.0,
            started_at="2026-03-20T00:10:00+00:00",
            finished_at="2026-03-20T00:10:01+00:00",
            degraded_reason_codes=("skills_budget_exhausted",),
            stage_latencies=(
                {"stage_name": "skills", "elapsed_ms": 9.0},
                {"stage_name": "total", "elapsed_ms": 35.0},
            ),
        )
    )


def _seed_dev_feedback_store(
    root: Path,
    *,
    repo: str,
    user_id: str = "bench-user",
    profile_key: str = "bugfix",
    reason_code: str = "memory_fallback",
) -> Path:
    store = DevFeedbackStore(db_path=root / ".ace-lite" / "dev_feedback.db")
    store.record_issue(
        {
            "issue_id": f"devi_{reason_code}",
            "title": "Memory fallback while planning",
            "reason_code": reason_code,
            "status": "open",
            "repo": repo,
            "user_id": user_id,
            "profile_key": profile_key,
            "query": "why did memory fallback",
            "selected_path": "src/auth.py",
            "related_invocation_id": "inv-dev-1",
            "notes": "first report",
            "created_at": "2026-03-19T00:00:00+00:00",
            "updated_at": "2026-03-19T00:00:00+00:00",
        }
    )
    store.record_fix(
        {
            "fix_id": f"devf_{reason_code}",
            "issue_id": f"devi_{reason_code}",
            "reason_code": reason_code,
            "repo": repo,
            "user_id": user_id,
            "profile_key": profile_key,
            "query": "why did memory fallback",
            "selected_path": "src/auth.py",
            "related_invocation_id": "inv-dev-1",
            "resolution_note": "added fallback diagnostics",
            "created_at": "2026-03-19T00:05:00+00:00",
        }
    )
    return store.db_path


def test_cli_runtime_watch_config_finishes(tmp_path: Path) -> None:
    (tmp_path / ".ace-lite.yml").write_text("plan:\n  top_k_files: 8\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "watch-config",
            "--root",
            str(tmp_path),
            "--max-polls",
            "1",
            "--poll-interval-seconds",
            "0",
            "--debounce-ms",
            "0",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    last_line = [line for line in result.output.splitlines() if line][-1]
    payload = json.loads(last_line)
    assert payload["event"] == "watch_finished"
    assert payload["ok"] is True


def test_cli_runtime_scheduler_runs_heartbeat_and_cron(tmp_path: Path) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "runtime:\n"
            "  scheduler:\n"
            "    enabled: true\n"
            "    heartbeat:\n"
            "      enabled: true\n"
            "      interval_seconds: 60\n"
            "      run_on_start: true\n"
            "    cron:\n"
            "      - name: every-minute\n"
            "        schedule: \"* * * * *\"\n"
            "        enabled: true\n"
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "run-scheduler",
            "--root",
            str(tmp_path),
            "--max-ticks",
            "2",
            "--tick-interval-seconds",
            "60",
            "--simulate-clock",
            "--start-at",
            "2026-02-13T10:00:00+00:00",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line]
    summary = json.loads(lines[-1])
    assert summary["event"] == "scheduler_finished"
    assert summary["ok"] is True
    assert summary["ticks"] == 2
    assert summary["run_count"] >= 2


def test_cli_runtime_scheduler_rejects_invalid_cron_config(tmp_path: Path) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "runtime:\n"
            "  scheduler:\n"
            "    enabled: true\n"
            "    cron:\n"
            "      - name: broken\n"
            "        schedule: \"not-a-cron\"\n"
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "run-scheduler",
            "--root",
            str(tmp_path),
            "--max-ticks",
            "1",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code != 0
    assert "Invalid .ace-lite.yml configuration" in result.output


def test_cli_runtime_test_mcp_self_test(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "test-mcp",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["ok"] is True
    assert payload["event"] == "mcp_self_test"
    assert payload["payload"]["ok"] is True
    assert isinstance(payload.get("warnings"), list)
    assert payload["warnings"]


def test_cli_runtime_test_mcp_require_memory_fails_on_none(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "test-mcp",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--require-memory",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code != 0
    assert "Memory providers are disabled" in result.output


def test_cli_runtime_doctor_mcp_reports_configuration(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "doctor-mcp",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--no-probe-endpoints",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["event"] == "mcp_doctor"
    assert payload["ok"] is True
    assert payload["snapshot_loaded"] is False
    checks = payload.get("checks", [])
    assert isinstance(checks, list)
    memory_check = next(item for item in checks if item.get("name") == "memory_configured")
    assert memory_check["ok"] is False


def test_cli_runtime_doctor_groups_settings_stats_cache_and_integration(
    tmp_path: Path,
) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    cache = StageArtifactCache(repo_root=tmp_path)
    cache.put_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
        query_hash="1111222233334444",
        fingerprint="fingerprint",
        payload={"value": "ok"},
        write_token="seed",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "doctor",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(skills_dir),
            "--no-probe-endpoints",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["event"] == "runtime_doctor"
    assert payload["ok"] is True
    assert payload["degraded_reason_codes"] == []
    assert "settings" in payload
    assert "stats" in payload
    assert "cache" in payload
    assert "git" in payload
    assert "version_sync" in payload
    assert "integration" in payload
    assert "settings" in payload["settings"]
    assert "fingerprint" in payload["settings"]
    assert "latest_match" in payload["stats"]
    assert "summary" in payload["stats"]
    assert payload["cache"]["ok"] is True
    assert payload["git"]["reason"] == "not_git_repo"
    assert payload["version_sync"]["ok"] is True
    assert payload["cache"]["entry_count"] == 1
    assert payload["integration"]["event"] == "mcp_doctor"
    assert "next_cycle_input" in payload
    assert payload["next_cycle_input"] == {}


def test_cli_runtime_doctor_can_record_synthetic_runtime_event(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "runtime-stats.db"

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "doctor",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(skills_dir),
            "--stats-db-path",
            str(db_path),
            "--record-runtime-event",
            "--no-probe-endpoints",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads([line for line in result.output.splitlines() if line.strip()][-1])
    assert payload["degraded_reason_codes"] == []
    assert payload["runtime_event_recording"]["recorded"] is False
    assert payload["runtime_event_recording"]["reason"] == "no_degraded_reasons"


def test_cli_doctor_alias_runs_grouped_runtime_doctor(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "doctor",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--no-probe-endpoints",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["event"] == "runtime_doctor"
    assert payload["ok"] is True


def test_cli_doctor_alias_can_record_synthetic_runtime_event(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "runtime-stats.db"

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "doctor",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--stats-db-path",
            str(db_path),
            "--record-runtime-event",
            "--no-probe-endpoints",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads([line for line in result.output.splitlines() if line.strip()][-1])
    assert payload["runtime_event_recording"]["recorded"] is False
    assert payload["runtime_event_recording"]["reason"] == "no_degraded_reasons"


def test_cli_runtime_doctor_records_degraded_runtime_event_when_requested(
    tmp_path: Path, monkeypatch
) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "runtime-stats.db"

    monkeypatch.setattr(
        runtime_module,
        "build_runtime_doctor_payload",
        lambda **kwargs: {
            "ok": False,
            "event": "runtime_doctor",
            "degraded_reason_codes": ["git_unavailable", "install_drift"],
            "settings": {"fingerprint": "fp-doctor"},
            "stats": {"latest_match": None, "summary": {}},
            "cache": {"ok": True},
            "git": {"ok": False, "issue_type": "git_unavailable"},
            "version_sync": {"ok": False, "reason": "install_drift"},
            "integration": {"ok": True, "event": "mcp_doctor"},
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "doctor",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(skills_dir),
            "--stats-db-path",
            str(db_path),
            "--record-runtime-event",
            "--no-probe-endpoints",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 1
    payload = next(
        json.loads(line)
        for line in result.output.splitlines()
        if line.strip().startswith("{")
    )
    assert payload["runtime_event_recording"]["recorded"] is True
    invocation_id = payload["runtime_event_recording"]["invocation_id"]
    stored = DurableStatsStore(db_path=db_path).read_invocation(invocation_id=invocation_id)
    assert stored is not None
    assert stored.degraded_reason_codes == ("git_unavailable", "install_drift")


def test_cli_runtime_doctor_recorded_event_does_not_override_runtime_stats_latest_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db(db_path)

    monkeypatch.setattr(
        runtime_module,
        "build_runtime_doctor_payload",
        lambda **kwargs: {
            "ok": False,
            "event": "runtime_doctor",
            "degraded_reason_codes": ["git_unavailable"],
            "settings": {"fingerprint": "fp-doctor"},
            "stats": {"latest_match": None, "summary": {}},
            "cache": {"ok": True},
            "git": {"ok": False, "issue_type": "git_unavailable"},
            "version_sync": {"ok": True, "reason": ""},
            "integration": {"ok": True, "event": "mcp_doctor"},
        },
    )

    runner = CliRunner()
    doctor_result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "doctor",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(skills_dir),
            "--stats-db-path",
            str(db_path),
            "--record-runtime-event",
            "--no-probe-endpoints",
        ],
        env=_cli_env(tmp_path),
    )

    assert doctor_result.exit_code == 1
    doctor_payload = next(
        json.loads(line)
        for line in doctor_result.output.splitlines()
        if line.strip().startswith("{")
    )
    assert doctor_payload["runtime_event_recording"]["recorded"] is True
    assert (
        doctor_payload["runtime_event_recording"]["event_class"]
        == RUNTIME_STATS_DOCTOR_EVENT_CLASS
    )

    stats_result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "stats",
            "--db-path",
            str(db_path),
            "--repo",
            "repo-beta",
            "--profile",
            "docs",
        ],
        env=_cli_env(tmp_path),
    )

    assert stats_result.exit_code == 0
    stats_payload = json.loads(
        [line for line in stats_result.output.splitlines() if line.strip()][-1]
    )
    assert stats_payload["latest_match"]["invocation_id"] == "inv-b1"
    assert stats_payload["latest_match"]["session_id"] == "session-gamma"
    assert stats_payload["latest_match"]["repo_key"] == "repo-beta"


def test_cli_runtime_doctor_applies_user_id_filter_to_preference_capture_summary(
    tmp_path: Path,
) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db(db_path)
    store = SelectionFeedbackStore(
        profile_path=tmp_path / ".ace-lite" / "profile.json",
        max_entries=8,
    )
    store.record(
        query="doctor bench",
        repo="repo-alpha",
        user_id="bench-user",
        selected_path="src/auth.py",
        captured_at="2026-03-18T00:00:00+00:00",
        position=1,
    )
    store.record(
        query="doctor other",
        repo="repo-alpha",
        user_id="other-user",
        selected_path="src/docs.py",
        captured_at="2026-03-18T00:01:00+00:00",
        position=1,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "doctor",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(skills_dir),
            "--stats-db-path",
            str(db_path),
            "--user-id",
            "bench-user",
            "--no-probe-endpoints",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["stats"]["filters"]["user_id"] == "bench-user"
    assert payload["stats"]["preference_capture_summary"]["event_count"] == 1
    assert payload["stats"]["preference_capture_summary"]["user_id"] == "bench-user"


def test_cli_doctor_alias_applies_user_id_filter_to_preference_capture_summary(
    tmp_path: Path,
) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db(db_path)
    store = SelectionFeedbackStore(
        profile_path=tmp_path / ".ace-lite" / "profile.json",
        max_entries=8,
    )
    store.record(
        query="doctor alias bench",
        repo="repo-alpha",
        user_id="bench-user",
        selected_path="src/auth.py",
        captured_at="2026-03-18T00:00:00+00:00",
        position=1,
    )
    store.record(
        query="doctor alias other",
        repo="repo-alpha",
        user_id="other-user",
        selected_path="src/docs.py",
        captured_at="2026-03-18T00:01:00+00:00",
        position=1,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "doctor",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(skills_dir),
            "--stats-db-path",
            str(db_path),
            "--user-id",
            "bench-user",
            "--no-probe-endpoints",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["stats"]["filters"]["user_id"] == "bench-user"
    assert payload["stats"]["preference_capture_summary"]["event_count"] == 1
    assert payload["stats"]["preference_capture_summary"]["user_id"] == "bench-user"


def test_cli_runtime_doctor_mcp_uses_snapshot_when_available(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = tmp_path / "context-map" / "mcp" / "ace-lite.env.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(
            {
                "name": "ace-lite",
                "env": {
                    "ACE_LITE_DEFAULT_ROOT": str(tmp_path),
                    "ACE_LITE_DEFAULT_SKILLS_DIR": str(skills_dir),
                    "ACE_LITE_MEMORY_PRIMARY": "rest",
                    "ACE_LITE_MEMORY_SECONDARY": "none",
                    "ACE_LITE_REST_BASE_URL": "http://localhost:8765",
                    "ACE_LITE_MCP_BASE_URL": "http://localhost:8765",
                    "ACE_LITE_USER_ID": "snapshot-user",
                    "ACE_LITE_APP": "ace-lite",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "doctor-mcp",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(skills_dir),
            "--require-memory",
            "--no-probe-endpoints",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["ok"] is True
    assert payload["snapshot_loaded"] is True
    assert payload["self_test"]["memory_primary"] == "rest"
    checks = payload.get("checks", [])
    memory_check = next(item for item in checks if item.get("name") == "memory_configured")
    assert memory_check["ok"] is True


def test_cli_runtime_doctor_cache_reports_clean_cache(tmp_path: Path) -> None:
    cache = StageArtifactCache(repo_root=tmp_path)
    cache.put_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
        query_hash="1111222233334444",
        fingerprint="fingerprint",
        payload={"value": "ok"},
        write_token="seed",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        ["runtime", "doctor-cache", "--root", str(tmp_path)],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip().startswith("{")]
    payload = json.loads(lines[-1])
    assert payload["event"] == "runtime_doctor_cache"
    assert payload["ok"] is True
    assert payload["summary"]["severe_issue_count"] == 0


def test_cli_runtime_doctor_cache_warning_only_stays_zero_exit(tmp_path: Path) -> None:
    cache = StageArtifactCache(repo_root=tmp_path)
    orphan_path = cache.payload_root / "source_plan" / "ff" / "ffffffffffffffff.json"
    orphan_path.parent.mkdir(parents=True, exist_ok=True)
    orphan_path.write_text('{"orphan": true}\n', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        ["runtime", "doctor-cache", "--root", str(tmp_path)],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip().startswith("{")]
    payload = json.loads(lines[-1])
    assert payload["ok"] is True
    assert payload["summary"]["severe_issue_count"] == 0
    assert payload["summary"]["warning_issue_count"] == 1
    assert len(payload["orphan_payload_files"]) == 1


def test_cli_runtime_doctor_cache_fails_on_severe_corruption(tmp_path: Path) -> None:
    cache = StageArtifactCache(repo_root=tmp_path)
    entry = cache.put_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
        query_hash="1111222233334444",
        fingerprint="fingerprint",
        payload={"value": "ok"},
        write_token="seed",
    )
    payload_path = cache.payload_root / Path(*Path(entry.payload_relpath).parts)
    payload_path.unlink()

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        ["runtime", "doctor-cache", "--root", str(tmp_path)],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code != 0
    lines = [line for line in result.output.splitlines() if line.strip().startswith("{")]
    payload = json.loads(lines[-1])
    assert payload["event"] == "runtime_doctor_cache"
    assert payload["ok"] is False
    assert payload["summary"]["severe_issue_count"] == 1
    assert len(payload["missing_payload_rows"]) == 1


def test_cli_runtime_cache_vacuum_apply_removes_expired_and_orphan_payloads(
    tmp_path: Path,
) -> None:
    cache = StageArtifactCache(repo_root=tmp_path)
    entry = cache.put_artifact(
        stage_name="source_plan",
        cache_key="aaaaaaaaaaaaaaaa",
        query_hash="1111222233334444",
        fingerprint="expired",
        payload={"value": "expired"},
        ttl_seconds=3600,
        write_token="seed",
    )
    cache.store.upsert_entry(replace(entry, expires_at="2000-01-01T00:00:00+00:00"))
    orphan_path = cache.payload_root / "source_plan" / "ff" / "ffffffffffffffff.json"
    orphan_path.parent.mkdir(parents=True, exist_ok=True)
    orphan_path.write_text('{"orphan": true}\n', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        ["runtime", "cache", "vacuum", "--root", str(tmp_path), "--apply"],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip().startswith("{")]
    payload = json.loads(lines[-1])
    assert payload["event"] == "runtime_cache_vacuum"
    assert payload["ok"] is True
    assert payload["dry_run"] is False
    assert payload["deleted_expired_rows"] == 1
    assert payload["deleted_expired_payload_files"] == 1
    assert payload["deleted_orphan_payload_files"] == 1
    assert cache.store.load_entry(stage_name="source_plan", cache_key="aaaaaaaaaaaaaaaa") is None
    assert orphan_path.exists() is False


def test_cli_runtime_setup_codex_mcp_dry_run_defaults(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "setup-codex-mcp",
            "--name",
            "ace-lite-test",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--dry-run",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["ok"] is True
    assert payload["event"] == "setup_codex_mcp"
    assert payload["apply"] is False
    assert payload["memory_enabled"] is False
    env_lines = payload.get("env", [])
    assert "ACE_LITE_MEMORY_PRIMARY=none" in env_lines
    assert "ACE_LITE_MEMORY_SECONDARY=none" in env_lines


def test_cli_runtime_setup_codex_mcp_dry_run_memory_enabled(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    config_pack = tmp_path / "mcp-pack.json"
    config_pack.write_text("{}", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "setup-codex-mcp",
            "--name",
            "ace-lite-test",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--enable-memory",
            "--memory-primary",
            "rest",
            "--memory-secondary",
            "none",
            "--enable-embeddings",
            "--embedding-provider",
            "ollama",
            "--embedding-model",
            "dengcao/Qwen3-Embedding-4B:Q4_K_M",
            "--embedding-dimension",
            "2560",
            "--config-pack",
            str(config_pack),
            "--user-id",
            "test-user",
            "--dry-run",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["ok"] is True
    assert payload["memory_enabled"] is True
    assert payload["embeddings_enabled"] is True
    assert payload["config_pack"] == str(config_pack.resolve())
    assert payload["resolved_user_id"] == "test-user"
    env_lines = payload.get("env", [])
    assert "ACE_LITE_MEMORY_PRIMARY=rest" in env_lines
    assert "ACE_LITE_MEMORY_SECONDARY=none" in env_lines
    assert "ACE_LITE_USER_ID=test-user" in env_lines
    assert "ACE_LITE_EMBEDDING_ENABLED=1" in env_lines
    assert "ACE_LITE_EMBEDDING_PROVIDER=ollama" in env_lines
    assert (
        "ACE_LITE_EMBEDDING_MODEL=dengcao/Qwen3-Embedding-4B:Q4_K_M" in env_lines
    )
    assert "ACE_LITE_EMBEDDING_DIMENSION=2560" in env_lines
    assert f"ACE_LITE_CONFIG_PACK={config_pack.resolve()}" in env_lines


def test_cli_runtime_setup_codex_mcp_apply_writes_snapshot(
    tmp_path: Path, monkeypatch
) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    config_pack = tmp_path / "mcp-pack.json"
    config_pack.write_text("{}", encoding="utf-8")

    def _fake_run(command, capture_output, text, check=False, env=None, timeout=None):
        _ = (capture_output, text, check, env, timeout)
        if command[:3] == ["codex", "mcp", "get"]:
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout="ace-lite\n  enabled: true\n",
                stderr="",
            )
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="ok\n",
            stderr="",
        )

    def _fake_self_test(*, root, skills_dir, python_executable, timeout_seconds, env_overrides=None):
        _ = (root, skills_dir, python_executable, timeout_seconds, env_overrides)
        return {
            "ok": True,
            "memory_primary": "rest",
            "memory_secondary": "none",
            "memory_ready": True,
        }

    monkeypatch.setattr(runtime_module.subprocess, "run", _fake_run)
    monkeypatch.setattr(runtime_module, "_run_mcp_self_test", _fake_self_test)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "setup-codex-mcp",
            "--name",
            "ace-lite",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(skills_dir),
            "--enable-memory",
            "--memory-primary",
            "rest",
            "--memory-secondary",
            "none",
            "--enable-embeddings",
            "--config-pack",
            str(config_pack),
            "--user-id",
            "snapshot-user",
            "--apply",
            "--verify",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    snapshot_path = Path(payload["snapshot_path"])
    assert snapshot_path.exists()
    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    env_payload = snapshot_payload.get("env", {})
    assert env_payload.get("ACE_LITE_MEMORY_PRIMARY") == "rest"
    assert env_payload.get("ACE_LITE_USER_ID") == "snapshot-user"
    assert env_payload.get("ACE_LITE_EMBEDDING_ENABLED") == "1"
    assert env_payload.get("ACE_LITE_CONFIG_PACK") == str(config_pack.resolve())


def test_cli_runtime_setup_codex_mcp_verify_disables_embeddings_when_not_enabled(
    tmp_path: Path, monkeypatch
) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    captured_env: dict[str, str] = {}

    def _fake_run(command, capture_output, text, check=False, env=None, timeout=None):
        _ = (capture_output, text, check, env, timeout)
        if command[:3] == ["codex", "mcp", "get"]:
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout="ace-lite\n  enabled: true\n",
                stderr="",
            )
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="ok\n",
            stderr="",
        )

    def _fake_self_test(*, root, skills_dir, python_executable, timeout_seconds, env_overrides=None):
        _ = (root, skills_dir, python_executable, timeout_seconds)
        captured_env.update(env_overrides or {})
        return {
            "ok": True,
            "memory_primary": "rest",
            "memory_secondary": "none",
            "memory_ready": True,
            "embedding_enabled": False,
        }

    monkeypatch.setattr(runtime_module.subprocess, "run", _fake_run)
    monkeypatch.setattr(runtime_module, "_run_mcp_self_test", _fake_self_test)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "setup-codex-mcp",
            "--name",
            "ace-lite",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(skills_dir),
            "--enable-memory",
            "--memory-primary",
            "rest",
            "--memory-secondary",
            "none",
            "--user-id",
            "snapshot-user",
            "--apply",
            "--verify",
        ],
        env={**_cli_env(tmp_path), "ACE_LITE_EMBEDDING_ENABLED": "1"},
    )

    assert result.exit_code == 0
    assert captured_env.get("ACE_LITE_EMBEDDING_ENABLED") == "0"


def test_cli_runtime_settings_show_prints_effective_snapshot(tmp_path: Path) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "plan:\n"
            "  retrieval:\n"
            "    top_k_files: 9\n"
            "runtime:\n"
            "  scheduler:\n"
            "    enabled: true\n"
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "settings",
            "show",
            "--root",
            str(tmp_path),
            "--no-use-snapshot",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["ok"] is True
    assert payload["event"] == "runtime_settings_show"
    assert payload["settings"]["plan"]["retrieval"]["top_k_files"] == 9
    assert payload["provenance"]["plan"]["retrieval"]["top_k_files"] == "repo_config"
    assert payload["settings"]["runtime"]["scheduler"]["enabled"] is True
    assert payload["fingerprint"]
    assert payload["selected_profile"] is None


def test_cli_runtime_settings_show_uses_last_known_good_snapshot(tmp_path: Path) -> None:
    current_path = tmp_path / "current-settings.json"
    lkg_path = tmp_path / "last-known-good.json"
    valid_payload = build_runtime_settings_record(
        snapshot={"plan": {"retrieval": {"top_k_files": 12}}},
        provenance={"plan": {"retrieval": {"top_k_files": "cli"}}},
        metadata={"selected_profile": "team-default"},
    )
    persist_runtime_settings_record(
        current_path=current_path,
        last_known_good_path=lkg_path,
        payload=valid_payload,
        update_last_known_good=True,
    )
    current_path.write_text('{"schema_version": 1, "snapshot": {"broken": true}}', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "settings",
            "show",
            "--root",
            str(tmp_path),
            "--no-use-snapshot",
            "--current-path",
            str(current_path),
            "--last-known-good-path",
            str(lkg_path),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["persisted_source"] == "last_known_good"
    assert payload["selected_profile"] == "team-default"


def test_cli_runtime_settings_show_reports_resolved_runtime_profile_and_stats_tags(
    tmp_path: Path,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        "plan:\n  runtime_profile: bugfix\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "settings",
            "show",
            "--root",
            str(tmp_path),
            "--no-use-snapshot",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["selected_profile"] == "bugfix"
    assert payload["settings"]["plan"]["retrieval"]["retrieval_policy"] == "bugfix_test"
    assert payload["stats_tags"]["profile_key"] == "bugfix"
    assert payload["stats_tags"]["settings_fingerprint"] == payload["fingerprint"]
    assert payload["metadata"]["selected_profile_source"] == "repo_config"


def test_cli_runtime_settings_show_runtime_profile_flag_overrides_repo_default(
    tmp_path: Path,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        "plan:\n  runtime_profile: bugfix\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "settings",
            "show",
            "--root",
            str(tmp_path),
            "--runtime-profile",
            "fast_path",
            "--no-use-snapshot",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["selected_profile"] == "fast_path"
    assert payload["settings"]["plan"]["retrieval"]["top_k_files"] == 5
    assert payload["metadata"]["selected_profile_source"] == "cli"


def test_cli_runtime_settings_show_matches_runtime_settings_manager(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "plan:\n"
            "  retrieval:\n"
            "    top_k_files: 5\n"
            "  chunk:\n"
            "    top_k: 13\n"
            "runtime:\n"
            "  scheduler:\n"
            "    enabled: true\n"
            "    heartbeat:\n"
            "      enabled: true\n"
            "      interval_seconds: 30\n"
        ),
        encoding="utf-8",
    )
    snapshot_env = {
        "ACE_LITE_MEMORY_PRIMARY": "rest",
        "ACE_LITE_MEMORY_SECONDARY": "none",
        "ACE_LITE_USER_ID": "snapshot-user",
    }
    current_path = tmp_path / "current-settings.json"
    lkg_path = tmp_path / "last-known-good.json"
    persisted_payload = build_runtime_settings_record(
        snapshot={"plan": {"retrieval": {"top_k_files": 5}}},
        provenance={"plan": {"retrieval": {"top_k_files": "repo_config"}}},
        metadata={"selected_profile": "parity-profile"},
    )
    persist_runtime_settings_record(
        current_path=current_path,
        last_known_good_path=lkg_path,
        payload=persisted_payload,
        update_last_known_good=True,
    )

    expected = RuntimeSettingsManager().resolve(
        root=tmp_path,
        cwd=Path.cwd(),
        mcp_env=_cli_env(tmp_path),
        mcp_snapshot_env=snapshot_env,
    )

    snapshot_path = tmp_path / "context-map" / "mcp" / "ace-lite.env.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps({"name": "ace-lite", "env": snapshot_env}, ensure_ascii=False),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "settings",
            "show",
            "--root",
            str(tmp_path),
            "--current-path",
            str(current_path),
            "--last-known-good-path",
            str(lkg_path),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["settings"] == expected.snapshot
    assert payload["provenance"] == expected.provenance
    assert payload["fingerprint"] == expected.fingerprint
    assert payload["selected_profile"] == "parity-profile"


def test_cli_runtime_stats_reports_latest_session_and_global_rollups(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db(db_path)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "stats",
            "--db-path",
            str(db_path),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["ok"] is True
    assert payload["event"] == "runtime_stats"
    assert payload["latest_match"]["session_id"] == "session-gamma"
    assert payload["latest_match"]["repo_key"] == "repo-beta"
    assert payload["latest_match"]["event_class"] == "runtime_invocation"
    assert payload["summary"]["session"]["counters"]["invocation_count"] == 1
    assert payload["summary"]["all_time"]["counters"]["invocation_count"] == 3
    assert payload["summary"]["all_time"]["latency"]["latency_ms_avg"] == 86.666667
    assert payload["summary"]["repo"]["scope_key"] == "repo-beta"
    assert payload["summary"]["profile"]["scope_key"] == "docs"
    assert payload["summary"]["repo_profile"]["scope_key"] == "repo-beta::docs"


def test_cli_runtime_stats_honors_repo_and_profile_filters(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db(db_path)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "stats",
            "--db-path",
            str(db_path),
            "--repo",
            "repo-alpha",
            "--profile",
            "bugfix",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["filters"] == {"repo": "repo-alpha", "profile": "bugfix"}
    assert payload["latest_match"]["session_id"] == "session-beta"
    assert payload["summary"]["session"]["scope_key"] == "session-beta"
    assert payload["summary"]["repo"]["counters"]["invocation_count"] == 2
    assert payload["summary"]["profile"]["counters"]["invocation_count"] == 2
    assert payload["summary"]["repo_profile"]["counters"]["invocation_count"] == 2
    assert (
        payload["summary"]["repo_profile"]["degraded_states"][0]["reason_code"]
        == "memory_fallback"
    )


def test_cli_runtime_stats_excludes_synthetic_doctor_sessions_from_scope_summaries(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db(db_path)
    DurableStatsStore(db_path=db_path).record_invocation(
        RuntimeInvocationStats(
            invocation_id="inv-doctor-alpha",
            session_id="runtime-doctor::repo-alpha",
            repo_key="repo-alpha",
            profile_key="bugfix",
            status="degraded",
            total_latency_ms=0.0,
            started_at="2026-03-11T00:03:00+00:00",
            finished_at="2026-03-11T00:03:00+00:00",
            degraded_reason_codes=("git_unavailable",),
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "stats",
            "--db-path",
            str(db_path),
            "--repo",
            "repo-alpha",
            "--profile",
            "bugfix",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["latest_match"]["session_id"] == "session-beta"
    assert payload["summary"]["all_time"]["counters"]["invocation_count"] == 3
    assert payload["summary"]["repo"]["counters"]["invocation_count"] == 2
    assert payload["summary"]["profile"]["counters"]["invocation_count"] == 2
    assert payload["summary"]["repo_profile"]["counters"]["invocation_count"] == 2
    assert (
        payload["summary"]["repo_profile"]["degraded_states"][0]["reason_code"]
        == "memory_fallback"
    )


def test_cli_runtime_stats_uses_default_user_scope_db_path(tmp_path: Path) -> None:
    db_path = tmp_path / ".ace-lite" / "runtime_state.db"
    _seed_runtime_stats_db(db_path)
    SelectionFeedbackStore(
        profile_path=tmp_path / ".ace-lite" / "profile.json",
        max_entries=8,
    ).record(
        query="repo alpha runtime",
        repo="repo-alpha",
        selected_path="src/auth.py",
        captured_at="2026-03-18T00:00:00+00:00",
        position=1,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "stats",
            "--repo",
            "repo-alpha",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["db_path"] == str(db_path.resolve())
    assert payload["latest_match"]["repo_key"] == "repo-alpha"
    assert payload["preference_capture_summary"]["event_count"] == 1
    assert payload["preference_capture_summary"]["distinct_target_path_count"] == 1


def test_cli_runtime_stats_profile_filter_applies_to_preference_capture_summary(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / ".ace-lite" / "runtime_state.db"
    _seed_runtime_stats_db(db_path)
    profile_path = tmp_path / ".ace-lite" / "profile.json"
    SelectionFeedbackStore(
        profile_path=profile_path,
        max_entries=8,
    ).record(
        query="repo alpha runtime bugfix",
        repo="repo-alpha",
        profile_key="bugfix",
        selected_path="src/auth.py",
        captured_at="2026-03-18T00:00:00+00:00",
        position=1,
    )
    SelectionFeedbackStore(
        profile_path=profile_path,
        max_entries=8,
    ).record(
        query="repo alpha runtime docs",
        repo="repo-alpha",
        profile_key="docs",
        selected_path="src/docs.py",
        captured_at="2026-03-18T00:01:00+00:00",
        position=1,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "stats",
            "--repo",
            "repo-alpha",
            "--profile",
            "bugfix",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["filters"]["profile"] == "bugfix"
    assert payload["preference_capture_summary"]["event_count"] == 1
    assert payload["preference_capture_summary"]["profile_key"] == "bugfix"


def test_cli_runtime_stats_user_id_filter_applies_to_preference_capture_summary(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / ".ace-lite" / "runtime_state.db"
    _seed_runtime_stats_db(db_path)
    profile_path = tmp_path / ".ace-lite" / "profile.json"
    store = SelectionFeedbackStore(
        profile_path=profile_path,
        max_entries=8,
    )
    store.record(
        query="repo alpha runtime bench",
        repo="repo-alpha",
        user_id="bench-user",
        selected_path="src/auth.py",
        captured_at="2026-03-18T00:00:00+00:00",
        position=1,
    )
    store.record(
        query="repo alpha runtime other",
        repo="repo-alpha",
        user_id="other-user",
        selected_path="src/docs.py",
        captured_at="2026-03-18T00:01:00+00:00",
        position=1,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "stats",
            "--repo",
            "repo-alpha",
            "--user-id",
            "bench-user",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["filters"]["user_id"] == "bench-user"
    assert payload["preference_capture_summary"]["event_count"] == 1
    assert payload["preference_capture_summary"]["user_id"] == "bench-user"


def test_cli_runtime_stats_exposes_dev_feedback_and_top_pain_summary(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / ".ace-lite" / "runtime_state.db"
    _seed_runtime_stats_db(db_path)
    _seed_dev_feedback_store(tmp_path, repo="repo-alpha")

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "stats",
            "--repo",
            "repo-alpha",
            "--profile",
            "bugfix",
            "--user-id",
            "bench-user",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["dev_feedback_summary"]["issue_count"] == 1
    assert payload["dev_feedback_summary"]["fix_count"] == 1
    assert payload["top_pain_summary"]["count"] == 1
    assert payload["top_pain_summary"]["items"][0]["reason_code"] == "memory_fallback"
    assert payload["top_pain_summary"]["items"][0]["runtime_event_count"] == 1
    assert payload["top_pain_summary"]["items"][0]["manual_issue_count"] == 1
    assert payload["top_pain_summary"]["items"][0]["open_issue_count"] == 1
    assert payload["top_pain_summary"]["items"][0]["fix_count"] == 1
    assert payload["top_pain_summary"]["items"][0]["linked_fix_issue_count"] == 1
    assert payload["top_pain_summary"]["items"][0]["dev_issue_to_fix_rate"] == 1.0


def test_cli_runtime_status_reports_service_health_and_cache_paths(tmp_path: Path) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "plan:\n"
            "  memory:\n"
            "    feedback:\n"
            "      enabled: true\n"
            "      path: runtime-feedback/profile.json\n"
            "  plan_replay_cache:\n"
            "    enabled: true\n"
            "    cache_path: context-map/runtime-cache/replay.json\n"
            "  trace:\n"
            "    export_enabled: true\n"
            "    export_path: context-map/traces/runtime-status.jsonl\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db(db_path)
    SelectionFeedbackStore(
        profile_path=tmp_path / "runtime-feedback" / "profile.json",
        max_entries=8,
    ).record(
        query="repo beta runtime status",
        repo="repo-beta",
        selected_path="src/auth.py",
        captured_at="2026-03-18T00:00:00+00:00",
        position=1,
    )
    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "status",
            "--root",
            str(tmp_path),
            "--db-path",
            str(db_path),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    service_health = {item["name"]: item for item in payload["service_health"]}
    assert payload["event"] == "runtime_status"
    assert len(payload["settings_fingerprint"]) == 64
    assert {
        "memory",
        "skills",
        "embeddings",
        "plan_replay_cache",
        "preference_capture",
        "trace_export",
        "durable_stats",
    }.issubset(service_health)
    assert (
        payload["cache_paths"]["plan_replay_cache"]
        == str((tmp_path / "context-map" / "runtime-cache" / "replay.json").resolve())
    )
    assert (
        payload["cache_paths"]["trace_export"]
        == str((tmp_path / "context-map" / "traces" / "runtime-status.jsonl").resolve())
    )
    assert service_health["memory"]["status"] == "disabled"
    assert service_health["plan_replay_cache"]["status"] == "ok"
    assert service_health["preference_capture"]["status"] == "ok"
    assert service_health["trace_export"]["status"] == "ok"
    assert service_health["durable_stats"]["status"] == "ok"
    assert payload["latest_runtime"]["latest_match"]["session_id"] == "session-gamma"
    assert payload["latest_runtime"]["preference_capture_summary"]["event_count"] == 1
    assert payload["next_cycle_input"]["primary_stream"]
    assert (
        payload["next_cycle_input"]["primary_stream"]
        in payload["next_cycle_input"]["degraded_service_names"]
    )
    assert payload["latest_runtime"]["next_cycle_input_summary"] == {}


def test_cli_runtime_status_scopes_preference_capture_to_selected_profile(
    tmp_path: Path,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "plan:\n"
            "  memory:\n"
            "    feedback:\n"
            "      enabled: true\n"
            "      path: runtime-feedback/profile.json\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db(db_path)
    profile_path = tmp_path / "runtime-feedback" / "profile.json"
    SelectionFeedbackStore(
        profile_path=profile_path,
        max_entries=8,
    ).record(
        query="repo beta runtime bugfix",
        repo="repo-beta",
        profile_key="bugfix",
        selected_path="src/auth.py",
        captured_at="2026-03-18T00:00:00+00:00",
        position=1,
    )
    SelectionFeedbackStore(
        profile_path=profile_path,
        max_entries=8,
    ).record(
        query="repo beta runtime docs",
        repo="repo-beta",
        profile_key="docs",
        selected_path="src/docs.py",
        captured_at="2026-03-18T00:01:00+00:00",
        position=1,
    )
    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "status",
            "--root",
            str(tmp_path),
            "--db-path",
            str(db_path),
            "--runtime-profile",
            "bugfix",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["selected_profile"] == "bugfix"
    assert payload["stats_tags"]["profile_key"] == "bugfix"
    assert payload["latest_runtime"]["preference_capture_summary"]["event_count"] == 1
    assert payload["latest_runtime"]["preference_capture_summary"]["profile_key"] == "bugfix"


def test_cli_runtime_status_applies_user_id_filter_to_preference_capture_summary(
    tmp_path: Path,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "plan:\n"
            "  memory:\n"
            "    feedback:\n"
            "      enabled: true\n"
            "      path: runtime-feedback/profile.json\n"
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db(db_path)
    profile_path = tmp_path / "runtime-feedback" / "profile.json"
    store = SelectionFeedbackStore(
        profile_path=profile_path,
        max_entries=8,
    )
    store.record(
        query="repo beta runtime bench",
        repo="repo-beta",
        user_id="bench-user",
        selected_path="src/auth.py",
        captured_at="2026-03-18T00:00:00+00:00",
        position=1,
    )
    store.record(
        query="repo beta runtime other",
        repo="repo-beta",
        user_id="other-user",
        selected_path="src/docs.py",
        captured_at="2026-03-18T00:01:00+00:00",
        position=1,
    )
    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "status",
            "--root",
            str(tmp_path),
            "--db-path",
            str(db_path),
            "--user-id",
            "bench-user",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["latest_runtime"]["filters"]["user_id"] == "bench-user"
    assert payload["latest_runtime"]["preference_capture_summary"]["event_count"] == 1
    assert payload["latest_runtime"]["preference_capture_summary"]["user_id"] == (
        "bench-user"
    )


def test_cli_runtime_status_exposes_dev_feedback_and_top_pain_summary(
    tmp_path: Path,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        "plan:\n  runtime_profile: bugfix\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db(db_path)
    _seed_dev_feedback_store(tmp_path, repo="repo-alpha")

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "status",
            "--root",
            str(tmp_path),
            "--db-path",
            str(db_path),
            "--runtime-profile",
            "bugfix",
            "--user-id",
            "bench-user",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["latest_runtime"]["dev_feedback_summary"]["issue_count"] == 1
    assert payload["latest_runtime"]["dev_feedback_summary"]["fix_count"] == 1
    assert payload["latest_runtime"]["top_pain_summary"]["count"] == 1
    assert payload["latest_runtime"]["top_pain_summary"]["items"][0]["reason_code"] == (
        "memory_fallback"
    )
    assert payload["latest_runtime"]["top_pain_summary"]["items"][0]["runtime_event_count"] == 1
    assert payload["latest_runtime"]["top_pain_summary"]["items"][0]["manual_issue_count"] == 1
    assert payload["latest_runtime"]["top_pain_summary"]["items"][0]["linked_fix_issue_count"] == 1
    assert payload["latest_runtime"]["top_pain_summary"]["items"][0]["dev_issue_to_fix_rate"] == 1.0
    assert payload["latest_runtime"]["memory_health_summary"]["linked_fix_issue_count"] == 1
    assert payload["latest_runtime"]["memory_health_summary"]["dev_issue_to_fix_rate"] == 1.0


def test_cli_runtime_status_canonicalizes_runtime_reason_aliases(
    tmp_path: Path,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        "plan:\n  runtime_profile: bugfix\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db_with_alias_reason(db_path)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "status",
            "--root",
            str(tmp_path),
            "--db-path",
            str(db_path),
            "--runtime-profile",
            "bugfix",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["latest_runtime"]["top_pain_summary"]["count"] == 1
    assert payload["latest_runtime"]["top_pain_summary"]["items"][0]["reason_code"] == (
        "latency_budget_exceeded"
    )
    assert payload["latest_runtime"]["top_pain_summary"]["items"][0]["reason_family"] == (
        "runtime"
    )
    assert payload["latest_runtime"]["top_pain_summary"]["items"][0]["capture_class"] == (
        "budget"
    )
    assert payload["latest_runtime"]["top_pain_summary"]["items"][0]["runtime_event_count"] == 1
    assert any(
        item["name"] == "runtime"
        and item["reason"] == "latency_budget_exceeded"
        and item.get("capture_class") == "budget"
        and item["source"] == "latest_runtime_stats"
        for item in payload["degraded_services"]
    )


def test_cli_runtime_status_exposes_skills_budget_exhausted_reason(
    tmp_path: Path,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        "plan:\n  runtime_profile: bugfix\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db_with_skills_budget_reason(db_path)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "status",
            "--root",
            str(tmp_path),
            "--db-path",
            str(db_path),
            "--runtime-profile",
            "bugfix",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["latest_runtime"]["top_pain_summary"]["count"] == 1
    assert payload["latest_runtime"]["top_pain_summary"]["items"][0]["reason_code"] == (
        "skills_budget_exhausted"
    )
    assert payload["latest_runtime"]["top_pain_summary"]["items"][0]["reason_family"] == (
        "skills"
    )
    assert payload["latest_runtime"]["top_pain_summary"]["items"][0]["capture_class"] == (
        "budget"
    )
    assert any(
        item["name"] == "skills"
        and item["reason"] == "skills_budget_exhausted"
        and item.get("capture_class") == "budget"
        and item["source"] == "latest_runtime_stats"
        for item in payload["degraded_services"]
    )


def test_cli_runtime_help_lists_runtime_profile_flags() -> None:
    runner = CliRunner()

    settings_help = runner.invoke(cli_module.cli, ["runtime", "settings", "show", "--help"])
    stats_help = runner.invoke(cli_module.cli, ["runtime", "stats", "--help"])
    status_help = runner.invoke(cli_module.cli, ["runtime", "status", "--help"])

    assert settings_help.exit_code == 0
    assert "--runtime-profile" in settings_help.output
    assert stats_help.exit_code == 0
    assert "--user-id" in stats_help.output
    assert status_help.exit_code == 0
    assert "--runtime-profile" in status_help.output
    assert "--user-id" in status_help.output


def test_cli_runtime_doctor_exposes_dev_feedback_and_top_pain_summary(
    tmp_path: Path,
) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".ace-lite.yml").write_text(
        "plan:\n  runtime_profile: bugfix\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db(db_path)
    _seed_dev_feedback_store(tmp_path, repo="repo-alpha")

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "doctor",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(skills_dir),
            "--stats-db-path",
            str(db_path),
            "--runtime-profile",
            "bugfix",
            "--user-id",
            "bench-user",
            "--no-probe-endpoints",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["stats"]["dev_feedback_summary"]["issue_count"] == 1
    assert payload["stats"]["dev_feedback_summary"]["fix_count"] == 1
    assert payload["stats"]["top_pain_summary"]["count"] == 1
    assert payload["stats"]["top_pain_summary"]["items"][0]["reason_code"] == "memory_fallback"
    assert payload["stats"]["top_pain_summary"]["items"][0]["runtime_event_count"] == 0
    assert payload["stats"]["top_pain_summary"]["items"][0]["manual_issue_count"] == 1
    assert payload["stats"]["top_pain_summary"]["items"][0]["linked_fix_issue_count"] == 1
    assert payload["stats"]["top_pain_summary"]["items"][0]["dev_issue_to_fix_rate"] == 1.0


def test_cli_runtime_doctor_canonicalizes_runtime_reason_aliases(
    tmp_path: Path,
) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".ace-lite.yml").write_text(
        "plan:\n  runtime_profile: bugfix\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "runtime-stats.db"
    _seed_runtime_stats_db_with_alias_reason(db_path)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "doctor",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(skills_dir),
            "--stats-db-path",
            str(db_path),
            "--runtime-profile",
            "bugfix",
            "--no-probe-endpoints",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["stats"]["top_pain_summary"]["count"] == 1
    assert payload["stats"]["top_pain_summary"]["items"][0]["reason_code"] == (
        "latency_budget_exceeded"
    )
    assert payload["stats"]["top_pain_summary"]["items"][0]["reason_family"] == "runtime"
    assert payload["stats"]["top_pain_summary"]["items"][0]["capture_class"] == "budget"
    assert payload["stats"]["top_pain_summary"]["items"][0]["runtime_event_count"] == 1


def test_cli_runtime_status_reports_degraded_services_for_bad_lsp_config(
    tmp_path: Path,
) -> None:
    (tmp_path / ".ace-lite.yml").write_text(
        (
            "plan:\n"
            "  lsp:\n"
            "    enabled: true\n"
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "runtime",
            "status",
            "--root",
            str(tmp_path),
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    service_health = {item["name"]: item for item in payload["service_health"]}
    assert service_health["lsp"]["status"] == "degraded"
    assert any(
        item["name"] == "lsp" and item["reason"] == "enabled_without_commands"
        for item in payload["degraded_services"]
    )

