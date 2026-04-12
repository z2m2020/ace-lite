# Phase 2 QuickFirst Review Template

**Date**: YYYY-MM-DD
**Phase**: Phase 2 (quick→full governance)
**Checkpoint ID**: `artifacts/checkpoints/phase2/YYYY-MM-DD/checkpoint_manifest.json`
**Prior Checkpoint**: `artifacts/checkpoints/phase1/YYYY-MM-DD/checkpoint_manifest.json`
**Related Tasks**: ALH1-0201, ALH1-0202, ALH1-0203, ALH1-0204, ALH1-0205

---

## Overview

Phase 2 establishes report-only governance for the `quick→full plan` upgrade decision.
This template aggregates the key signals from Phase 2 artifacts and produces a
human-readable review overlay for maintainers.

**Important**: All Phase 2 artifacts are **report-only**. `upgrade_recommended`
must NOT be used as a release gate during Phase 2.

---

## Inputs

### Current Phase 2 Artifacts

| Artifact | Path | Schema Version | Status |
|---|---|---|---|
| paired_eval_cases | `benchmark/cases/paired_eval_cases.yaml` | N/A (YAML case set) | ✅ Created |
| quick_to_plan_utility_summary | `artifacts/observability/quick_to_plan/latest/quick_to_plan_utility_summary.json` | `quick_to_plan_utility_summary_v1` | ✅ Created |
| plan_quick_outcome_summary | `artifacts/plan-quick-outcomes/latest/plan_quick_outcome_summary.json` | `plan_quick_outcome_summary_v1` | ✅ Created |
| smoke_summary | `artifacts/smoke/latest/smoke_summary.json` | `smoke_summary_v1` | ✅ Created |
| version_drift_report | `artifacts/doctor/latest/version_drift_report.json` | `version_drift_report_v1` | ✅ Created |
| checkpoint_manifest | `artifacts/checkpoints/phase2/YYYY-MM-DD/checkpoint_manifest.json` | `checkpoint_manifest_v1` | Pending |

---

## Metrics Summary

### Quick→Full Upgrade Signal

| Signal | Source Artifact | Key Field | Current Value | Interpretation |
|---|---|---|---|---|
| `quick_to_plan_incremental_utility_ratio` | `quick_to_plan_utility_summary.json` | `ratio` | TBD | >1.0 = full plan wins |
| `upgrade_recommended` rate | `plan_quick_outcome_summary.json` | `aggregate.upgrade_recommended_count / run_count` | TBD | Higher = more consistent upgrade signal |
| Paired eval pass rate | `benchmark/cases/paired_eval_cases.yaml` results | `task_success_hit` delta | TBD | ≥80% = consistent upgrade case |

### Operational Health

| Signal | Source Artifact | Key Field | Current Value | Interpretation |
|---|---|---|---|---|
| Smoke pass rate | `smoke_summary.json` | `healthy` | TBD | true = smoke is green |
| Install drift detected | `version_drift_report.json` | `has_install_drift` | TBD | false = no drift |
| Stale process detected | `version_drift_report.json` | `has_stale_process` | TBD | false = no staleness |

---

## Review Checklist

Before promoting any Phase 2 signal to **enforced**, all of the following
must be confirmed:

- [ ] **Paired eval baseline exists** — `benchmark/cases/paired_eval_cases.yaml` has been executed at least once and results are archived.
- [ ] **Prior baseline for upgrade signal** — `quick_to_plan_incremental_utility_ratio` has a dated baseline in `artifacts/observability/quick_to_plan/archive/`.
- [ ] **Smoke is green on main** — `artifacts/smoke/latest/smoke_summary.json` shows `healthy = true` for the candidate commit.
- [ ] **No install drift on candidate** — `version_drift_report.json` shows `has_install_drift = false`.
- [ ] **Outcome summary artifact exists** — `plan_quick_outcome_summary.json` is present and `run_count > 0`.
- [ ] **Checkpoint manifest is complete** — all Phase 2 artifacts are listed in `checkpoint_manifest.json`.

---

## Promotion Decision

### Gate Registry Summary (Phase 2 gates)

| Gate ID | Gate Mode | Prior Baseline | Current Value | Decision |
|---|---|---|---|---|
| `quick_upgrade_signal` | `report_only` | N/A (Phase 2) | TBD | stay_experimental |
| `smoke_health` | `report_only` | N/A (Phase 2) | TBD | stay_experimental |
| `drift_recovery` | `report_only` | N/A (Phase 2) | TBD | stay_experimental |

### Decision Criteria

- **stay_experimental**: Phase 2 signals remain `report_only` until:
  - At least one paired eval baseline exists
  - `quick_to_plan_incremental_utility_ratio` shows ≥80% cases with ratio > 1.0
  - Smoke is consistently green across 5+ consecutive runs
- **promote**: may only be considered after Phase 3 evidence is available

---

## Relationship to Other Phases

| Phase | Focus | Key Question |
|---|---|---|
| Phase 1 | Evidence surfaces | Are contracts stable? |
| **Phase 2** | **quick→full governance** | **Can we measure upgrade value?** |
| Phase 3 | Feedback/memory loops | Is the loop closing? |
| Phase 4 | Promotion + multi-repo | Is promotion safe? |
| Phase 5 | Closeout | Is PRD-88 complete? |

---

## Artifact Provenance

Each Phase 2 artifact must include these provenance fields:

```json
{
  "schema_version": "<schema_v1>",
  "generated_at": "<ISO-8601 UTC>",
  "git_sha": "<git commit SHA>",
  "phase": "phase2",
  "command": "<CLI command used to produce>",
  "inputs": {
    "<input_name>": "<input_path or description>"
  }
}
```

If any artifact is missing `git_sha` or `schema_version`, do not include it
in the checkpoint manifest — flag it as a gap in the review.
