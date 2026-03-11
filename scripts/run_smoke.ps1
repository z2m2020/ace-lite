param(
  [string]$Query = "fix openmemory 405 dimension mismatch",
  [string]$Repo = "mem0"
)

$root = (Resolve-Path ".").Path
$skills = Join-Path $root "skills"

Write-Host "[ace-lite] running plan smoke..."
ace-lite plan --query $Query --repo $Repo --root $root --skills-dir $skills --languages "python,typescript,javascript,go" --memory-primary none --memory-secondary none
