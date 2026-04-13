from __future__ import annotations

from pathlib import Path

import yaml


def test_full_validation_script_includes_required_gates() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "run_full_validation.ps1"
    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")
    assert "function Assert-LastExitCode" in content
    assert "[switch]$IncludeValidationRichBenchmark" in content
    assert "run_scenario_validation.py" in content
    assert "run_benchmark_matrix.py" in content
    assert "run_benchmark.ps1" in content
    assert "-Lane validation_rich" in content
    assert "validation-rich benchmark" in content
    assert '$validationRichOutputDir = Join-Path $OutputDir "validation_rich"' in content
    assert '$validationRichResultsPath = Join-Path $validationRichOutputDir "results.json"' in content
    assert '$validationRichSummaryPath = Join-Path $validationRichOutputDir "summary.json"' in content
    assert '$validationRichReportPath = Join-Path $validationRichOutputDir "report.md"' in content
    assert '$validationRichTrendOutputDir = Join-Path $validationRichOutputDir "trend"' in content
    assert '$validationRichTrendJsonPath = Join-Path $validationRichTrendOutputDir "validation_rich_trend_report.json"' in content
    assert '$validationRichTrendMarkdownPath = Join-Path $validationRichTrendOutputDir "validation_rich_trend_report.md"' in content
    assert "run_release_freeze_regression.py" in content
    assert "--validation-rich-summary" in content
    assert "metrics_collector.py" in content
    assert "--validation-rich-current" in content
    assert "build_validation_rich_trend_report.py" in content
    assert "--history-root artifacts/benchmark/validation_rich" in content
    assert "validation-rich results:" in content
    assert "validation-rich summary:" in content
    assert "validation-rich report:" in content
    assert "validation-rich trend json:" in content
    assert "validation-rich trend md:" in content
    assert 'Assert-LastExitCode -StepName "validation-rich benchmark"' in content
    assert 'Assert-LastExitCode -StepName "trend checks"' in content
    assert 'Assert-LastExitCode -StepName "validation-rich trend report"' in content


def test_full_validation_matrix_config_enforces_validation_rich_gate() -> None:
    matrix_path = Path(__file__).resolve().parents[2] / "benchmark" / "matrix" / "repos.yaml"
    assert matrix_path.exists()

    payload = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)

    freeze = payload.get("freeze")
    assert isinstance(freeze, dict)
    validation_rich_gate = freeze.get("validation_rich_gate")
    assert isinstance(validation_rich_gate, dict)
    assert validation_rich_gate.get("mode") == "enforced"
    assert validation_rich_gate.get("thresholds") == {
        "task_success_rate_min": 0.90,
        "precision_at_k_min": 0.40,
        "noise_rate_max": 0.60,
        "latency_p95_ms_max": 700.0,
        "validation_test_count_min": 5.0,
        "missing_validation_rate_max": 0.0,
        "evidence_insufficient_rate_max": 0.0,
    }
