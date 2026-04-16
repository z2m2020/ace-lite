# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

No notable changes.

## [0.3.84] - 2026-04-16

### Added

- Added a tag-driven `publish-pypi.yml` workflow so `refs/tags/vX.Y.Z` can build validated distributions and publish them through Trusted Publisher/OIDC.

### Changed

- Updated release and upgrade documentation to distinguish internal editable/source updates from versions that are actually published to PyPI/TestPyPI.

## [0.3.83] - 2026-04-16

### Added

- Added install/update introspection for ACE-Lite so runtime surfaces can report install mode, recommended upgrade command, and fail-open latest-release visibility.
- Added `ace-lite self-update` with `--check` support to resolve the correct update path for editable checkouts versus installed packages.

### Changed

- Extended MCP/runtime doctor version reporting to expose structured `update_status`, and documented the recommended Python-native upgrade flows including `pipx` and `uv tool`.

## [0.3.82] - 2026-04-16

### Changed

- Closed the late maintainability wave set by stabilizing shared seams across skills catalog/MCP-CLI handoff, workspace context-report writing, case-evaluation payload builders, observability summaries, and source-plan report-only helpers.
- Added dedicated benchmark/config lanes plus focused optimizations for `context_refine`, index candidate cache reuse, repomap seed pruning, and skills budget defaults, while expanding the golden/test maintenance guardrails that keep those seams stable.

## [0.3.79] - 2026-04-14

### Changed

- Added shared benchmark summary-view helpers in `report_summary.py` so report-only consumers can read top-level and nested summary mappings without duplicating dict-unwrapping boilerplate.
- Switched benchmark runtime-stats and observability report rendering paths to use the shared summary-view helpers, further shrinking the report stack's repetitive parsing surface while preserving report-layer governance boundaries.

## [0.3.78] - 2026-04-14

### Changed

- Split `orchestrator_runtime_support_compat.py` so stage-group rerun policy now lives behind `OrchestratorRuntimeStageGroups`, while compat patchpoint re-exports remain a thinner shell with Protocol-typed dependencies.
- Reused precomputed `ltm_latency_alignment_summary` during benchmark report rendering and made `write_results()` reuse a single `build_results_summary()` result for both markdown rendering and `summary.json` emission.

## [0.3.77] - 2026-04-14

### Changed

- Added explicit typed bridge casts in `orchestrator_runtime_support.py` so the runtime-support wrapper seam no longer leaks `Any` across lifecycle, source-plan replay, finalization, and agent-loop passthrough helpers.
- Expanded the strict hotspot `mypy` override to include `ace_lite.orchestrator_runtime_support`, closing the immediate no-any-return follow-up identified after the Wave19 scope tightening.

## [0.3.76] - 2026-04-14

### Changed

- Tightened `mypy` checks for the typed orchestration support seams added in the recent finalization and factory refactor waves, without yet widening the scope to `orchestrator_runtime_support.py`.
- Updated quality governance guidance to mark the new strict hotspot boundary and preserve `orchestrator_runtime_support.py` as the next focused typing cleanup target.

## [0.3.75] - 2026-04-14

### Changed

- Canonicalized `validation_rich` trend reporting so the default latest input now resolves to `validation_rich/latest/summary.json`, while `tuned/latest` remains an explicit override path.
- Added trend-report metadata for latest input semantics to reduce ambiguity between canonical current and explicit latest-report overrides.

## [0.3.74] - 2026-04-14

### Changed

- Extracted grouped-config normalization and runtime projection payload-map assembly from `create_orchestrator()` into `orchestrator_factory_support.py`, reducing factory shell density without changing CLI config behavior.
- Added a direct unit seam for factory payload-map assembly so grouped overrides remain locked outside the `create_orchestrator()` entrypoint.

## [0.3.73] - 2026-04-14

### Changed

- Added a typed finalization dependency boundary so orchestrator runtime finalization now consumes a single dataclass-backed dependency object instead of multiple loose callback and runtime-handle parameters.
- Exposed minimal Protocol contracts for finalization payload building, trace export, durable stats recording, and runtime state/manager hooks to support further orchestration typing work.

