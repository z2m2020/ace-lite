# Long-Term Memory and Feedback Loop Requirements

## 1. Document Role

Date: `2026-03-20`

This document is no longer a pure greenfield design note.
It is a reality-aligned requirements and phase-tracking document for the ACE-Lite long-term memory and feedback loop.

It serves three purposes:

1. describe the target product and engineering loop
2. record what is already implemented in the current codebase
3. isolate the remaining Phase 2 backlog so future work does not mix completed foundations with deferred metrics

Status labels used below:

- `implemented`: shipped in the current codebase and covered by runtime, CLI, MCP, benchmark, or tests
- `partial`: the main path exists, but the capability is not yet complete or not yet fully measured
- `deferred`: still a design requirement or backlog item, not a current system capability

## 2. Background

The current ACE-Lite primary pipeline remains:

`memory -> index -> repomap -> augment -> skills -> source_plan -> validation`

The existing system already provides these baseline capabilities:

- `MemoryProvider` V2 contract with `search_compact()` and `fetch()`
- memory-stage temporal filtering, timeline handling, recency boost, namespace routing, and postprocessing
- `local_notes`, `profile_store`, `selection_feedback`, and durable preference capture
- benchmark summaries, regression gates, runtime stats, and MCP/CLI entry points

As of `2026-03-20`, the main gap is no longer "whether a memory or feedback interface exists".
The main remaining gaps are:

- long-term memory evaluation is only partially complete
- the developer auto-capture taxonomy is narrower than originally planned
- several advanced metrics and issue lifecycle metrics are still missing
- the original benchmark lane design in this document no longer matches the actual benchmark case taxonomy

## 3. Goals

This capability area still aims to unify four loops into one evolvable product and engineering system:

1. Long-term memory: persist high-value observations, facts, and lightweight relation edges across sessions, and use them as first-class retrieval signals during `ace_plan`.
2. User issue reporting: allow real users to submit structured problem reports that developers can track, triage, attribute, and convert into benchmark and optimization work.
3. Developer inner-loop feedback: allow local dogfooding failures, degradations, and manual corrections to flow back into development decisions automatically or semi-automatically.
4. Evaluation and validation: make gains, noise, replay stability, and operational cost measurable and regression-gated.

## 4. Design Principles

### 4.1 First-Class Capability, Not a Sidecar Primary Path

- Long-term memory must stay integrated into the existing `memory` stage as a first-class capability.
- It should not be reintroduced as a separate primary retrieval path.

### 4.2 Preserve Existing Public Contracts

- Do not break the base `MemoryProvider` contract.
- Keep public CLI, MCP, benchmark, schema, and replay contracts backward-compatible whenever practical.

### 4.3 Local-First and Deterministic by Default

- The first implementation remains local `SQLite + FTS5`.
- Retrieval and write paths should support `as_of` or an equivalent temporal boundary to reduce replay drift and future-information leakage.

### 4.4 Observation Before Fact

- Raw events should first be captured as `observation` records.
- Facts should remain a traceable, supersedable, and expirable derived layer.

### 4.5 Closed Loops Over Passive Storage

- Feedback must flow back into benchmark cases, long-term memory observations and facts, and developer prioritization.
- The system should not become a passive warehouse with no optimization feedback path.

### 4.6 Phase 1 Contract Freeze

The first pass of `memory.long_term.*` is intentionally narrow and should remain stable:

- `enabled`
- `path`
- `top_n`
- `token_budget`
- `write_enabled`
- `as_of_enabled`

The default path is:

- `context-map/long_term_memory.db`

The first schema versions are:

- `long_term_observation_v1`
- `long_term_fact_v1`

The preserved scope fields are:

- `repo`
- `root`
- `namespace`
- `user_id`
- `profile_key`
- `as_of`

## 5. Current Implementation Snapshot

### 5.1 Long-Term Memory Core

Status: `implemented`

Implemented in the current codebase:

- `LongTermMemoryStore`
- `LongTermMemoryProvider`
- `LongTermMemoryCaptureService`
- repo-local SQLite storage under `context-map/long_term_memory.db`
- observation and fact schema helpers
- `as_of` filtering on the main retrieval path
- integration with the memory-stage provider chain

