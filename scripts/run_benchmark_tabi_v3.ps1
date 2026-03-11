param(
  [string]$RepoRoot = "",
  [string]$Repo = "tabi-v3",
  [string]$Languages = "go",
  [int]$TopKFiles = 6,
  [int]$MinCandidateScore = 4,
  [double]$CandidateRelativeThreshold = 0.45,
  [string]$CandidateRanker = "heuristic",
  [int]$ChunkTopK = 24,
  [bool]$Cochange = $true,
  [bool]$IndexIncremental = $false,
  [string]$MemoryPrimary = "none",
  [string]$MemorySecondary = "none",
  [string]$App = "codex",
  [string]$OutputDir = "",
  [string]$IndexCachePath = ""
)

$aceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$cases = Join-Path $aceRoot "benchmark/cases/tabi_v3_large.yaml"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  throw "RepoRoot is required. Pass the local tabi-v3 checkout path with -RepoRoot."
}
if (-not (Test-Path $RepoRoot)) {
  throw "RepoRoot not found: $RepoRoot"
}
if (-not (Test-Path $cases)) {
  throw "Cases file not found: $cases"
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path $aceRoot "artifacts/benchmark/tabi-v3-latest"
}

if ([string]::IsNullOrWhiteSpace($IndexCachePath)) {
  $IndexCachePath = Join-Path $OutputDir "index.json"
}

$indexIncrementalFlag = "--index-incremental"
if (-not $IndexIncremental) {
  $indexIncrementalFlag = "--no-index-incremental"
}

$cochangeFlag = "--cochange"
if (-not $Cochange) {
  $cochangeFlag = "--no-cochange"
}

Write-Host "[ace-lite] running tabi-v3 benchmark..."
Write-Host "  repo      : $Repo"
Write-Host "  root      : $RepoRoot"
Write-Host "  languages : $Languages"
Write-Host "  index     : $IndexCachePath"
Write-Host "  tuning    : top_k_files=$TopKFiles min_score=$MinCandidateScore rel_th=$CandidateRelativeThreshold ranker=$CandidateRanker chunk_top_k=$ChunkTopK cochange=$Cochange"
Write-Host "  memory    : $MemoryPrimary/$MemorySecondary"
Write-Host "  output    : $OutputDir"

ace-lite index `
  --root $RepoRoot `
  --languages $Languages `
  --output $IndexCachePath | Out-Null

ace-lite benchmark run `
  --cases $cases `
  --repo $Repo `
  --root $RepoRoot `
  --skills-dir (Join-Path $aceRoot "skills") `
  --top-k-files $TopKFiles `
  --min-candidate-score $MinCandidateScore `
  --candidate-relative-threshold $CandidateRelativeThreshold `
  --candidate-ranker $CandidateRanker `
  --chunk-top-k $ChunkTopK `
  $cochangeFlag `
  --languages $Languages `
  --index-cache-path $IndexCachePath `
  $indexIncrementalFlag `
  --memory-primary $MemoryPrimary `
  --memory-secondary $MemorySecondary `
  --app $App `
  --output $OutputDir

$results = Join-Path $OutputDir "results.json"
$report = Join-Path $OutputDir "report.md"

ace-lite benchmark report --input $results --output $report | Out-Null

python -c "import json, pathlib; p=pathlib.Path(r'$results'); d=json.loads(p.read_text(encoding='utf-8')); m=d.get('metrics',{}); print('[ace-lite] metrics:', m)"
Write-Host "[ace-lite] report: $report"
