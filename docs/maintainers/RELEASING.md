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
python scripts/smoke_summary.py --input artifacts/plan/latest/plan.json --output artifacts/smoke/latest/smoke_summary.json
python scripts/validate_docs_cli_snippets.py
```

If the release touches quality or packaging behavior, also run:

```powershell
python scripts/run_quality_gate.py --root . --output-dir artifacts/quality/latest --pip-audit-baseline benchmark/quality/pip_audit_baseline.json --fail-on-new-vulns --friction-log artifacts/friction/events.jsonl
```

## 2. Versioning And Release Notes

- bump `pyproject.toml` `version`
- rerun `python scripts/update.py` (or `./scripts/update.ps1` on Windows) and require the install-sync check to stay green before collecting release evidence
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
- if the candidate touches repomap ranking or cache/precompute behavior, review
  the benchmark `repomap_seed_summary` contract in `summary.json` / `report.md`
  so release notes cite the same seed/cache evidence used by feature-slice
  scripts

If the release touches validation planning, `agent_loop`, MCP self-test / doctor,
or `validation_result` schema contracts, also collect the narrower validation-rich
lane from the same tree:

```powershell
./scripts/run_benchmark.ps1 -Lane validation_rich -Repo ace-lite-engine -OutputDir artifacts/benchmark/validation_rich/latest
```

Review `artifacts/benchmark/validation_rich/latest/results.json` and the paired
report output to confirm `task_success_rate`, `precision_at_k`, `noise_rate`,
and `validation_test_count` stay non-regressed on that validation-specific lane.
If the release changes chunk selection, chunk semantic rerank, or contextual
chunking behavior, also review the same summary/report pair for top-level
`retrieval_context_observability_summary` and
`retrieval_default_strategy_summary`, and confirm the retrieval-context /
default-strategy surface remains interpretable and report-only:

- `chunk_count_mean` and `coverage_ratio` are not regressing unexpectedly
- `pool_chunk_count_mean` and `pool_coverage_ratio` still match the intended
  chunk semantic rerank pool behavior
- any rise in `char_count_mean` is explained by an intentional retrieval-context
  expansion rather than silent sidecar bloat
- `graph_lookup_dominant_normalization` and the guard means in
  `retrieval_default_strategy_summary` still match the intended default
  graph-aware retrieval policy
- `topological_shield_dominant_mode` plus attenuation means still reflect the
  intended default shield contract rather than an unreviewed threshold drift

For the current graph-aware retrieval lane, use this rollback order if the
default strategy or graph summaries drift unexpectedly:

1. keep the checkpoint report-only and record the failing summary plus dated
   artifact path instead of promoting a broader default change
2. revert the candidate workload to the prior dated retrieval policy/profile,
   or downgrade the experiment from `feature` / `refactor` back to `general`
3. if the drift is dominated by repomap seed expansion, use a scoped config
   rollback with `repomap.enabled: false`, rerun the same benchmark/freeze
   evidence set, and only then consider a wider runtime revert

Treat that rollback order as maintainer guidance for graph-aware retrieval
changes; do not invent new release gates from it.

When the release touches learning-router rollout evidence, also review the same
summary/report pair for top-level `learning_router_rollout_summary` and confirm
the rollout-readiness surface stays report-only and interpretable:

- `eligible_case_rate` is not regressing unexpectedly
- `reason_counts` does not show a new spike in `failure_signal_present` or `missing_source_plan_cards`
- any increase in `adaptive_router_not_shadow` or `shadow_arm_missing` is explained by an intentional config or routing change

For the current `Y7502` retrieval-frontier stream, review the same summary for
`retrieval_frontier_gate_summary` and confirm these Q3 readiness metrics remain
inside the active thresholds:

- `deep_symbol_case_recall`
- `native_scip_loaded_rate`
- `precision_at_k`
- `noise_rate`
When writing release notes or freeze commentary, also prefer the paired
top-level `deep_symbol_summary` and `native_scip_summary` blocks from the same
validation-rich `summary.json` if you need stable deep-symbol recall and native
SCIP means without re-deriving them from raw `metrics`.
If you pass that summary into freeze regression, the generated
`freeze_regression.json` / `.md` will also carry a report-only
`validation_rich_benchmark` section for the same evidence set:

```powershell
python scripts/run_release_freeze_regression.py --matrix-config benchmark/matrix/repos.yaml --output-dir artifacts/release-freeze/latest --validation-rich-summary artifacts/benchmark/validation_rich/latest/summary.json
```

If a prior dated `validation_rich` artifact exists, pass it as well so freeze
can surface current-vs-previous delta in the same report-only section:

```powershell
python scripts/run_release_freeze_regression.py --matrix-config benchmark/matrix/repos.yaml --output-dir artifacts/release-freeze/latest --validation-rich-summary artifacts/benchmark/validation_rich/latest/summary.json --validation-rich-previous-summary artifacts/benchmark/validation_rich/2026-03-11/summary.json
```

When collecting a release checkpoint for this lane, record these four items
together so reviewers can interpret the freeze artifact without reopening the
raw config:

- current summary: `artifacts/benchmark/validation_rich/latest/summary.json`
- previous summary if available: a dated prior `summary.json` from the same lane
- gate mode: `disabled`, `report_only`, or `enforced`
- gate result: passed / failed, plus rollback reason if `enforced` was reverted
- Q3 frontier gate result: pass / fail from the same summary or freeze
  `validation_rich_benchmark.retrieval_frontier_gate_summary`
- Q4 retrieval default strategy summary:
  `retrieval_default_strategy_summary` from the same summary or freeze
  `validation_rich_benchmark` section when checkpoint notes need a stable,
  report-only description of retrieval-context availability, graph-lookup
  normalization/guard means, graph signal weights, or topological-shield
  attenuation means
- Q4 validation summaries: `validation_probe_summary` and
  `source_plan_validation_feedback_summary` from the same summary or freeze
  `validation_rich_benchmark` section when checkpoint notes need stable probe
  coverage, probe failure rate, feedback presence, or executed-test means
- stable frontier evidence blocks: `deep_symbol_summary` and
  `native_scip_summary` from the same benchmark summary when citing recall or
  native SCIP evidence in a checkpoint or changelog

Treat those Q4 validation summaries as report-only release evidence in the
current lane:
- freeze and promotion reporting may copy them forward directly from the
  validation-rich summaries
- they are intended to explain validation-test coverage and feedback drift
- they do not add new blocking thresholds unless the gate contract is expanded
  explicitly in a future stream

Treat `retrieval_default_strategy_summary` the same way in the current Q4
retrieval-governance lane:
- freeze and release reporting may copy it forward directly from the
  validation-rich summaries
- it is intended to explain the default retrieval-context, graph-lookup, and
  topological-shield contract without reopening raw payload JSON
- it does not add a new blocking threshold or promotion gate by itself

Treat `branch_validation_archive` the same way in the current branch-validation
stream:
- it is a targeted runtime / orchestrator evidence surface, not a matrix or
  freeze gate
- use it to explain current winner selection, rejected reasons, and artifact
  archive shape while runtime still executes a single real branch
- do not cite it as proof of multi-candidate execution until a future stream
  lands actual `N>1` candidate generation and concurrent sandbox validation

Treat `learning_router_rollout_summary` the same way in the current `Y7504`
lane:
- it is a maintainer-facing readiness summary, not an automatic release gate
- use it to explain why guarded rollout remains disabled or why a report-only checkpoint looks ready for the next governance review
- if release notes cite guarded-rollout readiness, cite the exact dated benchmark artifact and the matching `reason_counts` / `eligible_case_rate` values from that summary instead of paraphrasing raw case payloads

If the release candidate depends on retry/downgrade visibility or any logic that
changes `decision_trace`, require the same freeze run to carry a
`decision_observability_gate` section:

```yaml
freeze:
  decision_observability_gate:
    mode: report_only
