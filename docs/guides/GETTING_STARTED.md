# Getting Started (ACE-Lite Engine)

This guide gets you to a working plan quickly and gives a simple workflow you can reuse on real repos.

Index supports (tree-sitter): Python, TypeScript/TSX, JavaScript, Go, Rust, Java, C, C++, C#, Ruby, PHP, Solidity (plus Kotlin/Swift/Bash/Lua via opt-in detection).

Note: the CLI `plan` command defaults to a **fast** language profile (`python,typescript,javascript,go,markdown`). If you work on other languages, pass `--languages ...` (or set defaults in MCP via `ACE_LITE_DEFAULT_LANGUAGES`).

## 1) Fastest end-to-end check

```bash
ace-lite demo
```

This seeds a tiny repo under `artifacts/demo/repo` and runs a plan query (no memory server required).

Optional baseline comparison:

```bash
rg -n "shutdown|allowlist|withdraw" artifacts/demo/repo
```

## 2) Which tool when (fast mental model)

- If you already know the symbol or file name: use `grep` or `rg` first.
- If you know what you want to change but not where: use `plan` with a short timeout.
- If the task is cross-module and dependency-heavy: run a full `plan` with RepoMap enabled.
- If you need a compact global map before opening files: build a RepoMap.

## 3) Basic CLI workflow on a real repo

```bash
ace-lite doctor
ace-lite index --root . --output context-map/index.json
ace-lite plan --query "where is shutdown middleware implemented" --repo myrepo --root . --skills-dir skills --memory-primary none --memory-secondary none
```

Notes:
- `ace-lite index` reuses `context-map/index.json` on subsequent runs and can do incremental refresh on git repos.
- If the full pipeline times out, `ace-lite plan` returns a `plan_quick`-style shortlist automatically.

## 4) MCP workflow (agent-facing)

Typical sequence for an agent:

1. `ace_health` to validate memory, embeddings, and skills wiring
2. `ace_index` on first run or after large repo changes
3. `ace_plan_quick` for a fast shortlist
4. `ace_plan` when you need the full planning payload
5. `ace_feedback_record` after the correct targets are confirmed
6. `ace_memory_store` for durable project rules when needed

## 5) Optional: global Codex MCP config pack sample

If you want the same ACE-Lite MCP tuning to apply across repos, keep the config pack in your global Codex home and point `ACE_LITE_CONFIG_PACK` at it from the MCP server env.

Windows example path:

```text
C:\Users\<you>\.codex\ace-lite-mcp-performance.json
```

Sample payload:

```json
{
  "schema_version": "ace-lite-config-pack-v1",
  "name": "ace-lite-mcp-performance-v1",
  "overrides": {
    "top_k_files": 10,
    "min_candidate_score": 1,
    "candidate_relative_threshold": 0.08,
    "candidate_ranker": "rrf_hybrid",
    "deterministic_refine_enabled": true,
    "hybrid_re2_fusion_mode": "rrf",
    "hybrid_re2_rrf_k": 60,
    "embedding_enabled": true,
    "embedding_provider": "ollama",
    "embedding_model": "dengcao/Qwen3-Embedding-4B:Q4_K_M",
    "embedding_dimension": 2560,
    "embedding_index_path": "context-map/embeddings/index.json",
    "embedding_rerank_pool": 16,
    "embedding_lexical_weight": 0.55,
    "embedding_semantic_weight": 0.45,
    "embedding_min_similarity": 0.05,
    "embedding_fail_open": true,
    "memory_notes_enabled": true,
    "memory_gate_enabled": false,
    "memory_gate_mode": "auto",
    "memory_postprocess_enabled": true,
    "memory_postprocess_noise_filter_enabled": true,
    "memory_postprocess_length_norm_anchor_chars": 500,
    "memory_postprocess_time_decay_half_life_days": 7.0,
    "memory_postprocess_hard_min_score": 0.05,
    "memory_postprocess_diversity_enabled": true,
    "memory_postprocess_diversity_similarity_threshold": 0.92,
    "policy_version": "mcp-performance-v1"
  }
}
```

You can then register the MCP with:

```bash
ace-lite runtime setup-codex-mcp --root . --skills-dir skills --enable-memory --enable-embeddings --config-pack C:\Users\<you>\.codex\ace-lite-mcp-performance.json --user-id <your-openmemory-user-id> --apply
```

## 6) Next steps

- MCP setup templates (Windows/WSL, OpenMemory, Ollama, Codex CLI): `docs/guides/MCP_SETUP.md`
- Architecture overview: `docs/design/ARCHITECTURE_OVERVIEW.md`
