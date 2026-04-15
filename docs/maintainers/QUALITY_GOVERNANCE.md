# Quality Governance

## Goal

Establish a repeatable quality gate for `ace-lite-engine` that combines:

- linting (`ruff`)
- skill metadata linting (`pytest -q tests/unit/test_skills.py -k lint`)
- type checks (`mypy`)
- security scanning (`bandit`)
- dependency auditing (`pip-audit`)
- coverage-enforced tests (`pytest --cov`)

Current gate is intentionally incremental. The blocking checks stay repo-wide,
while the report-only hotspot summary now tracks the current post-backlog
maintainability set:

- `src/ace_lite/orchestrator.py`
- `src/ace_lite/orchestrator_contracts.py`
- `src/ace_lite/runtime_settings.py`
- `src/ace_lite/plan_quick.py`
- `src/ace_lite/plan_quick_strategies.py`
- `src/ace_lite/benchmark/report.py`
- `src/ace_lite/benchmark/report_observability.py`
- `src/ace_lite/benchmark/summaries.py`

The prior facade-centric hotspots (`cli_app/orchestrator_factory_support.py`,
`cli_app/params_option_groups.py`, and the first-wave CLI payload helpers) were
retired after the 2026-03-18 helper-extraction waves. As of 2026-04-13 the
remaining concentration risk shifted to typed orchestration boundaries,
runtime-setting projection, and the `plan_quick` plus benchmark-report stacks.
Earlier report-only hotspots such as `benchmark/case_evaluation.py`,
`cli_app/orchestrator_factory.py`, `config_models.py`, `runtime.py`, and
`mcp_server/service.py` remain retired or demoted.

For the benchmark report stack, keep `src/ace_lite/benchmark/report.py` as the
assembly shell and move report-only summary sections into support modules such
as `src/ace_lite/benchmark/report_observability.py` rather than growing the
shell again.

As of `0.3.80`, shared summary-view helpers under
`src/ace_lite/benchmark/report_summary.py` also own the repeated dict-unwrapping
logic for report-only summary sections. Keep future report-stack cleanup flowing
through those read-only helpers instead of duplicating new `summary_raw if
isinstance(..., dict)` branches across `report.py` and
`report_observability.py`.

The current hotspot set is intentionally report-only. Update the target list in
`benchmark/quality/hotspot_baseline.json` together with `scripts/run_quality_gate.py`
when a new maintainability wave changes the main concentration risks.

Quality execution is unified via:

- `scripts/run_quality_gate.py`
- `.pre-commit-config.yaml`
- `scripts/run_precommit_validation.py`
- audit baseline: `benchmark/quality/pip_audit_baseline.json`
- friction event log: `artifacts/friction/events.jsonl`
- friction report builder: `scripts/build_friction_report.py`

## Refactor Guard Suites

When a change touches runtime assembly, stage boundaries, benchmark orchestration, or the maintainability seams documented in `docs/design/ARCHITECTURE_OVERVIEW.md` and `docs/design/ORCHESTRATOR_DESIGN.md`, run these focused suites before treating the tree as release-ready:

```powershell
python -m pytest tests/unit/test_architecture_golden.py tests/unit/test_stage_contracts.py -q
python -m pytest tests/integration/test_cli_runtime.py tests/integration/test_cli_repomap.py tests/integration/test_cli_plan_output_json.py -q
```

These suites freeze three contracts that are easy to drift during refactors:

- design docs stay aligned with the live pipeline and top-level stage payload contract
- `validate_stage_output(...)` continues to accept real orchestrator stage payloads
- CLI runtime / repomap / plan JSON surfaces keep the current shell-layer boundary shape

## Baseline (2026-02-14)

- test result: `361 passed`
- coverage result: `TOTAL 84.15%`
- coverage gate baseline: `fail_under = 83`

## Baseline (2026-02-15)

- test result: `492 passed`
- freeze gates: passed (see `artifacts/release-freeze/s12-*`)
- coverage gate: `fail_under = 83` (unchanged)

## Hotspot Refresh (2026-04-13)

- report-only hotspot targets were refreshed to match the current 0.3.65
  maintainability risks after the first seam-extraction wave
- blocking quality commands and coverage gate are unchanged
- maintainers should update `benchmark/quality/hotspot_baseline.json` together
  with `scripts/run_quality_gate.py` whenever a refactor wave moves the largest
  remaining concentration risks into new helper/support modules

## Typed Hotspot Scope (2026-04-14)

- `mypy` tightening now starts to move from general utility/helper seams into
  the typed orchestration boundaries created by the recent Wave16/Wave17
  refactors.
