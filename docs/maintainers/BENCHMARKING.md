# Benchmarking (ACE-Lite Engine)

ACE-Lite supports repeatable benchmark cases and regression gates so retrieval quality can be improved safely.

Canonical adaptive-feature promotion rules live in
`docs/maintainers/ADAPTIVE_PROMOTION_GOVERNANCE_2026-03-09.md`.
This document defines the evidence lanes and metrics; the governance doc defines
whether a path is currently `promote`, `stay_experimental`, or `reject`.

## Author cases (YAML)

```yaml
cases:
  - case_id: repo-auth-01
    query: how token validation works
    expected_keys: [validate_token, auth, expiry]
    filters: { repo: mem0, topic: auth }
    top_k: 8

  - case_id: repo-benchmarking-negative-control
    query: where is the maintainers benchmarking guide
    expected_keys: [docs, maintainers, benchmarking]
    top_k: 8
    task_success:
      mode: negative_control
      min_validation_tests: 1
```

## Scored metrics (high level)

Common metrics include:
- `recall_at_k`, `precision_at_k`, `noise_rate`, `dependency_recall`
- `task_success_rate` as the canonical task-oriented metric
- `utility_rate` as the legacy compatibility alias for older artifacts
- `latency_p95_ms`, `latency_median_ms`
- stage-level latency summaries for `memory`, `index`, `repomap`, `augment`, `skills`, and `source_plan`
- explicit SLO budget and downgrade signals such as `parallel_docs_timeout_ratio`, `embedding_time_budget_exceeded_ratio`, `chunk_semantic_fallback_ratio`, and `slo_downgrade_case_rate`
- `chunk_hit_at_k`, `chunk_budget_used`
- source-plan grounding ratios such as `source_plan_direct_evidence_ratio`, `source_plan_neighbor_context_ratio`, and `source_plan_hint_only_ratio`
- skills-budget signals such as `skills_token_budget_used_mean`, `skills_budget_exhausted_ratio`, and `skills_skipped_for_budget_mean`
- skills-routing signals such as `skills_route_latency_p95_ms`, `skills_hydration_latency_p95_ms`, `skills_metadata_only_routing_ratio`, and `skills_precomputed_route_ratio`
- evidence-insufficiency rates such as `evidence_insufficient_rate`, `no_candidate_rate`, `low_support_chunk_rate`, `missing_validation_rate`, `budget_limited_recovery_rate`, and `noisy_hit_rate`

For chunk-oriented metrics, benchmark scoring prefers the final `source_plan.candidate_chunks` and `source_plan.chunk_budget_used` payload when present, and falls back to raw `index` chunk outputs otherwise. That keeps chunk-packing experiments visible in the same benchmark and freeze artifacts that already track task success, latency, and noise.
When `source_plan.evidence_summary` is present, benchmark artifacts also surface additive grounding ratios so maintainers can distinguish directly retrieved support from neighboring context and hint-only support without parsing `why` strings or other free-text explanations.
When chunk selection emits internal retrieval-context sidecars, benchmark artifacts also surface additive retrieval-context observability through top-level `retrieval_context_observability_summary`, so maintainers can review context coverage, average context size, and rerank-pool exposure without reopening raw case payloads.
The same benchmark artifacts also surface top-level `retrieval_default_strategy_summary`, which is the stable report-only contract for the current default retrieval shape: retrieval-context sidecar availability, graph-lookup default normalization and guard means, graph signal weight means, and topological-shield dominant mode plus attenuation means. Use that top-level summary when you need freeze- or release-facing evidence about the default retrieval contract instead of re-deriving those values from raw `metrics`, `candidate_ranking`, or chunk-selection payloads.
For graph-aware retrieval work, keep governance minimal and explicit:
- treat `feature`, `refactor`, and `general` as the current graph-aware policies because they all combine `graph_seeded` repomap with `index.graph_lookup`
- compare them against the non-graph reference policies (`bugfix_test` / `doc_intent`) or against the prior dated config, not against raw single-case payloads
- if graph-aware evidence turns noisy, record the failing summary and fallback to the prior dated policy/profile before widening rollout claims
When `index.graph_lookup` is present, benchmark artifacts also surface additive graph-lookup observability such as `graph_lookup_enabled_ratio`, `graph_lookup_guarded_ratio`, `graph_lookup_candidate_count_mean`, `graph_lookup_query_hit_paths_mean`, the stable path-mix means for `scip`, `xref`, `symbol`, `import`, and `coverage`, the stable guard contract (`graph_lookup_reason`, `graph_lookup_guard_max_candidates`, `graph_lookup_guard_min_query_terms`, `graph_lookup_guard_max_query_terms`) copied from `candidate_ranking` / `metadata` when raw payload access is unavailable, and the stable signal-shape trace (`graph_lookup_normalization`, `graph_lookup_max_inbound`, `graph_lookup_max_xref_count`, `graph_lookup_max_query_hits`, `graph_lookup_max_symbol_hits`, `graph_lookup_max_import_hits`, `graph_lookup_max_query_coverage`) for tuning graph weights without reopening raw payload JSON.

