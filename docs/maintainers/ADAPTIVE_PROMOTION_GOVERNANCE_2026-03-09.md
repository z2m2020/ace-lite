Updated: 2026-03-10
Related Tasks: `FP08`, `Y04`, `Y19`

## Purpose

This document is the canonical promotion matrix for adaptive retrieval features
in ACE-Lite.

Use it to answer five questions before any adaptive behavior is promoted,
expanded, or rejected:

1. What triggers the path?
2. What hard budget or bounded scope keeps it safe?
3. What is the fallback when evidence or runtime conditions are weak?
4. Which benchmark lane or release gate is the source of truth?
5. Is the current decision `promote`, `stay_experimental`, or `reject`?

## Decision States

- `promote`: the path may stay enabled by default or may be treated as the
  documented default shape for its scope because paired evidence is already
  green and rollback is explicit.
- `stay_experimental`: the path is opt-in, report-only, or offline-only.
  Evidence may exist, but it is not yet strong enough for a default-path switch.
- `reject`: the path conflicts with current architectural constraints and should
  not be promoted in the current roadmap.

## Global Rules

1. No adaptive path is promotable without a named evidence surface.
2. Benchmark wins are not enough on their own; promotion must also preserve
   task success, precision, noise, and relevant latency or downgrade budgets.
3. If a path lacks a clean fallback to the deterministic baseline, it stays
   experimental.
4. Release-freeze interpretation must be explicit. Report-only evidence cannot
   be restated later as if it were already a blocking release gate.
5. A later regression rolls the path back to its fallback rather than justifying
   the drift with anecdotes.

## Router Default-Switch Criteria

A router default switch means changing the executed default away from the current
heuristic `auto` behavior for normal runs. Shadow-only evidence and one-off
benchmark wins are not enough.

Any proposal to switch the default router must satisfy all of the following:

1. Evidence must come from at least two dated artifact sets on the same arm set,
   benchmark lane, and release-freeze config. One ad hoc benchmark run is not a
   promotion surface.
2. `adaptive_router_observability_summary` must show the candidate default is
   non-regressed versus current `auto` on task success, MRR, precision, and
   noise across the maintained benchmark suite.
3. The same evidence set must still show positive headroom versus fixed
   `general`; if the candidate arm cannot beat `general`, there is no case for a
   broader default switch.
4. `adaptive_router_pair_summary` must make disagreement clusters explicit, and
   any high-volume executed-versus-shadow pair must not show worse latency,
   fallback, or downgrade behavior than the current executed path.
5. `latency_slo_summary` and its dated trend report must not show a new
   regression cluster for total latency, index latency, or
   `slo_downgrade_case_rate`.
6. Per-arm fallback and downgrade signals
   (`fallback_case_rate`, `downgrade_case_rate`, `fallback_targets`,
   `downgrade_targets`) must stay bounded and rollback-safe; unexplained new
   degradation targets block promotion.
7. Benchmark, trace, and stage-tag artifacts must still expose executed arm,
   shadow arm, confidence, and fallback metadata so rollback remains observable.
8. Release-freeze evidence must stay aligned: `feature_slices_gate` and
   `retrieval_policy_guard` may still be report-only, but the candidate switch
   must not introduce new freeze regressions or reinterpret report-only lanes as
   already enforced approval.

## Chunk-Guard Enforce Promotion Criteria

A broader `chunk_guard.mode=enforce` rollout means moving beyond benchmark-only
or explicit local experimentation into a more generally enabled retrieval path.
Green enforce runs are not enough on their own.

Any proposal to broaden enforce-mode chunk filtering must satisfy all of the
following:

1. The earlier report-only evidence surface must already be green. Treat the
   `stale_majority` report-only lane as the precondition, not as optional
   historical context that can be skipped once enforce exists.
2. A dated controlled benchmark artifact set must show both `stale_majority`
   and lexical `perturbation` slices green with the same `chunk_guard` knobs
   and `chunk_guard.mode=enforce`.
3. The same evidence set must keep stale-majority latency within the configured
   growth budget while task success, precision, and noise stay non-regressed.
   Harmless lexical perturbations must also stay non-regressed under the same
   enforce configuration.
4. Determinism evidence must remain green: permutation-level chunk ordering and
   `index -> source_plan` integration tests must still prove stable retained
   subsets, fail-open fallback when prerequisites are missing, and no hidden
   output drift beyond the intended filtered-list change.
5. Release interpretation must remain strict: feature-slice or freeze artifacts
   may supply evidence, but report-only gates still do not by themselves
   authorize a broader default-path switch.

## Online-Bandit Broader-Rollout Criteria

A broader online-bandit rollout discussion means considering anything beyond the
current limited opt-in, fallback-safe benchmark path. Observability alone is not
enough.

