# Releasing (ACE-Lite Engine)

This doc is the reusable release validation and upgrade template for ACE-Lite.

Canonical adaptive-feature promotion states live in
`docs/maintainers/ADAPTIVE_PROMOTION_GOVERNANCE_2026-03-09.md`.
Use this release doc to validate evidence; use the governance doc to decide
whether a feature may stay default-on, remain experimental, or be rejected.

Use it when:

- cutting a tagged release
- validating a release candidate
- checking whether a dependency or retrieval-policy upgrade is safe to ship
- preparing a dated maintainers checkpoint that needs reproducible evidence paths

## 1. Pre-flight

Run the fast local checks first. Do not start release evidence collection on a broken tree.

```powershell
python -m pytest -q
./scripts/run_smoke.ps1
python scripts/validate_docs_cli_snippets.py
```

If the release touches quality or packaging behavior, also run:

```powershell
python scripts/run_quality_gate.py --root . --output-dir artifacts/quality/latest --pip-audit-baseline benchmark/quality/pip_audit_baseline.json --fail-on-new-vulns --friction-log artifacts/friction/events.jsonl
```

## 2. Versioning And Release Notes

- bump `pyproject.toml` `version`
- rerun `./scripts/update.ps1` and require the install-sync check to stay green before collecting release evidence
- move `CHANGELOG.md` `[Unreleased]` entries into a dated version section
- record which benchmark and freeze artifact directories will be treated as the release evidence set

Recommended artifact convention:

- benchmark matrix: `artifacts/benchmark/matrix/<window>/<YYYY-MM-DD>`
- latency/SLO trend: `artifacts/benchmark/matrix/<window>/<YYYY-MM-DD>-latency-slo-trend`
- freeze regression: `artifacts/release-freeze/<YYYY-MM-DD>-rc`
- freeze stability: `artifacts/release-freeze/stability/<YYYY-MM-DD>-rc-stability`

## 3. Required Release Evidence

### 3.1 Benchmark matrix

```bash
python scripts/run_benchmark_matrix.py --matrix-config benchmark/matrix/repos.yaml --output-dir artifacts/benchmark/matrix/latest --fail-on-thresholds
```

Required files to inspect:

- `artifacts/benchmark/matrix/latest/matrix_summary.json`
- `artifacts/benchmark/matrix/latest/matrix_summary.md`
- `artifacts/benchmark/matrix/latest/latency_slo_summary.json`
- `artifacts/benchmark/matrix/latest/latency_slo_summary.md`

Minimum checks:

- `passed = true`
- no unexpected `benchmark_regression_detected`
- `retrieval_policy_summary` does not show a new regression cluster for the candidate policy mix
- `latency_slo_summary` still matches the expected workload buckets and does not hide downgrade spikes

### 3.2 Latency and SLO trend report

Build this whenever the release changes retrieval policy, embedding behavior, repomap behavior, or time-budget logic.

```bash
python scripts/build_latency_slo_trend_report.py --history-root artifacts/benchmark/matrix/h2_2026 --latest-report artifacts/benchmark/matrix/latest/latency_slo_summary.json --output-dir artifacts/benchmark/matrix/latest-latency-slo-trend
```

Required checks:

- the report orders baselines by `generated_at`, not filesystem time
- if the previous dated artifact lacks stage/SLO coverage, treat the delta as report-only context
- if the latest artifact is a targeted probe rather than a whole-matrix rerun, keep the delta report-only and pair it with the last whole-matrix dated baseline in release notes
- do not promote the trend to a blocking claim until there is a prior full-fidelity baseline

### 3.2.1 Router default-switch review

Use this subsection only when the candidate release touches adaptive-router
behavior or proposes a router default switch.

Required router evidence to inspect from the same dated benchmark directory:

- `summary.json` for `adaptive_router_arm_summary`,
  `adaptive_router_observability_summary`, and
  `adaptive_router_pair_summary`
- `report.md` for the human-readable agreement, per-arm quality, latency,
  fallback, and downgrade rollups
- `results.json` if a disagreement cluster or downgrade target needs case-level
  inspection

Required checks:

- the candidate switch is non-regressed versus current `auto` and still shows
  positive headroom versus fixed `general`
- no high-volume executed-versus-shadow pair shows new latency, fallback, or
  downgrade regressions
- the paired `latency_slo_summary` artifact does not show a new router-linked
  latency or `slo_downgrade_case_rate` spike
- one release candidate is not enough on its own; router default switches still
  require the repeated dated evidence defined in
  `docs/maintainers/ADAPTIVE_PROMOTION_GOVERNANCE_2026-03-09.md`

### 3.2.2 Chunk-guard enforce review

Use this subsection only when the candidate release touches `chunk_guard`,
SHARS-lite filtering, or chunk-pack selection behavior that could broaden
enforce-mode usage.

Required benchmark evidence to inspect:

```bash
python scripts/run_feature_slice_matrix.py --config benchmark/matrix/feature_slices.yaml --output-dir artifacts/benchmark/slices/feature_slices/latest
```

Required files to inspect from the same dated artifact set:

- `artifacts/benchmark/slices/feature_slices/latest/feature_slices_summary.json`
- `artifacts/benchmark/slices/feature_slices/latest/feature_slices_summary.md`

