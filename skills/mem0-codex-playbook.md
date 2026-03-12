---
name: mem0-codex-playbook
description: OpenMemory and Mem0 operations playbook for bridge-mode setup, SSE or 405 failures, embedding dimension alignment, and scope-safe memory retrieval.
intents: [memory, troubleshoot, implement]
modules: [openmemory, mem0, mcp, embeddings, vectorstore, memory_profile, memory_postprocess, memory_capture]
error_keywords: [405, dimension, 维度, mismatch, 不匹配]
default_sections: [Workflow, Config Checklist, Command Template, Scenario Templates, Troubleshooting]
topics: [openmemory, mem0, bridge, sse, qdrant, ollama, embeddings, scope, memory_profile, memory_postprocess, memory_capture, memory_notes, memory_feedback, 桥接, 嵌入, 检索]
priority: 3
token_estimate: 260
---

# Workflow

1. Search memory before edits so you do not paper over a known constraint.
2. Keep repo, user, app, namespace, and profile scope stable while debugging retrieval quality.
3. Verify bridge mode, embedding model, vector dimension, and MCP wiring before changing prompts.
4. Prefer `ace-lite runtime doctor-mcp` or `ace-lite runtime test-mcp` over ad hoc probing when the issue looks like endpoint or transport drift.
5. Stabilize memory lifecycle knobs before tuning prompts: profile budget, postprocess filters, capture policy, notes mode, and feedback store.
6. Write back only durable architectural constraints, not one-off debugging notes.

# Config Checklist

State these explicitly before changing retrieval behavior:

- Scope: repo, user, app, namespace, bridge mode
- Embeddings: model, dimension, collection compatibility
- Memory lifecycle: profile path/budget, postprocess filters, notes mode, capture keywords, feedback path
- Failure policy: whether noisy or stale results should fail open or be filtered first

# Command Template

Use a fixed-scope command when validating retrieval changes:

```bash
ace-lite plan \
  --query "<memory retrieval issue>" \
  --repo ace-lite-engine \
  --root . \
  --memory-primary rest \
  --memory-secondary none \
  --embedding-provider ollama \
  --embedding-model dengcao/Qwen3-Embedding-4B:Q4_K_M
```

Keep repo, user, app, namespace, and embedding dimension constant across comparisons unless one of them is the variable under test.

For Codex-side wiring or endpoint checks, use:

```bash
ace-lite runtime doctor-mcp --root . --skills-dir skills
ace-lite runtime test-mcp --root . --skills-dir skills
ace-lite runtime setup-codex-mcp --root . --skills-dir skills --enable-memory --apply
```

# Scenario Templates

## Bridge or SSE incident

- Scope: verify the bridge mode, endpoint shape, and request path before changing client retry logic.
- Required evidence: failing status code, transport mode, and the exact endpoint or bridge process under test.
- Exit rule: fix transport or endpoint wiring first; do not retune prompts to mask a bridge failure.

## Dimension mismatch

- Scope: compare embedding model, configured dimension, and target collection metadata before re-indexing.
- Required evidence: active embedding model, collection dimension, and where the mismatch was observed.
- Exit rule: realign the model or collection contract before any data rebuild.

## Noisy retrieval cleanup

- Scope: stabilize scope filters and memory lifecycle knobs before deleting data or tightening prompts.
- Required evidence: repo/user/app/namespace scope, `memory_profile`, `memory_postprocess`, and `memory_capture` settings.
- Exit rule: change one lifecycle surface at a time and confirm duplication or stale-hit rate improves.

# Troubleshooting

- `405`: verify bridge mode and the SSE endpoint shape before touching client code.
- `dimension mismatch`: align embedding dimensions with the target collection before re-indexing.
- empty or sparse results: re-check user, app, namespace, repo filters, and profile token budget before retuning retrieval.
- stale or duplicated memories: inspect collection scope, postprocess filtering, notes/capture policy, and writeback behavior before wiping data.
- MCP drift or wrong endpoint: run `ace-lite runtime doctor-mcp` or `ace-lite runtime test-mcp` before changing memory prompts or bridge code.
