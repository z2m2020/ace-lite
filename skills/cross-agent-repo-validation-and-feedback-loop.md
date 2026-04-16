---
name: cross-agent-repo-validation-and-feedback-loop
description: Validate ACE-Lite on real repositories, turn actual-usage misses into issue and fix evidence, and close the loop with reruns, feedback capture, and developer reports.
intents: [troubleshoot, review]
modules: [validation, retrieval, ranking, mcp, issue_report, dev_feedback, repo_validation]
error_keywords: [retrieval pollution, route misfire, misleading summary, cross-repo contamination, ranking drift, actual usage miss, 误路由, 检索污染, 跨仓污染, 误计数]
default_sections: [Workflow, Prompt Template, Evidence Contract, Command Template, Scenario Templates, Output Contract]
topics: [repo validation, real repo, actual usage, real-world verification, issue report, developer feedback, ace_health, ace_plan_quick, ace_plan, ace_index, ace_issue_report_record, ace_issue_report_list, ace_dev_issue_record, ace_dev_fix_record, ace_dev_issue_apply_fix, ace_feedback_record, ace_feedback_stats, ace_memory_search, ace_memory_store, rerun evidence, validation rerun, artifact pollution, routing failure, 真实仓库, 实际使用, 开发者反馈, 复验, 问题复现]
priority: 3
token_estimate: 620
---

# Workflow

1. Start with `ace_health` and record runtime drift, `default_root`, `skills_dir`, and whether MCP/runtime wiring is already suspect.
2. Build a small real-repo query set first: 3-8 keyword-heavy queries that represent the user task, not a single natural-language paragraph.
3. Run `ace_plan_quick` against the target repo before touching source. Capture shortlist quality, routing profile, misleading summaries, and any polluted candidates.
4. Escalate to `ace_plan` only when the quick shortlist still mixes domains, hides the root cause, or needs chunk-level evidence.
5. Convert concrete misses into structured evidence immediately: wrong top files, polluted docs, cross-repo memory bleed, summary count mismatch, or routing misfire.
6. Record user-visible failures with `ace_issue_report_record`; if the problem is an ACE-Lite source defect, also create or update developer-side feedback with `ace_dev_issue_record` or `ace_dev_fix_record`.
7. Patch the smallest ACE-Lite source area that explains the miss. Avoid mixing product bugs, benchmark tuning, and runtime-drift cleanup in one patch.
8. Re-run targeted tests, refresh the repo index with `ace_index`, then rerun the same real-repo queries to prove the observed failure actually moved.
9. Capture winning paths via `ace_feedback_record`, summarize drift with `ace_feedback_stats`, and store reusable constraints with `ace_memory_store`.
10. If the change touched `skills/`, run skill-routing validation before claiming success; routing regressions count as product regressions.

# Prompt Template

- Target repo: <repo name + root path>
- Real task: <what the user was actually trying to do>
- Query set: <3-8 concrete queries>
- Expected evidence: <which files, domains, or summaries should appear>
- Actual miss: <wrong route / polluted candidate / misleading summary / memory bleed>
- Runtime status: <ace_health + drift/self-test note>
- Suspected ACE-Lite area: <policy / plan_quick / memory / mcp / skills>
- Acceptance criteria: <what must improve after rerun>
- Feedback destination: <issue report / dev feedback / memory / selection feedback>

# Evidence Contract

Do not call a real-repo validation run "useful" without these artifacts:

- `ace_health` snapshot or equivalent runtime-consistency note
- exact query set used against the target repo
- pre-fix shortlist or summary evidence from `ace_plan_quick` or `ace_plan`
- one concrete failure statement tied to file paths, counts, or routing fields
- post-fix rerun evidence using the same query set
- targeted test evidence from the ACE-Lite source checkout
- feedback writeback note: which `ace_feedback_record`, issue report, dev fix, or memory note was created

