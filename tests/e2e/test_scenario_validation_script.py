from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_script(name: str):
    module_name = f"script_{name.replace('.', '_')}"
    module_path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _plan_payload() -> dict[str, object]:
    return {
        "memory": {"count": 1, "profile": {"selected_count": 1}, "capture": {"triggered": True}},
        "index": {
            "policy_name": "feature",
            "cochange": {"enabled": True},
            "candidate_files": [
                {"path": "src/ace_lite/pipeline/stages/index.py"},
                {"path": "src/ace_lite/pipeline/stages/source_plan.py"},
            ],
        },
        "repomap": {"enabled": True},
        "source_plan": {
            "steps": [{"id": 1}, {"id": 2}],
            "chunk_steps": [{"id": 1}, {"id": 2}],
            "candidate_chunks": [{"path": "src/ace_lite/pipeline/stages/index.py"}],
            "chunk_budget_used": 90.0,
            "chunk_budget_limit": 300.0,
        },
    }


def test_scenario_expectations_helper_passes() -> None:
    module = _load_script("run_scenario_validation.py")
    checks = module._evaluate_plan_expectations(
        payload=_plan_payload(),
        expected={
            "expected_policy": "feature",
            "repomap_enabled": True,
            "cochange_enabled": True,
            "require_memory_hit": True,
            "require_profile_selected": True,
            "require_capture_triggered": True,
            "candidate_paths_contains": ["pipeline/stages"],
            "min_candidate_files": 2,
            "min_candidate_chunks": 1,
            "min_source_plan_steps": 2,
            "min_chunk_steps": 2,
            "max_chunk_budget_ratio": 0.4,
        },
    )

    assert checks
    assert all(bool(item.get("passed", False)) for item in checks)


def test_scenario_main_writes_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script("run_scenario_validation.py")
    root = tmp_path / "repo"
    skills_dir = root / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "skill.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nok\n",
        encoding="utf-8",
    )

    scenarios = root / "scenarios.yaml"
    scenarios.write_text(
        """
scenarios:
  - name: one
    steps:
      - action: plan
        query: demo
""".lstrip(),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    def fake_run_step(**kwargs):
        _ = kwargs
        return module.StepExecution(
            action="plan",
            passed=True,
            elapsed_ms=12.0,
            checks=[{"metric": "demo", "passed": True}],
            details={"query": "demo"},
            error=None,
        )

    monkeypatch.setattr(module, "_run_step", fake_run_step)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_scenario_validation.py",
            "--scenarios",
            str(scenarios),
            "--output-dir",
            str(output_dir),
            "--root",
            str(root),
            "--skills-dir",
            str(skills_dir),
            "--min-pass-rate",
            "1.0",
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    results = json.loads((output_dir / "results.json").read_text(encoding="utf-8"))
    report = (output_dir / "report.md").read_text(encoding="utf-8")

    assert summary["scenario_count"] == 1
    assert summary["passed_count"] == 1
    assert summary["threshold_passed"] is True
    assert len(results["scenarios"]) == 1
    assert "# ACE-Lite Scenario Validation" in report


def test_scenario_fail_on_thresholds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script("run_scenario_validation.py")
    root = tmp_path / "repo"
    skills_dir = root / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "skill.md").write_text(
        "---\nname: sample\nintents: [implement]\n---\n# Intro\nok\n",
        encoding="utf-8",
    )

    scenarios = root / "scenarios.yaml"
    scenarios.write_text(
        """
scenarios:
  - name: one
    steps:
      - action: plan
        query: demo
""".lstrip(),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    def fake_run_step(**kwargs):
        _ = kwargs
        return module.StepExecution(
            action="plan",
            passed=False,
            elapsed_ms=5.0,
            checks=[{"metric": "demo", "passed": False}],
            details={"query": "demo"},
            error="check_failed",
        )

    monkeypatch.setattr(module, "_run_step", fake_run_step)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_scenario_validation.py",
            "--scenarios",
            str(scenarios),
            "--output-dir",
            str(output_dir),
            "--root",
            str(root),
            "--skills-dir",
            str(skills_dir),
            "--min-pass-rate",
            "1.0",
            "--fail-on-thresholds",
        ],
    )

    exit_code = module.main()
    assert exit_code == 1
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["passed_count"] == 0
    assert summary["threshold_passed"] is False
