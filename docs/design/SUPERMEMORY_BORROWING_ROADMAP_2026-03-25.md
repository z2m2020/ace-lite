# Supermemory Borrowing Roadmap

Date: 2026-03-25

## Goal
Define what ACE-Lite should borrow from Supermemory without restructuring the existing `memory`, `profile`, or long-term memory core. The target is a minimal, additive roadmap with clear boundaries.

## L8201 Graph Visualization Interface

### Implemented Surfaces
- Added a read-only `ltm_graph_view_v1` payload builder:
  - `src/ace_lite/memory_long_term/graph_view.py`
- Added a CLI entrypoint:
  - `ace-lite memory graph --fact-handle <handle> --db-path context-map/long_term_memory.db`
- Added an MCP tool:
  - `ace_memory_graph_view`

### Response Schema
Top-level fields:
- `ok`
- `schema_version`
- `fact_handle`
- `seeds`
- `scope`
- `summary`
- `focus`
- `nodes`
- `edges`
- `triples`

Design intent:
- `nodes` and `edges` are directly consumable by a future UI or external graph component.
- `triples` preserve ACE-Lite fact semantics instead of forcing the storage layer into a UI-native shape.
- `focus` makes the centered fact explicit for inspectors and detail panels.

### Borrowing Boundary
Supermemory's graph surface is effectively a layered design: a read-only backend graph payload plus a frontend graph component. It does not require the storage schema and the UI representation to be identical.

ACE-Lite follows the same direction here:
- add a read-only graph view payload
- keep `LongTermMemoryStore` unchanged
- keep `LongTermMemoryProvider` unchanged
- keep the existing observation/fact contracts unchanged

### Minimal Demo Path
```
ace-lite memory graph --db-path context-map/long_term_memory.db --fact-handle fact-1 --max-hops 2 --limit 8
```

MCP:
```
ace_memory_graph_view(
  fact_handle="fact-1",
  max_hops=2,
  limit=8,
  root="F:\\deployed\\ace-lite-engine-open-20260311"
)
```

### UI Follow-up
- Phase 1: consume `nodes` and `edges` directly for a minimal inspector or debug surface.
- Phase 2: if a Supermemory-style graph component is desirable, add a frontend adapter that maps the ACE-Lite payload into the component's expected shape.
- Avoid turning the long-term schema into a document-memory relation model purely to satisfy a third-party graph widget.

## L8202 Protocol Compatibility Layer

### Current Supermemory External Protocol Surface
- `POST /v4/search`
  - core inputs: `q`, `containerTag`, `threshold`, `limit`, `searchMode`
  - core outputs: `results`, `timing`, `total`
- `POST /v4/profile`
  - core inputs: `containerTag`, optional `q`
  - core outputs: `profile.static`, `profile.dynamic`, `searchResults`
- `POST /v4/memories`
  - writes memory entries with fields centered on `content`, `isStatic`, `metadata`, `containerTag`

### Current Reusable ACE-Lite Surfaces
- CLI:
  - `memory search/store/wipe/vacuum`
  - `profile show/add-fact/wipe/vacuum`
  - `memory graph`
- MCP:
  - `ace_memory_search`
  - `ace_memory_store`
  - `ace_memory_wipe`
  - `ace_memory_graph_view`
- internal:
  - `ProfileStore`
  - `LongTermMemoryStore`
  - `LongTermMemoryProvider`
  - `DualChannelMemoryProvider`
  - `HybridMemoryProvider`

### Conclusion
A compatibility shim is reasonable, but only as a new outer protocol layer. It should not feed Supermemory response semantics back into ACE-Lite's internal contracts.

Recommended mappings:
- `containerTag` -> ACE-Lite `memory.namespace.container_tag` or a repo/user/profile scope composition
- `profile.static` -> stable facts and preferences stored in `ProfileStore`
- `profile.dynamic` -> a projected view over recent context or dynamic selections
- `searchResults` -> a projection of existing memory provider retrieval results

Not recommended:
- rewriting the internal provider protocol into Supermemory response formats
- reshaping profile synthesis just to mirror a `whoAmI` or `profile` surface

### Recommended Path
1. Add a thin REST or MCP adapter only if there is an actual integration need.
2. Keep the adapter limited to input normalization and response projection.
3. Prefer compatibility for `search` and `profile` first, not the full write lifecycle.

## L8203 Benchmark Alignment

### Public Shape of Supermemory MemoryBench
MemoryBench is presented as a pluggable benchmark framework with emphasis on:
- provider-benchmark decoupling
- checkpointed pipeline execution
- side-by-side provider comparison
- a MemScore-style triad: `accuracy% / latencyMs / contextTokens`

Public pipeline stages:
- `ingest -> index -> search -> answer -> evaluate -> report`

Representative benchmark families mentioned publicly:
- `locomo`
- `longmemeval`
- `convomem`

### ACE-Lite Capabilities That Already Exist
ACE-Lite already has:
- structured benchmark case contracts
- comparison lanes
- reporting and regression gates
- long-term-memory-specific metrics, including:
  - `ltm_hit_ratio`
  - `ltm_effective_hit_rate`
  - `ltm_false_help_rate`
  - `ltm_stale_hit_rate`
  - `ltm_replay_drift_rate`
  - `ltm_latency_overhead_ms`
- reporting and aggregation surfaces in:
  - `case_evaluation.py`
  - `case_evaluation_metrics.py`
  - `case_evaluation_row.py`
  - `report_metrics.py`
  - `runner.py`

### Alignment Opportunities
Presentation-layer alignment:
- add a MemoryBench-style summary overlay
- add an `accuracy / latency / context-token-budget` triad view
- add provider adapter identifiers for side-by-side comparisons on the same case sets

Data-layer alignment:
- add adapter schemas for external benchmark datasets
- map ACE-Lite case taxonomy into public benchmark dimensions such as `single-session`, `multi-session`, `temporal`, and `preference`

### Explicit Gaps
- ACE-Lite does not yet have a generic benchmark adapter for arbitrary memory providers.
- ACE-Lite benchmarking is still optimized for coding-agent and retrieval/source-plan evaluation, not a generic memory-provider benchmark harness.
- ACE-Lite does not currently expose a MemScore-style triad as a first-class summary output.

### Recommended Path
1. Start with a summary overlay and keep the core benchmark runner unchanged.
2. Then add dataset and provider adapters so external benchmark suites can enter as additive lanes.
3. Only after that evaluate whether a MemoryBench-style multi-provider compare command is worth adding.

## Final Boundary
- Borrow from Supermemory at the product, presentation, and external protocol layers.
- Keep ACE-Lite's internal fact model, provider composition, LTM explainability, and benchmark core free from reverse coupling.
- All new work in this area should be additive adapters or views, not replacements.

## References
- Supermemory MemoryBench overview, accessed 2026-03-25
  - https://supermemory.ai/docs/memorybench/overview
- Supermemory MemoryBench GitHub repository, accessed 2026-03-25
  - https://github.com/supermemoryai/memorybench
- Supermemory graph viewport API, accessed 2026-03-25
  - https://supermemory.ai/docs/api-reference/graph/get-graph-viewport-data
- Supermemory memory graph integration docs, accessed 2026-03-25
  - https://supermemory.ai/docs/integrations/memory-graph
- Supermemory profile API, accessed 2026-03-25
  - https://supermemory.ai/docs/api-reference/profile/get-user-profile
- Supermemory memory operations docs, accessed 2026-03-25
  - https://supermemory.ai/docs/memory-operations
