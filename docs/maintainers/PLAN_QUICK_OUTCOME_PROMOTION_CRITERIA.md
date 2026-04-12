# Plan_Quick Outcome Promotion Criteria

**Schema Version**: `plan_quick_outcome_summary_v1`
**Phase**: Phase 2 (report-only)
**Date**: 2026-04-12
**Checkpoint ID**: `artifacts/checkpoints/phase2/YYYY-MM-DD/checkpoint_manifest.json`
**Related Tasks**: ALH1-0201.T1, ALH1-0202.T1, ALH1-0202.T2
**Script**: `scripts/plan_quick_outcome_summary.py`

---

## Overview

`plan_quick` emits two report-only fields on every run:

- `outcome_label` — one of `plan_quick_success`, `plan_quick_timeout_fallback`, `plan_quick_error`
- `upgrade_outcome_hint` — a dict with `expected_incremental_value`, `expected_cost_ms_band`, and `upgrade_recommended`

`scripts/plan_quick_outcome_summary.py` aggregates these fields across all runs in a given
input directory and writes two artifacts:

- `plan_quick_outcome_summary.json` — machine-readable aggregate
- `plan_quick_outcome_summary.md` — human-readable summary

**Important**: This artifact is **report-only** during Phase 2. `upgrade_recommended`
does NOT block release and must not be treated as a gating signal.

---

## Output Schema (`plan_quick_outcome_summary_v1`)

```json
{
  "schema_version": "plan_quick_outcome_summary_v1",
  "generated_at": "<ISO-8601 UTC>",
  "input_dir": "<path to run artifacts>",
  "run_count": "<int>",
  "outcome_counts": {
    "plan_quick_success": "<int>",
    "plan_quick_timeout_fallback": "<int>",
    "plan_quick_error": "<int>"
  },
  "records": [
    {
      "outcome_label": "<str>",
      "upgrade_recommended": "<bool | null>",
      "expected_incremental_value": "<str | null>",
      "expected_cost_ms_band": "<str | null>",
      "source_file": "<str>"
    }
  ],
  "aggregate": {
    "upgrade_recommended_count": "<int>",
    "upgrade_not_recommended_count": "<int>",
    "unknown_count": "<int>",
    "value_breakdown": {
      "<expected_incremental_value>": "<count>"
    }
  },
  "warnings": ["<str>"]
}
```

### Field semantics

| Field | Values | Meaning |
|---|---|---|
| `outcome_label` | `plan_quick_success` | plan_quick produced a valid source plan within budget |
| `outcome_label` | `plan_quick_timeout_fallback` | plan_quick fell back to a quicker response |
| `outcome_label` | `plan_quick_error` | plan_quick encountered an error |
| `upgrade_recommended` | `true` | paired evidence suggests upgrading to full plan is worth the cost |
| `upgrade_recommended` | `false` | paired evidence suggests staying with plan_quick |
| `upgrade_recommended` | `null` | insufficient evidence to determine |
| `expected_incremental_value` | `high`, `medium`, `low` | perceived delta between plan_quick and full plan quality |
| `expected_cost_ms_band` | `low`, `medium`, `high` | perceived latency cost of upgrading to full plan |

---

## How to Read the Summary

### Step 1 — Check `run_count`

If `run_count == 0`, the input directory was empty or not found. The summary is not
meaningful until you have at least one plan_quick run artifact.

### Step 2 — Inspect `outcome_counts`

A healthy plan_quick population should show predominantly `plan_quick_success`.
A high count of `plan_quick_timeout_fallback` or `plan_quick_error` indicates
instability that needs investigation before any promotion decision.

### Step 3 — Check `aggregate.upgrade_recommended_count`

When most runs have `upgrade_recommended == true`, there is a consistent signal
that plan_quick is leaving meaningful quality on the table versus the full plan.

### Step 4 — Cross-reference `value_breakdown`

If `upgrade_recommended == true` but `expected_incremental_value` is `low`, the
cost-benefit case is weak. Do not promote based on volume alone.

---

## Promotion Checklist

Before `upgrade_recommended` can be used as a **release gate** (not a report), all
of the following must be true:

- [ ] **At least one prior baseline exists** — `artifacts/benchmark/baseline.json`
  or equivalent baseline metrics have been captured for the same benchmark case set.
- [ ] **Paired eval is active** — `benchmark/cases/paired_eval_cases.yaml` (or a named
  equivalent) has been executed in the same environment with both `quick` and `full`
  arms.
- [ ] **Paired eval shows consistent win** — `quick_to_plan_incremental_utility_ratio`
  is above `1.0` in ≥80% of the paired cases, or a named threshold profile in
  `REGRESSION_THRESHOLD_PROFILES` is satisfied.
- [ ] **No recent regressions** — `ace-lite benchmark diff` shows no regressions on
  `task_success_hit` or `utility_hit` versus the stored baseline.
- [ ] **Outcome summary artifact exists** — `plan_quick_outcome_summary.json` is
  present in the checkpoint manifest for the release candidate.

If any item is unchecked, `upgrade_recommended` remains **report-only**. Do not
add a blocking assertion in CI that reads `upgrade_recommended`.

---

## When to Regenerate the Summary

Regenerate `plan_quick_outcome_summary.json` whenever:

- A new set of plan_quick runs has completed (e.g., after a benchmark suite run).
- The `schema_version` in `scripts/plan_quick_outcome_summary.py` is bumped.
- A new `outcome_label` value is introduced in `src/ace_lite/observability.py`.

---

## Relationship to Other Phase 2 Artifacts

| Artifact | Role |
|---|---|
| `benchmark/cases/paired_eval_cases.yaml` | Paired quick-vs-full eval case definitions |
| `scripts/quick_to_plan_utility_summary.py` | Computes `quick_to_plan_incremental_utility_ratio` |
| `scripts/plan_quick_outcome_summary.py` | Aggregates `outcome_label` across all runs |
| `RELEASING.md` | Checkpoint manifest entry point for Phase 2 |
| `PHASE2_QUICKFIRST_REVIEW_TEMPLATE.md` | Human-readable review overlay for Phase 2 |

---

## Report-Only Waiver

During Phase 2, the following constraints are **explicitly waived** for this artifact:

- `upgrade_recommended` must NOT appear in any CI gate that would fail a release.
- Any dashboard or Slack notification built on this artifact must label it
  " advisory — not a release gate."
- The `unknown_count` in `aggregate` represents runs where `upgrade_recommended`
  could not be determined; these must not be treated as failures.