## [0.3.72] - 2026-04-14

### Changed

- Simplified orchestrator finalization by removing trace and durable-stats passthrough helpers from `AceOrchestrator` and injecting the finalization runtime with explicit payload/observability callbacks.
- Promoted skill metadata linting to the default quality gate and added a `skills/`-aware pre-commit validation path that runs `pytest -q tests/unit/test_skills.py -k lint`.

## [0.3.65] - 2026-04-13

### Added

- Added a dated quality-optimization baseline generator plus focused regression coverage for hotspot metrics and artifact emission.
- Added explicit orchestrator typed contract and runtime projection test coverage, including shared config projection helpers and commit-time pre-commit hook validation.

### Changed

- Wired the `plan_quick` strategy registry, reduced `repomap/cache` payload copying, narrowed high-risk cache exception handling, and trimmed `indexer` scan overhead while preserving output ordering.
- Moved orchestrator request/response typing and state projection into shared contract and payload-builder seams, and split config boundary validation from runtime projection so `runtime_settings` and CLI orchestrator factory reuse the same normalization path.
- Updated maintainer architecture, onboarding, quality governance, and system map documentation to reflect the stabilized Phase 1 and Phase 2 quality optimization surfaces.

## [0.3.64] - 2026-04-12

### Added

- Added task-level note slots to `ace_memory_store` across CLI and MCP surfaces so requirement, contract, area, decision type, and task ID metadata can be captured explicitly.
- Added a reproducible replay benchmark under `benchmark/session_feedback_2026_04_12/` plus a maintainer guide for session feedback capture.

### Changed

- Hardened `plan_quick` and retrieval policy intent detection so requirement IDs such as `EXPL-01` and `req-02` are recognized case-insensitively and normalized consistently.
- Updated maintainer documentation to reflect the real `--context-report-path` and `feedback_record` public contracts.

## [0.3.63] - 2026-04-08

### Added

- Added `src/ace_lite/plan_payload_view.py` to centralize read-only fallback resolution for `source_plan`, validation payloads, stage lists, repomap, and retrieval subgraph inputs.
- Added unit coverage in `tests/unit/test_plan_payload_view.py` to lock the fallback contract used by report and graph view builders.

### Changed

- Refactored `context_report.py` and `retrieval_graph_view.py` to consume the shared plan payload view helpers instead of duplicating nested/top-level payload parsing.
- Normalized read-only report and retrieval graph warning text so rendered output is more stable for humans and downstream agents.

## [0.3.60] - 2026-03-26

### Added

- Added the H2 2026 optimization roadmap under `docs/maintainers/ROADMAP_2026H2_OPTIMIZATION.md`.
- Added focused unit coverage for skill frontmatter linting and the shared `classify_tier()` helper.

### Changed

- Promoted duplicated index tier classification into a module-level `classify_tier()` helper for full and incremental indexing paths.
- Skill manifest linting now tracks missing frontmatter fields before runtime backfill so CI can flag missing `token_estimate` and `default_sections` accurately.

## [0.3.54] - 2026-03-23

### Added

- Added runtime persistence for `learning_router_rollout_decision` plus guarded-rollout scaffold payloads in `index.adaptive_router` and `observability`, while keeping rollout disabled by default.
- Added top-level benchmark and report contracts for `source_plan_failure_signal_summary` and `learning_router_rollout_summary` so validation-rich, freeze, and maintainer review flows can consume stable rollout-readiness evidence.

### Changed

- Extended validation-rich and release-freeze scripts to preserve the newer report-only rollout summaries across metrics collection, trend/comparison reports, promotion review, and freeze regression.
- Updated maintainer benchmarking and releasing guides to document the guarded-rollout readiness review path and the new report-only evidence surfaces.

## [0.3.52] - 2026-03-23

### Added

- Added `benchmark_ops` readers for `retrieval_frontier_gate_summary` and `repomap_seed_summary` so scripts and CI can consume those summaries without hand-parsing benchmark result payloads.

### Changed

