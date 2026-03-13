param(
    [string]$OutputDir = "artifacts/validation/latest",
    [switch]$IncludeValidationRichBenchmark
)

$ErrorActionPreference = "Stop"

function Assert-LastExitCode {
    param(
        [Parameter(Mandatory=$true)]
        [string]$StepName
    )
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $StepName (exit code=$LASTEXITCODE)"
    }
}

Write-Host "=== ACE-Lite Full Validation Suite ===" -ForegroundColor Cyan

$validationRichOutputDir = Join-Path $OutputDir "validation_rich"
$validationRichResultsPath = Join-Path $validationRichOutputDir "results.json"
$validationRichSummaryPath = Join-Path $validationRichOutputDir "summary.json"
$validationRichReportPath = Join-Path $validationRichOutputDir "report.md"
$validationRichTrendOutputDir = Join-Path $validationRichOutputDir "trend"
$validationRichTrendJsonPath = Join-Path $validationRichTrendOutputDir "validation_rich_trend_report.json"
$validationRichTrendMarkdownPath = Join-Path $validationRichTrendOutputDir "validation_rich_trend_report.md"

$totalSteps = if ($IncludeValidationRichBenchmark) { 9 } else { 7 }
$step = 1

Write-Host "`n[$step/$totalSteps] Running unit tests..." -ForegroundColor Yellow
python -m pytest tests/unit/ -q --tb=short
Assert-LastExitCode -StepName "unit tests"
$step += 1

Write-Host "`n[$step/$totalSteps] Running integration tests..." -ForegroundColor Yellow
python -m pytest tests/integration/ -q --tb=short
Assert-LastExitCode -StepName "integration tests"
$step += 1

Write-Host "`n[$step/$totalSteps] Running E2E tests..." -ForegroundColor Yellow
python -m pytest tests/e2e/ -q --tb=short
Assert-LastExitCode -StepName "e2e tests"
$step += 1

Write-Host "`n[$step/$totalSteps] Running scenario validation..." -ForegroundColor Yellow
python scripts/run_scenario_validation.py `
    --scenarios benchmark/cases/scenarios/real_world.yaml `
    --output-dir "$OutputDir/scenarios" `
    --fail-on-thresholds `
    --min-pass-rate 1.0
Assert-LastExitCode -StepName "scenario validation"
$step += 1

Write-Host "`n[$step/$totalSteps] Running benchmark matrix..." -ForegroundColor Yellow
python scripts/run_benchmark_matrix.py `
    --matrix-config benchmark/matrix/repos.yaml `
    --output-dir "$OutputDir/benchmark" `
    --fail-on-thresholds
Assert-LastExitCode -StepName "benchmark matrix"
$step += 1

if ($IncludeValidationRichBenchmark) {
    Write-Host "`n[$step/$totalSteps] Running validation-rich benchmark..." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "run_benchmark.ps1") `
        -Lane validation_rich `
        -Repo ace-lite-engine `
        -OutputDir $validationRichOutputDir
    Assert-LastExitCode -StepName "validation-rich benchmark"
    Write-Host "  validation-rich results: $validationRichResultsPath" -ForegroundColor DarkGray
    Write-Host "  validation-rich summary: $validationRichSummaryPath" -ForegroundColor DarkGray
    Write-Host "  validation-rich report:  $validationRichReportPath" -ForegroundColor DarkGray
    $step += 1
}

Write-Host "`n[$step/$totalSteps] Running freeze regression..." -ForegroundColor Yellow
$freezeArgs = @(
    "scripts/run_release_freeze_regression.py",
    "--matrix-config",
    "benchmark/matrix/repos.yaml",
    "--output-dir",
    "$OutputDir/freeze",
    "--fail-on-thresholds",
    "--plugin-gate-profile",
    "strict"
)
if ($IncludeValidationRichBenchmark) {
    $freezeArgs += @(
        "--validation-rich-summary",
        $validationRichSummaryPath
    )
}
python @freezeArgs
Assert-LastExitCode -StepName "freeze regression"
$step += 1

Write-Host "`n[$step/$totalSteps] Running trend checks..." -ForegroundColor Yellow
$metricsArgs = @(
    "scripts/metrics_collector.py",
    "--current",
    "$OutputDir/benchmark/matrix_summary.json",
    "--output",
    "$OutputDir/metrics.json",
    "--fail-on-regression"
)
if ($IncludeValidationRichBenchmark) {
    $metricsArgs += @(
        "--validation-rich-current",
        $validationRichSummaryPath
    )
}
python @metricsArgs
Assert-LastExitCode -StepName "trend checks"

if ($IncludeValidationRichBenchmark) {
    $step += 1
    Write-Host "`n[$step/$totalSteps] Running validation-rich trend report..." -ForegroundColor Yellow
    python scripts/build_validation_rich_trend_report.py `
        --history-root artifacts/benchmark/validation_rich `
        --latest-report $validationRichSummaryPath `
        --output-dir $validationRichTrendOutputDir
    Assert-LastExitCode -StepName "validation-rich trend report"
    Write-Host "  validation-rich trend json: $validationRichTrendJsonPath" -ForegroundColor DarkGray
    Write-Host "  validation-rich trend md:   $validationRichTrendMarkdownPath" -ForegroundColor DarkGray
}

Write-Host "`n=== Validation Complete ===" -ForegroundColor Green