Required checks:

- `stale_majority` and lexical `perturbation` both stay green with the same
  `chunk_guard.mode=enforce` config shown in the artifact
- report-only stale-majority evidence is already green and is treated as the
  precondition, not replaced by the enforce run
- stale-majority `latency_growth_factor` remains inside the configured slice
  threshold and no new task-success, precision, or noise regression appears
- benchmark evidence is cross-checked with the deterministic chunk-order and
  `index -> source_plan` integration regressions before any broader rollout is
  discussed

### 3.3 Release-freeze regression

Run this for release candidates, protected-branch release prep, and upgrades that touch ranking behavior, memory policy, provider config, or benchmark thresholds.

```bash
python scripts/run_release_freeze_regression.py --matrix-config benchmark/matrix/repos.yaml --output-dir artifacts/release-freeze/latest --fail-on-thresholds --skip-skill-validation
```

Required files to inspect:

- `artifacts/release-freeze/latest/freeze_regression.json`
- `artifacts/release-freeze/latest/freeze_regression.md`

Required gates to review:

- `tabiv3_gate`
- `concept_gate`
- `external_concept_gate`
- `feature_slices_gate`
- `retrieval_policy_guard`
- `e2e_success_gate`
- `memory_gate`
- `embedding_gate`

For `retrieval_policy_guard`, review the mode before interpreting failures:

- `disabled`: ignore the guard for release pass/fail decisions
- `report_only`: record failures in the artifact, but do not let them flip the overall freeze result
- `enforced`: failures block the freeze result

When a release candidate changes an adaptive feature, verify that the affected
path still matches its status in
`docs/maintainers/ADAPTIVE_PROMOTION_GOVERNANCE_2026-03-09.md`. Do not treat a
green report-only lane as permission to silently promote a default-path switch.
This is especially strict for adaptive-router work: a green
`retrieval_policy_guard` or `feature_slices_gate` in `report_only` mode is
evidence to review, not approval to switch the router default.

### 3.4 Repeated-run freeze stability

Run this when the release changes release-freeze behavior, guard thresholds, or robustness-sensitive retrieval paths.

```bash
python scripts/run_freeze_stability.py --runs 2 --output-dir artifacts/release-freeze/stability/latest --skip-skill-validation --max-failure-rate 1.0 --tracked-feature-slices perf_routing,dependency_recall,perturbation,repomap_perturbation --min-feature-slice-pass-rate 1.0
```

Required checks:

- tracked robustness slices stay `stable_pass`
- treat whole-freeze failures as release-readiness issues, not as evidence that the robustness lane is invalid

## 4. Upgrade Validation

Use this section for dependency, provider, policy, or schema upgrades.

### Safe upgrade checklist

1. Rerun the benchmark matrix and freeze regression on the upgraded tree.
2. Compare the new `matrix_summary.json` and `freeze_regression.json` to the last known-good dated artifacts.
3. If the upgrade touches latency-critical code, regenerate `latency_slo_summary.json` and the trend report.
4. If the upgrade touches embeddings, rerank providers, or memory replay, confirm the corresponding opt-in gates remain green and still look fail-open.
5. If the upgrade changes output shape, validate downstream docs and changelog examples in the same patch.

### Required release note callouts for upgrades

- what changed
- what validation was rerun
- which dated artifacts are the source of truth
- any known downgrade or report-only caveats that remain

## 5. Artifact Review Template

Use the following headings in a release checkpoint or PR comment:

```md
## Release Validation Summary

- Candidate version:
- Evidence date:
- Benchmark matrix:
- Latency/SLO trend:
- Router observability summary:
- Freeze regression:
- Freeze stability:
- Workspace benchmark (if used):

## Required Checks

- Benchmark thresholds:
- Retrieval policy guard:
- Router disagreement / fallback review:
- Latency/SLO drift:
- Robustness slice stability:
- Upgrade-specific validation:

## Known Limits

- ...
```

## 6. Known Limits

- The latency/SLO trend lane is still report-only overall even though the newest comparison pair is now full-fidelity.
- A targeted dependency-heavy probe such as `artifacts/benchmark/matrix/h2_2026/2026-03-11-grpc-java/` can refresh maintainability evidence, but it does not replace the latest whole-matrix release baseline on its own.
- The tracked robustness slices can be stable while the overall freeze remains red; treat those as different signals.
- `perf_routing` is now part of the release-facing feature-slice evidence. Treat it as the required benchmark proof before proposing any perf-route promotion beyond the current offline proxy.
- Release-freeze evidence is intentionally heavier than PR validation. Do not treat every release-only check as a fast inner-loop requirement.
- The canonical `freeze.policy_guard` config is currently `report_only` while threshold taxonomy and longer-baseline evidence are being validated.
- Optional providers and memory experiments remain opt-in. A green release should not depend on them being default-on.

## 7. Reusable Sources

Primary docs and workflows to cross-check:

- `docs/maintainers/BENCHMARKING.md`
- `docs/maintainers/QUALITY_GOVERNANCE.md`
- `.github/workflows/ci.yml`
- `.github/workflows/release-freeze-regression.yml`
- `.github/workflows/freeze-stability-nightly.yml`
