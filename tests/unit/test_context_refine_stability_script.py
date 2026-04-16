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


def test_context_refine_stability_evaluate_stability() -> None:
    module = _load_script("run_context_refine_stability.py")

    iterations = [
        module.IterationResult(
            run_id=1,
            command=["python", "benchmark"],
            returncode=0,
            elapsed_seconds=0.2,
            report_path="run-01/summary.json",
            summary_loaded=True,
            benchmark_passed=True,
            regressed=False,
            failures=[],
            metrics={
                "present_case_rate": 1.0,
                "watch_case_rate": 0.2,
                "thin_context_case_rate": 0.0,
                "keep_count_mean": 2.0,
                "need_more_read_count_mean": 1.0,
            },
            context_refine_summary={
                "present_case_rate": 1.0,
                "watch_case_rate": 0.2,
                "thin_context_case_rate": 0.0,
                "keep_count_mean": 2.0,
                "need_more_read_count_mean": 1.0,
            },
        ),
        module.IterationResult(
            run_id=2,
            command=["python", "benchmark"],
            returncode=1,
            elapsed_seconds=0.3,
            report_path="run-02/summary.json",
            summary_loaded=True,
            benchmark_passed=False,
            regressed=True,
            failures=[{"metric": "watch_case_rate"}],
            metrics={
                "present_case_rate": 0.75,
                "watch_case_rate": 0.8,
                "thin_context_case_rate": 0.25,
                "keep_count_mean": 1.0,
                "need_more_read_count_mean": 3.0,
            },
            context_refine_summary={
                "present_case_rate": 0.75,
                "watch_case_rate": 0.8,
                "thin_context_case_rate": 0.25,
                "keep_count_mean": 1.0,
                "need_more_read_count_mean": 3.0,
            },
        ),
    ]

    summary = module.evaluate_stability(iterations=iterations, max_failure_rate=0.4)

    assert summary["run_count"] == 2
    assert summary["failed_count"] == 1
    assert summary["classification"] == "one_off_pass"
    assert summary["passed"] is False
    assert summary["latest_context_refine_summary"]["watch_case_rate"] == pytest.approx(0.8)


def test_context_refine_stability_main_writes_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_script("run_context_refine_stability.py")
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "context_refine_summary": {
                    "present_case_rate": 1.0,
                    "watch_case_rate": 0.1,
                    "thin_context_case_rate": 0.0,
                    "keep_count_mean": 2.0,
                    "need_more_read_count_mean": 0.5,
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        module.subprocess, "run", lambda *args, **kwargs: type("R", (), {"returncode": 0})()
    )
    output_path = tmp_path / "context_refine_stability.json"
    module.sys.argv = [
        "run_context_refine_stability.py",
        "--root",
        str(tmp_path),
        "--summary",
        str(summary_path),
        "--output",
        str(output_path),
        "--runs",
        "1",
    ]

    exit_code = module.main()
    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "context_refine_stability_v1"
    assert payload["passed"] is True
    assert payload["latest_context_refine_summary"]["keep_count_mean"] == pytest.approx(2.0)