`task_success` schema v1:
- `mode`: `positive` (default) or `negative_control`
- `require_recall_hit`: defaults to `true`
- `min_validation_tests`: minimum `source_plan.validation_tests` count required for task success

Negative-control cases are allowed to retrieve relevant files while still producing `task_success_hit = 0` when downstream execution evidence is insufficient.
Benchmark reports now emit a dedicated retrieval-to-task gap section so cases with `recall_hit > 0` but `task_success_hit = 0` are visible without reading raw JSON.
Benchmark reports also emit:
- `Stage Latency Summary` so per-stage p95/mean latency drift is visible alongside the total latency budget
- `SLO Budget Summary` so explicit downgrade boundaries and budget-trigger signals are visible in both current artifacts and baseline deltas
- `Evidence Insufficiency Summary` so failing positive cases are classified into additive `no_hit`, `low_support`, `missing_validation`, `budget_limited`, and `noisy_hit` surfaces without changing stable benchmark report contracts
- `Decision Observability Summary` so retry, skip, fallback, downgrade, and exact-search boost events are aggregated without changing stage behavior
- `Retrieval Context Summary` so maintainers can inspect retrieval-context chunk coverage, average context size, and chunk-rerank pool coverage without opening raw JSON
- `Graph Lookup Summary` so maintainers can inspect `graph_lookup` enablement, guard-hit rate, candidate-count pressure, query-term guard thresholds, normalization mix, signal maxima, and the per-signal path mix without opening raw payload JSON
- `Retrieval Default Strategy Summary` so maintainers can inspect the current default retrieval-context, graph-lookup, and topological-shield contract in the same top-level form that freeze and release artifacts consume
- `Learning Router Rollout Summary` so maintainers can inspect guarded-rollout readiness as a report-only surface before any online default switch is considered

Evidence-insufficiency reporting is intentionally report-only in the current lane:
- it applies only to failing `positive` task-success cases
- `negative_control` cases are excluded from the insufficiency summary counts
- per-case rows still carry additive `evidence_insufficiency_reason` and `evidence_insufficiency_signals` fields for debugging retrieval-to-task gaps

Decision observability is also additive and report-only in the current lane:
- per-case rows carry `decision_trace_count` and `decision_trace`
- each decision event records `stage`, `action`, `target`, `reason`, and optional `outcome`
- benchmark summaries aggregate action/target/reason/outcome counts so maintainers can see why retries or downgrades happened before any adaptive feature promotion
- `scripts/run_release_freeze_regression.py` can now gate on the presence and structural integrity of `decision_observability_summary` without turning any of its counts into hard promotion thresholds

The rollout-readiness summary is additive and report-only in the current lane:
- `summary.json` / `report.md` carry top-level `learning_router_rollout_summary`
- the summary classifies each case into the same readiness reasons used by the current guarded-rollout evidence path: `adaptive_router_disabled`, `adaptive_router_not_shadow`, `shadow_arm_missing`, `missing_source_plan_cards`, `failure_signal_present`, or `eligible_pending_guarded_rollout`
- use it to review whether shadow coverage, source-plan cards, and failure-signal hygiene are converging before proposing any guarded-rollout default switch
- do not treat it as an automatic release blocker until a future stream explicitly promotes it into a normative freeze gate

## Run benchmarks

```bash
ace-lite benchmark run --cases benchmark/cases/default.yaml --repo mem0 --root . --output artifacts/benchmark/latest
ace-lite benchmark report --input artifacts/benchmark/latest/results.json
```

```powershell
./scripts/run_benchmark.ps1
./scripts/run_benchmark.ps1 -Lane validation_rich -Repo ace-lite-engine
```

## Multi-repo matrix (external evidence)

```bash
python scripts/run_benchmark_matrix.py --matrix-config benchmark/matrix/repos.yaml --output-dir artifacts/benchmark/matrix/latest --fail-on-thresholds
```

