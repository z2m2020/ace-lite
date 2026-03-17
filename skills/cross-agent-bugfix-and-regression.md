---
name: cross-agent-bugfix-and-regression
description: Deterministic bugfix loop with regression-safe validation.
intents: [troubleshoot]
modules: [orchestrator, indexer, memory, tests, scip, trace_export, validation, agent_loop, doctor, version, mcp]
error_keywords: [stack trace, timeout, 405, failing test, behavior regression, validation failed, install drift, 超时, 回归]
default_sections: [Workflow, Prompt Template, Diagnostics Inputs, Command Template, Scenario Templates, Output Contract]
topics: [bugfix, fix, regression, test, exception, traceback, rollback, junit_xml, failed_test_report, sbfl_metric, scip_provider, trace_export_path, validation, validation_result_v1, validation_tests, agent_loop_action_v1, verify_version_install_sync, runtime_doctor, doctor_mcp, test_mcp, final_query, replay_fingerprint, 修复, 测试, 异常, 回滚]
priority: 4
token_estimate: 380
---

# Workflow

1. Reproduce the issue with the smallest reliable command.
2. If the failure appeared after an upgrade, reinstall, editable install, or MCP config change, verify version/install sync before deeper debugging.
3. Capture failing signal first: stacktrace, assertion, `failed_test_report`, `junit_xml`, `sbfl_metric`, validation diagnostics, doctor output, or trace artifact.
4. Locate root cause; avoid symptom-only patches.
5. Implement minimal fix with focused code changes.
6. Run targeted tests covering the failing path.
7. If validation-stage diagnostics exist, decide whether the failure is in runtime code, patch-sandbox application, or xref collection before editing.
8. If symbol resolution or cross-file navigation matters, declare the `scip_provider` and fallback strategy used during diagnosis.
9. Run broader regression checks and summarize risk.

# Prompt Template

- Bug: <what is wrong>
- Repro command: <exact command>
- Expected vs actual: <difference>
- Suspected area: <files/modules>
- Diagnostics artifacts: <failed_test_report/junit_xml/sbfl_json/trace path/validation summary/doctor output if any>
- Structural context: <scip provider / fallback / xref assumptions if relevant>
- Runtime drift status: <not checked / clean / drift detected via verify_version_install_sync or doctor>
- Acceptance criteria: <what must pass>
- Constraints: <no API break / no unrelated refactor>

# Diagnostics Inputs

Prefer explicit artifacts over prose when available:

- `failed_test_report` or `junit_xml` for failing-test triage
- `sbfl_json` plus `sbfl_metric` when ranking suspicious files
- `trace_export_path` when the bug involves latency, plugin execution, or timeout fallback
- `scip_provider` when the failure depends on definitions, references, or cross-file symbol edges
- `validation.result.summary`, `validation.diagnostics`, or sandbox apply status when the failing behavior first appears in orchestrator validation
- `verify_version_install_sync()`, `ace-lite doctor`, or `ace-lite runtime doctor-mcp` when the failure may come from install drift or MCP wiring
- `final_query`, `replay_fingerprint`, or rerun-stage output when agent-loop replay behavior influences the bug

# Command Template

Use a diagnostics-first command when the bug depends on ranked evidence:

```bash
ace-lite plan \
  --query "<bug summary>" \
  --repo ace-lite-engine \
  --root . \
  --failed-test-report reports/junit.xml \
  --sbfl-metric ochiai \
  --scip-provider auto \
  --trace-export \
  --trace-export-path context-map/traces/bugfix.jsonl
```

If the issue may come from runtime wiring instead of source code, run the drift bundle before editing:

```bash
ace-lite doctor --root . --skills-dir skills
ace-lite runtime doctor-mcp --root . --skills-dir skills
ace-lite runtime test-mcp --root . --skills-dir skills
python -m ace_lite.mcp_server --self-test --root . --skills-dir skills
```

If you skip one of these inputs, say why the bug does not need it.

# Scenario Templates

## Failing-test triage

- Scope: one reproducible failing test or assertion with machine-readable diagnostics attached.
- Required evidence: repro command, `failed_test_report` or `junit_xml`, and the acceptance test that proves the fix.
- Exit rule: do not broaden the patch until the original failing path is stable and explained.

## Timeout or trace incident

- Scope: latency spike, timeout fallback, or plugin execution stall where trace evidence is available.
- Required evidence: timeout symptom, `trace_export_path`, and whether the failure is deterministic or flaky.
- Exit rule: separate performance diagnosis from semantic behavior changes so rollback stays simple.

## Validation-stage incident

- Scope: failure first shows up under sandbox validation, xref collection, or `validation.result.summary.status`.
- Required evidence: validation status, diagnostic paths/messages, patch-apply result, and whether agent loop requested a focused rerun.
- Exit rule: isolate validation wiring or sandbox behavior before broadening the bugfix into unrelated retrieval changes.

## Install-drift or MCP incident

- Scope: the symptom appeared after pull, reinstall, editable install changes, or MCP runtime wiring updates.
- Required evidence: `verify_version_install_sync()`, `ace-lite doctor`, `ace-lite runtime doctor-mcp`, and, when relevant, MCP self-test output from the same checkout.
- Exit rule: do not edit runtime logic until drift or MCP wiring has been confirmed or ruled out.

## Symbol-edge regression

- Scope: bug where definitions, references, or cross-file navigation affect diagnosis quality.
- Required evidence: declared `scip_provider`, fallback policy, and the symbol path or xref assumption that failed.
- Exit rule: fix the structural diagnosis path or fail-open behavior before layering ranking tweaks on top.

# Output Contract

- Repro status: reproducible / not reproducible.
- Runtime drift status: clean / drift detected / not applicable.
- Root cause statement in 1-2 lines.
- Patched files with concise rationale.
- Test evidence (targeted + regression).
- Rollback strategy if regression appears.

# Tool Notes

- Keep evidence-first flow so all three agents can reason consistently.
- Prefer deterministic commands and explicit pass/fail signals.
- Treat install drift and MCP wiring as first-class bug classes, not as afterthoughts once source debugging has already started.
