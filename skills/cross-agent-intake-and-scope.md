---
name: cross-agent-intake-and-scope
description: Task intake and scoping contract before any code edits.
intents: [implement, review]
modules: [planning, requirements, docs, validation, config]
error_keywords: [scope mismatch, 范围不一致, missing constraint, 缺少约束, contradictory requirement]
default_sections: [Workflow, Prompt Template, Config Checklist, Artifact Checklist, Output Contract]
topics: [scope, scoping, plan, planning, validation, constraint, constraints, embeddings, scip_provider, adaptive_router_mode, trace_export_path, plan_replay_cache_enabled, chunk_guard_mode, 范围, 规划, 验证, 约束]
priority: 4
token_estimate: 340
---

# Workflow

1. Restate the goal in one sentence and list hard constraints.
2. Identify impacted modules/files first; do not edit until scope is explicit.
3. Define success criteria (functional, test, performance, docs, artifacts).
4. Propose a short plan with checkpoints and risk notes.
5. Execute in small reversible patches.
6. Validate with targeted tests first, then broader regression checks.

# Prompt Template

Use this template in any agent:

- Goal: <single clear objective>
- Constraints: <must/should/cannot>
- Scope: <allowed files or modules>
- Non-goals: <what not to change>
- Config surfaces: <embeddings/scip/router/replay/trace/chunk controls touched or explicitly out of scope>
- Validation: <commands and expected signals>
- Deliverable: <patch/docs/report>

# Config Checklist

Before editing, decide whether the task changes any of these first-class surfaces:

- Retrieval and ranking: embeddings, adaptive router, retrieval policy, repomap weights.
- Structural context: SCIP provider, LSP xref, index cache or conventions files.
- Diagnostics and observability: `failed_test_report`, `sbfl_metric`, `trace_export_*`.
- Quality controls: chunk guard, diversity, topological shield, replay cache.

If the answer is "no", say so explicitly to keep the task bounded.

# Artifact Checklist

Before coding, decide whether the task must produce any of these:

- `output_json` plan payload
- `trace_export_path`
- `failed_test_report` or `junit_xml`
- benchmark output path
- replay-cache path

If none apply, state that explicitly so later handoffs do not invent missing evidence.

# Output Contract

Every response should include:

- Confirmed scope and assumptions.
- Ordered plan (3-6 steps).
- Files to change (or evidence if no change needed).
- Validation status and remaining risks.
- Next action recommendation.

# Tool Notes

- Works for Codex, OpenCode, and Claude Code.
- Keep wording tool-agnostic; avoid platform-specific shortcuts in core workflow.
