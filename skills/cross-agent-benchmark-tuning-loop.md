---
name: cross-agent-benchmark-tuning-loop
description: Benchmark tuning loop for retrieval, routing, and chunking changes with measurable keep-or-rollback decisions.
intents: [benchmark, troubleshoot]
modules: [benchmark, ranking, retrieval, repomap, feedback, embeddings, scip, adaptive_router, plan_replay_cache, trace_export, chunk_guard]
error_keywords: [metric regression, timeout, latency spike]
default_sections: [Workflow, Prompt Template, Tuning Knobs, Artifact Checklist, Metrics Contract, Tool Notes]
topics: [benchmark, tuning, precision, noise, latency, threshold, recall, ranking, feedback, embedding_rerank_pool, embedding_lexical_weight, embedding_semantic_weight, scip_provider, adaptive_router_mode, plan_replay_cache_enabled, plan_replay_cache_path, trace_export_enabled, trace_export_path, chunk_guard_mode, topological_shield, 基准, 调优, 精度, 噪声, 延迟, 召回]
priority: 3
token_estimate: 560
---

# Workflow

1. Establish baseline metrics from the same case set and repo revision.
2. Run `ace_health` and `ace_memory_search` to recover prior tuning constraints.
3. Freeze replay inputs first: repo revision, case set, router mode, and replay cache policy.
4. Change one parameter group per iteration (weights, thresholds, router mode, structure source, chunk controls).
5. Run targeted benchmark first, then matrix benchmark if gates are close; export trace artifacts when latency or plugin behavior is under review.
6. Record actual useful files via `ace_feedback_record` and compute trend via `ace_feedback_stats`.
7. Compare deltas against explicit keep/rollback rules.
8. Keep only changes that improve primary objective without violating latency and recall constraints.
9. Record iteration summary so another agent can resume without context loss.

# Prompt Template

- Objective: <e.g., precision_at_k to 0.65+>
- Baseline artifact: <path/to/results.json>
- Editable knobs: <parameters allowed to tune>
- Fixed constraints: <recall floor, latency ceiling, schema compatibility>
- Cases: <yaml path or matrix config>
- Decision rule: <what qualifies as keep>

# Tuning Knobs

Use the smallest relevant knob family for each iteration:

- Retrieval weights: `candidate_ranker`, `retrieval_policy`, `hybrid_re2_*`, `adaptive_router_mode`, `adaptive_router_arm_set`.
- Embeddings: `embedding_model`, `embedding_dimension`, `embedding_rerank_pool`, `embedding_lexical_weight`, `embedding_semantic_weight`, `embedding_min_similarity`, `embedding_fail_open`.
- Structure: `repomap_ranking_profile`, `repomap_signal_weights`, `scip_provider`, `scip_generate_fallback`, `lsp_xref_enabled`.
- Quality controls: `chunk_guard_*`, `chunk_diversity_*`, `topological_shield`, `plan_replay_cache_enabled`, `trace_export_enabled`.

# Artifact Checklist

Keep one artifact bundle per benchmark iteration:

- result JSON or markdown summary
- `plan_replay_cache_path` if replay stability matters
- `trace_export_path` when latency or plugin behavior is part of the decision
- exact config diff for the knob family under test
- baseline and winning run identifiers

# Metrics Contract

Track and report for every iteration:

- `recall_at_k`
- `precision_at_k`
- `noise_rate`
- `dependency_recall`
- `latency_p95_ms`
- `failed_thresholds` (if any)
- `router_mode` and `artifact_paths` used for the winning run

Final report format:

- Best parameter set
- Baseline vs best delta table
- Risks and tradeoffs
- Rollback command/path

# Tool Notes

- Keep commands deterministic and repo-relative.
- Avoid hidden manual steps so Codex/OpenCode/Claude Code can reproduce the same outcome.
- If a run depends on replay stability, write down `plan_replay_cache_path`, trace path, and the exact router mode.
- Example feedback loop:

```python
ace_feedback_record(query="<benchmark query>", selected_path="<path>")
ace_feedback_stats(query="<benchmark query>", decay_days=60, max_boost=0.6, top_n=10)
```
