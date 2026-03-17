---
name: ace-dev
description: ACE-Lite MCP operations workflow for repository indexing, retrieval config, validation diagnostics, upgrade drift recovery, and feedback-driven planning loops.
argument-hint: "<your ACE-Lite task>"
intents: [implement, troubleshoot]
modules: [ace-lite, ace_plan, ace_plan_quick, ace_index, ace_repomap_build, feedback, memory, repomap, embeddings, scip, adaptive_router, plan_replay_cache, trace_export, chunk_guard, validation, agent_loop, doctor, version, mcp, skills, source_plan, prompt_rendering]
error_keywords: [timeout, 404, 405, 429, 500, 503, version drift, install drift, editable install]
default_sections: [Workflow, Context Recovery, Planning, Config Surfaces, Command Templates, Scenario Templates, Upgrade and Drift Recovery, Execution and Feedback, Memory Notes]
topics: [ace-lite, ace_plan, ace_plan_quick, ace_index, ace_repomap_build, ace_feedback_record, ace_feedback_stats, ace_memory_search, ace_memory_store, context-map, embedding_rerank_pool, scip_provider, adaptive_router_mode, adaptive_router_arm_set, plan_replay_cache_enabled, plan_replay_cache_path, trace_export_enabled, trace_export_path, trace_otlp_endpoint, junit_xml, failed_test_report, sbfl_metric, chunk_guard_mode, chunk_diversity_path_penalty, topological_shield, validation, validation_result_v1, validation_tests, agent_loop_action_v1, agent_loop_summary_v1, runtime_doctor, mcp_self_test, verify_version_install_sync, install_sync, metadata_only_routing, precomputed_skills_routing_enabled, skills_token_budget, selected_manifest_token_estimate_total, hydrated_skill_count, prompt_rendering_boundary_v1, chunk_contract, subgraph_payload, final_query, replay_fingerprint, doctor_mcp]
priority: 5
token_estimate: 900
---

# Workflow

Use this skill when the task is specifically about ACE-Lite MCP operations, index freshness, retrieval tuning, validation diagnostics, or memory workflows.

1. Confirm the local ACE-Lite service is healthy before planning.
2. Reload prior constraints with `ace_memory_search` when the task looks iterative.
3. Start with `ace_plan_quick`; escalate to `ace_plan` only when symbol-level guidance or broader source planning is needed.
4. Pin the relevant config surface before comparing runs: embeddings, SCIP, skills routing, chunking, adaptive router, replay cache, source-plan prompt boundaries, validation, or trace export.
5. Use `ace_repomap_build` when adjacency or symbol-neighbor context matters before changing retrieval logic.
6. If the task includes an upgrade, reinstall, or branch switch, verify version/install sync before debugging behavior.
7. Refresh retrieval artifacts with `ace_index` after relevant code changes.
8. Run MCP self-test or `ace-lite doctor` when the observed behavior may come from runtime wiring rather than source code.
9. Record useful file hits with `ace_feedback_record` and review ranking drift with `ace_feedback_stats`.

# Context Recovery

```python
ace_health()
ace_memory_search(query="<ace-lite query terms>", limit=5)
```

Prefer short keyword queries built from tool names, modules, config groups, and failure symptoms rather than full sentences.

# Planning

Use `ace_plan_quick` for most ACE-Lite maintenance tasks:

```python
ace_plan_quick(
  query="<tool names + failure symptoms + target module>",
  candidate_ranker="rrf_hybrid",
  top_k_files=8,
  index_incremental=True,
)
```

Escalate to `ace_plan` when you need chunk-level evidence, broader dependency context, or explicit step suggestions.

When the investigation touches skill routing, record whether routing stayed metadata-only and which budget fields changed: `routing_mode`, `metadata_only_routing`, `token_budget`, `token_budget_used`, `selected_manifest_token_estimate_total`, `hydrated_skill_count`, `budget_exhausted`, and `skipped_for_budget`.

When the investigation touches prompt assembly or source-plan output, capture the boundary contract explicitly: `prompt_rendering_boundary_v1`, `chunk_contract`, and `subgraph_payload`.

Build a dependency-oriented view before editing structural ranking or symbol edges:

```python
ace_repomap_build(root=".", output_json="context-map/repomap.json", top_k=24)
```

Use `ace_repomap_build` when you need a stable dependency snapshot or want to compare repomap-related behavior across iterations.

# Config Surfaces

When the task is about ACE-Lite behavior rather than one bug, state which config family is in scope:

- Retrieval: `embedding_provider`, `embedding_model`, `embedding_dimension`, `embedding_index_path`, `embedding_rerank_pool`, `embedding_lexical_weight`, `embedding_semantic_weight`, `embedding_min_similarity`, `embedding_fail_open`.
- Structure and routing: `scip_provider`, `scip_generate_fallback`, `adaptive_router_mode`, `adaptive_router_arm_set`, `plan_replay_cache_enabled`, `plan_replay_cache_path`.
- Skills routing: `precomputed_skills_routing_enabled`, `skills_top_n`, `skills_token_budget`, `routing_mode`, `metadata_only_routing`, `token_budget_used`, `selected_manifest_token_estimate_total`, `hydrated_skill_count`, `budget_exhausted`, `skipped_for_budget`.
- Source-plan and prompt boundary: `prompt_rendering_boundary_v1`, `chunk_contract`, `subgraph_payload`, and any boundary-specific output schema notes carried with `source_plan`.
- Validation and runtime wiring: `validation.enabled`, `validation.include_xref`, sandbox timeouts, `agent_loop` limits, `runtime doctor`, MCP self-test behavior.
- Agent loop replay surface: `final_query`, `replay_fingerprint`, rerun stages, stop reason, and iteration count when comparing pre/post behavior.
- Diagnostics: `junit_xml` or `failed_test_report`, `coverage_json`, `sbfl_json`, `sbfl_metric`, `trace_export_enabled`, `trace_export_path`, `trace_otlp_endpoint`.
- Chunking: `chunk_guard_mode`, `chunk_guard_lambda_penalty`, `chunk_diversity_*`, `topological_shield`.

