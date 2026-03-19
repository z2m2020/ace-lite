# Long-Term Memory and Feedback Loop Requirements

## 1. Background

Date: `2026-03-19`

The current ACE-Lite primary pipeline is:

`memory -> index -> repomap -> augment -> skills -> source_plan -> validation`

The existing system already provides these baseline capabilities:

- `MemoryProvider` V2 contract: `search_compact()` + `fetch()`
- memory-stage temporal filtering, timeline handling, recency boost, namespace routing, and postprocessing
- `local_notes`, `profile_store`, `selection_feedback`, and durable preference capture
- benchmark summaries, regression gates, runtime stats, and MCP/CLI entry points

The main gap is no longer "whether a memory interface exists", but rather:

- there is no durable, writable, replayable, and measurable long-term memory layer
- there is no structured issue-reporting surface for real user problems
- there is no tight developer dogfooding feedback loop that feeds directly into optimization decisions
- there is no dedicated evaluation loop for the benefits and risks of long-term memory

## 2. Goals

This requirement set aims to unify four capability areas into one evolvable product and engineering loop:

1. Long-term memory: allow ACE-Lite to persist high-value observations, facts, and lightweight graph edges across sessions, and use them as first-class retrieval signals during `ace_plan`.
2. User issue reporting: allow real users to submit structured problem reports that developers can track, triage, attribute, and convert into benchmark and optimization work.
3. Developer inner-loop feedback: allow local dogfooding failures, degradations, and manual corrections to flow back into development decisions automatically or semi-automatically.
4. Evaluation and validation: make the gains, noise, latency overhead, and replay stability of long-term memory and feedback systems measurable, comparable, and regression-gated.

## 3. Design Principles

### 3.1 First-Class Capability, Not a Sidecar Primary Path

- Long-term memory must be integrated into the existing `memory` stage as a first-class capability.
- It should not first be implemented as an external MCP plugin or a separate side-route primary retrieval path.

### 3.2 Preserve Existing Public Contracts

- Do not break the base `MemoryProvider` contract.
- Keep public CLI, MCP, benchmark, schema, and replay contracts backward-compatible whenever possible.

### 3.3 Local-First and Deterministic by Default

- The first implementation should prioritize local `SQLite + FTS5`.
- All retrieval and write paths should support `as_of` or an equivalent temporal boundary to prevent replay drift and future-information leakage.

### 3.4 Observation Before Fact

- Raw events should first be captured as `observation` records.
- Facts should be a traceable, supersedable, and expirable derived layer.

### 3.5 Closed Loops Over Isolated Features

- Every feedback capability must flow back into:
  - benchmark cases
  - long-term memory observations and facts
  - developer prioritization and optimization decisions
- The system must not become a passive warehouse that only collects data.

### 3.6 2026-03-19 Phase 1 Contract Freeze

- The first pass of `memory.long_term.*` should freeze only the minimal contract, without prematurely binding to store or provider internals:
  - `enabled`
  - `path`
  - `top_n`
  - `token_budget`
  - `write_enabled`
  - `as_of_enabled`
- The default path is fixed to `context-map/long_term_memory.db`.
- Observation and fact schemas should be frozen through dedicated helpers, without directly mutating the existing public `memory -> augment` payload.
- The first pass must preserve these scoping fields:
  - `repo`
  - `root`
  - `namespace`
  - `user_id`
  - `profile_key`
  - `as_of`
- The first schema versions are:
  - `long_term_observation_v1`
  - `long_term_fact_v1`

## 4. Scope

### 4.1 In Scope

- long-term memory storage, provider, and capture/ingestion pipeline
- user issue-report templates, persistence, aggregation, and developer consumption paths
- developer inner-loop automatic capture and manual confirmation paths
- benchmark, summary, and regression metric expansion for long-term memory and feedback
- CLI, MCP, runtime status, and runtime doctor surfaces for feedback and observability

### 4.2 Out of Scope

