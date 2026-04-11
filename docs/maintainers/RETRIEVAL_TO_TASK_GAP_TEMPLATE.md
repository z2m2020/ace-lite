# Retrieval-to-Task Gap Review Template

**Phase**: Phase N
**Date**: YYYY-MM-DD
**Checkpoint ID**: `artifacts/checkpoints/phaseN/YYYY-MM-DD/checkpoint_manifest.json`
**Prior Checkpoint**: `artifacts/checkpoints/phaseN/YYYY-MM-DD/../PRIOR_DATE/checkpoint_manifest.json`

---

## Purpose

This template structures the review of retrieval-to-task gaps: situations where the retrieved context does not fully support the planned task. It produces a dated gap report (JSON + MD) used in phase governance and as input to subsequent phase checkpoints.

**Scope**: This is a **report-only** artifact during Phase 1. Gap findings do not block releases but must be recorded for governance review.

---

## Inputs

### Required Artifacts

| Artifact | Path | Schema |
|---|---|---|
| ContextReport | `artifacts/context-reports/YYYY-MM-DD/context_report.md` (or `.json`) | `context_report_v1` |
| Retrieval Graph View | `artifacts/retrieval-graphs/YYYY-MM-DD/retrieval_graph_view.json` | `retrieval_graph_view_v1` |

### Optional Artifacts

| Artifact | Path | Schema |
|---|---|---|
| Benchmark Summary | `artifacts/benchmark/latest/summary.json` | (informal) |
| Freeze Regression | `artifacts/freeze/latest/freeze_regression.json` | (informal) |
| Problem Ledger | `artifacts/checkpoints/phaseN/YYYY-MM-DD/problem_ledger.json` | `problem_ledger_v1` |

---

## Gap Analysis

### Retrieval-to-Task Alignment Signals

For each retrieved chunk / node, assess:

1. **Directness**: Is the retrieved chunk a direct match for the planned task?
   - EXTRACTED → direct match
   - INFERRED → plausible but indirect
   - AMBIGUOUS / UNKNOWN → potential gap

2. **Coverage**: Do retrieved nodes cover all required artifacts for the task?
   - Identify missing artifact types
   - Identify truncated retrieval (node_limit_applied)

3. **Noise**: Are retrieved chunks irrelevant to the task?
   - High `noise_rate` from benchmark evidence
   - Retrieval producing chunks outside `path_set`

### Gap Severity Classification

| Severity | Criteria | Governance Action |
|---|---|---|
| **Low** | `grounded_ratio` > 0.7 AND no truncation | Record; no action needed |
| **Medium** | `grounded_ratio` 0.5–0.7 OR truncation occurred | Record; monitor in next checkpoint |
| **High** | `grounded_ratio` < 0.5 OR `unknown_ratio` > 0.15 | Record; investigate before promotion |
| **Critical** | Task completely unsupported by retrieval | Escalate; block promotion until resolved |

---

## Gap Report (JSON Output)

```json
{
  "schema_version": "retrieval_task_gap_report_v1",
  "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
  "git_sha": "abcdefg",
  "phase": "phaseN",
  "checkpoint_id": "artifacts/checkpoints/phaseN/YYYY-MM-DD/checkpoint_manifest.json",
  "prior_checkpoint_id": "artifacts/checkpoints/phaseN/YYYY-MM-DD/../PRIOR_DATE/checkpoint_manifest.json",
  "gap_summary": {
    "total_retrieved_nodes": 0,
    "direct_matches": 0,
    "indirect_matches": 0,
    "gaps_identified": 0,
    "overall_severity": "low|medium|high|critical"
  },
  "severity_breakdown": {
    "low": 0,
    "medium": 0,
    "high": 0,
    "critical": 0
  },
  "gaps": [
    {
      "gap_id": "GAP-001",
      "description": "...",
      "severity": "medium",
      "affected_chunks": ["chunk_id_1"],
      "root_cause": "budget_truncation|inferred_only|unknown_evidence|noise",
      "remediation_suggestion": "..."
    }
  ],
  "retrieval_signals": {
    "grounded_ratio": 0.0,
    "unknown_ratio": 0.0,
    "noise_rate": 0.0,
    "truncation_applied": false,
    "node_limit_applied": false
  },
  "warnings": [],
  "gate_mode": "report_only"
}
```

---

## Gap Report (MD Summary)

### Executive Summary
> 1-3 sentences summarizing the most significant gap and its severity.

### Top Findings

1. **[SEVERITY] Gap title**
   - Description: ...
   - Affected artifacts: ...
   - Remediation: ...

### Retrieval Signal Summary

| Signal | Value | Threshold | Status |
|---|---|---|---|
| `grounded_ratio` | TBD | > 0.7 | ⚠️ |
| `unknown_ratio` | TBD | < 0.1 | ✅ |
| `noise_rate` | TBD | < 0.15 | ✅ |
| Truncation applied | false | false | ✅ |

### Recommendations

- **Stay in Phase**: if critical gaps found and unresolved
- **Promote to next Phase**: if all gaps are medium or below and grounded_ratio > 0.6

---

## Promotion Decision

### Decision Criteria

- **promote**: no critical gaps AND grounded_ratio > 0.6 AND truncation is documented
- **stay_experimental**: critical gaps present OR grounded_ratio < 0.6
- **reject**: architectural conflict OR persistent retrieval failure across checkpoints

### Summary

**Overall Decision**: promote / stay_experimental / reject

**Rationale**:
> (1-3 sentence rationale referencing specific gap signals and severity)

---

## Rollback Plan

### Trigger Conditions

| Gap ID | Trigger Condition | Rollback Action |
|---|---|---|
| GAP-001 | severity remains `critical` in next checkpoint | Revert retrieval config to prior checkpoint baseline |

### Rollback Procedure

1. Identify prior checkpoint: `artifacts/checkpoints/phaseN/PRIOR-DATE/`
2. Compare retrieval config against prior checkpoint
3. Restore prior retrieval configuration
4. Re-run retrieval pipeline
5. Verify `grounded_ratio` returns to baseline
6. Record rollback event in `artifacts/checkpoints/phaseN/YYYY-MM-DD/rollback_log.json`

---

## Artifact Provenance

| Field | Value |
|---|---|
| ContextReport | `artifacts/context-reports/YYYY-MM-DD/context_report.md` |
| Retrieval Graph View | `artifacts/retrieval-graphs/YYYY-MM-DD/retrieval_graph_view.json` |
| Checkpoint Manifest | `artifacts/checkpoints/phaseN/YYYY-MM-DD/checkpoint_manifest.json` |
| Problem Ledger | `artifacts/checkpoints/phaseN/YYYY-MM-DD/problem_ledger.json` |

---

## References

- ContextReport contract: `docs/maintainers/CONTEXT_REPORT_CONTRACT.md`
- Retrieval graph view contract: `docs/maintainers/RETRIEVAL_GRAPH_VIEW_CONTRACT.md`
- PQ-003 evidence overlay: `docs/maintainers/PQ003_EVIDENCE_OVERLAY_CONTRACT.md`
- Governance: `docs/maintainers/ADAPTIVE_PROMOTION_GOVERNANCE_2026-03-09.md`