```

Required checks for that gate:
- `summary_present = true`
- the summary exposes the expected scalar keys (`case_count`, `case_with_decisions_count`, `case_with_decisions_rate`, `decision_event_count`)
- the summary exposes the expected mapping keys (`actions`, `targets`, `reasons`, `outcomes`)
- the freeze artifact does not report structural mismatches such as negative bucket totals or rate/count disagreement

If the release candidate depends on more than one dated validation-rich run,
also build the report-only trend artifact for the same evidence set:

```bash
python scripts/build_validation_rich_trend_report.py --history-root artifacts/benchmark/validation_rich --latest-report artifacts/benchmark/validation_rich/latest/summary.json --output-dir artifacts/benchmark/validation_rich/trend/latest
```

Review:

- `artifacts/benchmark/validation_rich/trend/latest/validation_rich_trend_report.json`
- `artifacts/benchmark/validation_rich/trend/latest/validation_rich_trend_report.md`

Minimum checks:

- latest and previous rows are ordered by `generated_at`, not directory mtime
- delta stays report-only and is paired with the exact current/previous summary paths used for freeze
- any `failed_checks` drift is called out in the release checkpoint before discussing `validation_rich_gate.mode=enforced`
- any `retrieval_frontier_gate_summary.failed_checks` drift is called out before
  treating the checkpoint as Q3-frontier-ready
- any drift in `validation_probe_summary` or
  `source_plan_validation_feedback_summary` is called out as Q4 validation
  evidence, but remains report-only unless a future gate revision makes those
  summaries normative

If a tuning round also compares a baseline snapshot against the current default
path and a tuned candidate, attach the three-way comparison artifact:

```bash
python scripts/build_validation_rich_comparison_report.py --baseline artifacts/benchmark/validation_rich/2026-03-10/summary.json --current artifacts/benchmark/validation_rich/latest/summary.json --tuned artifacts/benchmark/validation_rich/tuned/latest/summary.json --output-dir artifacts/benchmark/validation_rich/comparison/latest
```

Review:

- `artifacts/benchmark/validation_rich/comparison/latest/validation_rich_comparison_report.json`
- `artifacts/benchmark/validation_rich/comparison/latest/validation_rich_comparison_report.md`

Minimum checks:

- baseline/current/tuned use the exact dated inputs cited in the release note or tuning review
- tuned improvements are not hiding worse `noise_rate`, `missing_validation_rate`, or `evidence_insufficient_rate`
- the comparison artifact is treated as decision support for `VR14`, not as an automatic gate on its own
- baseline/current/tuned `retrieval_frontier_gate_summary` blocks are reviewed
  together so native SCIP and deep-symbol recall gains are not claimed from a
  single raw summary only
- if release notes cite Q3 retrieval-frontier improvements, verify the matching
  `deep_symbol_summary` and `native_scip_summary` blocks across the same
  baseline/current/tuned inputs so the prose uses the same stable contract as
  scripts and `report.md`

Before changing `validation_rich_gate.mode`, generate the explicit promotion
decision artifact:

```bash
python scripts/evaluate_validation_rich_gate_promotion.py --trend-report artifacts/benchmark/validation_rich/trend/latest/validation_rich_trend_report.json --stability-report artifacts/benchmark/validation_rich/stability/latest/stability_summary.json --comparison-report artifacts/benchmark/validation_rich/comparison/latest/validation_rich_comparison_report.json --output artifacts/benchmark/validation_rich/promotion/latest/promotion_decision.json
```

Required checks:

- `recommendation` must explicitly say `eligible_for_enforced` before any
  config proposal moves beyond `report_only`
- otherwise keep `validation_rich_gate.mode=report_only` and carry the reasons
  forward into the next checkpoint
- if `failed_gates` includes `retrieval_frontier`, keep the release note or
  tuning checkpoint in evidence-gathering mode even when the core
  `validation_rich_gate` recommendation remains green

### 3.2 Latency and SLO trend report

Build this whenever the release changes retrieval policy, embedding behavior, repomap behavior, or time-budget logic.

```bash
python scripts/build_latency_slo_trend_report.py --history-root artifacts/benchmark/matrix/h2_2026 --latest-report artifacts/benchmark/matrix/latest/latency_slo_summary.json --output-dir artifacts/benchmark/matrix/latest-latency-slo-trend
```

When validation planning or `agent_loop` evidence is also part of the release
story, include the current validation-rich lane in the lightweight metrics
collector output so the dated checkpoint carries both matrix-level and
validation-specific signals in one `metrics.json` artifact:

```powershell
python scripts/metrics_collector.py --current artifacts/benchmark/matrix/latest/matrix_summary.json --validation-rich-current artifacts/benchmark/validation_rich/latest/summary.json --output artifacts/benchmark/matrix/latest-metrics.json
```

Review the generated metrics payload for both:

- `validation_rich_gate_summary`
- `retrieval_frontier_gate_summary`

If the release checkpoint also needs a dated validation-rich trend artifact,
build it from the same lane before writing release notes:

```powershell
python scripts/build_validation_rich_trend_report.py --history-root artifacts/benchmark/validation_rich --latest-report artifacts/benchmark/validation_rich/latest/summary.json --output-dir artifacts/benchmark/validation_rich/trend/latest
```

Required files to inspect for that report-only trend lane:

- `artifacts/benchmark/validation_rich/trend/latest/validation_rich_trend_report.json`
- `artifacts/benchmark/validation_rich/trend/latest/validation_rich_trend_report.md`

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

Keep `--skip-skill-validation` only when the candidate does not touch skills,
skill manifests, skill-routing heuristics, release-readiness playbooks, or
benchmark-tuning guidance. If any of those surfaces change, rerun freeze
without the skip flag and review these additional artifacts together with the
normal freeze result:

- `artifacts/release-freeze/latest/skill-validation/skill_validation_matrix.json`

When `freeze.decision_observability_gate.mode` is enabled, also review:

- `decision_observability_gate.summary_present`
- `decision_observability_gate.required_scalar_keys`
- `decision_observability_gate.required_mapping_keys`
- `decision_observability_gate.failures`

Recommended rollout policy:
- keep `decision_observability_gate.mode: report_only` while a lane is still proving that every benchmark matrix emits the summary consistently
- only switch to `enforced` once missing/malformed summaries are treated as release blockers for that lane
- `artifacts/release-freeze/latest/skill-validation/skill_validation_index.json`

When skill validation is enabled, require:

- the `skill_validation_matrix` step is present in `freeze_regression.json`
- overall skill pass rate stays at or above the configured `--skill-validation-min-pass-rate`
- misses are reviewed before interpreting the freeze as GO-ready, even if the
  rest of the regression steps are green

Required files to inspect:

- `artifacts/release-freeze/latest/freeze_regression.json`
- `artifacts/release-freeze/latest/freeze_regression.md`

Required gates to review:

- `tabiv3_gate`
- `concept_gate`
- `external_concept_gate`
- `validation_rich_gate` when the release also ships `validation_rich` evidence
- `feature_slices_gate`
- `retrieval_policy_guard`
- `e2e_success_gate`
- `memory_gate`
- `embedding_gate`

For `retrieval_policy_guard`, review the mode before interpreting failures:

- `disabled`: ignore the guard for release pass/fail decisions
- `report_only`: record failures in the artifact, but do not let them flip the overall freeze result
- `enforced`: failures block the freeze result

Apply the same mode interpretation to `validation_rich_gate`:

- `disabled`: `validation_rich` stays only as report-only benchmark evidence
- `report_only`: emit `validation_rich_gate` failures into freeze artifacts, but do not block release
- `enforced`: require the configured `validation_rich` thresholds to stay green before release passes

Recommended config shape for release maintainers:

```yaml
freeze:
  validation_rich_gate:
    mode: enforced
    thresholds:
      task_success_rate_min: 0.90
      precision_at_k_min: 0.40
      noise_rate_max: 0.60
      latency_p95_ms_max: 700.0
      validation_test_count_min: 5.0
      missing_validation_rate_max: 0.0
      evidence_insufficient_rate_max: 0.0