- no external graph store such as Neo4j or JanusGraph in the first version
- no full Graphiti-style property graph evolution in the first version
- no full web UI in the first version
- no mutation of public `index` or `source_plan` contracts driven directly by long-term memory in the first version

## 5. Requirement Overview

### 5.1 Long-Term Memory Capability

Add a long-term memory chain compatible with the current memory contract:

`capture/ingestion -> LongTermMemoryStore -> LongTermMemoryProvider -> memory stage`

Requirements:

- the store is based on local `SQLite + FTS5`
- the provider implements `search_compact()` and `fetch()`
- the memory stage can consume long-term memory results without special casing
- it can cooperate with the existing `OpenMemoryMemoryProvider`, `LocalNotesProvider`, and `SelectionFeedbackStore`
- it supports `repo`, `root`, `namespace` or `container_tag`, `user_id`, `profile_key`, and `as_of`

### 5.2 User Issue Reporting

Add a structured `issue_report` capability for collecting real user problems.

Requirements:

- users can submit structured issues via CLI and MCP
- the issue template must include:
  - `title`
  - `query`
  - `repo`
  - `root`
  - `user_id`
  - `profile_key`
  - `occurred_at`
  - `severity`
  - `category`
  - `expected_behavior`
  - `actual_behavior`
  - `repro_steps`
  - `selected_path`
  - `plan_payload_ref`
  - `attachments`
  - `status`
  - `resolution_note`
- each issue should be able to link to a concrete plan, run, or observability snapshot
- issues should support lifecycle states such as `open`, `in_review`, `fixed`, and `rejected`

### 5.3 Developer Inner-Loop Feedback

Local developer usage of ACE-Lite should feed real failures and manual corrections back into development decisions.

Requirements:

- automatic capture should include:
  - `ace_plan` failure, timeout, and downgrade events
  - `evidence_insufficient`
  - `memory_fallback`
  - `noisy_hit`
  - latency budget exceeded
  - repeated retries for the same query
  - developer manual selection of a path different from the top candidate
- manual confirmation should include:
  - raising an automatically captured event to a `dev_issue`
  - recording a `dev_fix` or `resolution_event`
- captured events must include:
  - query, repo, root, and git/version snapshot
  - runtime profile and config fingerprint
  - key observability summaries from memory, index, source_plan, and validation
  - candidate files, selected path, error, and trace references

### 5.4 Evaluation and Validation Loop

The benchmark system must be extended so that long-term memory and feedback can be measured explicitly.

Requirements:

- support these case classes:
  - `memory-neutral`
  - `memory-helpful`
  - `memory-harmful-negative-control`
  - `time-sensitive`
  - `cross-session-recovery`
- support these comparison lanes:
  - `baseline_none`
  - `ltm_readonly_seeded`
  - `ltm_readwrite_sequence`
  - `ltm_ablation`
- support temporal validation through `as_of` replay
- support converting real issues into benchmark cases

## 6. Proposed Architecture

### 6.1 Storage Layer

The first version should use `context-map/long_term_memory.db` or an equivalent local path.

Recommended core tables:

- `observations`
  - raw events such as query, plan, validation, feedback, issue_report, dev_issue, and dev_fix
- `facts`
  - stable facts derived from observations
- `triples`
  - lightweight relation edges as `subject/predicate/object`
- `retrieval_log`
  - records long-term memory hits, selection, and attribution

Optional additional tables:

- `issue_reports`
- `issue_links`
- `ingestion_jobs`

### 6.2 Provider Layer

Add `LongTermMemoryProvider`.

Requirements:

- continue exposing `search_compact()` and `fetch()` externally
- support fused retrieval over observations, facts, and triples internally
- support temporal, namespace, and repo filtering
- support lightweight graph-neighborhood expansion, but only 1-hop and 2-hop in the first version

### 6.3 Capture and Ingestion Layer

Add `LongTermMemoryCaptureService` or an equivalent sink.

Recommended capture points:

- after `source_plan`
- after `validation`
- when `selection_feedback` is recorded
- when an `issue_report` is submitted
- when `dev_issue` or `dev_fix` is recorded

Notes:

- do not embed complex write logic into the provider itself
- move expensive extraction into asynchronous or delayed processing where possible

## 7. Data Model Requirements

### 7.1 Observation

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

### 7.2 Fact

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

### 7.3 Issue Report

Required fields:

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

## 8. Integration Points

Priority integration points:

- `src/ace_lite/cli_app/orchestrator_factory.py`
  - wire in long-term memory providers and feedback channels
- `src/ace_lite/orchestrator_config.py`
  - add `memory.long_term.*`, `feedback.issue_report.*`, and `feedback.dev_loop.*`
- `src/ace_lite/orchestrator.py`
  - connect the capture sink
- `src/ace_lite/pipeline/stages/memory.py`
  - consume long-term memory results and attribution summaries
- `src/ace_lite/mcp_server/service.py`
  - expose new MCP surfaces
- `src/ace_lite/mcp_server/server_tool_registration.py`
  - register issue and developer feedback tools
- `src/ace_lite/benchmark/*`
  - extend case schema, metrics, summaries, and regression checks

## 9. Validation Requirements

### 9.1 First-Class Outcome Metrics

- `task_success_rate`
- `precision_at_k`
- `noise_rate`
- `evidence_insufficient_rate`
- `latency_p95_ms`
- `memory_latency_p95_ms`

### 9.2 Long-Term Memory Metrics

- `ltm_hit_ratio`
- `ltm_effective_hit_rate`
- `ltm_false_help_rate`
- `ltm_stale_hit_rate`
- `ltm_conflict_rate`
- `ltm_cross_session_win_rate`
- `ltm_replay_drift_rate`
- `ltm_latency_overhead_ms`
- `ltm_selected_count`
- `ltm_attributed_success`

### 9.3 Feedback Loop Metrics

- `issue_report_submission_rate`
- `issue_report_linked_plan_rate`
- `issue_to_benchmark_case_conversion_rate`
- `issue_reopen_rate`
- `time_to_triage`
- `time_to_fix`
- `post_fix_regression_rate`
- `dev_issue_capture_rate`
- `dev_issue_to_fix_rate`
- `manual_override_rate`

### 9.4 Validation Gates

On the `memory-helpful` subset, long-term memory should satisfy:

- `task_success_rate` is higher than the no-memory baseline
- `precision_at_k` does not degrade materially
- `noise_rate` does not increase materially
- `latency_p95_ms` growth remains bounded
- `ltm_false_help_rate` and `ltm_stale_hit_rate` remain below preset thresholds

## 10. Main Risks

- memory contamination: incorrect observations are promoted into facts
- replay distortion: missing `as_of` causes result drift
- future-information leakage: benchmark replay reads future facts
- more hits but lower quality: memory increases hit rate while hurting `precision` and `noise`
- write-path bloat: excessive capture causes database growth and analysis degradation
- developer-feedback flooding: too many auto-captured events drown out high-value signals

## 11. Success Criteria

This requirement set is successful if:

1. long-term memory is integrated into the main pipeline without breaking the existing memory contract
2. user issue reporting and developer inner-loop feedback both persist in structured form and can be linked to concrete runs
3. at least one batch of real issues is converted into benchmark cases and used in regression gating
4. benchmark results can answer whether long-term memory is helpful or simply injecting noise
5. developers can prioritize work quickly based on issue clusters, severity, frequency, and benchmark impact

## 12. Near-Term Recommendations

Recommended implementation order:

1. build `SQLite LongTermMemoryStore + LongTermMemoryProvider + as_of`
2. build the `issue_report` and `dev_issue/dev_fix` data surfaces
3. extend benchmark, summary, and regression support for long-term memory metrics
4. add lightweight triple or edge neighborhood expansion and stronger automatic attribution later