- The stricter per-module override currently covers:
  - `ace_lite.orchestrator_runtime_support_types`
  - `ace_lite.orchestrator_runtime_finalization`
  - `ace_lite.orchestrator_runtime_support`
  - `ace_lite.cli_app.orchestrator_factory_support`
  - `ace_lite.cli_app.orchestrator_factory`
- As of `0.3.77`, the `orchestrator_runtime_support.py` wrapper seam has also
  been promoted into the stricter hotspot batch after its remaining
  `no-any-return` passthrough regressions were closed.
- The next typing cleanup target should move downstream into the next compat or
  runtime helper that still leaks `Any`, rather than reopening these wrapper
  seams.

## Local Commands

```powershell
pip install -e .[dev]
python scripts/validate_docs_cli_snippets.py
python scripts/run_precommit_validation.py --staged
pre-commit install
python -m pytest -q tests/unit/test_skills.py -k lint
python scripts/run_quality_gate.py --root . --output-dir artifacts/quality/latest --pip-audit-baseline benchmark/quality/pip_audit_baseline.json --fail-on-new-vulns --friction-log artifacts/friction/events.jsonl
python scripts/run_quality_gate.py --root . --output-dir artifacts/quality/hotspots --hotspot-path src/ace_lite/orchestrator.py --hotspot-path src/ace_lite/plan_quick.py
python scripts/build_friction_report.py --events-path artifacts/friction/events.jsonl --output-dir artifacts/friction/latest
python scripts/log_friction_event.py --stage planning --expected "ace_plan_quick returns focused candidates" --actual "results include noisy files" --root-cause retrieval-noise --manual-fix "tighten query terms + rerun ace_plan" --severity medium --time-cost-min 4 --tag mcp --tag retrieval
```

`run_quality_gate.py` now also emits report-only hotspot `ruff` and `mypy` results for the tracked hotspot file set. These hotspot checks are observability-only and do not flip the overall gate result, but they give maintainers a stable way to track whether the highest-risk files are converging.
The blocking gate now also runs the repository skill frontmatter lint slice so metadata regressions fail fast before release packaging.

When a refactor wave is working through the hotspot backlog incrementally, use
`--hotspot-path` to narrow the report-only hotspot checks and summary to the
current batch without changing the repo-wide blocking gate.

## Tuning Workflow (Config Packs)

ACE-Lite supports tuned override bundles ("config packs") that are designed to be:

- deterministic (stable precedence)
- fail-open (invalid packs are ignored)

### Generate a pack

Run the offline tuning loop and capture artifacts under `artifacts/tuning/*`:

```powershell
python scripts/ralph_wiggum_iterate.py --cases benchmark/cases/ace_lite_engine.yaml --repo ace-lite-engine --root . --skills-dir skills --iterations 50 --output-dir artifacts/tuning/latest
```

Outputs include:

- `artifacts/tuning/latest/config_pack.json` (apply this)
- `artifacts/tuning/latest/summary.json` (+ `iter-*.json` details)
- `artifacts/tuning/latest/ralph_wiggum_iterations.md` (human-readable log)

### Apply a pack (CLI)

```powershell
ace-lite plan --query "..." --repo ace-lite-engine --root . --skills-dir skills --config-pack artifacts/tuning/latest/config_pack.json
```

Precedence is: explicit CLI args > config pack overrides > layered repo config > defaults.

### Apply a pack (MCP)

- Server default: set `ACE_LITE_CONFIG_PACK` in the MCP server environment.
- Per-request: pass `config_pack` to the `ace_plan` tool input.

### Retention policy

- Keep `config_pack.json` + `summary.json` for every tuning run.
- Prune `iter-*.json` in older runs if disk usage becomes an issue.

## CI Contract

`ci.yml` now contains:

- `docs-validate` job: validates docs CLI snippets against the current CLI surface
- `test` job: fast regression (`pytest -q`)
- `quality` job: runs unified quality gate, builds friction report, uploads quality+friction artifacts
- `release-freeze-gates` job: runs on protected branch pushes and opt-in PR benchmark runs

`pip-audit` now uses baseline diff mode: existing known vulnerabilities are tracked in baseline, and CI fails only on newly introduced findings.

## Friction Loop

1. Auto capture: quality gate writes friction events on failed checks and new vulnerability diffs.
2. Manual capture: `log_friction_event.py` records analyst-observed friction moments.
3. Aggregation: `build_friction_report.py` produces machine-readable and markdown summaries.
4. Optimization: prioritize top root causes/stages into next TODO sprint and convert fixes into regression tests.

## Tightening Strategy

1. Keep coverage gate at `83` until quality job is stable for one full iteration window.
2. Raise to `85` after hotspot modules close major branch gaps.
3. Expand `mypy` scope incrementally from utility modules to broader pipeline modules.
4. Revisit `bandit` skip list after each security remediation batch.
