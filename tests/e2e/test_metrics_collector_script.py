from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

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


def _matrix_summary(payload_path: Path, *, precision: float, noise: float) -> None:
    payload = {
        "repos": [
            {
                "name": "repo-a",
                "metrics": {
                    "precision_at_k": precision,
                    "noise_rate": noise,
                    "latency_p95_ms": 200.0,
                    "chunk_hit_at_k": 0.91,
                    "notes_hit_ratio": 0.75,
                    "profile_selected_mean": 0.65,
                },
            },
            {
                "name": "repo-b",
                "metrics": {
                    "precision_at_k": precision - 0.02,
                    "noise_rate": noise + 0.01,
                    "latency_p95_ms": 220.0,
                    "chunk_hit_at_k": 0.89,
                    "notes_hit_ratio": 0.70,
                    "profile_selected_mean": 0.55,
                },
            },
        ]
    }
    payload_path.write_text(json.dumps(payload), encoding="utf-8")


def _validation_rich_summary(
    payload_path: Path,
    *,
    task_success: float,
    precision: float,
    noise: float,
    validation_tests: float,
) -> None:
    payload_path.write_text(
        json.dumps(
            {
                "metrics": {
                    "task_success_rate": task_success,
                    "precision_at_k": precision,
                    "noise_rate": noise,
                    "latency_p95_ms": 620.0,
                    "validation_test_count": validation_tests,
                    "missing_validation_rate": 0.0,
                    "evidence_insufficient_rate": 0.0,
                }
            }
        ),
        encoding="utf-8",
    )


def test_metrics_collector_helpers_detect_regression(tmp_path: Path) -> None:
    module = _load_script("metrics_collector.py")
    current_path = tmp_path / "current.json"
    previous_path = tmp_path / "previous.json"
    _matrix_summary(previous_path, precision=0.70, noise=0.30)
    _matrix_summary(current_path, precision=0.62, noise=0.36)

    current = module.collect_metrics(summary_path=current_path)
    previous = module.collect_metrics(summary_path=previous_path)
    regressions = module.check_regressions(
        current=current,
        previous=previous,
        tolerance_ratio=0.05,
    )
    target_failures = module.check_targets(metrics=current)

    assert current["precision_at_k"] < previous["precision_at_k"]
    assert regressions
    assert any(item["metric"] == "precision_at_k" for item in regressions)
    assert target_failures
    assert any(item["metric"] == "precision_at_k" for item in target_failures)


def test_metrics_collector_main_writes_report(tmp_path: Path, monkeypatch) -> None:
    module = _load_script("metrics_collector.py")
    current_path = tmp_path / "current.json"
    previous_path = tmp_path / "previous.json"
    _matrix_summary(previous_path, precision=0.72, noise=0.28)
    _matrix_summary(current_path, precision=0.73, noise=0.27)
    output_path = tmp_path / "report.json"

    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "metrics_collector.py",
            "--current",
            str(current_path),
            "--previous",
            str(previous_path),
            "--output",
            str(output_path),
            "--fail-on-regression",
        ],
    )

    exit_code = module.main()
    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["matrix_lane"] == {
        "enabled": True,
        "loaded": True,
        "repo_count": 2,
        "passed": True,
    }
    assert payload["regressions"] == []


def test_metrics_collector_collects_validation_rich_metrics(tmp_path: Path) -> None:
    module = _load_script("metrics_collector.py")
    summary_path = tmp_path / "validation-rich.json"
    _validation_rich_summary(
        summary_path,
        task_success=1.0,
        precision=0.425,
        noise=0.575,
        validation_tests=5.0,
    )

    metrics = module.collect_validation_rich_metrics(summary_path=summary_path)
    assert metrics == {
        "task_success_rate": 1.0,
        "precision_at_k": 0.425,
        "noise_rate": 0.575,
        "latency_p95_ms": 620.0,
        "validation_test_count": 5.0,
        "missing_validation_rate": 0.0,
        "evidence_insufficient_rate": 0.0,
    }


