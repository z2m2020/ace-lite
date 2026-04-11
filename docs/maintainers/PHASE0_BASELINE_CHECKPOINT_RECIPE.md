# Phase 0 Baseline Checkpoint Recipe

This document describes how to create a Phase 0 baseline checkpoint — a dated, archived snapshot of the problem ledger and governance artifacts used to establish the initial PRD-88 measurement baseline.

## When to Run

Run this recipe:
- **Once**, at the start of Phase 0, to establish the `phase0` baseline.
- After any structural change to `problem_ledger_v1`, `run_manifest_v1`, or `checkpoint_manifest_v1` schemas that requires a fresh baseline.
- Before promoting any gate from `report_only` to `enforced` (Phase 1+), to ensure a stable baseline exists.

## Prerequisites

Ensure the following are available:

- `python` (3.11+) with `ace-lite` installed (`pip install -e .[dev]`)
- `git` with a clean working tree (recommended but not required)
- Access to `context-map/run_manifest.jsonl` (created by `scripts/write_run_manifest.py`)
- Access to `artifacts/checkpoints/phase0/*/` artifacts from prior waves

## Artifact Layout

Checkpoints are stored under:

```
artifacts/checkpoints/
└── phase0/
    └── YYYY-MM-DD/
        ├── checkpoint_manifest.json   ← created by this recipe
        ├── problem_ledger.json        ← produced by build_problem_ledger.py
        └── run_manifest.jsonl         ← produced by write_run_manifest.py
```

## Step-by-Step Recipe

### Step 1 — Build the Problem Ledger

```powershell
# From repo root
python scripts/build_problem_ledger.py `
    --benchmark-artifacts-root "artifacts/benchmark/latest" `
    --freeze-artifacts-root "artifacts/freeze/latest" `
    --output "artifacts/checkpoints/phase0/YYYY-MM-DD/problem_ledger.json"
```

> If benchmark/freeze artifacts do not yet exist, run without those arguments to emit a report-only ledger:
> ```powershell
> python scripts/build_problem_ledger.py `
>     --output "artifacts/checkpoints/phase0/YYYY-MM-DD/problem_ledger.json"
> ```

### Step 2 — Write Run Manifest Entries

For each Wave N task that has completed, append an entry:

```powershell
python scripts/write_run_manifest.py `
    --manifest-path "artifacts/checkpoints/phase0/YYYY-MM-DD/run_manifest.jsonl" `
    --unit-id "ALH1-0001.T1" `
    --phase "phase0" `
    --priority "high" `
    --owner-role "governance" `
    --status "done" `
    --goal "Add problem_ledger_v1 schema." `
    --deliverable "src/ace_lite/problem_ledger_schema.py" `
    --input-contracts "problem_ledger_v1 schema" `
    --output-contracts "problem_ledger JSON" `
    --metrics-touched "execution_traceability" `
    --verification-commands "pytest -q tests/unit/test_problem_ledger.py" `
    --artifacts-emitted "context-map/run_manifest.jsonl" `
    --rollback-steps "Remove the appended JSONL row." `
    --done-definition "Entry validates against run_manifest_v1." `
    --failure-signals "status is invalid"
```

Repeat for each completed task unit.

### Step 3 — Create the Dated Checkpoint Manifest

```powershell
python scripts/create_dated_checkpoint.py `
    --date "YYYY-MM-DD" `
    --phase "0" `
    --output-root "artifacts/checkpoints" `
    --artifact-ledger "artifacts/checkpoints/phase0/YYYY-MM-DD/problem_ledger.json" `
    --artifact-run-manifest "artifacts/checkpoints/phase0/YYYY-MM-DD/run_manifest.jsonl"
```

This creates `artifacts/checkpoints/phase0/YYYY-MM-DD/checkpoint_manifest.json`.

### Step 4 — Verify the Checkpoint

```bash
# Verify the manifest is valid JSON and has the expected structure
python -c "
import json, sys
with open('artifacts/checkpoints/phase0/YYYY-MM-DD/checkpoint_manifest.json') as f:
    m = json.load(f)
assert m['schema_version'] == 'checkpoint_manifest_v1', 'wrong schema version'
assert m['phase'] == 'phase0', 'wrong phase'
assert 'included_artifacts' in m, 'missing included_artifacts'
assert 'warnings' in m, 'missing warnings'
print('OK: checkpoint_manifest.json is valid')
"

# Verify problem_ledger is valid
python -c "
import json
with open('artifacts/checkpoints/phase0/YYYY-MM-DD/problem_ledger.json') as f:
    p = json.load(f)
assert p['schema_version'] == 'problem_ledger_v1'
assert len(p['problems']) >= 8, 'expected at least 8 problems'
print('OK: problem_ledger.json is valid')
"
```

### Step 5 — Commit the Checkpoint

```bash
git add artifacts/checkpoints/phase0/YYYY-MM-DD/
git commit -m "phase0: add baseline checkpoint YYYY-MM-DD"
```

> Checkpoint artifacts under `artifacts/` are **NOT** excluded from git by default. If the repository has a `.gitignore` that ignores `artifacts/`, either force-add or update `.gitignore` to track checkpoints specifically:
> ```gitignore
> # Track checkpoint baselines
> !artifacts/checkpoints/
> artifacts/checkpoints phase0/**/*
> !artifacts/checkpoints/phase0/
> ```

## Rollback Procedure

If a baseline checkpoint must be invalidated:

1. Identify the prior checkpoint: `artifacts/checkpoints/phase0/PRIOR-DATE/`
2. Restore prior `problem_ledger.json` and `checkpoint_manifest.json`
3. Remove the regressed checkpoint directory
4. Re-run the verification step above

## Relationship to Other Artifacts

| Artifact | Used By | Purpose |
|---|---|---|
| `problem_ledger.json` | Promotion governance (Phase 3+) | PQ baseline for comparison |
| `run_manifest.jsonl` | Audit trail | Trace task completion |
| `checkpoint_manifest.json` | Promotion governance | Git SHA + artifact completeness |
| `wave_scorecard.json` | Phase 4+ | Per-wave throughput metrics |
