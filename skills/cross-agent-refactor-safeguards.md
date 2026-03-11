---
name: cross-agent-refactor-safeguards
description: Behavior-preserving refactor playbook with guardrails and rollback checks.
intents: [refactor, implement, review]
modules: [cli, orchestrator, repomap, config, pipeline]
error_keywords: [behavior regression, api breakage, merge conflict]
default_sections: [Workflow, Prompt Template, Output Contract]
topics: [refactor, cleanup, maintainability, rename, restructure, debt, duplication, duplicated, deduplicate, chunk_guard_mode, trace_export_path, config_schema, 重构, 清理, 重命名, 重复, 去重]
priority: 3
token_estimate: 290
---

# Workflow

1. Define refactor intent and non-functional boundaries.
2. Snapshot current behavior with representative tests/commands, and capture any config or trace artifacts that define the current contract.
3. Split change into small commits/patch steps.
4. Preserve external contracts (CLI flags, schema, output shape).
5. Re-run snapshots and compare before/after outputs.
6. Document migration notes if behavior intentionally changes.

# Prompt Template

- Refactor target: <module/function>
- Why now: <debt/perf/readability>
- Invariants: <must stay the same, including config keys/artifact schema when relevant>
- Allowed change surface: <files>
- Forbidden changes: <API/format/breaking behavior>
- Validation matrix: <tests + smoke + benchmark if needed>

# Output Contract

- Before/after architecture summary.
- Invariant check results.
- Changed files grouped by purpose.
- Follow-up debt not included in this patch.

# Tool Notes

- Encourage surgical edits over broad rewrites.
- Keep diffs readable so review quality is high across all agents.