Thresholds are defined in `benchmark/matrix/repos.yaml`.
Foundry-style repositories that vendor contract dependencies as git submodules can add `submodules: true` or a list of submodule paths in the repo spec; the matrix runner will sync and initialize those submodules after checkout before benchmarking.
The primary release-facing matrix now intentionally carries a broader dependency-heavy mix instead of leaving those repos only in the auxiliary external OSS lane:
- `blockscout-frontend` for large TypeScript/JavaScript frontend graph pressure
- `protobuf-go` for generated-code-heavy Go dependency recall
- `grpc-java` for Java multi-module transport, xDS, and builder dependency pressure
- `lens-core` and `uniswap-v4-core` for Solidity dependency and submodule traversal
The matrix summary now carries forward stage-latency and SLO-budget summaries so release-freeze reporting can surface the same latency and downgrade signals at the multi-repo level.
The matrix runner now also emits a dedicated `latency_slo_summary.json` and `latency_slo_summary.md` next to `matrix_summary.*`. Those focused artifacts are intended to be the maintainer-facing decision surface for latency and downgrade work, rather than forcing future provider or policy experiments to grep the full matrix payload.
Workload buckets default to repo-size buckets derived from each repo `index.json` `file_count` (`repo_size_small <= 128`, `repo_size_medium <= 1024`, `repo_size_large >= 1025`). A matrix repo spec can override that classification later with `workload_bucket` when a more explicit workload taxonomy is needed.
The current full-fidelity dated latency/SLO artifacts are:
- `artifacts/benchmark/matrix/h2_2026/2026-03-06/latency_slo_summary.json`
- `artifacts/benchmark/matrix/h2_2026/2026-03-06/latency_slo_summary.md`
- `artifacts/benchmark/matrix/h2_2026/2026-03-06-release-readiness/latency_slo_summary.json`
- `artifacts/benchmark/matrix/h2_2026/2026-03-06-release-readiness/latency_slo_summary.md`
- `artifacts/benchmark/matrix/h2_2026/2026-03-11-grpc-java/latency_slo_summary.json`
- `artifacts/benchmark/matrix/h2_2026/2026-03-11-grpc-java/latency_slo_summary.md`

The dedicated latency/SLO artifact lists two different control surfaces explicitly:
- hard-budget features: `parallel_time_budget_ms_mean`, `embedding_time_budget_ms_mean`, `chunk_semantic_time_budget_ms_mean`, `xref_time_budget_ms_mean`
- dynamic-downgrade features: `parallel_docs_timeout_ratio`, `parallel_worktree_timeout_ratio`, `embedding_time_budget_exceeded_ratio`, `embedding_adaptive_budget_ratio`, `embedding_fallback_ratio`, `chunk_semantic_time_budget_exceeded_ratio`, `chunk_semantic_fallback_ratio`, `xref_budget_exhausted_ratio`, `slo_downgrade_case_rate`

The matrix summary also emits a richer `retrieval_policy_summary` so each policy can be compared by:
- repo coverage and regression rate
- task-success and positive-task success
- retrieval-to-task gap rate
- precision/noise
- latency and repomap latency
- SLO downgrade rate

`scripts/run_release_freeze_regression.py` now consumes those policy rows through `freeze.policy_guard`, so task-aware policy tuning only survives when policy-level benchmark evidence and SLO guardrails stay inside configured limits.
That report-only `freeze.policy_guard` surface is also the first governance stop for graph-aware retrieval changes: use it to record regressions and rollback reasons before changing default policy posture.
The same release-freeze summary also evaluates `freeze.memory_gate` against benchmark-level `notes_hit_ratio`, `profile_selected_mean`, and `capture_trigger_ratio`, so memory-policy experiments stay evidence-gated instead of quietly drifting into the default path.

## Feature And Perturbation Slices

```bash
python scripts/run_feature_slice_matrix.py --config benchmark/matrix/feature_slices.yaml --output-dir artifacts/benchmark/slices/feature_slices/latest --fail-on-thresholds
```

The feature slice matrix now also includes a perturbation slice that checks robustness against:
- `feedback`: replays local selection feedback as an opt-in experience-reuse experiment and requires measurable precision/noise improvement before the boosted path is considered viable
- `temporal`: constrains local notes to an explicit time window so recency-driven memory policy changes can be compared off/on without changing the default plan path
- `late_interaction`: compares the default lightweight rerank path against the optional `hash_colbert` provider path under explicit precision/noise thresholds, so the provider prototype stays rollback-safe and benchmark-gated
- `dependency_recall`: compares `heuristic` versus `graph_seeded` repomap ranking profiles on a dependency-aware seeded repo and gates dependency recall, precision, noise, and latency together
- `perf_routing`: compares `general` against the current perf proxy policy (`refactor`) on a seeded hotspot repo and gates task success, precision, noise, latency, and `slo_downgrade_case_rate` together before any perf-route promotion is considered
- `rename`
- `path_move`
- `doc_noise`
- `file_growth`
- `query_paraphrase`
- `repomap_perturbation`: reruns paired harmless graph/path perturbations with `repomap` enabled and gates `dependency_recall` alongside task success, precision, and noise so graph-aware retrieval remains stable under dependency rename and path-move changes

The provider path stays opt-in through `embeddings.enabled` / `--embedding-enabled`, so local-first default plans continue on the existing path unless a benchmarked provider experiment is explicitly enabled.
For the current repo, paired graph-seeded repomap review should prefer the
stable `repomap_seed_summary` contract in `summary.json` and `report.md`
instead of re-deriving seed/cache numbers from raw metrics only. The maintained
fields are:

- `worktree_seed_count_mean`
- `subgraph_seed_count_mean`
- `seed_candidates_count_mean`
- `cache_hit_ratio`
- `precompute_hit_ratio`

