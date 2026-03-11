from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from click.testing import CliRunner

import ace_lite.cli as cli_module
import ace_lite.cli_app.commands.plan as plan_command_module
from ace_lite.memory import NullMemoryProvider


def _seed_root(root: Path) -> None:
    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "sample.py").write_text("def demo() -> int:\n    return 1\n", encoding="utf-8")


def _cli_env(root: Path) -> dict[str, str]:
    return {"HOME": str(root), "USERPROFILE": str(root)}


def test_cli_plan_timeout_returns_fallback_payload(tmp_path: Path, monkeypatch) -> None:
    _seed_root(tmp_path)

    def fake_create_memory_provider(**kwargs: Any) -> NullMemoryProvider:
        return NullMemoryProvider()

    def slow_run_plan(**kwargs: Any) -> dict[str, Any]:
        time.sleep(1.2)
        return {"ok": True}

    def fake_plan_quick(**kwargs: Any) -> dict[str, Any]:
        return {
            "candidate_files": ["src/sample.py"],
            "steps": ["Inspect candidate files."],
        }

    monkeypatch.setattr(cli_module, "create_memory_provider", fake_create_memory_provider)
    monkeypatch.setattr(cli_module, "run_plan", slow_run_plan)
    monkeypatch.setattr(plan_command_module, "build_plan_quick", fake_plan_quick)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.cli,
        [
            "plan",
            "--query",
            "timeout demo",
            "--timeout-seconds",
            "1",
            "--repo",
            "demo",
            "--root",
            str(tmp_path),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--languages",
            "python",
            "--memory-primary",
            "none",
            "--memory-secondary",
            "none",
        ],
        env=_cli_env(tmp_path),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "3.2"
    assert payload["observability"]["error"]["type"] == "plan_timeout"
    assert payload["observability"]["error"]["fallback_mode"] == "plan_quick"
    assert payload["index"]["candidate_files"][0]["path"] == "src/sample.py"
    assert payload["source_plan"]["steps"] == ["Inspect candidate files."]

