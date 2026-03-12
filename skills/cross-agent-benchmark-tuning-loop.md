---
name: cross-agent-benchmark-tuning-loop
description: Benchmark tuning loop for retrieval, routing, validation, and agent-loop changes with measurable keep-or-rollback decisions.
intents: [benchmark, troubleshoot]
modules: [benchmark, ranking, retrieval, repomap, feedback, embeddings, scip, adaptive_router, plan_replay_cache, trace_export, chunk_guard, validation, agent_loop, doctor, version]
error_keywords: [metric regression, timeout, latency spike, version drift, install drift, validation failed]
default_sections: [Workflow, Prompt Template, Tuning Knobs, Artifact Checklist, Metrics Contract, Tool Notes]
topics: [benchmark, tuning, precision, noise, latency, threshold, recall, ranking, feedback, embedding_rerank_pool, embedding_lexical_weight, embedding_semantic_weight, scip_provider, adaptive_router_mode, plan_replay_cache_enabled, plan_replay_cache_path, trace_export_enabled, trace_export_path, chunk_guard_mode, topological_shield, validation, validation_result_v1, validation_tests, agent_loop, agent_loop_summary_v1, runtime_doctor, mcp_self_test, verify_version_install_sync, install_sync, 基准, 调优, 精度, 噪声, 延迟, 召回, 验证, 漂移]
priority: 3
token_estimate: 560
---

# Workflow

1. Establish baseline metrics from the same case set, repo revision, and execution mode.
2. Run `ace_health` and `ace_memory_search` to recover prior tuning constraints.
3. Freeze replay inputs first: repo revision, case set, router mode, replay cache policy, and whether validation or agent loop is enabled.
4. Before comparing runs, verify runtime consistency: if using an installed CLI, run `verify_version_install_sync()` or equivalent doctor/self-test evidence; otherwise prefer `PYTHONPATH=src` so source and runtime stay aligned.
5. Default benchmark baselines to `agent_loop.enabled=false` unless this iteration is explicitly evaluating loop behavior; if validation is in scope, keep `validation.enabled` and xref settings fixed across baseline/candidate runs.
6. Change one parameter group per iteration (weights, thresholds, router mode, structure source, chunk controls, validation policy, or loop policy).
7. Run targeted benchmark first, then matrix benchmark if gates are close; export trace artifacts when latency, plugin behavior, validation diagnostics, or incremental reruns are under review.
8. Record actual useful files via `ace_feedback_record` and compute trend via `ace_feedback_stats`.
9. Compare deltas against explicit keep/rollback rules, including evidence sufficiency and benchmark comparability.
10. Keep only changes that improve the primary objective without violating latency, recall, validation, or loop-stability constraints.
11. Record iteration summary so another agent can resume without context loss.

# Prompt Template

- Objective: <e.g., precision_at_k to 0.65+>
- Baseline artifact: <path/to/results.json>
- Editable knobs: <parameters allowed to tune>
- Fixed constraints: <recall floor, latency ceiling, schema compatibility, validation/agent-loop policy>
- Cases: <yaml path or matrix config>
- Decision rule: <what qualifies as keep>

# Tuning Knobs

Use the smallest relevant knob family for each iteration:

- Retrieval weights: `candidate_ranker`, `retrieval_policy`, `hybrid_re2_*`, `adaptive_router_mode`, `adaptive_router_arm_set`.
- Embeddings: `embedding_model`, `embedding_dimension`, `embedding_rerank_pool`, `embedding_lexical_weight`, `embedding_semantic_weight`, `embedding_min_similarity`, `embedding_fail_open`.
- Structure: `repomap_ranking_profile`, `repomap_signal_weights`, `scip_provider`, `scip_generate_fallback`, `lsp_xref_enabled`.
- Validation and loop controls: `validation.enabled`, `validation.include_xref`, validation timeout budgets, `agent_loop.enabled`, loop iteration limits, replay-safe rerun expectations.
- Quality controls: `chunk_guard_*`, `chunk_diversity_*`, `topological_shield`, `plan_replay_cache_enabled`, `trace_export_enabled`.

# Artifact Checklist

Keep one artifact bundle per benchmark iteration:

- result JSON or markdown summary
- `plan_replay_cache_path` if replay stability matters
- `trace_export_path` when latency or plugin behavior is part of the decision
- `validation.result.summary.status` and `validation.diagnostic_count` when validation is enabled
- selected `validation_tests` or the reason they were intentionally out of scope
- whether `agent_loop` was enabled; if yes, `stop_reason`, `iteration_count`, final query, and replay fingerprint
- runtime doctor or self-test evidence when the run could be affected by MCP/runtime wiring
- install-sync evidence when the benchmark used an installed CLI instead of `PYTHONPATH=src`
- exact config diff for the knob family under test
- baseline and winning run identifiers

# Metrics Contract

Track and report for every iteration:

- `recall_at_k`
- `precision_at_k`
- `noise_rate`
- `dependency_recall`
- `latency_p95_ms`
- `validation_status`
- `validation_diagnostic_count`
- `validation_test_count`
- `agent_loop_enabled`
- `agent_loop_iteration_count`
- `agent_loop_stop_reason`
- `failed_thresholds` (if any)
- `router_mode` and `artifact_paths` used for the winning run
- `runtime_consistency` evidence used for the run

Final report format:

- Best parameter set
- Baseline vs best delta table
- Benchmark comparability statement: which validation/agent-loop/runtime assumptions were held constant
- Risks and tradeoffs
- Rollback command/path

# Tool Notes

- Keep commands deterministic and repo-relative.
- Avoid hidden manual steps so Codex/OpenCode/Claude Code can reproduce the same outcome.
- If a run depends on replay stability, write down `plan_replay_cache_path`, trace path, exact router mode, and whether validation or agent loop changed the final query.
- If latency spikes, empty retrieval, or plugin instability appear, run `ace-lite doctor` or `ace-lite runtime test-mcp` before blaming ranking parameters.
- If validation diagnostics or loop actions differ between baseline and candidate, treat the benchmark as non-comparable until those settings are pinned or intentionally under test.
- When benchmarking an installed CLI, verify version/install sync first; otherwise a drifted editable install can invalidate the comparison.
- Example feedback loop:

```python
ace_feedback_record(query="<benchmark query>", selected_path="<path>")
ace_feedback_stats(query="<benchmark query>", decay_days=60, max_boost=0.6, top_n=10)
```