These are the same seed/cache values consumed by `benchmark_ops` helpers and by
the `dependency_recall` / `repomap_perturbation` feature-slice scripts.
For the current `Y7502` retrieval-frontier lane, maintainers should treat the
top-level `deep_symbol_summary` and `native_scip_summary` contracts in
`summary.json` / `results.json` as the canonical evidence surface for:

- deep-symbol case volume and recall
- native SCIP load rate
- native SCIP document / definition-occurrence / reference-occurrence /
  symbol-definition means

`report.md` renders the same sections and now prefers those top-level summaries
before falling back to `retrieval_frontier_gate_summary` or raw `metrics`, so
benchmark review, script automation, and human-readable reports stay aligned on
the same Q3 evidence contract.

## Validation-Rich Lane

Use `benchmark/cases/validation_rich_cases.yaml` when you need a lane that
explicitly requires non-empty `source_plan.validation_tests` and exercises the
newer validation / agent-loop / MCP doctor surfaces against the current repo.

```bash
ace-lite benchmark run \
  --cases benchmark/cases/validation_rich_cases.yaml \
  --repo ace-lite-engine \
  --root . \
  --junit-xml benchmark/fixtures/validation_rich_junit.xml \
  --output artifacts/benchmark/validation_rich/latest
```

```powershell
./scripts/run_benchmark.ps1 -Lane validation_rich -Repo ace-lite-engine
./scripts/run_full_validation.ps1 -IncludeValidationRichBenchmark
```

This lane is intended to answer a narrower question than the default
`ace_lite_engine` lane: whether retrieval still lands on the correct files while
the source-plan path also carries forward validation-test evidence.
Standard artifact contract for this lane:
- output directory: `artifacts/benchmark/validation_rich/latest`
- summary: `artifacts/benchmark/validation_rich/latest/summary.json`
- report: `artifacts/benchmark/validation_rich/latest/report.md`
- results: `artifacts/benchmark/validation_rich/latest/results.json`
- junit fixture input: `benchmark/fixtures/validation_rich_junit.xml`

When `scripts/run_full_validation.ps1 -IncludeValidationRichBenchmark` is used,
the same `summary.json` is also threaded into the freeze artifact as report-only
context so maintainers can inspect validation-specific quality without turning
the lane into a default release blocker.

If the same artifact set is later threaded into
`scripts/run_release_freeze_regression.py`, keep the checkpoint metadata aligned
across benchmark and freeze review:
- current summary: `artifacts/benchmark/validation_rich/latest/summary.json`
- previous summary: a dated prior `summary.json` when delta review is needed
- gate mode: `freeze.validation_rich_gate.mode`
- Q3 frontier gate summary: `retrieval_frontier_gate_summary` in the same
  current/previous validation-rich summaries and the paired freeze artifact
- Q4 retrieval default strategy summary: `retrieval_default_strategy_summary`
  in the same current/previous validation-rich summaries and the paired freeze
  artifact when you need stable retrieval-context, graph-lookup guard,
  normalization, or topological-shield attenuation evidence
- Q4 validation summaries: `validation_probe_summary` and
  `source_plan_validation_feedback_summary` in the same current/previous
  validation-rich summaries and the paired freeze artifact when you need stable
  probe enablement, probe failure rate, feedback presence, or executed-test
  means without re-deriving them from raw `metrics`
- top-level frontier evidence: `deep_symbol_summary` and `native_scip_summary`
  in the same summaries when you need stable recall / native-SCIP means without
  re-deriving them from raw metrics

The Q4 validation summaries are additive evidence only in the current lane:
- benchmark review, promotion review, freeze regression, and freeze-trend
  reports may surface them directly
- they do not change the existing `validation_rich_gate` pass/fail thresholds by
  themselves
- use them to explain validation probe coverage and validation-feedback drift,
  not to replace the canonical gate metrics above

`validation_rich_gate` mode guidance for the current repo:
- `disabled`: benchmark evidence is collected, but freeze does not evaluate a
  validation-rich gate
- `report_only`: keep available as the rollback mode when the lane turns noisy
  or the promotion evidence goes stale
- `enforced`: only use after the lane has a stable dated baseline and the team
  is willing to fail release freeze on missing summaries or threshold drift

Current recommendation as of 2026-03-19:
- promotion evidence is `eligible_for_enforced`, so the maintainer-facing
  default for the active repo can move to `enforced`
- keep the same rollback path to `report_only` if a later checkpoint becomes
  noisy or unstable

Example gate config:

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

If an `enforced` rollout proves noisy, revert `freeze.validation_rich_gate.mode`
to `report_only`, rerun `./scripts/run_full_validation.ps1 -IncludeValidationRichBenchmark`
or the equivalent freeze command, and record the rollback reason alongside the
failing metrics.

`decision_observability_gate` mode guidance for the current repo:
- `disabled`: freeze ignores the summary completely
- `report_only`: recommended default; freeze records missing or malformed decision-observability summaries without failing the release
- `enforced`: only use when every release checkpoint in the current lane is already expected to emit a stable `decision_observability_summary`