Any broader rollout discussion for `adaptive_router.online_bandit` must satisfy
all of the following:

1. Evidence must come from at least two dated limited opt-in artifact sets on
   the same benchmark lane, arm set, and reward-log configuration. One dated
   checkpoint only proves the instrumentation path exists.
2. Each evidence set must show router observability fully materialized on the
   intended lane: `adaptive_router_observability_summary.enabled_case_rate = 1`
   and visible `router_online_bandit_requested`,
   `router_experiment_enabled`, `router_online_bandit_reason`, and
   `router_fallback_reason` fields in the dated `results.json` / `report.md`.
3. Each evidence set must also show reward logging active on the same run with
   non-zero eligible and written event counts; a bandit discussion without
   matching reward telemetry is blocked.
4. Repeated evidence must be green versus the current executed heuristic path
   on task success, MRR, precision, noise, total latency, index latency, and
   `slo_downgrade_case_rate`. One green run and one degraded run is not enough.
5. Repeated evidence must remain rollback-safe: fallback and downgrade metadata
   must stay explicit, and no run may require hidden state or ambiguous runtime
   behavior to explain the result.
6. If the bandit path is still report-only or heuristic-fallback-only, treat
   that state as evidence gathering rather than approval. Broader rollout
   discussion stays blocked until the repeated green requirement is met.

## Governance Matrix

