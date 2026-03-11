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


def test_freeze_stability_evaluate_stability() -> None:
    module = _load_script("run_freeze_stability.py")

    iterations = [
        module.IterationResult(
            run_id=1,
            command=["python", "freeze"],
            returncode=0,
            elapsed_seconds=1.0,
            report_path="a.json",
            freeze_passed=True,
            tabiv3_retry_attempts=1,
            gate_failures=[],
            feature_slice_results={
                "dependency_recall": True,
                "perturbation": True,
                "repomap_perturbation": True,
            },
        ),
        module.IterationResult(
            run_id=2,
            command=["python", "freeze"],
            returncode=1,
            elapsed_seconds=2.0,
            report_path="b.json",
            freeze_passed=False,
            tabiv3_retry_attempts=3,
            gate_failures=[{"gate": "tabiv3_gate", "metric": "latency_p95_ms"}],
            feature_slice_results={
                "dependency_recall": True,
                "perturbation": False,
                "repomap_perturbation": True,
            },
        ),
    ]

    summary = module.evaluate_stability(
        iterations=iterations,
        max_failure_rate=0.40,
        max_retry_median=2.0,
        tracked_feature_slices=["dependency_recall", "perturbation"],
        min_feature_slice_pass_rate=1.0,
    )

    assert summary["run_count"] == 2
    assert summary["passed_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["pass_rate"] == 0.5
    assert summary["tabiv3_retry_median"] == 2.0
    assert summary["passed"] is False
    assert summary["classification"] == "one_off_pass"
    assert summary["failed_runs"][0]["run_id"] == 2
    assert summary["tracked_feature_slice_failures"] == [
        {
            "slice": "perturbation",
            "pass_rate": 0.5,
            "expected_min_pass_rate": 1.0,
            "classification": "one_off_pass",
        }
    ]


def test_freeze_stability_main_writes_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("run_freeze_stability.py")

    def fake_run_freeze_iteration(**kwargs):
        run_id = int(kwargs["run_id"])
        return module.IterationResult(
            run_id=run_id,
            command=["python", "freeze", str(run_id)],
            returncode=0 if run_id != 3 else 1,
            elapsed_seconds=0.1 * run_id,
            report_path=str(tmp_path / f"run-{run_id:02d}" / "freeze_regression.json"),
            freeze_passed=run_id != 3,
            tabiv3_retry_attempts=1 if run_id != 2 else 2,
            gate_failures=[] if run_id != 3 else [{"gate": "concept_gate", "metric": "noise_rate"}],
            feature_slice_results={
                "dependency_recall": True,
                "perturbation": True,
                "repomap_perturbation": True,
                "feedback": run_id == 1,
            },
        )

    monkeypatch.setattr(module, "_run_freeze_iteration", fake_run_freeze_iteration)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "run_freeze_stability.py",
            "--runs",
            "3",
            "--output-dir",
            str(tmp_path / "stability"),
            "--max-failure-rate",
            "0.34",
            "--max-retry-median",
            "2",
            "--tracked-feature-slices",
            "dependency_recall,perturbation,repomap_perturbation",
            "--min-feature-slice-pass-rate",
            "1.0",
            "--fail-on-gate",
        ],
    )

    exit_code = module.main()
    assert exit_code == 0

    summary_path = tmp_path / "stability" / "stability_summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))

    assert payload["run_count"] == 3
    assert payload["passed_count"] == 2
    assert payload["failed_count"] == 1
    assert payload["passed"] is True
    assert payload["classification"] == "mixed"
    assert payload["tracked_feature_slices"] == [
        "dependency_recall",
        "perturbation",
        "repomap_perturbation",
    ]
    assert payload["tracked_feature_slice_failures"] == []
    assert len(payload["iterations"]) == 3
    assert payload["feature_slice_stability"][0]["name"] == "dependency_recall"
    assert payload["feature_slice_stability"][0]["classification"] == "stable_pass"