Example config:

```yaml
freeze:
  decision_observability_gate:
    mode: report_only
```

This gate is intentionally structural, not threshold-based:
- it requires the summary to exist
- it requires scalar keys such as `case_count` and `decision_event_count`
- it requires mapping keys such as `actions`, `targets`, `reasons`, and `outcomes`
- it checks basic internal consistency such as count/rate agreement and non-negative bucket totals

Validation-rich dated artifact and trend convention:
- latest lane output: `artifacts/benchmark/validation_rich/latest`
- dated checkpoint copy: `artifacts/benchmark/validation_rich/<YYYY-MM-DD>`
- trend output: `artifacts/benchmark/validation_rich/trend/latest`

```bash
python scripts/build_validation_rich_trend_report.py \
  --history-root artifacts/benchmark/validation_rich \
  --latest-report artifacts/benchmark/validation_rich/latest/summary.json \
  --output-dir artifacts/benchmark/validation_rich/trend/latest
```

If `--latest-report` is omitted, the script now defaults to the canonical
current lane artifact under `artifacts/benchmark/validation_rich/latest/summary.json`.
`artifacts/benchmark/validation_rich/tuned/latest/summary.json` remains an
explicit override input for comparison workflows rather than an implicit trend source.

The trend report is report-only. Use it to review current-vs-previous deltas for
`task_success_rate`, `precision_at_k`, `noise_rate`, `validation_test_count`,
`missing_validation_rate`, and `evidence_insufficient_rate` before tightening
release gating.
The same trend artifact now also carries the current and previous
`retrieval_frontier_gate_summary` blocks so maintainers can review the Q3
frontier-readiness deltas in the same place:

- `deep_symbol_case_recall`
- `native_scip_loaded_rate`
- `precision_at_k`
- `noise_rate`
- gate-level `failed_checks`

When you are comparing a known-good baseline, the current default path, and a
tuned experiment in one review, build the three-way comparison artifact:

```bash
python scripts/build_validation_rich_comparison_report.py \
  --baseline artifacts/benchmark/validation_rich/2026-03-10/summary.json \
  --current artifacts/benchmark/validation_rich/latest/summary.json \
  --tuned artifacts/benchmark/validation_rich/tuned/latest/summary.json \
  --output-dir artifacts/benchmark/validation_rich/comparison/latest
```

Expected comparison artifacts:
- `validation_rich_comparison_report.json`
- `validation_rich_comparison_report.md`

This report is also report-only. Its role is to make `baseline -> current ->
tuned` tradeoffs explicit before any discussion of gate-mode upgrades.
It now mirrors the same Q3 frontier gate surface across baseline/current/tuned
inputs so tuning reviews can compare `retrieval_frontier_gate_summary` without
opening raw summaries.

To make the gate-mode decision explicit, evaluate the accumulated trend and
stability evidence with the promotion helper:

```bash
python scripts/evaluate_validation_rich_gate_promotion.py \
  --trend-report artifacts/benchmark/validation_rich/trend/latest/validation_rich_trend_report.json \
  --stability-report artifacts/benchmark/validation_rich/stability/latest/stability_summary.json \
  --comparison-report artifacts/benchmark/validation_rich/comparison/latest/validation_rich_comparison_report.json \
  --output artifacts/benchmark/validation_rich/promotion/latest/promotion_decision.json
```

Expected promotion artifacts:
- `promotion_decision.json`
- `promotion_decision.md`

Promotion evaluation contract:
- `trend.latest.regressed`, latest metric thresholds, stability classification, and comparison regressions are hard gates.
- `trend.failed_check_top3` remains maintainer-facing history context and is emitted as a warning in the promotion decision; it should not permanently block promotion after the current latest/stability/comparison evidence is healthy.
- `retrieval_frontier` is evaluated as an additional offline gate. A failed
  `retrieval_frontier_gate_summary` keeps the recommendation at
  `stay_report_only` even when the core validation-rich gate remains green.

If the recommendation still says `stay_report_only`, archive the current
evidence snapshot and carry the unresolved reasons into the next cycle:

```bash
python scripts/archive_validation_rich_evidence.py \
  --date 2026-03-12 \
  --summary artifacts/benchmark/validation_rich/latest/summary.json \
  --results artifacts/benchmark/validation_rich/latest/results.json \
  --report artifacts/benchmark/validation_rich/latest/report.md \
  --trend-dir artifacts/benchmark/validation_rich/trend/latest \
  --stability-dir artifacts/benchmark/validation_rich/stability/latest \
  --comparison-dir artifacts/benchmark/validation_rich/comparison/latest \
  --promotion-decision artifacts/benchmark/validation_rich/promotion/latest/promotion_decision.json \
  --output-root artifacts/benchmark/validation_rich/archive
```

Archive behavior for the current repo:
- `archive_manifest.json` retains both `validation_rich_gate_summary` and
  `retrieval_frontier_gate_summary`
