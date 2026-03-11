from __future__ import annotations

import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

import ace_lite.cli as cli_module
from ace_lite.cli_app.commands import runtime as runtime_module


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


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
    assert payload["resolved_user_id"] == "test-user"
    env_lines = payload.get("env", [])
    assert "ACE_LITE_MEMORY_PRIMARY=rest" in env_lines
    assert "ACE_LITE_MEMORY_SECONDARY=none" in env_lines
    assert "ACE_LITE_USER_ID=test-user" in env_lines


def test_cli_runtime_setup_codex_mcp_apply_writes_snapshot(
    tmp_path: Path, monkeypatch
) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

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
