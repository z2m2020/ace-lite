# Repository Guidelines

## Project Structure & Module Organization
This repository is a Python package using a `src/` layout.

- `src/ace_lite/`: core engine modules (`indexer.py`, `skills.py`, `memory.py`, `orchestrator.py`, `cli.py`).
- `tests/`: pytest suite (`test_indexer.py`, `test_skills.py`, `test_orchestrator.py`).
- `skills/`: Markdown skill manifests and section content loaded at runtime.
- `docs/`: architecture and implementation design notes.
- `scripts/run_smoke.ps1`: quick local CLI smoke check.
- `context-map/`: generated artifacts (for example `index.json`).

Keep new runtime code inside `src/ace_lite/` and mirror behavior with focused tests in `tests/`.

## Build, Test, and Development Commands
- `python -m venv .venv` then `.venv\\Scripts\\activate`: create and activate local environment (PowerShell).
- `pip install -e .[dev]`: install package with test dependencies.
- `ace-lite index --root . --output context-map/index.json`: build distilled repository index.
- `ace-lite plan --query ... --repo ace-lite-engine --root . --skills-dir skills`: run orchestration pipeline.
- `pytest`: run all tests.
- `pytest --cov=ace_lite --cov-report=term-missing`: optional coverage-focused run.
- `./scripts/run_smoke.ps1`: smoke test CLI planning flow.

## Coding Style & Naming Conventions
Follow existing Python style in `src/ace_lite/`:

- 4-space indentation, UTF-8 files, type hints for public functions.
- `snake_case` for functions/variables/modules, `PascalCase` for classes.
- Prefer small pure helpers and deterministic outputs (especially in orchestrator pipeline stages).
- Keep CLI options explicit and aligned with current `click` command patterns.

No formatter/linter is currently configured; keep code PEP 8-compatible and consistent with nearby files.

## Testing Guidelines
Use `pytest` with tests named `test_*.py` and functions named `test_*`.

- Add or update tests for every behavior change.
- Favor isolated unit tests with `tmp_path` for file-driven flows.
- Validate end-to-end CLI behavior with `CliRunner` when changing commands.

## Commit & Pull Request Guidelines
Git history is currently empty, so adopt a consistent standard now:

- Commit messages: imperative mood with optional scope (for example, `orchestrator: add fallback memory provider`).
- Keep commits focused and logically grouped.
- PRs should include: summary, rationale, test evidence (`pytest` output), and any docs/CLI example updates.
- Link related issues/tasks and include sample command output when behavior changes.

## Security & Configuration Tips
- Do not hardcode secrets or environment-specific endpoints.
- Treat generated artifacts in `context-map/` as disposable unless intentionally versioned.
- Keep memory-provider integrations behind interfaces (`MemoryProvider`) to avoid leaking implementation details.


## ace-lite MCP
- Before starting work, use `ace_health` to confirm the service and configuration are healthy, especially `default_root`, `skills_dir`, and `memory_ready`.
- After code changes, run `ace_index` to generate or refresh `context-map/index.json` so subsequent retrieval uses current repository state.
- Before taking on a new request or code change, use `ace_plan_quick` to locate candidate files and modules first; if that is not enough, use `ace_plan` for a fuller execution plan aligned with the rules in `skills/`.
- When you need a global structure or dependency view, use `ace_repomap_build` to generate a repo map before making broad changes.
- For long-running development consistency, record important decisions and conventions with `ace_memory_store`, then use `ace_memory_search` later to recover module boundaries, naming conventions, and error-handling rules.