- `next_cycle_todo.md` includes a dedicated `Q3 Retrieval Frontier Gate`
  section so the next tuning cycle can pick up the failed Q3 checks directly

The same promotion rule now applies to future skills-routing architecture experiments:
- keep `route early, hydrate later` off the default path until a paired benchmark lane shows no task-success, precision, noise, latency, or skills-budget regressions
- treat `skills_token_budget_used_mean`, `skills_budget_exhausted_ratio`, `skills_route_latency_p95_ms`, and `skills_hydration_latency_p95_ms` as the first maintainer-facing evidence surface before proposing any routing promotion

These paired runs are intended to fail freeze/CI reporting when a provider experiment or harmless repository/query perturbation causes `task_success_rate` or precision to regress, or noise to increase.
The dependency-recall slice is also intended to keep graph-prior experiments honest: if a query-aware repomap profile does not improve dependency-aware retrieval, it must at least avoid precision/noise/latency regressions.
The perf-routing slice plays the same role for future perf-aware routing: `refactor` remains only an offline proxy for perf intent until its paired slice shows no hotspot-localization, latency, or SLO-downgrade regressions against `general`.
The current `stale_majority` and lexical `perturbation` lanes are also the controlled evidence surface for SHARS-lite `chunk_guard.mode=enforce`: benchmark config may turn enforce on there without changing the default runtime path, and the slice artifacts now record the exact chunk-guard mode and thresholds used for that run.
The repomap perturbation slice extends that guardrail into paired baseline/perturbed repos, so maintainers can inspect the same `feature_slices_summary.json` artifact for graph/path robustness instead of relying only on lexical perturbation evidence.

When reviewing SHARS-lite enforce evidence, read the same dated
`feature_slices_summary.json` / `.md` artifact with these rules:

- confirm `stale_majority` stays green first in report-only history, then in the
  controlled enforce run with the same `chunk_guard` knobs shown in the slice
  payload
- require lexical `perturbation` to stay green under the same enforce-mode
  config so harmless rename/path/doc/query changes are not confounded by the
  feature toggle itself
- use the stale-majority `latency_growth_factor` check as the primary bounded
  latency surface for enforce-mode evaluation
- cross-check the benchmark artifact with the chunk-guard permutation and
  orchestrator integration regressions before discussing any broader rollout

## Repeated-Run Stability

```bash
python scripts/run_freeze_stability.py \
  --runs 2 \
  --output-dir artifacts/release-freeze/stability/latest \
  --skip-skill-validation \
  --max-failure-rate 1.0 \
  --tracked-feature-slices dependency_recall,perturbation,repomap_perturbation \
  --min-feature-slice-pass-rate 1.0
```

Keep `--skip-skill-validation` only when the repeated-run question is strictly
about retrieval robustness, latency drift, or release-freeze stability. If the
change also touches skill routing, skill manifests, release skills, or benchmark
playbooks, rerun the same freeze workflow without `--skip-skill-validation` so
the artifact bundle also includes:

- `artifacts/release-freeze/stability/latest/skill-validation/skill_validation_matrix.json`
- `artifacts/release-freeze/stability/latest/skill-validation/skill_validation_index.json`

For a standalone skill-routing check outside the full freeze workflow, run:

```bash
python scripts/run_skill_validation.py \
  --repo-url <repo-url> \
  --repo-ref <ref> \
  --repo-name <repo-name> \
  --repo-dir artifacts/repos-workdir/skill-validation \
  --skills-dir skills \
  --index-cache-path artifacts/release-freeze/stability/latest/skill-validation/skill_validation_index.json \
  --output-path artifacts/release-freeze/stability/latest/skill-validation/skill_validation_matrix.json \
  --languages typescript,javascript \
  --apps codex,claude-code,opencode \
  --min-pass-rate 0.8 \
  --fail-on-miss
```

Acceptable drift policy for the current robustness lane:

- Core robustness slices (`dependency_recall`, `perturbation`, `repomap_perturbation`) must classify as `stable_pass` across the repeated runs.
- A tracked slice classification of `one_off_pass`, `mixed`, or `stable_fail` counts as drift and blocks further robustness tuning work.
- Whole-freeze `pass_rate` is still informative, but it is currently report-level context for this lane rather than the primary blocker. The dated 2026-03-06 stability artifact showed the tracked robustness slices at `stable_pass` while the overall freeze was `stable_fail` because `concept_gate` and `e2e_success_gate` were below threshold in that run; the later release-quality rerun repaired those adjacent gates.

Current stability artifact:

- `artifacts/release-freeze/stability/2026-03-06-feature-slice-stability/stability_summary.json`
- `artifacts/release-freeze/stability/2026-03-06-feature-slice-stability/stability_summary.md`

When validation-specific quality itself is being tuned, run the lighter
validation-rich repeated-run lane as well:

```bash
python scripts/run_validation_rich_stability.py \
  --runs 2 \
  --output-dir artifacts/benchmark/validation_rich/stability/latest \
  --max-failure-rate 0.0
```