Current limitation:

- the system is intentionally conservative and does not yet attempt a richer graph-evolution or advanced attribution model

### 5.2 User Issue Reporting

Status: `implemented`

Implemented in the current codebase:

- structured issue reporting through CLI
- structured issue reporting through MCP
- issue persistence and listing
- issue export to benchmark case YAML
- issue resolution from stored developer fixes
- lifecycle persistence with issue-to-plan or issue-to-fix linkage

Current limitation:

- the issue lifecycle is operational, and benchmark/report already summarize `issue_report_time_to_fix_hours_mean`
- reopen-oriented lifecycle metrics such as `issue_reopen_rate` and `time_to_triage` still do not have a stable event source

### 5.3 Developer Inner-Loop Feedback

Status: `partial`

Implemented in the current codebase:

- `dev_issue` and `dev_fix` persistence
- CLI and MCP entry points for developer feedback
- runtime event promotion into developer issues
- developer fix application back into issue resolution
- capture failure is non-blocking for the main pipeline

Partially implemented:

- runtime degradation and fallback reasons already exist and can feed feedback surfaces
- selection feedback can be written back into long-term memory
- developer feedback can be linked to issue resolution and later benchmark conversion
- developer feedback reason codes now pass through a shared normalization taxonomy with canonical reason codes, reason families, and capture classes
- runtime status and top-pain summaries now expose the same normalized reason taxonomy fields
- developer feedback summaries now expose `resolved_issue_count`, `linked_fix_issue_count`, `dev_issue_to_fix_rate`, `issue_time_to_fix_case_count`, and `issue_time_to_fix_hours_mean`
- runtime-originated `evidence_insufficient` and `noisy_hit` signals now flow from source-plan evidence and validation coverage signals into `RuntimeInvocationStats.degraded_reason_codes`
- runtime-originated `repeated_retry` now flows from `agent_loop.stop_reason=max_iterations`, and generic `latency_budget_exceeded` now flows from retrieval time-budget overruns in addition to the stage-specific degraded reasons
- generic `latency_budget_exceeded` now also covers parallel docs/worktree timeout and `xref_budget_exhausted` paths when runtime degraded reasons are materialized
- runtime-originated `skills_budget_exhausted` now flows from `skills` stage token-budget exhaustion into durable stats and downstream runtime status surfaces

Still missing:

- a fully normalized auto-capture taxonomy for all planned cases
- a runtime-originated `manual_override` signal; current `manual_override` remains a normalization target for explicit human-recorded issue/fix flows rather than an automatically emitted runtime event
- first-class metrics for manual override frequency, retry clustering, and end-to-end developer issue capture coverage
- automatic exporter or case-generation coverage that stamps richer developer issue/fix lifecycle metadata into all feedback benchmark cases; issue-report benchmark export now carries `attachments` inside the exported `issue_report` payload and derives minimal `dev_feedback` metadata from resolved reports with `dev-fix://...` attachments, benchmark case loading now normalizes the same metadata through a shared contract before runner evaluation, the shared contract also restores `created_at` and `resolved_at` from `issue_report` for recognized issue-capture and issue-resolution lanes when explicit `dev_feedback` is absent, and benchmark row assembly still keeps the same derivation logic as a fail-open fallback, but broader generic case generation still lacks a universal derivation contract

### 5.4 Evaluation and Validation

Status: `partial`

Implemented in the current codebase:

- benchmark case classes for:
  - `memory-neutral`
  - `memory-helpful`
  - `memory-harmful-negative-control`
  - `time-sensitive`
  - `cross-session-recovery`
- feedback-oriented benchmark lanes already in use:
  - `issue_report_feedback`
  - `dev_feedback_resolution`
- benchmark summaries for core long-term memory and feedback metrics
- regression checks for selected long-term memory and feedback metrics
- runtime memory health summary
- long-term memory explainability summary

Still missing:

- the originally proposed quartet of comparison lanes:
  - `baseline_none`
  - `ltm_readonly_seeded`
  - `ltm_readwrite_sequence`
  - `ltm_ablation`
