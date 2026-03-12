---
name: cross-agent-refactor-safeguards
description: Behavior-preserving refactor playbook with guardrails for pipeline order, validation and agent-loop contracts, runtime wiring, and rollback checks.
intents: [refactor, implement, review]
modules: [cli, orchestrator, repomap, config, pipeline, validation, agent_loop, doctor, version]
error_keywords: [behavior regression, api breakage, merge conflict, version drift, install drift, validation regression]
default_sections: [Workflow, Prompt Template, Output Contract]
topics: [refactor, cleanup, maintainability, rename, restructure, debt, duplication, duplicated, deduplicate, chunk_guard_mode, trace_export_path, config_schema, pipeline_order, validation_result_v1, agent_loop_summary_v1, observability, stage_metrics, runtime_doctor, mcp_self_test, verify_version_install_sync, 重构, 清理, 重命名, 重复, 去重, 验证, 漂移]
priority: 3
token_estimate: 420
---

# Workflow

1. Define refactor intent and non-functional boundaries.
2. Snapshot current behavior with representative tests or commands, and capture the contract surfaces that must not drift: `pipeline_order`, `observability.stage_metrics`, CLI flags, and any runtime doctor or self-test evidence.
3. Split change into small commits/patch steps.
4. If the refactor touches orchestrator, pipeline, validation, agent loop, config, or runtime CLI wiring, explicitly preserve external contracts: `validation_result_v1`, `agent_loop_summary_v1`, validation default fail-open behavior, and stage-metric shape.
5. If the validation path is part of the surface, compare before and after payloads for validation status, diagnostic count, and the last stage in `observability.stage_metrics`.
6. If the agent loop path is in scope, verify stop reason, iteration count, rerun stages, and final query remain intentionally unchanged.
7. When validating through installed commands instead of `PYTHONPATH=src`, check version/install sync before trusting any before-after comparison.
8. Re-run snapshots and compare before/after outputs.
9. Document migration notes only when behavior intentionally changes, and name the contract that changed.

# Prompt Template

- Refactor target: <module/function>
- Why now: <debt/perf/readability>
- Invariants: <must stay the same, including CLI flags, `pipeline_order`, `validation_result_v1`, `agent_loop_summary_v1`, `observability.stage_metrics`, config keys, and artifact schema when relevant>
- Allowed change surface: <files>
- Forbidden changes: <API/format/breaking behavior, silent validation contract drift, runtime wiring regressions>
- Runtime contract snapshot: <doctor/self-test output, stage-metric sample, validation or agent-loop payload if relevant>
- Validation matrix: <tests + smoke + benchmark if needed>
- Install mode: <`PYTHONPATH=src` or installed CLI; include version-sync check when installed>

# Output Contract

- Before/after architecture summary.
- Invariant check results, including whether `pipeline_order` and stage counts stayed stable.
- Validation contract check: <not applicable or summary of `validation_result_v1` / validation status / diagnostic count comparison>
- Agent-loop contract check: <not applicable or summary of `agent_loop_summary_v1`, stop reason, and rerun-stage comparison>
- Runtime wiring check: <not applicable or `doctor-mcp` / `test-mcp` / self-test result summary>
- Version drift check: <not applicable or `verify_version_install_sync()` / installed metadata status>
- Changed files grouped by purpose.
- Follow-up debt not included in this patch.

# Tool Notes

- Encourage surgical edits over broad rewrites.
- Keep diffs readable so review quality is high across all agents.
- If the refactor touches runtime CLI or MCP wiring, run `ace-lite runtime doctor-mcp` or `ace-lite runtime test-mcp` before declaring behavior unchanged.
- If the refactor is validated via installed entry points, run `verify_version_install_sync()` or equivalent install-drift evidence first; otherwise use `PYTHONPATH=src` to pin execution to the working tree.
- Treat schema and observability payloads as public contracts once tests assert on them; do not collapse or rename fields like `validation.result`, `observability.stage_metrics`, or `observability.agent_loop` without an explicit migration plan.
