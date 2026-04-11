# PQ-003 Evidence Overlay Contract

**Schema Version**: `pq_003_evidence_overlay_v1`
**Phase**: Phase 1 (report-only)
**Date**: YYYY-MM-DD
**Checkpoint ID**: `artifacts/checkpoints/phase1/YYYY-MM-DD/checkpoint_manifest.json`

---

## Overview

PQ-003 ("evidence strength interpretability") tracks whether the ACE-Lite retrieval evidence is explainable and grounded. The evidence overlay contract defines how evidence confidence breakdowns from `source_plan/evidence_confidence.py` are summarized and surfaced alongside retrieval artifacts.

**Important**: This contract is **report-only** during Phase 1. It must NOT be used as a release blocker or enforced gate.

---

## Input Schema (source_plan/evidence_confidence.py)

The overlay is derived from the `confidence_summary` dict produced by `build_confidence_summary()`:

```python
confidence_summary: {
    "total_candidates": int,
    "extracted_count": int,
    "inferred_count": int,
    "ambiguous_count": int,
    "unknown_count": int,
    "extracted_ratio": float,   # extracted_count / total_candidates
    "inferred_ratio": float,    # inferred_count / total_candidates
    "ambiguous_ratio": float,   # ambiguous_count / total_candidates
    "unknown_ratio": float,     # unknown_count / total_candidates
    "avg_confidence_score": float,
    "low_confidence_chunks": list[str],   # chunk IDs with AMBIGUOUS or UNKNOWN
}
```

### Evidence Confidence Taxonomy (PRD R8503)

| Level | Score | Meaning |
|---|---|---|
| `EXTRACTED` | 1.0 | Direct symbol hit, exact rg hit, SCIP reference, test path evidence |
| `INFERRED` | 0.6–0.9 | cochange, graph_lookup, semantic rerank, skills route, memory hint |
| `AMBIGUOUS` | 0.1–0.5 | hint-only, stale memory, fallback ranker, budget truncation |
| `UNKNOWN` | 0.0 | Cannot identify evidence source |

---

## Output: PQ-003 Evidence Overlay

The overlay is a JSON block appended to (or co-located with) `benchmark/summary.json` and `freeze_regression.json` artifacts. It does **not** modify existing `schema_version` fields — it is additive only.

```json
{
  "schema_version": "pq_003_evidence_overlay_v1",
  "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
  "git_sha": "abcdefg",
  "phase": "phase1",
  "source": "source_plan/evidence_confidence.py",
  "pq_id": "PQ-003",
  "pq_title": "evidence_strength_interpretability",
  "confidence_breakdown": {
    "total_candidates": 120,
    "extracted_count": 45,
    "inferred_count": 38,
    "ambiguous_count": 28,
    "unknown_count": 9,
    "extracted_ratio": 0.375,
    "inferred_ratio": 0.317,
    "ambiguous_ratio": 0.233,
    "unknown_ratio": 0.075
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
  "low_confidence_chunks": [],
  "warnings": [],
  "gate_mode": "report_only"
}
```

---

## Field Definitions

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | string | Yes | Fixed: `pq_003_evidence_overlay_v1` |
| `generated_at` | string (ISO 8601) | Yes | UTC timestamp of generation |
| `git_sha` | string | Yes | Git SHA of the repo at generation time |
| `phase` | string | Yes | Phase identifier, e.g. `phase1` |
| `source` | string | Yes | Module that produced the overlay |
| `pq_id` | string | Yes | Fixed: `PQ-003` |
| `pq_title` | string | Yes | Fixed: `evidence_strength_interpretability` |
| `confidence_breakdown` | object | Yes | Raw counts and ratios from `build_confidence_summary` |
| `derived_metrics` | object | Yes | Computed PQ-003 metric values (see below) |
| `ratios` | object | Yes | Key ratios for governance review |
| `low_confidence_chunks` | array | Yes | List of chunk IDs with low confidence (may be empty) |
| `warnings` | array | Yes | Warnings about missing data or partial failures (may be empty) |
| `gate_mode` | string | Yes | Fixed: `report_only` |

### Derived Metrics

| Metric | Formula | Expected Direction |
|---|---|---|
| `evidence_strength_score` | `extracted_ratio * 1.0 + inferred_ratio * 0.75 + ambiguous_ratio * 0.25 + unknown_ratio * 0.0` | Higher is better |
| `deep_symbol_case_recall` | `extracted_count / total_symbol_cases` (from benchmark evidence) | Higher is better |
| `native_scip_loaded_rate` | `native_scip_loaded / total_chunks` | Higher is better |

### Key Ratios

| Ratio | Formula | Governance Note |
|---|---|---|
| `hint_only_ratio` | `ambiguous_count / total_candidates` | High values (>0.3) indicate retrieval is relying on weak signals |
| `ambiguous_ratio` | `ambiguous_count / total_candidates` | Same as `hint_only_ratio` (alias for clarity) |
| `unknown_ratio` | `unknown_count / total_candidates` | Values >0.1 indicate significant evidence gaps |
| `grounded_ratio` | `(extracted_count + inferred_count) / total_candidates` | Higher = more evidence-backed retrieval |

---

## Gate Mode

**Phase 1 = `report_only`**

During Phase 1:
- Overlay MUST be produced whenever `confidence_summary` data is available
- Missing overlay is NOT a failure
- Overlay MUST NOT affect benchmark scores or rankings
- Overlay MUST NOT be used as a release blocker

Transition to `enforced` requires:
1. At least one Phase boundary with stable `evidence_strength_score` baseline
2. Rollback trigger defined (e.g., `evidence_strength_score drops below 0.6`)
3. Governance approval documented in the phase review artifact

---

## Consumer Artifacts

| Artifact | Consumer | Purpose |
|---|---|---|
| `benchmark/summary.json` (with overlay) | `scripts/build_problem_ledger.py` | PQ-003 ledger entry |
| `freeze_regression.json` (with overlay) | `scripts/build_freeze_trend_report.py` | Freeze trend PQ-003 trace |
| `problem_surface.json` | `ALH1-0003.T2` extractors | Unified PQ surface |

---

## References

- Evidence confidence taxonomy: `src/ace_lite/source_plan/evidence_confidence.py`
- PQ definition: `docs/maintainers/PRODUCTION_QUANT_REVIEW_TEMPLATE.md` (PQ-003 row)
- Governance: `docs/maintainers/ADAPTIVE_PROMOTION_GOVERNANCE_2026-03-09.md`