- a dedicated run-mode or A/B benchmark dimension that would make those lanes meaningful
- full metric coverage for advanced long-term memory and issue lifecycle reporting

Important note:

- the current benchmark system uses `comparison_lane` mainly as a case taxonomy label
- the original four-lane design should only be revived if a true baseline-vs-variant execution model is added
- until then, those four names should be treated as `deferred`, not as current benchmark requirements

## 6. Scope

### 6.1 In Scope

- long-term memory storage, provider, and capture or ingestion pipeline
- user issue-report templates, persistence, aggregation, and developer consumption paths
- developer inner-loop automatic capture and manual confirmation paths
- benchmark, summary, and regression metric expansion for long-term memory and feedback
- CLI, MCP, runtime status, and runtime doctor surfaces for feedback and observability

### 6.2 Out of Scope for Phase 1

- no external graph store such as Neo4j or JanusGraph
- no full Graphiti-style property graph evolution
- no full web UI
- no direct mutation of public `index` or `source_plan` contracts beyond the existing memory-stage integration

## 7. Architecture

### 7.1 Storage Layer

Status: `implemented`

The current storage path is:

- `context-map/long_term_memory.db`

Core persisted concepts already exist across the codebase:

- observations
- facts
- lightweight relation or attribution payloads
- issue reports
- developer feedback records

The originally proposed `retrieval_log`, `issue_links`, and `ingestion_jobs` remain useful architectural concepts, but they should be treated as implementation details or future expansion points rather than mandatory first-phase tables.

### 7.2 Provider Layer

Status: `implemented`

Requirements satisfied by the current provider layer:

- continue exposing `search_compact()` and `fetch()`
- support repo, namespace, user, and temporal filtering
- integrate into the existing memory-stage retrieval flow

Still deferred:

- stronger graph-neighborhood expansion beyond the current lightweight payload approach
- richer retrieval attribution scoring that can be used directly as a benchmark metric

### 7.3 Capture and Ingestion Layer

Status: `partial`

Capture points already present or linked:

- after memory or planning related runs through runtime-linked feedback
- when selection feedback is recorded
- when an issue report is submitted
- when a developer issue or developer fix is recorded
- when a stored developer fix resolves an issue
- when source-plan runtime evidence shows missing direct support, missing validation suggestions, or hint-heavy mixed support that should be surfaced as normalized degraded reasons

Still deferred:

- a broader normalized ingestion path for all runtime degradations
- stronger delayed extraction and consolidation jobs for high-volume event streams

## 8. Data Model Requirements

### 8.1 Observation

Status: `implemented`

Required fields:

- `id`
- `kind`
- `repo`
- `root`
- `namespace`
- `user_id`
- `profile_key`
- `query`
- `payload`
- `observed_at`
- `as_of`
- `source_run_id`
- `severity`
- `status`

### 8.2 Fact

Status: `implemented`

Required fields:

- `id`
- `fact_type`
- `subject`
- `predicate`
- `object`
- `confidence`
- `valid_from`
- `valid_to`
- `superseded_by`
- `derived_from_observation_id`

### 8.3 Issue Report

Status: `implemented`

Required fields for the structured issue-report surface:

- `issue_id`
- `title`
- `category`
- `severity`
- `status`
- `query`
- `repo`
- `root`
- `user_id`
- `profile_key`
- `expected_behavior`
- `actual_behavior`
- `repro_steps`
- `plan_payload_ref`
- `selected_path`
- `occurred_at`
- `resolved_at`
- `resolution_note`

## 9. Integration Points

### 9.1 Already Integrated

- `src/ace_lite/cli_app/orchestrator_factory.py`
  - wires long-term memory options into runtime planning and provider creation
- `src/ace_lite/orchestrator_config.py`
  - exposes `memory.long_term.*` configuration
- `src/ace_lite/orchestrator.py`
  - participates in runtime-linked capture flow through existing orchestration hooks
- `src/ace_lite/pipeline/stages/memory.py`
  - consumes long-term memory results and explainability payloads
- `src/ace_lite/mcp_server/service.py`
  - exposes the MCP surface
