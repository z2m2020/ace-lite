# Contributing to ACE-Lite Engine

Thanks for your interest in contributing.

## Development setup

1. Create and activate a virtual environment.
2. Install development dependencies:

```bash
pip install -e .[dev]
```

## Local validation

Run these commands before opening a pull request:

```bash
pytest -q
```

Optional smoke checks:

```powershell
./scripts/run_smoke.ps1
python scripts/run_release_freeze_regression.py --matrix-config benchmark/matrix/repos.yaml --output-dir artifacts/release-freeze/local
```

## Pull request guidelines

- Keep changes focused and reversible.
- Include tests for behavior changes.
- Update relevant docs when changing CLI, config, or schema behavior.
- Add benchmark evidence when tuning ranking, thresholds, or retrieval quality.

## Code style

- Follow existing Python style in `src/ace_lite/`.
- Use type hints on public functions.
- Prefer deterministic logic in pipeline stages.

## Commit messages

Use imperative style with optional scope, for example:

- `orchestrator: improve candidate ranking signal fusion`
- `cli: deduplicate shared plan options`

## Reporting issues

- Security issues: follow `SECURITY.md`.
- Bugs/features: open an issue with reproduction steps and expected behavior.
