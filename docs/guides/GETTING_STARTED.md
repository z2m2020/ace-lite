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
- `ace-lite doctor` now reports grouped runtime health including git launch diagnostics and install-drift/version-sync status.
- `ace-lite self-update --check` shows the recommended upgrade path for the current install mode before changing anything.
- `ace-lite index` reuses `context-map/index.json` on subsequent runs and can do incremental refresh on git repos.
- If the full pipeline times out, `ace-lite plan` returns a `plan_quick`-style shortlist automatically.

## 4) MCP workflow (agent-facing)

Typical sequence for an agent:

1. `ace_health` to validate memory, embeddings, and skills wiring
2. `ace_memory_search` to recover prior project rules, pitfalls, and naming conventions
3. `ace_index` on first run or after large repo changes
4. `ace_plan_quick` for a fast shortlist
5. Read the top candidate files before treating the shortlist as evidence
6. If `ace_plan_quick` returns `upgrade_recommended=false`, keep reading the shortlist first; use `onboarding_view`, `candidate_details`, and `why_not_plan_yet` as the default guide
7. `ace_plan` only when the quick shortlist is still insufficient or `upgrade_recommended=true`
8. `ace_feedback_record` after the correct targets are confirmed
9. `ace_memory_store` for durable project rules when needed

Recent `ace_plan_quick` payloads also expose compact decision helpers:
- `candidate_details`: per-file labels plus a compact role summary
- `onboarding_view`: grouped `entrypoints`, `public_contracts`, `runtime_core`, `tests`, and `recommended_read_order` for repo familiarization
- `upgrade_recommended`, `expected_incremental_value`, `expected_cost_ms_band`, `why_not_plan_yet`, `why_upgrade_now`: quick guidance on whether a full `ace_plan` is likely worth the extra latency
- `ace_feedback_record` can also receive `candidate_paths` so a host can attach the shortlist it showed before the user confirmed the final file

Discipline rules:

- Do not use file names as the main query when the real question is behavioral.
- Prefer behavior + symptom + module boundary in the query text.
- Final conclusions should cite `file:line`, not just tool output.
- If `ace_plan` is too large or noisy, fall back to `ace_plan_quick` and manual read-based evidence closure.
- For repo familiarization tasks, prefer quick-first reading order from `onboarding_view` before escalating to a full plan.

Recommended query shape:

```text
[target behavior] in [module boundary] shows [observable symptom]; locate implementation path, error handling, observability, and weak test coverage.
```

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
- Team workflow, query discipline, evidence gates, and fallback ladder: `docs/guides/ACE_LITE_TEAM_PLAYBOOK.md`
- Architecture overview: `docs/design/ARCHITECTURE_OVERVIEW.md`
