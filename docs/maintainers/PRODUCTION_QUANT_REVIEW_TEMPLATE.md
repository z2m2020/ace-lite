# Production Quant Review Template

Date: YYYY-MM-DD
Phase: Phase N (e.g., Phase 0 / Phase 1 / ...)
Checkpoint ID: checkpoint_manifest YYYY-MM-DD (e.g., `artifacts/checkpoints/phase0/2026-04-25/checkpoint_manifest.json`)
Prior Checkpoint: `artifacts/checkpoints/phaseN/YYYY-MM-DD/checkpoint_manifest.json`

---

## Inputs

### Current Checkpoint Artifacts
| Artifact | Path | Schema Version |
|---|---|---|
| problem_ledger | `artifacts/checkpoints/phaseN/YYYY-MM-DD/problem_ledger.json` | problem_ledger_v1 |
| run_manifest | `artifacts/run-manifest/phaseN/run_manifest.jsonl` | run_manifest_v1 |
| gate_registry | `artifacts/gate-registry/latest/gate_registry.json` | gate_registry_v1 |
| checkpoint_manifest | `artifacts/checkpoints/phaseN/YYYY-MM-DD/checkpoint_manifest.json` | checkpoint_manifest_v1 |

### Prior Checkpoint for Diff
| Artifact | Prior Path |
|---|---|
| problem_ledger | `artifacts/checkpoints/phaseN/YYYY-MM-DD/../PRIOR_DATE/problem_ledger.json` |
| gate_registry | `artifacts/gate-registry/archive/YYYY-MM-DD/gate_registry.json` |

### Diff Recipe
```bash
# Compare problem_ledger across checkpoints
python -c "import json; prev=json.load(open('prior/problem_ledger.json')); curr=json.load(open('curr/problem_ledger.json')); print([k for k in curr if curr[k]!=prev.get(k)])"

# Compare gate registry
python -c "import json; prev=json.load(open('prior/gate_registry.json')); curr=json.load(open('curr/gate_registry.json')); print([g for g in curr['gates'] if g not in prev['gates']])"

# Verify checkpoint_manifest git_sha matches reported sha
git -C . show SHA --quiet
```

---

## Artifacts Produced This Phase

| Artifact | Files | Produced By |
|---|---|---|
| problem_ledger.json | `artifacts/checkpoints/phaseN/YYYY-MM-DD/problem_ledger.json` | `scripts/build_problem_ledger.py` |
| run_manifest.jsonl | `artifacts/run-manifest/phaseN/run_manifest.jsonl` | `scripts/write_run_manifest.py` |
| wave_scorecard.json | `artifacts/observability/phaseN/wave_scorecard.json` | `scripts/write_run_manifest.py` |
| checkpoint_manifest.json | `artifacts/checkpoints/phaseN/YYYY-MM-DD/checkpoint_manifest.json` | `scripts/create_dated_checkpoint.py` |

---

## Metrics (PQ-001..PQ-010)

| PQ ID | Metric Name | Current Value | Threshold / Expected Direction | Gate Mode | Status |
|---|---|---|---|---|---|
| PQ-001 | task_success_rate | TBD | higher is better | report_only | — |
| PQ-001 | precision_at_k | TBD | higher is better | report_only | — |
| PQ-001 | noise_rate | TBD | lower is better | report_only | — |
| PQ-002 | quick_to_full_upgrade_rate | TBD | higher is better | report_only | — |
| PQ-003 | evidence_strength_score | TBD | higher is better | report_only | — |
| PQ-004 | validation_coverage | TBD | higher is better | report_only | — |
| PQ-005 | memory_coldstart_usefulness | TBD | higher is better | report_only | — |
| PQ-006 | feedback_capture_rate | TBD | higher is better | report_only | — |
| PQ-007 | doctor_drift_detected | TBD | lower is better | report_only | — |
| PQ-008 | smoke_pass_rate | TBD | higher is better | report_only | — |
| PQ-009 | typed_contracts_coverage | TBD | higher is better | report_only | — |
| PQ-010 | wave_throughput_p50 | TBD | higher is better | report_only | — |

**Interpretation**: "TBD" means no baseline established yet. For report_only gates, a TBD value is acceptable. For enforced gates, a prior baseline must exist before enforcement.

---

## Promotion Decision

### Gate Registry Summary
| Gate ID | Gate Mode | Prior Baseline | Current Value | Decision |
|---|---|---|---|---|
| (list each gate from gate_registry.json) | — | — | — | promote / stay_experimental / reject |

### Decision Criteria
- **promote**: prior baseline exists AND current value meets threshold AND rollback trigger is defined
- **stay_experimental**: prior baseline does not yet exist OR evidence is mixed OR rollback is not defined
- **reject**: architectural conflict OR persistent regression AND no viable rollback

### Summary
**Overall Phase N Decision**: promote / stay_experimental / reject

Rationale:
> (1-3 sentence rationale referencing specific PQ metrics and gate decisions)

---

## Rollback Plan

### Gate Rollback Triggers
| Gate ID | Trigger Condition | Rollback Action |
|---|---|---|
| (list each enforced gate) | — | — |

### Rollback Procedure
1. Identify the regression: check `artifacts/checkpoints/phaseN/YYYY-MM-DD/` for the most recent passing checkpoint
2. Revert gated feature to prior baseline: `git revert SHA` or configuration rollback
3. Re-run acceptance tests: `pytest -q`
4. Verify gate is back to prior state: compare current vs. prior checkpoint_manifest
5. Record rollback event in `artifacts/gate-registry/archive/YYYY-MM-DD/rollback_log.json`

---

## PQ Reference (for this document)

- **PQ-001**: Retrieval quality (task_success_rate, precision_at_k, noise_rate) — benchmark/freeze evidence
- **PQ-002**: quick→full plan upgrade worthiness — plan_quick payload + feedback
- **PQ-003**: Evidence strength interpretability — confidence taxonomy
- **PQ-004**: Validation evidence sufficiency — validation-rich summary
- **PQ-005**: Memory cold-start / vague query usefulness — curated set + paired eval
- **PQ-006**: Feedback capture loop existence — capture_coverage + attach rate
- **PQ-007**: Install/runtime drift controllability — doctor + smoke
- **PQ-008**: Cross-platform CLI/MCP stability — smoke scripts
- **PQ-009**: Structural complexity control — typed contracts coverage
- **PQ-010**: Subagent concurrent throughput improvement — wave scorecard
