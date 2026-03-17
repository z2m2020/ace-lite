---
name: cross-agent-refactor-safeguards
description: Behavior-preserving refactor playbook with guardrails for pipeline order, validation and agent-loop contracts, runtime wiring, skills routing, and rollback checks.
intents: [refactor, implement, review]
modules: [cli, orchestrator, repomap, config, pipeline, validation, agent_loop, doctor, version, skills, source_plan, prompt_rendering]
error_keywords: [behavior regression, api breakage, merge conflict, version drift, install drift, validation regression]
default_sections: [Workflow, Prompt Template, Output Contract]
topics: [refactor, cleanup, maintainability, rename, restructure, debt, duplication, duplicated, deduplicate, chunk_guard_mode, trace_export_path, config_schema, pipeline_order, validation_result_v1, agent_loop_summary_v1, observability, stage_metrics, runtime_doctor, mcp_self_test, verify_version_install_sync, metadata_only_routing, selected_manifest_token_estimate_total, prompt_rendering_boundary_v1, chunk_contract, subgraph_payload, final_query, replay_fingerprint, rerun_stages, doctor_mcp, 重构, 清理, 重命名, 重复, 去重]
priority: 3
token_estimate: 420
---

# Workflow

1. Define refactor intent and non-functional boundaries.
2. Snapshot current behavior with representative tests or commands, and capture the contract surfaces that must not drift: `pipeline_order`, `observability.stage_metrics`, CLI flags, skills-routing fields, prompt-boundary payloads, and any runtime doctor or self-test evidence.
3. Split change into small commits/patch steps.
4. If the refactor touches orchestrator, pipeline, validation, agent loop, config, skills, source plan, or runtime CLI wiring, explicitly preserve external contracts: `validation_result_v1`, `agent_loop_summary_v1`, `metadata_only_routing`, `selected_manifest_token_estimate_total`, `prompt_rendering_boundary_v1`, `chunk_contract`, `subgraph_payload`, validation default fail-open behavior, and stage-metric shape.
5. If the validation path is part of the surface, compare before and after payloads for validation status, diagnostic count, and the last stage in `observability.stage_metrics`.
6. If the agent loop path is in scope, verify stop reason, iteration count, rerun stages, `final_query`, and `replay_fingerprint` remain intentionally unchanged.
7. If the skills stage is in scope, compare `routing_mode`, `metadata_only_routing`, token-budget fields, and hydrated-skill counts before and after the refactor.
8. When validating through installed commands instead of `PYTHONPATH=src`, check version/install sync before trusting any before-after comparison.
9. Re-run snapshots and compare before/after outputs.
10. Document migration notes only when behavior intentionally changes, and name the contract that changed.

# Prompt Template

- Refactor target: <module/function>
- Why now: <debt/perf/readability>
- Invariants: <must stay the same, including CLI flags, `pipeline_order`, `validation_result_v1`, `agent_loop_summary_v1`, `metadata_only_routing`, `selected_manifest_token_estimate_total`, `prompt_rendering_boundary_v1`, `chunk_contract`, `subgraph_payload`, `final_query`, `replay_fingerprint`, config keys, and artifact schema when relevant>
- Allowed change surface: <files>
- Forbidden changes: <API/format/breaking behavior, silent validation contract drift, skills-routing regressions, prompt-boundary regressions, runtime wiring regressions>
- Runtime contract snapshot: <doctor/self-test output, stage-metric sample, validation or agent-loop payload if relevant>
- Validation matrix: <tests + smoke + benchmark if needed>
- Install mode: <`PYTHONPATH=src` or installed CLI; include version-sync check when installed>

# Output Contract

- Before/after architecture summary.
- Invariant check results, including whether `pipeline_order` and stage counts stayed stable.
- Skills-routing contract check: <not applicable or summary of `routing_mode`, `metadata_only_routing`, token-budget fields, and hydrated-skill count comparison>
- Prompt-boundary contract check: <not applicable or summary of `prompt_rendering_boundary_v1`, `chunk_contract`, and `subgraph_payload` comparison>
- Validation contract check: <not applicable or summary of `validation_result_v1` / validation status / diagnostic count comparison>
- Agent-loop contract check: <not applicable or summary of `agent_loop_summary_v1`, stop reason, `final_query`, `replay_fingerprint`, and rerun-stage comparison>
- Runtime wiring check: <not applicable or `doctor-mcp` / `test-mcp` / self-test result summary>
- Version drift check: <not applicable or `verify_version_install_sync()` / installed metadata status>
- Changed files grouped by purpose.
- Follow-up debt not included in this patch.

# Tool Notes

- Encourage surgical edits over broad rewrites.
- Keep diffs readable so review quality is high across all agents.
- If the refactor touches runtime CLI or MCP wiring, run `ace-lite runtime doctor-mcp` or `ace-lite runtime test-mcp` before declaring behavior unchanged.
- If the refactor is validated via installed entry points, run `verify_version_install_sync()` or equivalent install-drift evidence first; otherwise use `PYTHONPATH=src` to pin execution to the working tree.
- Treat schema and observability payloads as public contracts once tests assert on them; do not collapse or rename fields like `validation.result`, `observability.stage_metrics`, `observability.agent_loop`, `prompt_rendering_boundary_v1`, or `chunk_contract` without an explicit migration plan.