Use exact config keys or exact CLI flags in notes and handoffs so future runs stay reproducible.

# Command Templates

Use explicit commands when you want reproducible ACE-Lite evidence:

```bash
ace-lite plan \
  --query "<task>" \
  --repo ace-lite-engine \
  --root . \
  --embedding-provider hash \
  --embedding-model hash-v2 \
  --embedding-rerank-pool 24 \
  --scip-provider auto \
  --plan-replay-cache \
  --trace-export \
  --trace-export-path context-map/traces/plan.jsonl \
  --output-json context-map/plan-output.json
```

For retrieval-sensitive diffs, keep the output JSON, trace path, and replay-cache path together in the same note or handoff.

For runtime wiring or upgrade drift checks, prefer an explicit doctor/self-test command:

```bash
ace-lite doctor --root . --skills-dir skills
ace-lite runtime doctor-mcp --root . --skills-dir skills
ace-lite runtime test-mcp --root . --skills-dir skills
python -m ace_lite.mcp_server --self-test --root . --skills-dir skills
```

# Scenario Templates

## Config-diff run

- Goal: compare one config family while keeping repo root, query, and artifact paths stable.
- Pin the baseline and candidate knobs in the same note before you run either command.
- Save both `--output-json` and trace artifacts so the diff is inspectable later.

## Trace-only diagnosis

- Goal: inspect stage tags, router decisions, replay-cache behavior, validation status, or agent-loop summaries without claiming retrieval quality changed.
- Turn on `--trace-export` and keep the query fixed; do not mix this run with unrelated config edits.
- Record the exact `trace_export_path` and whether replay cache was enabled during capture.

## Skills-routing budget diagnosis

- Goal: explain why a skill was or was not hydrated after metadata-only routing.
- Required evidence: `routing_mode`, `metadata_only_routing`, `token_budget`, `token_budget_used`, `selected_manifest_token_estimate_total`, `hydrated_skill_count`, and any `skipped_for_budget` items.
- Exit rule: do not rewrite skill text or ranking heuristics until budget exhaustion and precomputed-route behavior are ruled in or out.

## Prompt boundary contract check

- Goal: confirm prompt rendering still emits the expected source-plan boundary contract after code or skill changes.
- Required evidence: `prompt_rendering_boundary_v1`, `chunk_contract`, `subgraph_payload`, and the source-plan payload generated from the same checkout.
- Exit rule: treat boundary payload shape as a first-class contract; do not claim success from summary text alone.

## Failed-test triage

- Goal: connect a failing test or flaky run back to ACE-Lite config surfaces before touching ranking logic.
- Pair `failed_test_report` or `junit_xml` with `sbfl_metric`, then narrow candidate files with `ace_plan_quick`.
- Refresh `context-map/index.json` only after the code fix lands so the post-fix retrieval evidence is current.

## Upgrade or drift recovery

- Goal: confirm the running CLI/MCP matches the working tree after a pull, branch switch, or editable reinstall.
- Required evidence: `get_version_info()` output, `python -m pip show ace-lite-engine`, and MCP self-test payload from the same checkout.
- Exit rule: do not debug retrieval or routing behavior until version/install drift is ruled out.

# Upgrade and Drift Recovery

When the task mentions upgrade, reinstall, version mismatch, or stale MCP behavior, verify the runtime before changing code:

```python
from ace_lite.version import get_version_info, verify_version_install_sync

print(get_version_info())
verify_version_install_sync()
```

Pair that with:

```bash
python -m pip show ace-lite-engine
ace-lite doctor --root . --skills-dir skills
ace-lite runtime doctor-mcp --root . --skills-dir skills
ace-lite runtime test-mcp --root . --skills-dir skills
python -m ace_lite.mcp_server --self-test --root . --skills-dir skills
```

# Execution and Feedback

After changing retrieval-sensitive code or docs, refresh the repo index:

```python
ace_index(root=".", output="context-map/index.json")
```

Capture useful file selections while you work:

```python
ace_feedback_record(
  query="<query used during planning>",
  selected_path="<repo-relative path>",
)
```

Summarize retrieval quality after a focused iteration:

```python
ace_feedback_stats(query="<topic>", decay_days=60, top_n=10)
```

If the task compares multiple ACE-Lite configurations, save an explicit artifact path for the JSON output or trace export before claiming a result.

# Memory Notes

Store reusable constraints, not raw transcripts:

```python
ace_memory_store(
  text="[ace-lite] <module>: <stable constraint or decision>",
  namespace="ace-lite",
)
```

Good candidates include ranking heuristics, tool boundary rules, known recovery procedures, validation-stage expectations, and stable config invariants.
