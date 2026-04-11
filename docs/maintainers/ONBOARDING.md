# Developer Onboarding (ACE-Lite Engine)

This document is a concise entry point for contributors: how the engine is structured, how to validate changes, and where to read deeper design notes.

## TL;DR

ACE-Lite is a **local-first Active Context Engine**. It turns a repo + query into a compact, explainable context selection and an execution-oriented **source plan**.

Default pipeline:

`memory -> index -> repomap -> augment -> skills -> source_plan`

Design principles:
- **Deterministic outputs** (stable ordering, fingerprints, bounded budgets)
- **Fail-open optional components** (memory, embeddings, exact search, LSP)
- **Benchmarkable quality** (track regressions with repeatable cases)

## Repository layout

- Runtime package: `src/ace_lite/`
- CLI entrypoint: `ace_lite.cli:main` (see `pyproject.toml`)
- MCP server entrypoint: `ace_lite.mcp_server:main`
- Skills: `skills/` (Markdown manifests + lazy-loaded sections)
- Tests: `tests/`
- Generated artifacts: `context-map/`, `artifacts/` (disposable)

## Quick contributor setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
ace-lite doctor
```

## What to run before/after changes

- Unit tests: `pytest`
- Docs snippet drift check: `python scripts/validate_docs_cli_snippets.py`
- Build/update index artifacts for local retrieval: `ace-lite index --root . --output context-map/index.json`
- Run a small plan smoke: `ace-lite plan --query "where is config loaded" --repo ace-lite-engine --root . --skills-dir skills --memory-primary none --memory-secondary none`
- Bench/regression (when changing retrieval): `ace-lite benchmark run ...` (see `docs/maintainers/BENCHMARKING.md`)

## Quick-first familiarization

For "where do I start reading this repo" tasks, prefer `ace_plan_quick` before a full `ace_plan`.

Useful quick-plan fields:
- `onboarding_view`: grouped entrypoints, contracts, runtime files, tests, and a recommended reading order
- `candidate_details`: per-file role and labels
- `upgrade_recommended` plus `why_not_plan_yet` / `why_upgrade_now`: compact guidance on whether a full plan is likely worth the extra cost

## Where to read next (by intent)

- Getting started / operational: `docs/guides/GETTING_STARTED.md`
- MCP client setup: `docs/guides/MCP_SETUP.md`
- Architecture overview: `docs/design/ARCHITECTURE_OVERVIEW.md`
- Orchestrator contract + plugins: `docs/design/ORCHESTRATOR_DESIGN.md`
- Indexer and rankers: `docs/design/INDEXER_DESIGN.md`
- Skill routing + lazy-load: `docs/design/SKILL_LAZYLOAD_DESIGN.md`
- Quality and tuning workflow: `docs/maintainers/QUALITY_GOVERNANCE.md`