- `src/ace_lite/mcp_server/server_tool_registration.py`
  - registers issue and developer feedback tools
- `src/ace_lite/benchmark/*`
  - already includes case schema, metrics, summaries, reporting, and regression checks for the first long-term memory and feedback loop

### 9.2 Still Worth Extending

- stronger runtime-to-feedback linkage with normalized reason codes
- more explicit summary and report surfaces for issue lifecycle timing
- clearer benchmark support for baseline-vs-variant memory execution modes

## 10. Validation Requirements

### 10.1 First-Class Outcome Metrics

Status: `partial`

Stable metrics already used elsewhere in the benchmark stack remain valid:

- `task_success_rate`
- `precision_at_k`
- `noise_rate`
- `evidence_insufficient_rate`
- `latency_p95_ms`
- `memory_latency_p95_ms`

These are not exclusive to long-term memory, but they remain the top-line guardrails for evaluating memory impact.

### 10.2 Long-Term Memory Metrics

Implemented:

- `ltm_hit_ratio`
- `ltm_effective_hit_rate`
- `ltm_false_help_rate`
- `ltm_stale_hit_rate`
- `ltm_replay_drift_rate`
- `ltm_latency_overhead_ms`
- `ltm_selected_count`
- `ltm_explainability_summary`
- `memory_health_summary`

Deferred:

- `ltm_conflict_rate`
- `ltm_cross_session_win_rate`
- `ltm_attributed_success`

Notes:

- `ltm_explainability_summary` is already available in summary and report surfaces, but it is not yet used as a regression gate
- `ltm_latency_overhead_ms` is now derived from benchmark case rows using `memory_latency_ms` and `ltm_plan_constraint_count`
- `runtime_stats_summary.memory_health_summary.memory_stage_latency_ms_avg` remains a useful report-side operational reference, but it is not the primary benchmark aggregation source

### 10.3 Feedback Loop Metrics

Implemented:

- `issue_report_linked_plan_rate`
- `issue_to_benchmark_case_conversion_rate`
- `dev_feedback_resolution_rate`
- `issue_report_time_to_fix_hours_mean`
- `dev_issue_to_fix_rate`
- `resolved_issue_count`
- `linked_fix_issue_count`
- `issue_time_to_fix_case_count`
- `issue_time_to_fix_hours_mean`

Deferred:

- `issue_report_submission_rate`
- `issue_reopen_rate`
- `time_to_triage`
- `post_fix_regression_rate`
- `dev_issue_capture_rate`
- `manual_override_rate`

Notes:

- `dev_issue_to_fix_rate` is now implemented across `feedback summary`, `runtime stats`, `runtime status`, `runtime doctor`, benchmark aggregation, benchmark report, and regression gating
- benchmark-side `dev_issue_to_fix_rate` is currently sourced from `case.dev_feedback.*` metadata on feedback benchmark cases; issue-report export now auto-derives that block for resolved reports with `dev-fix://...` attachments, but there is still no global runtime-store join or fully automatic backfill for all benchmark cases
- `resolved_issue_count`, `linked_fix_issue_count`, and developer-side `issue_time_to_fix_*` are currently benchmark or report observability fields, but they are not all individual regression gates

### 10.4 Validation Gates

Status: `partial`

The current regression layer already gates a subset of the intended requirements:

- memory-helpful success should not regress materially
- `ltm_false_help_rate` should stay bounded
- `ltm_stale_hit_rate` should stay bounded
- replay-drift related safety signals should stay bounded
- issue and developer feedback conversion metrics should not regress materially

Still missing:

- an explicit latency overhead gate for long-term memory
- a gate for explainability or attribution quality
- lifecycle-quality gates around triage, reopen, and fix timing

## 11. Main Risks

The original risks still stand:

- memory contamination: incorrect observations are promoted into facts
- replay distortion: missing `as_of` causes result drift
- future-information leakage: benchmark replay reads future facts
- more hits but lower quality: memory increases hit rate while hurting precision and noise
- write-path bloat: excessive capture causes database growth and analysis degradation
- developer-feedback flooding: too many auto-captured events drown out high-value signals