- Extended Q3 benchmark observability so graph-lookup weights, normalization traces, repomap seed/cache signals, and deep-symbol hard cases flow through benchmark summaries, reports, and arm-sweeper review surfaces.
- Updated arm-sweeper and benchmark CLI support contracts to retain both Q2 and Q3 gate summaries through script, markdown, and writer paths.

## [0.3.40] - 2026-03-12

### Added

- Added a sandbox-aware `validation` stage with a stable top-level contract, timeout fallback payload, and focused regression coverage.
- Added bounded agent-loop action contracts plus a controller shell that can request one incremental rerun from validation diagnostics.

### Changed

- Extended plan payload observability with `validation` and `agent_loop` runtime summaries while keeping fail-open defaults intact.
- Enabled post-validation incremental rerun orchestration for the `index -> repomap -> augment -> skills -> source_plan -> validation` path when the bounded loop is explicitly enabled.

## [0.3.38] - 2026-03-11

### Added

- Added the `grpc-java` dependency-heavy benchmark target plus a dated Java large-repo evidence artifact.
- Added post-hotspot release-governance and handoff documentation used during the maintainability wave closeout.

### Changed

- Decomposed benchmark evaluation, summary, CLI benchmark, runtime, MCP service, repomap builder, and orchestrator maintainer paths into smaller helper or handler boundaries.
- Refreshed hotspot governance, release/install drift verification, and latency/SLO release guidance for the closed post-backlog maintainability wave.

## [0.3.33] - 2026-03-10

### Added

- Added reward-log replay artifacts for router delayed rewards and explicit online-bandit rollout checkpoint documentation.

### Changed

- Closed the yearly `Y22` online-bandit stream with dated opt-in benchmark evidence and explicit repeated-green promotion requirements.
- Hardened layered config loading so benchmark target roots use their own `.ace-lite.yml` during local opt-in experiments and MCP/runtime upgrades.

## [0.3.32] - 2026-03-09

### Added

- Added a dedicated `stale_majority` feature slice to the benchmark matrix with a synthetic benchmark repo and stable report-only chunk-guard gates.

### Changed

- Extended comparison-lane benchmark summaries and Markdown reports with retained-anchor hit metrics for stale-majority analysis.
- Closed the `Y12` yearly stream by promoting stale-majority evidence from an observational lane to an enforced feature-slice gate while keeping SHARS-lite in `report_only` mode.

## [0.3.31] - 2026-03-09

### Added

- Added adaptive router Phase 0 observability plumbing so plan/benchmark config can surface router metadata through index payloads and trace tags without changing retrieval behavior.
- Added index payload and stage-tag coverage for adaptive router metadata, including repo-config driven CLI validation.

### Changed

- Added a safe source-plan replay cache guarded by stable upstream fingerprints to reduce repeated planning cost without reusing stale plans.
- Added an adaptive promotion governance matrix to document benchmark-backed rollout controls for future retrieval/chunking promotion work.
- Added a stage-aware chunking hard-case benchmark slice to stress latency/quality tradeoffs on difficult retrieval cases.

## [0.3.27] - 2026-03-05

### Changed

- Hardened co-change in-memory cache operations with a lock to prevent race conditions during concurrent reads/writes.
- Refactored embedding/cross-encoder rerank paths to a shared core implementation for consistent scoring, thresholding, and stats generation.
- Simplified embedding stats serialization using dataclass conversion and unified empty-input stats handling.

## [0.3.26] - 2026-03-05

### Added

- Added `ace-lite workspace` command group for multi-repo decision hubs (manifest validation, summary indexing, routing/plan building, and routing benchmarks).
- Added workspace summary index v1 (`context-map/workspace/summary-index.v1.json`) for repo-level routing tokens.
- Added workspace benchmark baseline artifacts and CI-friendly threshold checks (`workspace benchmark --baseline-json ... --fail-on-baseline`).

### Changed

- Workspace evidence validation rejects non-finite `min_confidence`/`confidence` inputs and emits structured violation details for machine checks.
- Workspace manifest and summary-index helpers now treat booleans as invalid integer limits to avoid YAML truthy surprises.

## [0.3.25] - 2026-02-26

