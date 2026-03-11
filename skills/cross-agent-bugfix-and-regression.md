---
name: cross-agent-bugfix-and-regression
description: Deterministic bugfix loop with regression-safe validation.
intents: [troubleshoot]
modules: [orchestrator, indexer, memory, tests, scip, trace_export]
error_keywords: [stack trace, timeout, 超时, 405, failing test, behavior regression]
default_sections: [Workflow, Prompt Template, Diagnostics Inputs, Command Template, Scenario Templates, Output Contract]
topics: [bugfix, fix, regression, test, exception, traceback, rollback, junit_xml, failed_test_report, sbfl_metric, scip_provider, trace_export_path, 修复, 回归, 测试, 异常, 回滚]
priority: 4
token_estimate: 340
---

# Workflow

1. Reproduce the issue with the smallest reliable command.
2. Capture failing signal first: stacktrace, assertion, `failed_test_report`, `junit_xml`, `sbfl_metric`, or trace artifact.
3. Locate root cause; avoid symptom-only patches.
4. Implement minimal fix with focused code changes.
5. Run targeted tests covering the failing path.
6. If symbol resolution or cross-file navigation matters, declare the `scip_provider` and fallback strategy used during diagnosis.
7. Run broader regression checks and summarize risk.

# Prompt Template

- Bug: <what is wrong>
- Repro command: <exact command>
- Expected vs actual: <difference>
- Suspected area: <files/modules>
- Diagnostics artifacts: <failed_test_report/junit_xml/sbfl_json/trace path if any>
- Structural context: <scip provider / fallback / xref assumptions if relevant>
- Acceptance criteria: <what must pass>
- Constraints: <no API break / no unrelated refactor>

# Diagnostics Inputs

Prefer explicit artifacts over prose when available:

- `failed_test_report` or `junit_xml` for failing-test triage
- `sbfl_json` plus `sbfl_metric` when ranking suspicious files
- `trace_export_path` when the bug involves latency, plugin execution, or timeout fallback
- `scip_provider` when the failure depends on definitions, references, or cross-file symbol edges

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
  --trace-export-enabled \
  --trace-export-path context-map/traces/bugfix.jsonl
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

## Symbol-edge regression

- Scope: bug where definitions, references, or cross-file navigation affect diagnosis quality.
- Required evidence: declared `scip_provider`, fallback policy, and the symbol path or xref assumption that failed.
- Exit rule: fix the structural diagnosis path or fail-open behavior before layering ranking tweaks on top.

# Output Contract

- Repro status: reproducible / not reproducible.
- Root cause statement in 1-2 lines.
- Patched files with concise rationale.
- Test evidence (targeted + regression).
- Rollback strategy if regression appears.

# Tool Notes

- Keep evidence-first flow so all three agents can reason consistently.
- Prefer deterministic commands and explicit pass/fail signals.