If the observed problem only appears under an installed CLI or MCP server, either verify version/install sync first or run from `PYTHONPATH=src` so source and runtime stay aligned.

# Command Template

Real-repo evidence pass:

```python
ace_health()
ace_plan_quick(
  query="<keyword query>",
  root="<target repo root>",
  repo="<target repo name>",
  candidate_ranker="rrf_hybrid",
  top_k_files=8,
  index_incremental=True,
)
```

Issue and feedback capture:

```python
ace_issue_report_record(
  title="<short failure title>",
  query="<real-repo query>",
  actual_behavior="<what ACE-Lite returned>",
  expected_behavior="<what should have happened>",
  repo="ace-lite",
  root=".",
)
ace_dev_fix_record(
  repo="ace-lite",
  reason_code="<routing_or_retrieval_reason>",
  resolution_note="<what source change fixed the issue>",
)
ace_feedback_record(query="<real-repo query>", selected_path="<actual useful file>")
ace_feedback_stats(query="<real-repo query>", top_n=10)
```

Source validation pass:

```bash
PYTHONPATH=src python -m pytest -q tests/unit/test_skills.py
PYTHONPATH=src python -m pytest -q <targeted tests>
```

After retrieval-sensitive changes:

```python
ace_index(root=".", output="context-map/index.json")
ace_memory_store(text="[repo-validation] <stable finding or guardrail>", namespace="ace-lite")
```

If the patch changes `skills/`, validate routing explicitly:

```bash
python scripts/run_skill_validation.py \
  --repo-url <repo-url> \
  --repo-ref <ref> \
  --repo-name <name> \
  --repo-dir artifacts/repos-workdir/skill-validation \
  --skills-dir skills \
  --output-path artifacts/skill-eval/<name>.json \
  --index-cache-path artifacts/skill-eval/<name>-index.json \
  --languages <languages> \
  --apps codex,opencode,claude-code \
  --min-pass-rate 1.0 \
  --fail-on-miss
```

# Scenario Templates

## Real-repo retrieval miss

- Scope: the user asks about real code, but top files are wrong or too noisy.
- Required evidence: query set, wrong shortlist, expected files or domains, and rerun proof after the patch.
- Exit rule: do not stop at "ranking looks better"; show the concrete query moved in the right direction.

## Tool-artifact pollution

- Scope: ACE-Lite-generated feedback, assessment, benchmark, or status docs pollute later retrieval.
- Required evidence: polluted path, why it is tool-generated noise, and the guardrail used to demote or exclude it.
- Exit rule: prove general queries improve without breaking explicit queries for that artifact family.

## Cross-repo memory contamination

- Scope: local notes, memory namespace, or feedback store from repo A bleeds into repo B.
- Required evidence: current `notes_path` or feedback path, conflicting repo hints, and post-fix filtered result.
- Exit rule: fix the boundary condition before retuning ranking weights.

## Misleading summary or contract mismatch

- Scope: top-level summary fields such as `candidate_files`, timeout fallback summaries, or validation cards disagree with the underlying payload.
- Required evidence: payload path, summary field, mismatch example, and post-fix parity.
- Exit rule: prefer one canonical source of truth and document its priority order.

## Skills change after real-repo learning

- Scope: the real-repo investigation changes `skills/`, routing metadata, or skill wording.
- Required evidence: new skill/query pair, `pytest -q tests/unit/test_skills.py`, and `run_skill_validation.py` evidence if routing behavior could shift across hosts.
- Exit rule: do not merge a skills change just because the prose is better; verify routing still behaves.

# Output Contract

- Real task and target repo
- Query set used for validation
- Pre-fix failure in 1-2 lines
- Root cause in 1-2 lines
- Patched ACE-Lite files and why
- Post-fix rerun result on the same queries
- Tests and validation commands
- Feedback artifacts written: issue report, dev fix, feedback record, memory note
- Residual risk and next suggested guardrail