def test_metrics_collector_main_writes_validation_rich_section(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("metrics_collector.py")
    current_path = tmp_path / "current.json"
    previous_path = tmp_path / "previous.json"
    validation_current = tmp_path / "validation-current.json"
    validation_previous = tmp_path / "validation-previous.json"
    _matrix_summary(previous_path, precision=0.72, noise=0.28)
    _matrix_summary(current_path, precision=0.73, noise=0.27)
    _validation_rich_summary(
        validation_previous,
        task_success=1.0,
        precision=0.425,
        noise=0.575,
        validation_tests=5.0,
    )
    _validation_rich_summary(
        validation_current,
        task_success=1.0,
        precision=0.43,
        noise=0.57,
        validation_tests=5.0,
    )
    output_path = tmp_path / "report.json"

    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "metrics_collector.py",
            "--current",
            str(current_path),
            "--previous",
            str(previous_path),
            "--validation-rich-current",
            str(validation_current),
            "--validation-rich-previous",
            str(validation_previous),
            "--output",
            str(output_path),
            "--fail-on-regression",
        ],
    )

    exit_code = module.main()
    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["matrix_lane"]["passed"] is True
    assert payload["validation_rich_lane"] == {
        "enabled": True,
        "loaded": True,
        "metric_count": 7,
        "passed": True,
    }
    assert payload["validation_rich_current_path"] == str(validation_current)
    assert payload["validation_rich_previous_path"] == str(validation_previous)
    assert payload["validation_rich_current_metrics"]["precision_at_k"] == 0.43
    assert payload["validation_rich_previous_metrics"]["precision_at_k"] == 0.425
    assert payload["validation_rich_regressions"] == []


def test_metrics_collector_does_not_fail_validation_rich_only_run_on_missing_matrix(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script("metrics_collector.py")
    missing_matrix = tmp_path / "missing-matrix.json"
    validation_current = tmp_path / "validation-current.json"
    _validation_rich_summary(
        validation_current,
        task_success=1.0,
        precision=0.43,
        noise=0.57,
        validation_tests=5.0,
    )
    output_path = tmp_path / "report.json"

    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "metrics_collector.py",
            "--current",
            str(missing_matrix),
            "--validation-rich-current",
            str(validation_current),
            "--output",
            str(output_path),
            "--fail-on-regression",
        ],
    )

    exit_code = module.main()
    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["matrix_lane"] == {
        "enabled": False,
        "loaded": False,
        "repo_count": 0,
        "passed": True,
    }
    assert payload["validation_rich_lane"] == {
        "enabled": True,
        "loaded": True,
        "metric_count": 7,
        "passed": True,
    }
    assert payload["target_failures"] == []


def test_metrics_collector_skips_memory_targets_when_memory_disabled(tmp_path: Path) -> None:
    module = _load_script("metrics_collector.py")
    summary_path = tmp_path / "matrix.json"
    summary_path.write_text(
        json.dumps(
            {
                "repos": [
                    {
                        "name": "repo-a",
                        "metrics": {
                            "precision_at_k": 0.9,
                            "noise_rate": 0.1,
                            "latency_p95_ms": 120.0,
                            "chunk_hit_at_k": 0.95,
                            "notes_hit_ratio": 0.0,
                            "profile_selected_mean": 0.0,
                            "capture_trigger_ratio": 0.0,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    metrics = module.collect_metrics(summary_path=summary_path)
    skipped_failures = module._check_targets(
        metrics=metrics,
        enforce_memory_metrics=False,
    )
    enforced_failures = module._check_targets(
        metrics=metrics,
        enforce_memory_metrics=True,
    )

    assert all(item["metric"] not in {"memory_recall_rate", "profile_utilization"} for item in skipped_failures)
    assert any(item["metric"] == "memory_recall_rate" for item in enforced_failures)
    assert any(item["metric"] == "profile_utilization" for item in enforced_failures)
