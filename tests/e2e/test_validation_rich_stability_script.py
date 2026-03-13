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


def test_validation_rich_stability_evaluate_stability() -> None:
    module = _load_script("run_validation_rich_stability.py")

    iterations = [
        module.IterationResult(
            run_id=1,
            command=["powershell", "benchmark"],
            returncode=0,
            elapsed_seconds=1.0,
            report_path="run-01/summary.json",
            summary_loaded=True,
            benchmark_passed=True,
            regressed=False,
            gate_failures=[],
            metrics={
                "task_success_rate": 1.0,
                "precision_at_k": 0.43,
                "noise_rate": 0.57,
                "latency_p95_ms": 617.66,
                "validation_test_count": 5.0,
                "evidence_insufficient_rate": 0.0,
                "missing_validation_rate": 0.0,
            },
        ),
        module.IterationResult(
            run_id=2,
            command=["powershell", "benchmark"],
            returncode=1,
            elapsed_seconds=1.2,
            report_path="run-02/summary.json",
            summary_loaded=True,
            benchmark_passed=False,
            regressed=True,
            gate_failures=[{"metric": "precision_at_k"}],
            metrics={
                "task_success_rate": 0.8,
                "precision_at_k": 0.35,
                "noise_rate": 0.65,
                "latency_p95_ms": 710.0,
                "validation_test_count": 4.0,
                "evidence_insufficient_rate": 0.2,
                "missing_validation_rate": 0.2,
            },
        ),
    ]

    summary = module.evaluate_stability(
        iterations=iterations,
        max_failure_rate=0.40,
    )

    assert summary["run_count"] == 2
    assert summary["passed_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["pass_rate"] == 0.5
    assert summary["failure_rate"] == 0.5
    assert summary["classification"] == "one_off_pass"
    assert summary["passed"] is False
    assert summary["failed_runs"][0]["run_id"] == 2
    precision_row = next(
        item for item in summary["metric_ranges"] if item["metric"] == "precision_at_k"
    )
    assert precision_row["min"] == pytest.approx(0.35)
    assert precision_row["max"] == pytest.approx(0.43)
    assert precision_row["spread"] == pytest.approx(0.08)


def test_validation_rich_stability_main_writes_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_validation_rich_stability.py")

    def fake_run_validation_rich_iteration(**kwargs):
        run_id = int(kwargs["run_id"])
        passed = run_id != 3
        return module.IterationResult(
            run_id=run_id,
            command=["powershell", "benchmark", str(run_id)],
            returncode=0 if passed else 1,
            elapsed_seconds=0.1 * run_id,
            report_path=str(tmp_path / f"run-{run_id:02d}" / "summary.json"),
            summary_loaded=True,
            benchmark_passed=passed,
            regressed=not passed,
            gate_failures=[] if passed else [{"metric": "task_success_rate"}],
            metrics={
                "task_success_rate": 1.0 if passed else 0.8,
                "precision_at_k": 0.43 if passed else 0.35,
                "noise_rate": 0.57 if passed else 0.65,
                "latency_p95_ms": 617.66 if passed else 710.0,
                "validation_test_count": 5.0 if passed else 4.0,
                "evidence_insufficient_rate": 0.0 if passed else 0.2,
                "missing_validation_rate": 0.0 if passed else 0.2,
            },
        )

    monkeypatch.setattr(
        module, "_run_validation_rich_iteration", fake_run_validation_rich_iteration
    )
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_validation_rich_stability.py",
            "--runs",
            "3",
            "--output-dir",
            str(tmp_path / "stability"),
            "--max-failure-rate",
            "0.34",
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    summary_path = tmp_path / "stability" / "stability_summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))

    assert payload["run_count"] == 3
    assert payload["passed_count"] == 2
    assert payload["failed_count"] == 1
    assert payload["classification"] == "mixed"
    assert payload["passed"] is True
    assert payload["thresholds"]["min_task_success_rate"] == pytest.approx(0.9)
    assert len(payload["iterations"]) == 3

    markdown = (tmp_path / "stability" / "stability_summary.md").read_text(
        encoding="utf-8"
    )
    assert "# Validation-Rich Stability Summary" in markdown
    assert "## Metric Ranges" in markdown
    assert "| precision_at_k |" in markdown


def test_validation_rich_stability_main_fails_on_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_validation_rich_stability.py")

    def fake_run_validation_rich_iteration(**kwargs):
        run_id = int(kwargs["run_id"])
        return module.IterationResult(
            run_id=run_id,
            command=["powershell", "benchmark", str(run_id)],
            returncode=1,
            elapsed_seconds=0.1,
            report_path=str(tmp_path / f"run-{run_id:02d}" / "summary.json"),
            summary_loaded=True,
            benchmark_passed=False,
            regressed=True,
            gate_failures=[{"metric": "precision_at_k"}],
            metrics={
                "task_success_rate": 0.8,
                "precision_at_k": 0.35,
                "noise_rate": 0.65,
                "latency_p95_ms": 710.0,
                "validation_test_count": 4.0,
                "evidence_insufficient_rate": 0.2,
                "missing_validation_rate": 0.2,
            },
        )

    monkeypatch.setattr(
        module, "_run_validation_rich_iteration", fake_run_validation_rich_iteration
    )
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_validation_rich_stability.py",
            "--runs",
            "2",
            "--output-dir",
            str(tmp_path / "stability"),
            "--fail-on-gate",
        ],
    )

    exit_code = module.main()
    assert exit_code == 1
