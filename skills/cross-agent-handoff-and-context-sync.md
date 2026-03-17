---
name: cross-agent-handoff-and-context-sync
description: Standardized handoff and context sync protocol for multi-agent continuity.
intents: [handoff, memory]
modules: [docs, context, session, pipeline, plan_replay_cache, trace_export, validation, agent_loop, skills, source_plan, doctor]
error_keywords: [stale context, context drift, context mismatch]
default_sections: [Workflow, Handoff Template, Artifact Contract, Resume Commands, Validation Checklist]
topics: [handoff, context, sync, onboarding, resume, session, plan_replay_cache_path, trace_export_path, junit_xml, sbfl_metric, validation_result_v1, agent_loop_summary_v1, runtime_doctor, routing_mode, metadata_only_routing, final_query, replay_fingerprint, rerun_stages, prompt_rendering_boundary_v1, chunk_contract, subgraph_payload, doctor_mcp, test_mcp, 交接, 上下文同步, 续接, 接手]
priority: 3
token_estimate: 500
---

# Workflow

1. Summarize completed work in terms of outcomes, not raw activity.
2. List exact modified files and unresolved risks.
3. Capture reproducible validation commands and latest results.
4. Add memory lifecycle status: what was searched, what was stored, what must never be wiped.
5. Persist artifact paths and structured summaries that make the next run reproducible: replay cache, trace export, failed-test reports, benchmark outputs, validation status, `routing_mode`, `metadata_only_routing`, prompt boundary snapshot, and agent-loop stop reason when present.
6. If agent loop or replay behavior changed, carry forward `final_query`, `replay_fingerprint`, and rerun stages rather than only a prose summary.
7. Document next actions with priority and owner hints.
8. Sync key facts into session context docs before ending the turn.
9. Start next session by reloading the handoff package and verifying repo state.

# Handoff Template

- Goal completed: <done/not done + scope>
- Changed files: <file list>
- Validation evidence: <commands + pass/fail>
- Validation summary: <validation status / diagnostic count / sandbox or xref note if relevant>
- Skills routing snapshot: <routing_mode / metadata_only_routing / token budget note if relevant>
- Prompt boundary snapshot: <prompt_rendering_boundary_v1 / chunk_contract / subgraph_payload summary if relevant>
- Agent-loop replay snapshot: <final_query / replay_fingerprint / rerun stages / stop reason if relevant>
- Open risks: <blocking/non-blocking>
- Feedback summary: <ace_feedback_stats key observations>
- Memory namespace status: <searched/stored/wipe-needed?>
- Artifact bundle: <trace path / replay cache / junit / sbfl / benchmark outputs>
- Next top 3 tasks: <ordered>
- Resume command set: <minimal commands to continue>

# Artifact Contract

If the previous agent used any of these, carry them forward explicitly:

- `plan_replay_cache_path`
- `trace_export_path` or `trace_otlp_endpoint`
- `failed_test_report` or `junit_xml`
- `sbfl_json` and `sbfl_metric`
- benchmark result JSON or markdown paths
- `validation.result.summary` or `agent_loop` summary when the orchestrator emitted them
- `final_query`, `replay_fingerprint`, and rerun-stage lists when the next run depends on replay behavior
- `routing_mode`, `metadata_only_routing`, or prompt-boundary artifacts when skills routing or source-plan output is in scope

# Resume Commands

Prefer a minimal resume bundle that another agent can run without interpretation:

```bash
git status --short
python -m pytest <targeted tests>
ace-lite plan --query "<resume task>" --repo ace-lite-engine --root . --trace-export --trace-export-path context-map/traces/resume.jsonl
```

If replay cache or failed-test artifacts were used, include those exact paths on the same line as the resume command set.

If the handoff is about runtime drift or MCP wiring, add the doctor bundle as well:

```bash
ace-lite doctor --root . --skills-dir skills
ace-lite runtime doctor-mcp --root . --skills-dir skills
```

# Validation Checklist

Before publishing handoff:

- `git status` is captured.
- Test/benchmark outcomes are timestamped.
- No broken file references in docs.
- TODOs are actionable and bounded.

Before consuming handoff:

- Confirm branch and latest commit.
- Re-run minimal validation commands.
- Confirm assumptions still hold (paths, config, thresholds).
- If the previous run depended on installed entry points, confirm version/install sync before trusting replay or doctor evidence.

# Tool Notes

- Keep handoff concise but executable.
- Prefer explicit paths and command examples so different agents produce identical continuation behavior.
- When the task touched skills or prompt assembly, include the exact routing and prompt-boundary fields instead of summarizing them loosely.
- Memory governance examples:

```python
ace_memory_search(query="<topic>", namespace="<project>", limit=5)
ace_memory_store(text="<decision>", namespace="<project>")
ace_memory_wipe(namespace="<project>")  # only when stale/incorrect memory is confirmed
```

- Feedback continuity examples:

```python
ace_feedback_record(query="<task query>", selected_path="<file>")
ace_feedback_stats(query="<task query>", top_n=10)
```
