param(
    [string]$OutputDir = "artifacts/validation/latest"
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

Write-Host "`n[1/7] Running unit tests..." -ForegroundColor Yellow
python -m pytest tests/unit/ -q --tb=short
Assert-LastExitCode -StepName "unit tests"

Write-Host "`n[2/7] Running integration tests..." -ForegroundColor Yellow
python -m pytest tests/integration/ -q --tb=short
Assert-LastExitCode -StepName "integration tests"

Write-Host "`n[3/7] Running E2E tests..." -ForegroundColor Yellow
python -m pytest tests/e2e/ -q --tb=short
Assert-LastExitCode -StepName "e2e tests"

Write-Host "`n[4/7] Running scenario validation..." -ForegroundColor Yellow
python scripts/run_scenario_validation.py `
    --scenarios benchmark/cases/scenarios/real_world.yaml `
    --output-dir "$OutputDir/scenarios" `
    --fail-on-thresholds `
    --min-pass-rate 1.0
Assert-LastExitCode -StepName "scenario validation"

Write-Host "`n[5/7] Running benchmark matrix..." -ForegroundColor Yellow
python scripts/run_benchmark_matrix.py `
    --matrix-config benchmark/matrix/repos.yaml `
    --output-dir "$OutputDir/benchmark" `
    --fail-on-thresholds
Assert-LastExitCode -StepName "benchmark matrix"

Write-Host "`n[6/7] Running freeze regression..." -ForegroundColor Yellow
python scripts/run_release_freeze_regression.py `
    --matrix-config benchmark/matrix/repos.yaml `
    --output-dir "$OutputDir/freeze" `
    --fail-on-thresholds `
    --plugin-gate-profile strict
Assert-LastExitCode -StepName "freeze regression"

Write-Host "`n[7/7] Running trend checks..." -ForegroundColor Yellow
python scripts/metrics_collector.py `
    --current "$OutputDir/benchmark/matrix_summary.json" `
    --output "$OutputDir/metrics.json" `
    --fail-on-regression
Assert-LastExitCode -StepName "trend checks"

Write-Host "`n=== Validation Complete ===" -ForegroundColor Green