```

Recommended default for the current release workflow:

- as of 2026-03-19, the current promotion artifact is
  `eligible_for_enforced`, so `freeze.validation_rich_gate.mode: enforced` is
  now the maintainer-facing default for this repo
- revert to `report_only` if the lane becomes noisy again or the next
  checkpoint loses stable promotion evidence

Rollback rule for false positives or unstable evidence:

1. change `freeze.validation_rich_gate.mode` from `enforced` back to `report_only`
2. rerun `./scripts/run_full_validation.ps1 -IncludeValidationRichBenchmark` or rerun freeze with the same `--validation-rich-summary` / `--validation-rich-previous-summary` inputs
3. record the rollback reason and the failing metrics in the release checkpoint or freeze artifact review comment

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

If the release candidate changed `skills/`, maintainer docs, or cross-agent
playbooks that directly affect prompt routing, repeat the same stability run
without `--skip-skill-validation` so the stability evidence includes skill
selection drift alongside the freeze summary.

Required checks:

- tracked robustness slices stay `stable_pass`
- treat whole-freeze failures as release-readiness issues, not as evidence that the robustness lane is invalid

If the release candidate changes validation planning, `agent_loop`, validation
schema contracts, or any path already covered by the validation-rich lane, also
run the lighter validation-rich stability check:

```bash
python scripts/run_validation_rich_stability.py --runs 2 --output-dir artifacts/benchmark/validation_rich/stability/latest --max-failure-rate 0.0
```

Required checks:

- `classification` stays `stable_pass` before discussing stricter
  `validation_rich_gate.mode`
- repeated runs do not introduce new `failed_checks` clusters or non-zero
  `missing_validation_rate` / `evidence_insufficient_rate`
- the stability artifact is reviewed together with the current
  `validation_rich_trend_report.*` outputs rather than as a replacement for them
- `q3_gate_failed_count` stays at `0` if the release candidate claims Q3
  retrieval-frontier readiness

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

### Plugin / MCP compatibility review

Use this checklist whenever the candidate changes plugin runtime behavior,
MCP tool signatures, timeout/auth/retry knobs, trust policy, or remote slot
filtering. The normative compatibility matrix lives in
`docs/design/ORCHESTRATOR_DESIGN.md`.

Required checks:

- `ace_plan` still defaults to `plugins_enabled = false` on the MCP surface
- MCP tool names and descriptions still match the expected public registry
- trusted `in_process` plugins still load locally, while untrusted
  `in_process` plugins still downgrade to MCP
- untrusted remote MCP endpoints still keep `mock://` by default and only keep
  `http(s)` when explicit opt-in is enabled