Validation-rich stability stays report-oriented for now, but it should answer a
more focused question than freeze stability: whether repeated validation-rich
benchmark runs keep passing the current task-success / precision / noise /
latency / validation-test-count thresholds without drifting into repeated
`failed_checks`, `missing_validation_rate`, or `evidence_insufficient_rate`
regressions.
The same stability artifact now also records Q3 frontier drift through
`q3_gate_failed_count` and `latest_retrieval_frontier_gate_summary`, so the
repeated-run review can distinguish "validation lane still green" from
"frontier-readiness regressed".

Current validation-rich stability artifacts:

- `artifacts/benchmark/validation_rich/stability/latest/stability_summary.json`
- `artifacts/benchmark/validation_rich/stability/latest/stability_summary.md`

When a dated checkpoint needs a compact machine-readable handoff artifact, emit:

```bash
python scripts/metrics_collector.py \
  --current artifacts/benchmark/matrix/latest/matrix_summary.json \
  --validation-rich-current artifacts/benchmark/validation_rich/latest/summary.json \
  --output artifacts/benchmark/matrix/latest-metrics.json
```

The collector now keeps both `validation_rich_gate_summary` and
`retrieval_frontier_gate_summary` so CI, dashboards, or release notes can
consume Q2 and Q3 readiness from one JSON surface.

## Latency And SLO Trend Reporting

```bash
python scripts/backfill_latency_slo_summary.py \
  --matrix-summary artifacts/benchmark/matrix/h2_2026/2026-03-06-release-readiness/matrix_summary.json

python scripts/build_latency_slo_trend_report.py \
  --history-root artifacts/benchmark/matrix/h2_2026 \
  --latest-report artifacts/benchmark/matrix/h2_2026/2026-03-06-release-readiness/latency_slo_summary.json \
  --output-dir artifacts/benchmark/matrix/h2_2026/2026-03-06-release-readiness-latency-slo-trend
```

`scripts/backfill_latency_slo_summary.py` exists for older matrix directories that already have a full-fidelity `matrix_summary.json` plus per-repo `index.json`, but were created before the dedicated latency/SLO artifact was emitted automatically.
The trend report remains intentionally report-only. It now compares the latest `2026-03-06-release-readiness` latency/SLO artifact against the prior full-fidelity `2026-03-06` artifact, but it still does not fail CI or release gates yet.
The older `2026-02-25` backfilled baseline remains in the history table for context, but it is no longer the immediate comparison baseline for the trend delta.
The current dated trend artifact is:

- `artifacts/benchmark/matrix/h2_2026/2026-03-06-release-readiness-latency-slo-trend/latency_slo_trend_report.json`
- `artifacts/benchmark/matrix/h2_2026/2026-03-06-release-readiness-latency-slo-trend/latency_slo_trend_report.md`

The current 2026-03-07 checkpoint shows why this still stays report-only: the newest comparison pair is finally full-fidelity, but it is still only a two-run comparison and the release `policy_guard` taxonomy has not been promoted from evidence gathering into explicit enforced modes yet.
The same report-only rule applies to the new decision observability lane: maintainers can inspect retry/downgrade/skip/fallback summaries in benchmark artifacts now, but those decision traces are not release blockers yet.

Before proposing any adaptive default-path switch, cross-check the benchmark
artifact against `docs/maintainers/ADAPTIVE_PROMOTION_GOVERNANCE_2026-03-09.md`
so the evidence lane and the promotion state stay aligned.

## Router Promotion Evidence

Adaptive-router promotion uses the normal benchmark output directory as its
primary evidence surface. For any router default-switch discussion, review the
same dated artifact set across these files together:

- `results.json` for per-case `router_arm_id`, `router_shadow_arm_id`,
  confidence fields, and downgrade/fallback `decision_trace` events
- `summary.json` for `adaptive_router_arm_summary`,
  `adaptive_router_observability_summary`, and
  `adaptive_router_pair_summary`
- `report.md` for the maintainer-facing agreement, per-arm quality, latency,
  fallback, and downgrade rollups
- the matching `latency_slo_summary.json` / `.md` and
  `freeze_regression.json` / `.md` artifacts from the same dated evidence set

Interpret those router artifacts with the following rules:

- compare the candidate switch against current `auto` and fixed `general`, not
  just against shadow agreement rate
- treat high-volume executed-versus-shadow disagreement pairs as blocking until
  their latency and fallback/downgrade behavior are explicitly reviewed
- do not treat a green `summary.json` in isolation as promotion evidence if the
  paired latency/SLO or release-freeze artifacts disagree
- if `retrieval_policy_guard` or `feature_slices_gate` remains `report_only`,
  record the evidence but do not reinterpret it as automatic approval for a
  default switch

## Online-Bandit Opt-In Evidence

For `adaptive_router.online_bandit`, the first question is not "should this
roll out more broadly?" The first question is "do repeated dated artifacts show
the opt-in path is green and rollback-safe?"