Additional current risk:

- documentation drift can now be as damaging as implementation gaps, because several Phase 1 capabilities already shipped while the document still reads like they are pending

## 12. Success Criteria

This capability area is successful when:

1. long-term memory stays integrated into the main pipeline without breaking the existing memory contract
2. user issue reporting and developer inner-loop feedback persist in structured form and can be linked to concrete runs
3. real issues can be converted into benchmark cases and used in regression analysis
4. benchmark results can answer whether long-term memory is helpful or simply injecting noise
5. developers can prioritize work quickly based on issue clusters, severity, frequency, and benchmark impact
6. the remaining Phase 2 metrics are implemented without reopening the stable Phase 1 contracts

## 13. Phase 2 Backlog

Recommended next iteration order:

1. decide whether `ltm_latency_overhead_ms` should also become a regression gate, and whether it needs alignment reporting against `runtime_stats_summary.memory_health_summary.memory_stage_latency_ms_avg`
2. extend the normalized developer auto-capture taxonomy to more runtime-originated signals so timeout, downgrade, repeated retry, manual override, and additional latency-budget style events are emitted consistently rather than only summarized consistently
3. add issue lifecycle metrics such as `time_to_triage` and `issue_reopen_rate`, and only add them after a stable triage or reopen event source exists
4. add coverage metrics such as `dev_issue_capture_rate`, and improve exporter or case-generation coverage so `dev_issue_to_fix_rate` and related lifecycle counts are stamped automatically rather than manually carried in case metadata
5. decide whether the original four comparison lanes should be implemented as a new benchmark execution dimension rather than as `comparison_lane` labels
6. add stronger explainability and attribution quality signals only after the metric source data is stable

2026-03-21 incremental note:

- item 1 is now partially resolved: `ltm_latency_overhead_ms` is promoted into the regression checker using the existing `latency_growth_factor`, while report and summary surfaces now expose a dedicated alignment summary against `runtime_stats_summary.memory_health_summary.memory_stage_latency_ms_avg`
- the remaining open part of item 1 is whether the latency-overhead gate should eventually receive its own dedicated threshold knob instead of sharing the general latency growth factor
- item 2 is now partially addressed for runtime-originated degradation capture: `chunk_guard_fallback`, `validation_timeout`, and `validation_apply_failed` are emitted as canonical degraded reason codes, validation stage tags now expose sandbox apply reason and timeout state for downstream runtime stats, top-pain summaries, and runtime-to-dev-issue promotion, runtime doctor payloads now also expose canonical doctor-only degraded reasons for `stage_artifact_cache_corrupt`, `git_unavailable`, and `install_drift`, and `runtime doctor --record-runtime-event` can now persist those doctor degraded reasons as an explicit synthetic runtime invocation when the operator intentionally opts in
- the remaining gap in item 2 is that doctor-only and manual-override style signals still do not flow through durable runtime invocation facts by default and do not yet participate in a dedicated first-class doctor-event model; current persistence is explicit opt-in and still shares the generic runtime invocation contract
- item 4 is now partially addressed through benchmark coverage for runtime-promoted developer issues: `feedback_loop_cases.yaml` includes CLI/MCP runtime issue-capture cases, summary/report surfaces expose `dev_issue_capture_rate`, exported issue-report benchmark cases now preserve `attachments` inside `issue_report`, `benchmark.runner.load_cases()` normalizes `dev_feedback` metadata through a shared contract at load time, and `case_evaluation_row` still auto-derives the same lifecycle counters as a fail-open fallback
- the remaining gap in item 4 is a broader universal derivation contract so `dev_issue_to_fix_rate` and related lifecycle counters no longer depend on manually curated metadata outside the currently recognized issue-report attachment patterns and feedback-surface patterns

## 14. Near-Term Recommendations

Recommended immediate working order:

1. keep the current Phase 1 contracts stable
2. treat this document as the source of truth for what is implemented, partial, and deferred
3. prioritize metrics and observability gaps over large architectural rewrites
4. only revive the original A/B lane design if the benchmark runner gains a true variant-execution model