### Added

- BM25-lite now caches file token statistics keyed by `index_hash` for faster repeated queries (LRU, best-effort).

### Changed

- Index-stage BM25-lite / hybrid_re2 now pass `index_hash` into BM25-lite to enable corpus caching.

## [0.3.24] - 2026-02-26

### Added

- Added shared code-aware tokenization helpers (`ace_lite.text_tokens`) for consistent lexical behavior across stages.

### Changed

- Improved lexical retrieval by splitting `camelCase`/`snake_case` identifiers in BM25-lite ranking and hybrid term coverage.
- Term extraction now supplements query tokens with code-aware splits for better identifier-style queries.
- Local notes lexical matching now reuses the shared code tokenization helper.

## [0.3.23] - 2026-02-26

### Added

- MCP config now supports `ACE_LITE_TOKENIZER_MODEL` for consistent token budgeting across tools.
- Unit tests ensuring RepoMap token budgeting uses the shared token estimator and respects `tokenizer_model`.

### Changed

- RepoMap token budgeting now uses the shared tokenizer-based estimator (tiktoken when available) instead of whitespace splitting.
- Repomap stage cache keys now include `tokenizer_model` to avoid cross-model cache reuse.

## [0.3.22] - 2026-02-25

### Added

- Added H2 2026 optimization roadmap (`docs/maintainers/ROADMAP_2026H2_OPTIMIZATION.md`).
- Extended the external OSS benchmark matrix with Lens Protocol core (Solidity) cases.

## [0.3.21] - 2026-02-25

### Added

- Plumbed `memory.gate` and `memory.postprocess` config through CLI config resolution and into `create_orchestrator()` / `run_plan()`.
- MCP `config_pack` overrides now support `memory_gate_*` and `memory_postprocess_*` tuning keys.

### Changed

- Memory retrieval gate is now opt-in by default (`memory.gate.enabled=false`) to avoid surprising behavior changes for short queries.
- Normalized documentation index encoding.

## [0.3.20] - 2026-02-25

### Added

- OpenClaw plugin wrapper under `integrations/openclaw/ace-lite-openclaw-plugin/` (stdio MCP) exposing core `ace_*` tools and optional auto-injected `plan_quick` context.
- `docs/guides/OPENCLAW.md` setup notes.

### Changed

- MCP default language profile now includes `solidity`.

## [0.3.19] - 2026-02-25

### Added

- Version drift detection: health/startup now warn when `pyproject.toml` differs from installed pip metadata (common after `git pull` without reinstall).
- `scripts/update.ps1` and `make update` to pull + `pip install -e` and print version info.
- Solidity indexing now discovers `.sol` sources under `node_modules/` (while still skipping non-Solidity files there).
- Index entries now include a `tier` field (`first_party` vs `dependency`) for better default ranking behavior.

### Changed

- Improved Solidity import resolution for `node_modules/` and common Foundry `lib/<pkg>/src|contracts` layouts (repomap adjacency + reverse-dependency expansion).

## [0.3.18] - 2026-02-25

### Added

- Solidity (`.sol`) indexing support (tree-sitter) with contract/function/event/import extraction.

## [0.3.17] - 2026-02-25

### Added

- `ace-lite demo` one-command flow (seed demo repo + run plan); optional `--clone-url` path.
- `ace-lite benchmark diff` for offline comparison between two benchmark runs.
- Config-driven tuning knobs for `hybrid_re2` weighting (BM25/heuristic/coverage/scale).
- Docs index and release readiness docs (compatibility matrix, upgrade guide, release checklist).

## [0.3.16] - 2026-02-25

### Added

- Optional ripgrep-powered exact search boost/injection for index-stage candidate ranking (feature-flagged via `--exact-search*`).

## [0.3.15] - 2026-02-25

### Added

- Index stage now emits `context_budget` and a stable `selection_fingerprint` for deterministic run diffs.

## [0.3.14] - 2026-02-25

### Changed

- `ace-lite index` now reuses and incrementally refreshes an existing index file by default.

## [0.3.13] - 2026-02-25

### Changed

