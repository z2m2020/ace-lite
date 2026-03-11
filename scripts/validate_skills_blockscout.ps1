param(
  [string]$RepoUrl = "https://github.com/blockscout/frontend.git",
  [string]$RepoRef = "main",
  [string]$RepoName = "blockscout-frontend",
  [string]$RepoDir = "artifacts/repos-workdir/skill-validation",
  [string]$OutputPath = "artifacts/skill-eval/blockscout_skill_validation_matrix.json",
  [string]$IndexCachePath = "artifacts/skill-eval/blockscout-index.json",
  [string]$Apps = "codex,opencode,claude-code",
  [float]$MinPassRate = 1.0
)

Write-Host "[ace-lite] validating cross-agent skills on blockscout frontend..."
python scripts/run_skill_validation.py `
  --repo-url $RepoUrl `
  --repo-ref $RepoRef `
  --repo-name $RepoName `
  --repo-dir $RepoDir `
  --skills-dir skills `
  --index-cache-path $IndexCachePath `
  --output-path $OutputPath `
  --languages "typescript,javascript" `
  --apps $Apps `
  --min-pass-rate $MinPassRate `
  --fail-on-miss
