# Orchestrator Design (P3)

## Deterministic pipeline

`memory -> index -> repomap -> augment -> skills -> source_plan -> validation`

## Runtime construction

`AceOrchestrator` now uses a typed configuration entrypoint:

- Preferred API: `AceOrchestrator(config=OrchestratorConfig(...), memory_provider=...)`
- Legacy flat kwargs are intentionally removed from the orchestrator constructor.
- CLI remains backward compatible by translating layered config + CLI flags through
  `OrchestratorConfig(...)` section payloads inside the factory layer.

## Runtime responsibilities

1. `memory`
- Query `MemoryProvider`
- Surface retrieval observability:
  - `memory.channel_used`
  - `memory.fallback_reason`

2. `index`
- Reuse `context-map/index.json` cache when valid
- Optional incremental refresh through git-changed files
- Normalize targets to canonical relative paths
- Emit candidate file ranking and cache mode telemetry

3. `repomap`
- Generate focused repository map under a token budget
- Expand neighborhood with ranking profile controls
- Emit ranking/neighbor telemetry for explainability

4. `augment`
- Optional LSP diagnostics enrichment on top-N candidate files
- Supports diagnostics-only mode by design
- Graceful degrade with reasons:
  - `disabled`
  - `broker_unavailable`

5. `skills`
- Select markdown skills by query context
- Lazy-load only matched sections

6. `source_plan`
- Build deterministic execution plan
- Emit writeback template contract

7. `validation`
- Run optional validation checks against the source-plan output
- Emit stable validation result and sandbox payloads for CLI, benchmark, and replay consumers

## Plugin system

`AceOrchestrator` loads plugin hooks from `plugins/*/plugin.yaml`.

- `before` hooks can observe stage transitions
- `after` hooks can patch stage payloads via deep-merge
- Untrusted `in_process` plugins are downgraded to MCP runtime by default
- MCP runtime optional knobs (manifest keys):
  - `mcp_timeout_seconds`: per-hook HTTP timeout (fail-open)
  - `mcp_retries`: retry count (integer, best-effort)
  - `mcp_auth_env`: environment variable name holding `Authorization` header value (no secrets in repo)

Output telemetry:
- `observability.plugins_loaded`
- per-stage metric list in `observability.stage_metrics`
- each stage metric includes `tags` (cache mode, selected count, diagnostics, plugin invocations, etc.)

## Schema contract

Each plan payload is schema-validated (`schema_version = 2.0`) and includes:

- Top-level stage payloads: `memory`, `index`, `repomap`, `augment`, `skills`, `source_plan`, `validation`
- `conventions` snapshot metadata
- `observability` runtime metrics and plugin trace

## Refactor boundaries

- `src/ace_lite/cli_app/orchestrator_factory.py` and `src/ace_lite/cli_app/runtime_command_support.py` own CLI-to-config translation and runtime command payload assembly.
- `src/ace_lite/mcp_server/server_tool_registration.py` owns MCP tool registration metadata and registration grouping.
- `src/ace_lite/index_stage/` owns extracted index-stage helper seams; `src/ace_lite/pipeline/stages/index.py` remains the stage orchestration entry.
- `src/ace_lite/benchmark/case_evaluation_*.py` owns extracted benchmark-evaluation seams; `src/ace_lite/benchmark/case_evaluation.py` remains the orchestration shell.

## Conventions loading

The orchestrator always loads conventions files (`AGENTS.md`, `CONVENTIONS.md` by default)
and keeps them read-only in context payload.

