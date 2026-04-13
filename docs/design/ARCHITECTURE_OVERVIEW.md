# Architecture Overview (ACE-Lite)

ACE-Lite is a local-first "Active Context Engine" that turns a repo plus a user
query into a compact, explainable context selection surface for AI coding
agents.

## High-level pipeline

The default plan path is:

`memory -> index -> repomap -> augment -> skills -> source_plan -> validation`

Key idea: start deterministic (structure plus signals), then expand only where
needed.

## Core subsystems

### Memory

- Optional: integrates with OpenMemory (MCP/REST), local notes, and repo-local long-term memory.
- Current local memory surfaces include notes, profile and feedback capture, plus a SQLite-backed long-term store routed through the normal memory-provider wiring.
- Output is treated as a set of signals (recent issues, relevant paths, user preferences), not as truth.

### Index (tree-sitter)

- Builds a language-aware file map: path/module plus symbols, imports, generated flags, and retrieval-ready chunk metadata.
- Candidate ranking happens here (fast, explainable), using one of several ranker profiles:
  - `heuristic` (path/module/symbol/import/content rules)
  - `bm25_lite`
  - `hybrid_re2`
  - `rrf_hybrid` (default)
- Optional exact-search boost (`ripgrep`) can inject or boost deep files when query terms appear in code.
- Optional docs-channel signals from repository Markdown can influence term extraction and ranking.
- Optional embedding rerank is used for semantic disambiguation under time-budget and fail-open policies.
- Structural rerank already includes `cochange`, `SCIP`, `graph_lookup`, and chunk semantic rerank. This is a graph-aware retrieval stack, but it is not a GNN/CPG/GraphRAG runtime.

### RepoMap

- Produces a prompt-friendly repository map constrained by token budget.
- Used to add neighborhood context (imports, refs, graph neighbors) without dumping the whole repo.

### Augment

- Adds extra signals (tests, VCS worktree hints, dependency edges) behind policy and time budgets.

### Skills

- Markdown skill manifests route queries to small, relevant sections (lazy-load).
- Skills provide operational playbooks without hardcoding domain logic into the orchestrator.

### Source plan

- Emits a stable payload containing:
  - `candidate_files` plus rationale
  - `candidate_chunks` (definition refs/snippets)
  - budgets, fingerprints, and observability fields
- Candidate chunks can carry internal retrieval-context sidecars during ranking and chunk semantic rerank, but those sidecars are stripped before the final user/model-facing payload is emitted.

### Validation

- Executes optional post-plan validation behind fail-open policy gates.
- Emits machine-readable validation diagnostics, result summaries, and sandbox metadata.
- Current validation runs through a temp-tree sandbox path with patch apply, compile/tests probes, and LSP diagnostics collection.
- Top-level `validation` payload stability is preserved so CLI, benchmark, and replay flows can compare outcomes safely.

## Current execution maturity

- `retrieval_context` / contextual chunking: implemented. Internal sidecars are built during chunk selection, consumed by chunk semantic rerank, and stripped at the prompt boundary.
- graph-aware retrieval: implemented as structural rerank (`cochange`, `SCIP`, `graph_lookup`) plus chunk-level graph prior and graph closure.
- topological shield: implemented as an explicit chunk-selection attenuation path with `off`, `report_only`, and `enforce` modes.
- validation feedback loop: implemented as a bounded rerun/query-refinement loop. It is not an autonomous code-writing agent.
- branch validation: score, selection, and archive contracts are implemented and exposed as report-only observability. Real `N>1` candidate generation and concurrent sandbox execution are still future work.

## 2026-03-27 baseline notes

- `ace_plan_quick` docs-sync guardrails are implemented in the live path: doc-intent path/domain biasing, risk hints, query refinements, domain summary, and `full_build_reason` observability.
- Memory search guardrails are implemented in both CLI and MCP surfaces: disclaimer, staleness warning, and recency alert.
- These are considered stabilized UX guardrails for the current architecture baseline and should not be implicitly removed during orchestrator refactor waves.

## Active structural hotspots (not yet resolved)

- `AceOrchestrator` remains a large orchestration shell with multiple cross-cutting concerns still co-located (replay cache flow, trace export, durable stats writeback, memory namespace resolution, memory signal capture).
- Config semantics still span multiple layers (`config_models`, `orchestrator_config`, runtime settings mapping), so field defaults and normalization behavior require careful compatibility checks before consolidation.
- Stage-to-stage payloads still rely heavily on dynamic dict contracts in hot paths; boundary typing is partial and remains a planned refactor area.

## Refactor seam boundaries

- `src/ace_lite/cli_app/runtime_command_support.py`: shared runtime doctor/status/settings/setup payload builders, keeping CLI command callbacks thin.
- `src/ace_lite/mcp_server/server_tool_registration.py`: MCP tool registration surface and metadata, keeping `server.py` as the server entry shell.
- `src/ace_lite/orchestrator_payload_builder.py`: source-plan payload and observability assembly seam, keeping `AceOrchestrator` focused on lifecycle coordination.
- `src/ace_lite/index_stage/`: index-stage helper seams for benchmark filters, fusion, parallel runtime, rerank timeouts, and repo-path normalization.
- `src/ace_lite/benchmark/case_evaluation_*.py`: benchmark evaluation seams for matching, context, metrics, diagnostics, row assembly, and detail output.
- `src/ace_lite/benchmark/report_observability.py`: extracted benchmark-report observability sections, keeping `benchmark/report.py` focused on report assembly and stable output ordering.

## Determinism and observability

ACE-Lite emphasizes:

- Stable sorting and bounded budgets (`context_budget`)
- Debuggable selection diffs (`selection_fingerprint`)
- Fail-open policies for optional components (embeddings, exact search, external memory)
- Report-only observability surfaces before promotion to default-on execution behavior