- remote slot policy still keeps `observability.mcp_plugins` allowlisted and
  does not silently broaden non-allowlisted remote writes

Minimum regression commands:

```powershell
python -m pytest tests/unit/test_mcp_server.py tests/unit/test_plugins_runtime.py tests/integration/test_orchestrator_slot_policy.py -q
```

## 5. Artifact Review Template

Use the following headings in a release checkpoint or PR comment:

```md
## Release Validation Summary

- Candidate version:
- Evidence date:
- Benchmark matrix:
- Validation-rich benchmark (if used):
  - Current summary:
  - Previous summary:
  - Gate mode:
  - Gate result / rollback note:
- Validation-rich trend (if used):
- Latency/SLO trend:
- Router observability summary:
- Freeze regression:
- Freeze stability:
- Workspace benchmark (if used):

## Required Checks

- Benchmark thresholds:
- Phase 2 QuickFirst overlay (`artifacts/checkpoints/phase2/latest/phase2_quickfirst_overlay.json`): Phase 2 artifacts complete, report-only signals present
- Smoke summary (`artifacts/smoke/latest/smoke_summary.json`): healthy = true (Phase 2: report-only; not a release gate):
  - timed_out = false
  - file_count > 0
  - step_count > 0
- Phase 2 QuickFirst overlay (`artifacts/checkpoints/phase2/latest/phase2_quickfirst_overlay.json`): Phase 2 artifacts are complete and all report-only
- Validation-rich task success / validation evidence (if used):
  - task_success_rate / precision_at_k / noise_rate / validation_test_count:
  - delta vs previous summary:
  - gate failures or rollback reason (if any):
- Validation-rich trend delta (if used):
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



