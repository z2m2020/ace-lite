param(
  [string]$Repo = "mem0"
)

$root = (Resolve-Path ".").Path
$cases = Join-Path $root "benchmark/cases/default.yaml"
$output = Join-Path $root "artifacts/benchmark/latest"

Write-Host "[ace-lite] running benchmark..."
ace-lite benchmark run --cases $cases --repo $Repo --root $root --skills-dir (Join-Path $root "skills") --languages "python,typescript,javascript,go" --memory-primary none --memory-secondary none --output $output

$results = Join-Path $output "results.json"
ace-lite benchmark report --input $results