Review the same dated artifact set across these files together:

- `results.json` for per-case `router_online_bandit_requested`,
  `router_experiment_enabled`, `router_online_bandit_reason`,
  `router_fallback_reason`, and reward-log case context
- `summary.json` for `adaptive_router_observability_summary`,
  `adaptive_router_pair_summary`, and `reward_log_summary`
- `report.md` for maintainer-facing router disagreement, latency, downgrade,
  and reward-log rollups

Interpret opt-in online-bandit evidence with these rules:

- require at least two dated artifact sets on the same lane/config before any
  broader rollout discussion
- require router observability to be fully visible on the intended lane, not
  just present in one raw JSON fragment
- require reward logging to be active on the same run with non-zero eligible
  and written event counts
- require repeated green task-success, precision, noise, latency, and
  `slo_downgrade_case_rate` evidence versus the current heuristic-executed path
- if the path is still heuristic-fallback-only, treat the artifact as
  evidence-gathering proof rather than rollout approval

## Recovery Hard Cases

`benchmark/cases/recovery_hard_cases.yaml` is the dedicated adaptive-retrieval lane for the four planned hard surfaces:
- `insufficiency`
- `ambiguity`
- `paraphrase_drift`
- `multi_file_recovery`

The file is intentionally separate from `default.yaml` so recovery-path gains stay separable from baseline retrieval quality.
Use the same case file for paired A/B runs:

```bash
ace-lite benchmark run --cases benchmark/cases/recovery_hard_cases.yaml --repo ace-lite-engine --root . --no-deterministic-refine --output artifacts/benchmark/recovery_hard_cases/baseline
ace-lite benchmark run --cases benchmark/cases/recovery_hard_cases.yaml --repo ace-lite-engine --root . --deterministic-refine --output artifacts/benchmark/recovery_hard_cases/adaptive
ace-lite benchmark diff --a artifacts/benchmark/recovery_hard_cases/baseline/results.json --b artifacts/benchmark/recovery_hard_cases/adaptive/results.json --output artifacts/benchmark/recovery_hard_cases/diff
```

Stable `case_id` values and the shared `comparison_lane: adaptive_recovery` tag are the intended join keys when maintainers compare single-pass versus adaptive-path artifacts.
The paired artifacts now expose the bounded refine gate explicitly through `index.candidate_ranking.refine_pass` and benchmark `decision_trace` events targeting `deterministic_refine`, so maintainers can separate "trigger condition met but disabled" from "retry executed and helped".

## Chunking Hard Cases

`benchmark/cases/chunking_hard_cases.yaml` is the Phase 0 chunking lane for
stage-aware miss attribution.

The intent is to distinguish where a miss happened before later chunking or
graph-aware changes are judged:

- `candidate_files_miss`
- `candidate_chunks_miss`
- `source_plan_pack_miss`

Each case carries an oracle file path plus an oracle chunk reference. Benchmark
case evaluation then classifies the miss without changing runtime retrieval
behavior. The resulting label is reported in per-case output and aggregated in
the `Chunk Stage Miss Summary` section.
The two Phase 3 structural probes also carry `retrieval_surface: deep_symbol`,
and `deep_symbol_case_recall` is derived from avoiding a chunk-stage miss rather
than from file-only recall.

The lane now also includes two Phase 3 structural probes so later graph-aware
chunking changes can be judged against fixed hard cases instead of anecdotes:

- `ace-chunking-sibling-shield-04` targets graph-near sibling/shared-parent
  attenuation in `src/ace_lite/chunking/topological_shield.py`
- `ace-chunking-hub-heavy-05` targets hub-heavy suppression pressure in
  `src/ace_lite/chunking/graph_prior.py`

Use the lane like this:

```bash
ace-lite benchmark run --cases benchmark/cases/chunking_hard_cases.yaml --repo ace-lite-engine --root . --output artifacts/benchmark/chunking_hard_cases/latest
ace-lite benchmark report --input artifacts/benchmark/chunking_hard_cases/latest/results.json
```

This lane is report-only in the current phase. It exists to localize file-stage,
raw-chunk-stage, and source-plan-packing misses before any Phase 1 or Phase 3
chunking change is promoted.

Promotion beyond report-only is gated separately by the `topological_shield`
feature slice in `benchmark/matrix/feature_slices.yaml`. That paired slice must
show non-zero attenuation evidence while repeated runs stay deterministic and
latency stays within the configured growth budget.

## Workspace benchmark baseline (decision hub)

```bash
ace-lite workspace benchmark \
  --manifest workspace.yaml \
  --cases-json benchmark/workspace/cases/baseline_cases.json \
  --baseline-json benchmark/workspace/baseline/default.json \
  --fail-on-baseline
```

Artifacts:

- Cases: `benchmark/workspace/cases/baseline_cases.json`
- Baseline thresholds: `benchmark/workspace/baseline/default.json`


