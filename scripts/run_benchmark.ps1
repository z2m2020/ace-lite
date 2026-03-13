param(
  [ValidateSet("default", "validation_rich")]
  [string]$Lane = "default",
  [string]$Repo,
  [string]$OutputDir
)

$root = (Resolve-Path ".").Path
$skillsDir = Join-Path $root "skills"
$defaultCases = Join-Path $root "benchmark/cases/default.yaml"
$defaultOutputDir = Join-Path $root "artifacts/benchmark/latest"
$defaultResultsPath = Join-Path $defaultOutputDir "results.json"
$defaultSummaryPath = Join-Path $defaultOutputDir "summary.json"
$defaultReportPath = Join-Path $defaultOutputDir "report.md"
$validationRichCases = Join-Path $root "benchmark/cases/validation_rich_cases.yaml"
$validationRichJunitXml = Join-Path $root "benchmark/fixtures/validation_rich_junit.xml"
$validationRichOutputDir = Join-Path $root "artifacts/benchmark/validation_rich/latest"
$validationRichResultsPath = Join-Path $validationRichOutputDir "results.json"
$validationRichSummaryPath = Join-Path $validationRichOutputDir "summary.json"
$validationRichReportPath = Join-Path $validationRichOutputDir "report.md"
$benchmarkLanguages = "python,typescript,javascript,go,markdown"
$benchmarkWarmupRuns = "1"

switch ($Lane) {
  "validation_rich" {
    if (-not $PSBoundParameters.ContainsKey("Repo")) {
      $Repo = "ace-lite-engine"
    }
    if (-not $PSBoundParameters.ContainsKey("OutputDir")) {
      $OutputDir = $validationRichOutputDir
    }
    $cases = $validationRichCases
    $extraArgs = @(
      "--junit-xml",
      $validationRichJunitXml
    )
  }
  default {
    if (-not $PSBoundParameters.ContainsKey("Repo")) {
      $Repo = "mem0"
    }
    if (-not $PSBoundParameters.ContainsKey("OutputDir")) {
      $OutputDir = $defaultOutputDir
    }
    $cases = $defaultCases
    $extraArgs = @()
  }
}

$contractResultsPath = Join-Path $OutputDir "results.json"
$contractSummaryPath = Join-Path $OutputDir "summary.json"
$contractReportPath = Join-Path $OutputDir "report.md"

$benchmarkArgs = @(
  "benchmark",
  "run",
  "--cases",
  $cases,
  "--repo",
  $Repo,
  "--root",
  $root,
  "--skills-dir",
  $skillsDir,
  "--languages",
  $benchmarkLanguages,
  "--warmup-runs",
  $benchmarkWarmupRuns,
  "--memory-primary",
  "none",
  "--memory-secondary",
  "none"
)
$benchmarkArgs += $extraArgs
$benchmarkArgs += @("--output", $OutputDir)

Write-Host "[ace-lite] refreshing index..."
& ace-lite index --root $root --languages $benchmarkLanguages --output (Join-Path $root "context-map/index.json")
if ($LASTEXITCODE -ne 0) {
  throw "ace-lite index failed with exit code $LASTEXITCODE"
}

Write-Host "[ace-lite] running benchmark lane '$Lane'..."
& ace-lite @benchmarkArgs

$results = Join-Path $OutputDir "results.json"
& ace-lite benchmark report --input $results

Write-Host "[ace-lite] benchmark artifacts:"
Write-Host "  output_dir: $OutputDir"
Write-Host "  results:    $contractResultsPath"
Write-Host "  summary:    $contractSummaryPath"
Write-Host "  report:     $contractReportPath"
