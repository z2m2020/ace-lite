from __future__ import annotations

import importlib
import sys
from pathlib import Path

from ace_lite.release_freeze import StepResult, load_yaml_config, run_step


def test_release_freeze_facade_exports_match_support_module() -> None:
    module = importlib.import_module("ace_lite.release_freeze.support")

    assert StepResult is module.StepResult
    assert load_yaml_config is module.load_yaml_config
    assert run_step is module.run_step


def test_load_yaml_config_is_fail_open_for_missing_and_invalid_files(tmp_path: Path) -> None:
    assert load_yaml_config(path=tmp_path / "missing.yaml") == {}

    invalid_path = tmp_path / "invalid.yaml"
    invalid_path.write_text(":\n- [", encoding="utf-8")
    assert load_yaml_config(path=invalid_path) == {}


def test_run_step_writes_logs_and_result_paths(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    result = run_step(
        name="version",
        command=[sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        logs_dir=logs_dir,
    )

    assert result.passed is True
    assert Path(result.stdout_path).exists()
    assert Path(result.stderr_path).exists()
    assert Path(result.stdout_path).read_text(encoding="utf-8").strip() == "ok"
    assert Path(result.stderr_path).read_text(encoding="utf-8") == ""
