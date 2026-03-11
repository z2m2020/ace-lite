# Orchestrator Design (P3)

## Deterministic pipeline

`memory -> index -> repomap -> augment -> skills -> source_plan`

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

- Top-level stage payloads: `memory`, `index`, `augment`, `skills`, `source_plan`
- `conventions` snapshot metadata
- `observability` runtime metrics and plugin trace

## Conventions loading

The orchestrator always loads conventions files (`AGENTS.md`, `CONVENTIONS.md` by default)
and keeps them read-only in context payload.

