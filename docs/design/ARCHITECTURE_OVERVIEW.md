# Architecture Overview (ACE-Lite)

ACE-Lite is a local-first “Active Context Engine” that turns a repo + a user query into a compact, explainable context selection (files + definition chunks), suitable for AI coding agents.

## High-level pipeline

The default plan path is:

`memory -> index -> repomap -> augment -> skills -> source_plan`

Key idea: start deterministic (structure + signals), then expand only where needed.

## Core subsystems

### Memory

- Optional: integrates with OpenMemory (MCP/REST) and can also use local notes.
- Output is treated as a set of signals (recent issues, relevant paths, user preferences), not as “truth”.

### Index (tree-sitter)

- Builds a language-aware file map: path/module + symbols + imports + generated flags.
- Candidate ranking happens here (fast, explainable), using one of several ranker profiles:
  - `heuristic` (path/module/symbol/import/content rules)
  - `bm25_lite`
  - `hybrid_re2`
  - `rrf_hybrid` (default)
- Optional: feature-flagged exact search boost (`ripgrep`) can inject/boost deep files when query terms appear in code.
- Optional: docs-channel signals from repository Markdown (evidence snippets + code hints) can influence term extraction and ranking.
- Optional: embedding rerank (Ollama / sentence-transformers) for semantic disambiguation.

### RepoMap

- Produces a prompt-friendly repository map constrained by token budget.
- Used to add neighborhood context (imports/refs/graph neighbors) without dumping the repo.

### Augment

- Adds extra signals (tests, VCS worktree hints, dependency edges) behind policy and time budgets.

### Skills

- Markdown skill manifests route queries to small, relevant sections (lazy-load).
- Skills provide operational playbooks (e.g., debugging patterns) without hardcoding domain logic.

### Source plan

- Emits a stable payload containing:
  - `candidate_files` + rationale
  - `candidate_chunks` (definition refs/snippets)
  - budgets, fingerprints, and observability fields

## Determinism and observability

ACE-Lite emphasizes:
- Stable sorting and bounded budgets (`context_budget`)
- Debuggable selection diffs (`selection_fingerprint`)
- Fail-open policies for optional components (embeddings, exact search, external memory)
