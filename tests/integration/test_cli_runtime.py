from __future__ import annotations

import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

import ace_lite.cli as cli_module
from ace_lite.cli_app.commands import runtime as runtime_module
from ace_lite.runtime_stats import RuntimeInvocationStats
from ace_lite.runtime_stats_store import DurableStatsStore
from ace_lite.runtime_settings import RuntimeSettingsManager
from ace_lite.runtime_settings_store import (
    build_runtime_settings_record,
    persist_runtime_settings_record,
)


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


def test_cli_doctor_alias_runs_mcp_doctor(tmp_path: Path) -> None:
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
    assert payload["event"] == "mcp_doctor"
    assert payload["ok"] is True


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


def test_cli_runtime_stats_uses_default_user_scope_db_path(tmp_path: Path) -> None:
    db_path = tmp_path / ".ace-lite" / "runtime_state.db"
    _seed_runtime_stats_db(db_path)

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