| Adaptive path | Trigger | Budget / bounded scope | Fallback | Evidence lane | Promotion rule | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `deterministic_refine_enabled` | Explicit refine-pass trigger on hard retrieval cases; benchmark `decision_trace` shows whether retry was skipped or executed | One bounded deterministic refine pass; exact-search and ranking budgets remain capped | Skip the refine pass and keep first-pass retrieval/source-plan output | `benchmark/cases/recovery_hard_cases.yaml` with `comparison_lane: adaptive_recovery`, plus `benchmark diff` on paired baseline/adaptive artifacts | Keep promoted only while the adaptive-recovery lane improves or matches hard-case task success without precision, noise, latency, or SLO regressions | `promote` |
| `precomputed_skills_routing_enabled` | Skills can be scored from manifest metadata before markdown hydration | Skills token budget, route latency, hydration latency, and budget-exhaustion signals remain bounded and benchmark-visible | Disable precomputed routing and fall back to same-stage routing plus normal hydration | The paired `FP03` / `Y01` benchmark evidence lane, plus ongoing tracking from `skills_precomputed_route_ratio`, `skills_route_latency_p95_ms`, `skills_hydration_latency_p95_ms`, `skills_token_budget_used_mean`, and the `perf_routing` feature slice | Promoted because paired evidence already closed with non-regressed task success, precision, noise, latency, and skills-budget metrics; roll back if those regress | `promote` |
| `plan_replay_cache.enabled` | Exact same normalized query plus repo fingerprint, policy/budget fingerprint, upstream fingerprints, and current repo-input content hash | Local-only cache lookup/store; source-plan-only replay; fail-open on miss, drift, or invalid payload; default remains off | Run the normal deterministic pipeline and optionally store a new replay entry | Standard benchmark/report artifacts via `plan_replay_cache_enabled_ratio`, `plan_replay_cache_hit_ratio`, and `plan_replay_cache_stale_hit_safe_ratio`; release interpretation remains report-only | Stay experimental until repeated benchmark runs show useful hit-rate evidence and safe invalidation behavior without masking stale results | `stay_experimental` |
| `memory.feedback` replay tuning | Explicit replayed feedback corpus and feedback boosting enabled for the run | `boost_per_select`, `max_boost`, `decay_days`, and `max_entries` must stay bounded and attributable | Disable feedback boosting and use the baseline memory path | `benchmark/matrix/feature_slices.yaml` `feedback` slice plus `freeze.memory_gate` | Promote only if the feedback slice improves precision/noise and the release memory gate remains green; host anecdotes are not enough | `stay_experimental` |
| Time-windowed memory (`temporal`) | Explicit start/end time window is requested for notes replay | The window must be explicit and benchmarked; filtered-out notes must stay visible in observability | Remove the time window and use the baseline memory path | `benchmark/matrix/feature_slices.yaml` `temporal` slice plus `freeze.memory_gate` | Promote only if time-windowed memory improves precision/noise without starving useful notes or weakening release memory evidence | `stay_experimental` |
| Optional late-interaction provider path | Explicit provider opt-in for the heavier rerank path | Provider latency, rerank ratio, and fallback ratio must stay inside the configured thresholds; fail-open remains mandatory | Return to the default lightweight rerank path with `embedding_fail_open` behavior | `benchmark/matrix/feature_slices.yaml` `late_interaction` slice plus `freeze.embedding_gate` | Promote only if the provider lane stays non-regressed on precision/noise and the embedding gate remains green | `stay_experimental` |
| `chunk.topological_shield` report-only attenuation | Explicit chunking config enables topological shield while base diversity scoring remains unchanged | Report-only first; attenuation must stay bounded by `max_attenuation`, preserve deterministic repeated outputs, and leave latency within the named slice thresholds | Disable topological shield and keep the existing diversity penalty unchanged | `benchmark/cases/chunking_hard_cases.yaml` plus `benchmark/matrix/feature_slices.yaml` `topological_shield` slice | Promote only if the hard-case lane shows non-zero structural attenuation evidence and the paired feature slice stays green for task success, precision, noise, latency, and repeated-run determinism | `stay_experimental` |
| Perf-oriented or task-aware routing beyond `general` | Offline policy comparison or future task-aware router chooses a non-default arm for perf-shaped queries | Total/index latency, skills latency, and downgrade-case rate remain bounded; runtime fallback stays explicit | Use `general` as the universal fallback policy | `benchmark/matrix/feature_slices.yaml` `perf_routing`, `freeze.policy_guard`, and dated latency/SLO trend reports | Remains manual/offline until the perf lane matches or beats `general` without worse latency or SLO-downgrade evidence | `stay_experimental` |
| Future shadow / learned router arms | Shadow-only arm computation after heuristic routing is already instrumented | No blocking writes on the main plan path; reward logging must stay append-only and opt-in | Executed arm stays heuristic/default while shadow or learned outputs are only observed | `adaptive_router_observability_summary`, `adaptive_router_pair_summary`, `latency_slo_summary`, `freeze.policy_guard`, and `ArmSweeper` / oracle-relabel evidence | No default switch before every rule in `Router Default-Switch Criteria` is satisfied, including non-regression versus `auto`, positive headroom versus `general`, bounded latency/SLO drift, bounded fallback/downgrade rates, and rollback-safe observability | `stay_experimental` |
| `adaptive_router.online_bandit` limited opt-in experiments | Explicit benchmark or local opt-in enables `adaptive_router.online_bandit.enabled` and `experiment_enabled` | Keep the path opt-in and rollback-safe; reward logging must be active on the same dated run; broader discussion requires repeated green evidence on the same lane/config | Fall back to the current heuristic-executed router path and keep exploration/fallback metadata explicit in artifacts | Dated `results.json`, `summary.json`, `report.md`, and reward-log output from the same opt-in lane | Apply every rule in `Online-Bandit Broader-Rollout Criteria`; until then keep online-bandit discussion limited to evidence gathering rather than rollout planning | `stay_experimental` |
| Future chunk filtering (`chunk_guard`, `SHARS-lite`) | Chunk-majority or stale-majority evidence suggests pack-level cleanup | Report-only evidence must already be green; benchmark-only enforce runs must keep identity/order determinism and latency bounded | Keep the current chunk packer with no filtering | `benchmark/matrix/feature_slices.yaml` `stale_majority` and `perturbation`, plus chunk-guard determinism/integration regressions and release `feature_slices_gate` evidence | Apply every rule in `Chunk-Guard Enforce Promotion Criteria`; until then keep filtering off the default path even if one enforce artifact set is green | `stay_experimental` |

## Rejected For This Roadmap

These ideas are explicitly out of scope for the current roadmap, even if they
look attractive in isolated demos:

- Generic LLM rewrite loops or LangGraph-style open-ended retry chains
- Default-on learned routers or online bandits before shadow evidence and
  reward logging are in place
- Enforced chunk filtering before report-only telemetry and hard-case slices are
  green
- Any adaptive default-path switch justified only by anecdotes or a single dated
  artifact

These are rejected because ACE-Lite still optimizes for deterministic local
execution, explicit fallbacks, and evidence-backed promotion.

## Release Interpretation

- `promote` paths may stay enabled by default, but they still remain subject to
  their paired benchmark lane and existing release-freeze evidence.
- `stay_experimental` paths must keep their opt-in, offline-only, or report-only
  status until the listed evidence lane is repeatedly green.
- `reject` paths should not appear in release proposals except as explicit
  non-goals.

## Canonical References

- Benchmark lanes and release evidence: `docs/maintainers/BENCHMARKING.md`
- Release interpretation and freeze workflow: `docs/maintainers/RELEASING.md`
- Retrieval-policy fallback rules: `docs/maintainers/TASK_AWARE_RETRIEVAL_TAXONOMY_2026-03-06.md`
- Benchmark lanes and dated evidence should be treated as the source of truth for promotion decisions; do not rely on private planning documents that are not part of the public branch.
