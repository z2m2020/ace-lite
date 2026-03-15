---
name: cross-agent-release-readiness
description: Release candidate and freeze-week checklist for go-no-go decisions.
intents: [release, review]
modules: [benchmark, ci, docs, release, changelog, tests, scip, trace_export, validation, agent_loop, mcp, version]
error_keywords: [release blocker, compatibility regression, incompatible, version drift, install drift]
default_sections: [Workflow, Prompt Template, Evidence Artifacts, Command Template, Scenario Templates, Go-NoGo Contract]
topics: [release, rc, freeze, gate, compatibility, changelog, go-no-go, failed_test_report, junit_xml, sbfl_metric, scip_provider, trace_export_path, embedding_index_path, validation_result_v1, validation_tests, agent_loop_summary_v1, runtime_doctor, mcp_self_test, install_sync, 发布, 发版, 冻结, 兼容性, 候选版本]
priority: 4
token_estimate: 420
---

# Workflow

1. Confirm target version/tag and release scope.
2. Run full test suite and smoke commands, capturing machine-readable artifacts when available.
3. Run benchmark matrix and threshold gates.
4. Verify diagnostics and structure artifacts: `failed_test_report` or `junit_xml`, `sbfl_metric`, trace export settings, and SCIP provider/index assumptions.
5. Verify config/schema compatibility and migration notes, including embeddings index, validation payload expectations, and replay-cache-sensitive workflows if they affect release evidence.
6. Verify local install/runtime consistency for the candidate build: version metadata, MCP self-test, and doctor output.
7. If the release touches `skills/`, benchmark playbooks, or release-readiness prompts, run freeze without `--skip-skill-validation` and review the skill validation artifact bundle.
8. Ensure governance docs/changelog are updated.
9. Produce go/no-go decision with blocking items.

# Prompt Template

- Release target: <version/tag>
- Scope: <features/fixes included>
- Required gates: <tests, smoke, benchmark thresholds>
- Compatibility checks: <schema/config/CLI/runtime>
- Evidence location: <artifacts paths for tests, benchmark, traces, failed-test reports>
- Decision deadline: <date/time>

# Evidence Artifacts

Prefer explicit release evidence over prose:

- `failed_test_report` or `junit_xml`
- `coverage_json`
- `sbfl_json` and `sbfl_metric`
- benchmark result JSON/markdown
- `skill_validation_matrix` when release scope touches skills, skill routing, or maintainer playbooks
- `trace_export_path` or OTLP endpoint used during release verification
- `scip_provider` and index path if structural retrieval is part of the release surface
- MCP self-test payload or `ace-lite doctor` output from the candidate environment
- validation status/diagnostic summary and `agent_loop` summary when the candidate depends on orchestrator post-validation behavior

# Command Template

Use one machine-readable release check command per candidate build:

```bash
ace-lite doctor --root . --skills-dir skills
ace-lite plan \
  --query "<release readiness review>" \
  --repo ace-lite-engine \
  --root . \
  --junit-xml reports/junit.xml \
  --sbfl-metric ochiai \
  --scip-provider auto \
  --trace-export \
  --trace-export-path context-map/traces/release.jsonl
```

Record the benchmark artifact path beside this command so the go/no-go package stays complete.

If release scope includes `skills/`, rerun freeze without `--skip-skill-validation` and attach:

- `artifacts/release-freeze/latest/skill-validation/skill_validation_matrix.json`
- `artifacts/release-freeze/latest/skill-validation/skill_validation_index.json`

# Scenario Templates

## RC dry run

- Scope: one candidate tag, one changelog snapshot, one benchmark artifact bundle.
- Required evidence: `junit_xml`, benchmark summary, and `trace_export_path` captured from the same candidate.
- Exit rule: promote only if all mandatory gates pass with no unresolved release blocker.

## Compatibility regression triage

- Scope: schema, config, CLI, and structural retrieval compatibility for one suspected breakage.
- Required evidence: failing command, `scip_provider`, embeddings or replay-cache assumptions, and the exact incompatible surface.
- Exit rule: classify as blocker, accepted risk, or docs-only remediation before the next RC.

## Install or MCP drift triage

- Scope: candidate artifact is built, but CLI/MCP behavior does not match the checked-out version.
- Required evidence: `python -m pip show ace-lite-engine`, self-test payload, and the exact checkout or editable project location under review.
- Exit rule: no GO decision until version/install drift is eliminated or explicitly accepted as packaging scope.

## Freeze-week rerun

- Scope: rerun only the locked release gates after a targeted fix during freeze.
- Required evidence: new machine-readable artifacts plus a clear diff against the previous freeze-week run.
- Exit rule: keep the go/no-go decision tied to the latest rerun package, not stale evidence.

# Go-NoGo Contract

- Status: GO / NO-GO
- Passed gates: <list>
- Failed gates: <list + owners>
- Risks accepted: <explicitly listed>
- Rollback and hotfix plan: <commands and branch/tag strategy>

# Tool Notes

- Keep release evidence machine-readable and linkable.
- Use the same gate language across Codex, OpenCode, and Claude Code handoffs.
