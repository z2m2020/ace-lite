# PQ-003 Evidence Overlay Dated Review Template

**PQ ID**: PQ-003
**PQ Title**: evidence_strength_interpretability
**Phase**: Phase 1
**Date**: YYYY-MM-DD
**Checkpoint ID**: `artifacts/checkpoints/phase1/YYYY-MM-DD/checkpoint_manifest.json`
**Prior Checkpoint**: `artifacts/checkpoints/phase1/PRIOR-DATE/checkpoint_manifest.json`

---

## Purpose

This template structures the review of PQ-003 ("evidence strength interpretability") across a Phase 1 checkpoint. It produces a dated overlay report used in phase governance and as input to the Phase 1 promotion decision.

PQ-003 tracks whether ACE-Lite retrieval evidence is explainable and grounded, via the evidence confidence taxonomy (EXTRACTED / INFERRED / AMBIGUOUS / UNKNOWN).

---

## Inputs

### Current Checkpoint Artifacts

| Artifact | Path | Schema |
|---|---|---|
| Benchmark Summary (with PQ-003 overlay) | `artifacts/benchmark/latest/summary.json` | (informal + `pq_003_evidence_overlay_v1`) |
| Freeze Regression (with PQ-003 overlay) | `artifacts/freeze/latest/freeze_regression.json` | (informal + `pq_003_evidence_overlay_v1`) |
| Problem Surface | `artifacts/checkpoints/phase1/YYYY-MM-DD/problem_surface.json` | `problem_surface_v1` |
| ContextReport | `artifacts/context-reports/YYYY-MM-DD/context_report.md` | `context_report_v1` |
| Checkpoint Manifest | `artifacts/checkpoints/phase1/YYYY-MM-DD/checkpoint_manifest.json` | `checkpoint_manifest_v1` |

### Prior Checkpoint for Diff

| Artifact | Prior Path |
|---|---|
| Benchmark Summary | `artifacts/benchmark/archive/PRIOR-DATE/summary.json` |
| Freeze Regression | `artifacts/freeze/archive/PRIOR-DATE/freeze_regression.json` |

---

## PQ-003 Overlay Structure

```json
{
  "schema_version": "pq_003_evidence_overlay_v1",
  "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
  "git_sha": "abcdefg",
  "phase": "phase1",
  "pq_id": "PQ-003",
  "pq_title": "evidence_strength_interpretability",
  "confidence_breakdown": {
    "total_candidates": 120,
    "extracted_count": 45,
    "inferred_count": 38,
    "ambiguous_count": 28,
    "unknown_count": 9
  },
  "derived_metrics": {
    "evidence_strength_score": 0.71,
    "deep_symbol_case_recall": 0.83,
    "native_scip_loaded_rate": 0.67
  },
  "ratios": {
    "hint_only_ratio": 0.233,
    "ambiguous_ratio": 0.233,
    "unknown_ratio": 0.075,
    "grounded_ratio": 0.692
  },
  "gate_mode": "report_only"
}
```

---

## Derived Metric Definitions

| Metric | Formula | Expected Direction |
|---|---|---|
| `evidence_strength_score` | `extracted_ratio * 1.0 + inferred_ratio * 0.75 + ambiguous_ratio * 0.25 + unknown_ratio * 0.0` | Higher is better |
| `deep_symbol_case_recall` | `extracted_count / total_symbol_cases` | Higher is better |
| `native_scip_loaded_rate` | `native_scip_loaded / total_chunks` | Higher is better |

---

## Ratio Thresholds (Phase 1 — report-only)

| Ratio | Threshold | Status During Phase 1 |
|---|---|---|
| `grounded_ratio` | > 0.7 = low concern | Monitor only |
| `unknown_ratio` | < 0.1 = acceptable | Monitor only |
| `ambiguous_ratio` | > 0.3 = investigate | Monitor only |
| `hint_only_ratio` | > 0.3 = investigate | Monitor only |

**Note**: All thresholds are advisory during Phase 1. PQ-003 is `report_only` and must NOT be used as a release blocker until Phase 2 at the earliest.

---

## Diff Recipe

```bash
# Compare PQ-003 overlay across checkpoints
python -c "
import json
prev = json.load(open('prior/summary.json'))
curr = json.load(open('curr/summary.json'))
prev_overlay = prev.get('pq_003_overlay', {})
curr_overlay = curr.get('pq_003_overlay', {})
if prev_overlay and curr_overlay:
    print('grounded_ratio diff:', curr_overlay.get('ratios', {}).get('grounded_ratio'), 'vs', prev_overlay.get('ratios', {}).get('grounded_ratio'))
    print('evidence_strength_score diff:', curr_overlay.get('derived_metrics', {}).get('evidence_strength_score'), 'vs', prev_overlay.get('derived_metrics', {}).get('evidence_strength_score'))
else:
    print('PQ-003 overlay missing in one or both summaries')
"
```

---

## Promotion Decision

### Decision Criteria

- **promote**: Phase 1 complete, PQ-003 overlay is stable, governance docs in place
- **stay_experimental**: PQ-003 overlay is missing or unstable
- **reject**: architectural conflict in evidence taxonomy

### Summary

**Overall Phase 1 Decision**: promote / stay_experimental / reject

**Rationale**:
> (1-3 sentence rationale referencing specific PQ-003 metric values and overlay availability)

---

## Rollback Plan

### Trigger Conditions

| Condition | Rollback Action |
|---|---|
| `grounded_ratio` drops > 20% from prior baseline | Revert retrieval configuration to prior checkpoint |
| PQ-003 overlay disappears from benchmark output | Investigate evidence confidence pipeline |

### Rollback Procedure

1. Identify prior checkpoint: `artifacts/checkpoints/phase1/PRIOR-DATE/`
2. Compare PQ-003 ratios against prior baseline
3. Restore prior retrieval configuration
4. Re-run benchmark
5. Verify PQ-003 overlay reappears with stable ratios
6. Record rollback event in `artifacts/checkpoints/phase1/YYYY-MM-DD/rollback_log.json`

---

## References

- PQ-003 contract: `docs/maintainers/PQ003_EVIDENCE_OVERLAY_CONTRACT.md`
- Evidence confidence taxonomy: `src/ace_lite/source_plan/evidence_confidence.py`
- Benchmark summary overlay: `src/ace_lite/benchmark/report.py`
- Freeze trend overlay: `scripts/build_freeze_trend_report.py`
- Governance: `docs/maintainers/ADAPTIVE_PROMOTION_GOVERNANCE_2026-03-09.md`
