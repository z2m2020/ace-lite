from __future__ import annotations

from pathlib import Path


def test_run_benchmark_script_supports_validation_rich_lane() -> None:
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "run_benchmark.ps1"
    assert script_path.exists()

    content = script_path.read_text(encoding="utf-8")
    assert '[ValidateSet("default", "validation_rich")]' in content
    assert 'Write-Host "[ace-lite] running benchmark lane' in content
    assert '$validationRichResultsPath = Join-Path $validationRichOutputDir "results.json"' in content
    assert '$validationRichSummaryPath = Join-Path $validationRichOutputDir "summary.json"' in content
    assert '$validationRichReportPath = Join-Path $validationRichOutputDir "report.md"' in content
    assert '$validationRichCases = Join-Path $root "benchmark/cases/validation_rich_cases.yaml"' in content
    assert '$validationRichJunitXml = Join-Path $root "benchmark/fixtures/validation_rich_junit.xml"' in content
    assert '$validationRichOutputDir = Join-Path $root "artifacts/benchmark/validation_rich/latest"' in content
    assert "benchmark/cases/default.yaml" in content
    assert "benchmark/cases/validation_rich_cases.yaml" in content
    assert "benchmark/fixtures/validation_rich_junit.xml" in content
    assert "artifacts/benchmark/validation_rich/latest" in content
    assert '$benchmarkLanguages = "python,typescript,javascript,go,markdown"' in content
    assert '$benchmarkWarmupRuns = "1"' in content
    assert 'Write-Host "[ace-lite] refreshing index..."' in content
    assert '& ace-lite index --root $root --languages $benchmarkLanguages --output (Join-Path $root "context-map/index.json")' in content
    assert '--languages' in content
    assert '$benchmarkLanguages,' in content
    assert '--warmup-runs' in content
    assert '$benchmarkWarmupRuns,' in content
    assert '$contractResultsPath = Join-Path $OutputDir "results.json"' in content
    assert '$contractSummaryPath = Join-Path $OutputDir "summary.json"' in content
    assert '$contractReportPath = Join-Path $OutputDir "report.md"' in content
    assert "& ace-lite @benchmarkArgs" in content
    assert "& ace-lite benchmark report --input $results" in content
    assert 'Write-Host "[ace-lite] benchmark artifacts:"' in content
