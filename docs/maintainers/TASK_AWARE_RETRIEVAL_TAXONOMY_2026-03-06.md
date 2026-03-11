# Task-Aware Retrieval Taxonomy (2026-03-06)

## Scope

- Goal: define a maintainer-facing intent taxonomy and an offline comparison plan for retrieval policies.
- Non-goal: change the runtime default router in this checkpoint.
- Current runtime policy surface comes from `src/ace_lite/index_stage/policy.py`.

## Current Policy Surface

| Policy | Primary Bias | Repomap | Graph Lookup | Cochange | Docs Bias | Semantic Budget | Best Current Use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `bugfix_test` | failing tests, error traces, worktree-local repair | off | off | off | low | `80 ms` | bugfix and regression repair |
| `doc_intent` | docs and architecture explanation | on (`graph_seeded`) | off | off | highest | `120 ms` | explain and architecture walkthroughs |
| `feature` | cross-file implementation and dependency expansion | on (`graph_seeded`) | on | on when enabled | medium | `110 ms` | new feature work |
| `refactor` | structural boundaries and symbol graph coverage | on (`graph_seeded`) | on | on when enabled | medium-low | `100 ms` | refactor and API reshaping |
| `general` | balanced default, definitions, broad code lookup | on (`graph_seeded`) | on | off | off | `90 ms` | default fallback and symbol lookup |
| `auto` | heuristic router over the above policies | delegated | delegated | delegated | delegated | delegated | control path, not a standalone retrieval shape |

## Intent Taxonomy

| Intent | User Shape | Primary Offline Candidate | Comparison Policy | Runtime Fallback | Current Evidence |
| --- | --- | --- | --- | --- | --- |
| `bugfix` | fix a failing test, exception, regression, stacktrace | `bugfix_test` | `general` | `general` if bugfix evidence is missing | `benchmark/cases/scenarios/real_world.yaml` bugfix session, `tests/unit/test_index_policy.py` troubleshoot routing |
| `refactor` | rename, split, cleanup, boundary changes, API reshaping | `refactor` | `general` | `general` if graph-heavy retrieval raises latency/noise | `benchmark/cases/scenarios/real_world.yaml` refactor session, current policy guard infrastructure |
| `explain` | explain architecture, mechanism, workflow, why/how questions | `doc_intent` | `general` | `general` when the query is actually a definition/where-is lookup | `tests/unit/test_index_policy.py` doc-intent routing, `benchmark/matrix/external_howwhy.yaml` |
| `feature` | add, implement, create, extend behavior | `feature` | `general` | `general` if policy-level SLO guardrails regress | `benchmark/cases/scenarios/real_world.yaml` feature session, retrieval-policy summaries in matrix/freeze reporting |
| `perf` | reduce latency, trim budgets, optimize hotspots, profiling-driven changes | `refactor` | `general` | `general` until the perf-routing benchmark lane passes | `benchmark/matrix/feature_slices.yaml` `perf_routing`, latency/SLO checkpoints and trend reports |

## Offline Comparison Table

| Intent | What To Measure Offline | Expected Win Condition | Main Risk | Required Guardrails Before Promotion |
| --- | --- | --- | --- | --- |
| `bugfix` | task success, validation tests, retrieval-task gap, noise | `bugfix_test` beats `general` on task success without worse noise | overfitting to tests and missing implementation files | release `policy_guard`, concept/e2e gates, robustness slices |
| `refactor` | dependency recall, candidate breadth, graph usefulness, total latency | `refactor` improves structure-aware retrieval without large latency or downgrade growth | excessive graph expansion and noisy neighbors | latency/SLO breakdown, trend report, perturbation stability |
| `explain` | docs hit rate, precision/noise, chunk sufficiency, architecture-answer quality | `doc_intent` improves explanation-oriented retrieval over `general` | docs overweight hiding actual source files | external how/why matrix, concept benchmarks, latency/SLO report |
| `feature` | task success, dependency recall, chunk hit, policy-level latency/downgrade | `feature` improves implementation coverage over `general` | graph lookup or repomap budgets drifting upward | retrieval `policy_guard`, latency/SLO breakdown, trend report |
| `perf` | hotspot localization accuracy, total/index p95, downgrade-case rate | `refactor` beats or matches `general` on hotspot retrieval without worse SLOs | optimizing retrieval policy before the perf lane is green | `perf_routing` feature slice, latency/SLO trend with full-fidelity baseline |

## Explicit Fallback Rules

- `auto` remains unchanged in this checkpoint.
- `general` is the universal runtime fallback whenever a task-aware candidate lacks benchmark evidence or fails policy-level SLO guardrails.
- `explain` queries fall back to `general` when the actual user ask is "where is X defined/implemented" instead of a narrative explanation request.
- `perf` stays manual and offline-only until the `perf_routing` benchmark lane compares `refactor` against `general` without worse latency or SLO downgrade evidence; no automatic promotion of a perf-specific route happens from this doc alone.

## Evidence Sources To Reuse

- Policy semantics: `src/ace_lite/index_stage/policy.py`
- Auto-routing tests: `tests/unit/test_index_policy.py`
- Scenario-level task checks: `benchmark/cases/scenarios/real_world.yaml`
- Explain-oriented external benchmark: `benchmark/matrix/external_howwhy.yaml`
- Policy-level guardrails: `benchmark/matrix/repos.yaml` `freeze.policy_guard`
- Latency/SLO interpretation: `docs/maintainers/BENCHMARKING.md` and `docs/maintainers/RELEASING.md`

## Rollout Constraint

- No default routing changes ship from this checkpoint.
- A future runtime change must first show:
  - benchmark evidence for the intent-specific candidate versus `general`
  - no regression in the current robustness slices
  - acceptable report-only latency/SLO drift against a full-fidelity prior baseline
