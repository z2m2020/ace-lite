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

## 2026-03-27 baseline guardrails

- `ace_plan_quick` retrieval guardrails are part of the current runtime baseline: docs-sync intent biasing, domain summary, query refinements, risk hints, and `full_build_reason` observability.
- Memory search guardrails are also baseline behavior across CLI/MCP surfaces: disclaimer, staleness warning, and recency alert.
- Current orchestrator refactor waves should preserve these guardrails as compatibility expectations unless an explicit replacement path is documented.

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

## Plugin / MCP Compatibility Matrix

This is the maintainer-facing compatibility surface for plugin runtime,
tool registration, and remote slot policy. Keep release checks aligned with
this matrix before changing plugin trust rules, MCP tool signatures, or
remote contribution policy.

| Surface | Supported mode | Compatibility rule | Evidence / release check |
| --- | --- | --- | --- |
| MCP public tools | `ace_health`, `ace_index`, `ace_repomap_build`, `ace_plan_quick`, `ace_plan`, memory, feedback | Tool names and descriptions are owned by `server_tool_registration.py`; parameter schema is derived from FastMCP function signatures. | `src/ace_lite/mcp_server/server_tool_registration.py`; `src/ace_lite/mcp_server/server.py`; `tests/unit/test_mcp_server.py` |
| `ace_plan` plugin toggle | `plugins_enabled=false` by default; `true` is opt-in | MCP callers stay deterministic by default and must opt in before repo plugins participate in runtime planning. | `src/ace_lite/mcp_server/server_tool_registration.py`; `src/ace_lite/mcp_server/service.py`; `src/ace_lite/mcp_server/plan_request.py`; `tests/unit/test_mcp_server.py`; `tests/unit/test_mcp_service_plan_runtime.py` |
| Trusted repo plugin | `runtime: in_process`, `trusted: true` | Trusted plugins may load a local Python entrypoint and register `before_stage` / `after_stage` hooks directly. | `src/ace_lite/plugins/loader.py`; `tests/unit/test_plugins_runtime.py` |
| Repo plugin over MCP | `runtime: mcp` | MCP plugins register fail-open hook wrappers and may use manifest knobs for endpoint, timeout, retries, and auth env. | `src/ace_lite/plugins/loader.py`; `tests/unit/test_plugins_runtime.py` |
| Untrusted local plugin | `runtime: in_process`, `trusted: false` | Untrusted in-process plugins are downgraded to the default untrusted runtime (`mcp`) before hooks are loaded. | `src/ace_lite/plugins/loader.py`; `tests/unit/test_plugins_runtime.py` |
| Untrusted remote endpoint | `mock://...` kept by default; `http(s)` cleared unless explicitly allowed | Untrusted remote endpoints are stripped unless `allow_untrusted_remote_mcp_endpoint` is enabled; `mock://` remains the safe default for tests and dry runs. | `src/ace_lite/plugins/loader.py`; `tests/unit/test_plugins_runtime.py` |
| Remote slot contribution policy | allowlisted remote slots only by default | `observability.mcp_plugins` is allowlisted; non-allowlisted remote slots are blocked in `strict`, recorded in `warn`, and passed through only in `off`. Local plugin slots are unchanged. | `src/ace_lite/pipeline/plugin_runtime.py`; `tests/integration/test_orchestrator_slot_policy.py` |

When this matrix changes, update the linked release checklist in
`docs/maintainers/RELEASING.md` in the same patch.

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

## Active structural hotspots (current)

- `AceOrchestrator` still carries several cross-cutting runtime concerns in one shell (replay cache path, trace/export writeback, durable stats flush, memory namespace wiring).
- Config behavior remains distributed across layered config models and runtime mapping, so default/normalization drift is still a practical refactor risk.
- Stage payload contracts are still largely dynamic dict-based in hot paths; stronger typing boundaries are only partially in place today.

## Conventions loading

The orchestrator always loads conventions files (`AGENTS.md`, `CONVENTIONS.md` by default)
and keeps them read-only in context payload.

