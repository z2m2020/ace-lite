# System Map

This document is the maintainer-facing map of the live ACE-Lite system. It answers four questions:

1. Where the core execution path lives
2. Where config enters and gets normalized
3. Which subsystems own which responsibilities
4. Which regression suites protect each high-risk surface

## 1. Core execution path

The canonical plan path is:

`memory -> index -> repomap -> augment -> skills -> source_plan -> validation`

The main orchestration shell is:

- `src/ace_lite/orchestrator.py`
- `src/ace_lite/orchestrator_payload_builder.py`

That shell should stay responsible for:

- runtime startup and shutdown coordination
- preparation, lifecycle, and finalization delegation
- ownership of stable public plan payload semantics

That shell should not continue absorbing:

- report rendering logic
- config default duplication
- stage-local business rules that belong in stage modules or services

## 2. Interface entrypoints

Public entry shells:

- CLI: `src/ace_lite/cli.py`
- Click tree: `src/ace_lite/cli_app/app.py`
- MCP server: `src/ace_lite/mcp_server/`

Current interface rule:

- keep public entrypoints thin
- move translation and payload-building logic into support/factory modules
- preserve CLI and MCP compatibility unless an explicit migration path is documented

## 3. Domain ownership

### Runtime orchestration

Primary modules:

- `src/ace_lite/orchestrator.py`
- `src/ace_lite/orchestrator_runtime_*`
- `src/ace_lite/pipeline/stages/`

Owns:

- stage execution order
- runtime observability
- replay and lifecycle handoff

### Retrieval and indexing

Primary modules:

- `src/ace_lite/index_stage/`
- `src/ace_lite/chunking/`
- `src/ace_lite/repomap/`
- `src/ace_lite/source_plan/`

Owns:

- candidate generation
- ranking and chunk selection
- graph and structural signals
- source-plan grounding

### Interfaces and host adaptation

Primary modules:

- `src/ace_lite/cli_app/`
- `src/ace_lite/mcp_server/`
- `src/ace_lite/plugins/`
- `src/ace_lite/workspace/`

Owns:

- CLI option parsing
- MCP tool registration and request handling
- plugin contracts
- multi-repo workspace flows

### Benchmark and quality

Primary modules:

- `src/ace_lite/benchmark/`
- `src/ace_lite/benchmark/report_observability.py`
- `scripts/run_quality_gate.py`
- `benchmark/quality/`

Owns:

- regression case evaluation
- summary and report generation
- extracted report-only observability sections for benchmark markdown output
- gate and hotspot observability

## 4. Config entry and normalization

Config currently enters through four layers:

1. defaults in config models and shared helpers
2. layered repo and home config resolution
3. CLI argument mapping in `cli_app`
4. runtime settings and MCP environment surfaces

Read these in order when changing config behavior:

- `src/ace_lite/orchestrator_config.py`
- `src/ace_lite/config_sections/`
- `src/ace_lite/cli_app/orchestrator_factory.py`
- `src/ace_lite/runtime_settings.py`

Maintainer rule:

- add new defaults in one canonical location first
- reuse shared normalizers before introducing new per-surface coercion
- verify CLI, runtime settings, and MCP contracts together when a field changes

## 5. Active structural hotspots

These files are the current concentration risks and should be treated as refactor shells, not as growth targets:

- `src/ace_lite/orchestrator.py`
- `src/ace_lite/orchestrator_config.py`
- `src/ace_lite/benchmark/report.py`
- `src/ace_lite/benchmark/summaries.py`

Current rule:

- add new logic in extracted helpers or registries
- keep shell files focused on orchestration and assembly
- extracted benchmark report sections should live in helper modules such as `benchmark/report_observability.py`, not flow back into `benchmark/report.py`
- when a hotspot grows, update `benchmark/quality/hotspot_baseline.json` and the quality gate docs in the same patch

## 6. Required regression suites by surface

When changing architecture or contracts, run:

```powershell
python -m pytest tests/unit/test_architecture_golden.py tests/unit/test_stage_contracts.py -q
```

When changing runtime CLI or payload assembly, run:

```powershell
python -m pytest tests/integration/test_cli_runtime.py tests/integration/test_cli_plan_output_json.py -q
```

When changing quality tooling, run:

```powershell
python -m pytest tests/e2e/test_quality_gate_script.py tests/unit/test_run_precommit_validation.py -q
```

When changing benchmark report or scoring contracts, run:

```powershell
python -m pytest tests/unit/test_benchmark_report.py tests/unit/test_benchmark_scoring.py -q
```

## 7. Fast navigation order for new maintainers

Use this read order:

1. `docs/design/ARCHITECTURE_OVERVIEW.md`
2. `docs/design/ORCHESTRATOR_DESIGN.md`
3. this file
4. `docs/maintainers/QUALITY_GOVERNANCE.md`
5. the concrete subsystem you are changing

If you are still unsure where a behavior lives, prefer `ace_plan_quick` before a full `ace_plan`.
