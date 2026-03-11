from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

import ace_lite.cli as cli_module
from ace_lite.memory import NullMemoryProvider


def _seed_root(root: Path) -> None:
    (root / "skills").mkdir(parents=True, exist_ok=True)


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def test_cli_plan_accepts_remote_slot_policy_options(
    tmp_path: Path, monkeypatch
) -> None:
    _seed_root(tmp_path)

    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        cli_module, "create_memory_provider", lambda **kwargs: NullMemoryProvider()
    )

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
            "--remote-slot-policy-mode",
            "warn",
            "--remote-slot-allowlist",
            "observability.mcp_plugins,source_plan.writeback_template",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert captured["plugins_config"] == {
        "enabled": True,
        "remote_slot_policy_mode": "warn",
        "remote_slot_allowlist": [
            "observability.mcp_plugins",
            "source_plan.writeback_template",
        ],
    }


def test_cli_plan_resolves_remote_slot_policy_from_config(
    tmp_path: Path, monkeypatch
) -> None:
    _seed_root(tmp_path)
    (tmp_path / ".ace-lite.yml").write_text(
        """
plan:
  plugins:
    remote_slot_policy_mode: off
    remote_slot_allowlist:
      - observability.mcp_plugins
      - source_plan.writeback_template
""".strip()
        + "\n",
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        cli_module, "create_memory_provider", lambda **kwargs: NullMemoryProvider()
    )

    def fake_run_plan(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(cli_module, "run_plan", fake_run_plan)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "q",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert captured["plugins_config"] == {
        "enabled": True,
        "remote_slot_policy_mode": "off",
        "remote_slot_allowlist": [
            "observability.mcp_plugins",
            "source_plan.writeback_template",
        ],
    }
