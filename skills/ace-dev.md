---
name: ace-dev
description: ACE-Lite MCP operations workflow for repository indexing, retrieval config, diagnostics artifacts, and feedback-driven planning loops.
argument-hint: "<your ACE-Lite task>"
intents: [implement, troubleshoot]
modules: [ace-lite, ace_plan, ace_plan_quick, ace_index, ace_repomap_build, feedback, memory, repomap, embeddings, scip, adaptive_router, plan_replay_cache, trace_export, chunk_guard]
error_keywords: [timeout, 404, 405, 429, 500, 503]
default_sections: [Workflow, Context Recovery, Planning, Config Surfaces, Command Templates, Scenario Templates, Execution and Feedback, Memory Notes]
topics: [ace-lite, ace_plan, ace_plan_quick, ace_index, ace_repomap_build, ace_feedback_record, ace_feedback_stats, ace_memory_search, ace_memory_store, context-map, embedding_rerank_pool, scip_provider, adaptive_router_mode, adaptive_router_arm_set, plan_replay_cache_enabled, plan_replay_cache_path, trace_export_enabled, trace_export_path, trace_otlp_endpoint, junit_xml, failed_test_report, sbfl_metric, chunk_guard_mode, chunk_diversity_path_penalty, topological_shield]
priority: 5
token_estimate: 760
---

# Workflow

Use this skill when the task is specifically about ACE-Lite MCP operations, index freshness, retrieval tuning, diagnostics artifacts, or memory workflows.

1. Confirm the local ACE-Lite service is healthy before planning.
2. Reload prior constraints with `ace_memory_search` when the task looks iterative.
3. Start with `ace_plan_quick`; escalate to `ace_plan` only when symbol-level guidance or broader source planning is needed.
4. Pin the relevant config surface before comparing runs: embeddings, SCIP, chunking, adaptive router, replay cache, or trace export.
5. Use `ace_repomap_build` when adjacency or symbol-neighbor context matters before changing retrieval logic.
6. Refresh retrieval artifacts with `ace_index` after relevant code changes.
7. Record useful file hits with `ace_feedback_record` and review ranking drift with `ace_feedback_stats`.

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

Build a dependency-oriented view before editing structural ranking or symbol edges:

```python
ace_repomap_build(root=".", output_json="context-map/repomap.json", top_k=24)
```

Use `ace_repomap_build` when you need a stable dependency snapshot or want to compare repomap-related behavior across iterations.

# Config Surfaces

When the task is about ACE-Lite behavior rather than one bug, state which config family is in scope:

- Retrieval: `embedding_provider`, `embedding_model`, `embedding_dimension`, `embedding_index_path`, `embedding_rerank_pool`, `embedding_lexical_weight`, `embedding_semantic_weight`, `embedding_min_similarity`, `embedding_fail_open`.
- Structure and routing: `scip_provider`, `scip_generate_fallback`, `adaptive_router_mode`, `adaptive_router_arm_set`, `plan_replay_cache_enabled`, `plan_replay_cache_path`.
- Diagnostics: `junit_xml` or `failed_test_report`, `coverage_json`, `sbfl_json`, `sbfl_metric`, `trace_export_enabled`, `trace_export_path`, `trace_otlp_endpoint`.
- Chunking: `chunk_guard_mode`, `chunk_guard_lambda_penalty`, `chunk_diversity_*`, `topological_shield`.

Use exact option names in notes and handoffs so future runs stay reproducible.

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
  --plan-replay-cache-enabled \
  --trace-export-enabled \
  --trace-export-path context-map/traces/plan.jsonl \
  --output-json context-map/plan-output.json
```

For retrieval-sensitive diffs, keep the output JSON, trace path, and replay-cache path together in the same note or handoff.

# Scenario Templates

## Config-diff run

- Goal: compare one config family while keeping repo root, query, and artifact paths stable.
- Pin the baseline and candidate knobs in the same note before you run either command.
- Save both `--output-json` and trace artifacts so the diff is inspectable later.

## Trace-only diagnosis

- Goal: inspect stage tags, router decisions, or replay-cache behavior without claiming retrieval quality changed.
- Turn on `trace_export_enabled` and keep the query fixed; do not mix this run with unrelated config edits.
- Record the exact `trace_export_path` and whether `plan_replay_cache_enabled` was on during capture.

## Failed-test triage

- Goal: connect a failing test or flaky run back to ACE-Lite config surfaces before touching ranking logic.
- Pair `failed_test_report` or `junit_xml` with `sbfl_metric`, then narrow candidate files with `ace_plan_quick`.
- Refresh `context-map/index.json` only after the code fix lands so the post-fix retrieval evidence is current.

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

Good candidates include ranking heuristics, tool boundary rules, known recovery procedures, and stable config invariants.