- Switched the default candidate ranker to `rrf_hybrid` (hybrid retrieval by default for index-stage candidate selection).

## [0.3.12] - 2026-02-25

### Added

- Added `sentence_transformers` embedding provider option for local embeddings (e.g. `nomic-ai/CodeRankEmbed`).

### Changed

- Hardened generated-code detection heuristics for down-weighting.
- Expanded MCP default languages to match the broader default language profile.

## [0.3.11] - 2026-02-25

### Added

- Added external OSS benchmark matrix config `benchmark/matrix/external_oss.yaml`.
- Added protobuf-go benchmark cases to cover generated-code-heavy repos.
- Added reproducible benchmarking documentation.

## [0.3.10] - 2026-02-24

### Added

- Expanded default language profile and file-extension detection (Rust/Java/C/C++/C#/Ruby/PHP + opt-in Kotlin/Swift/Bash/Lua).
- Best-effort Tree-sitter symbol extraction for additional languages.
- Added new documentation: getting started, MCP setup templates, and `.aceignore` cookbook.

### Changed

- Updated README and Getting Started to reflect expanded language support and new docs.

## [0.3.9] - 2026-02-24

### Added

- Added `ace-lite doctor` as a convenience alias for `ace-lite runtime doctor-mcp`.
- Added English getting started documentation.

### Changed

- README now links Getting Started and highlights `ace-lite doctor` for quick checks.

## [0.3.8] - 2026-02-24

### Added

- `plan_quick` now supports index cache reuse, ranker selection, and optional seeded repomap expansion output.
- `ace_plan_quick` MCP tool exposes plan_quick tuning options (ranker, cache path, incremental toggle, and repomap expansion).

### Changed

- `plan_quick` uses `build_or_refresh_index()` by default to avoid full index rebuild per call.

## [0.3.7] - 2026-02-24

### Added

- Index entries now include a `generated` flag to help down-weight auto-generated code without hard-excluding it.

### Changed

- `plan_quick` now uses index-term heuristic ranking as the primary signal (repomap is only a safety fallback).
- RepoMap base scoring down-weights generated files to prevent static maps from over-favoring generated code.
- README now includes `.aceignore` examples for Go repos with generated code.

## [0.2.0-rc3] - 2026-02-13

### Added

- Local notes recall path via `LocalNotesProvider` with namespace-aware filtering and deterministic lexical scoring.
- Expiry maintenance commands: `ace-lite profile vacuum` and `ace-lite memory vacuum`.
- Memory quality regression metrics and gates in benchmark/freeze flows (`notes_hit_ratio`, `profile_selected_mean`, `capture_trigger_ratio`).

### Changed

- `ProfileStore` now supports near-duplicate dedupe and deterministic importance/recency-aware injection ranking.
- Memory stage observability now reports notes source mix, disclosure/cost fields, and capture/profile selection telemetry.
- Benchmark matrix and release-freeze reports include memory-focused thresholds and summaries.

### Fixed

- Memory note pruning and persistence paths are now expiry-aware and idempotent across repeated vacuum runs.

## [0.2.0-rc2] - 2026-02-13

### Added

- Namespace/profile/capture memory workflow and local memory CLI flows (`memory search/store/wipe`, profile actions).
- Signal extraction module for deterministic memory capture trigger evaluation.

### Changed

- `AceOrchestrator` initialization is config-driven via `OrchestratorConfig` (breaking API change).
- CLI entrypoints were modularized under `cli_app/commands`.

### Chore

- Ignore local review/tool artifacts in git (`.context/`, `.claude/`, `test_output.*`).

## [0.2.0-rc1] - 2026-02-10

### Added

- Multi-repository benchmark matrix support and threshold gates.
- Release-freeze regression script and CI workflow.
- RepoMap signal fusion improvements (graph/import-depth/reference-aware).
- MCP runtime JSON-RPC path with timeout/retry and fallback behavior.

### Changed

- Pipeline observability and benchmark artifacts expanded for release gating.
- Documentation updated with release candidate playbook and onboarding guidance.

### Fixed

- Stabilized ranking defaults and cochange cache behavior for reproducibility.
