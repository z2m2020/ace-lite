# Retrieval Graph View Contract

**Schema Version**: `retrieval_graph_view_v1`
**Phase**: Phase 1
**Module**: `src/ace_lite/retrieval_graph_view.py`

---

## Overview

`retrieval_graph_view` produces a top-K candidate subgraph from an already-computed plan payload. It is intentionally lightweight (no NetworkX, no external services) and read-only (does not write files or call LLM APIs).

**Contract status**: Phase 1 — report-only governance artifact. Truncation warnings are emitted but enforcement is not yet required.

---

## Schema Version

```
retrieval_graph_view_v1
```

---

## Top-Level Required Fields

| Field | Type | Description |
|---|---|---|
| `ok` | bool | Whether the payload represents a successful run |
| `schema_version` | string | Fixed: `retrieval_graph_view_v1` |
| `repo` | string | Repository identifier |
| `root` | string | Repository root path |
| `query` | string | The original query string |
| `scope` | object | Scope parameters (repo, root, limit, max_hops) |
| `summary` | object | Node/edge counts and truncation signals |
| `nodes` | array | List of graph nodes |
| `edges` | array | List of graph edges |
| `warnings` | array | Warning strings (may be empty) |

---

## Scope Schema (required sub-object)

| Field | Type | Description |
|---|---|---|
| `repo` | string | Repository identifier |
| `root` | string | Repository root path |
| `limit` | int | Node limit (capped at 200) |
| `max_hops` | int | Maximum traversal depth (capped at 3) |

---

## Summary Schema (required sub-object)

| Field | Type | Description |
|---|---|---|
| `node_count` | int | Number of nodes in the subgraph |
| `edge_count` | int | Number of edges in the subgraph |
| `node_limit_applied` | bool | Whether truncation occurred |
| `max_hops` | int | Applied max_hops value |
| `limit` | int | Applied node limit |

---

## Node Schema

Each node in the `nodes` array has:

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique node identifier |
| `label` | string | Human-readable short label |
| `kind` | string | Node type: `file`, `chunk`, or other |
| `path` | string | File path (if applicable) |
| `source` | string | Origin: `source_plan`, `index`, `repomap` |
| `score` | float | Retrieval score |
| `chunk_count` | int | Number of chunks in this file (files only) |
| `evidence_confidence` | string \| null | EXTRACTED / INFERRED / AMBIGUOUS / UNKNOWN |
| `confidence_score` | float \| null | Numeric confidence in [0.0, 1.0] |
| `lineno` | int | Line number (chunks only) |
| `end_lineno` | int | End line number (chunks only) |

---

## Edge Schema

Each edge in the `edges` array has:

| Field | Type | Description |
|---|---|---|
| `source` | string | Source node ID |
| `target` | string | Target node ID |
| `kind` | string | Edge type: `file_chunk`, `neighbor`, `cochange`, `xref`, `scipr`, `graph_lookup` |
| `weight` | float | Edge weight (0.0–1.0) |

---

## Parameter Boundaries

| Parameter | Input Range | Applied Range | Behavior |
|---|---|---|---|
| `limit` | any int or str | 1–200 | Values outside are clamped; non-int strings use default 50 |
| `max_hops` | any int or str | 1–3 | Values above 3 are capped; below 1 use 1 |

When a boundary is exceeded, a warning is appended to the `warnings` array:

```python
# Example truncation warnings:
"node_limit_applied: truncated from 80 to 50 nodes"
"max_hops_capped: requested 10, capped at 3"
```

---

## Truncation Semantics

**`node_limit_applied = true`** means the graph contains fewer nodes than the total available candidates because `limit` was reached. This is normal for large retrieval sets.

**Warning interpretation**:

| Warning | Meaning | Action |
|---|---|---|
| `node_limit_applied` | Graph is a subset of candidates | Review whether limit is appropriate |
| `max_hops_capped` | Traversal depth was limited | Confirm 3-hop depth is sufficient |
| `no_nodes_available` | No candidates found | Check retrieval pipeline |

---

## Top-K Subgraph Principle

The retrieval graph view intentionally **does not** produce a full-repo graph. It limits to the top-K candidates by score, capping nodes at `limit` and depth at `max_hops`.

**Guardrails**:

- **DO NOT** use `retrieval_graph_view` as a full-repo dependency analysis tool
- **DO NOT** infer that unvisited nodes are irrelevant — they may be below the top-K threshold
- **DO NOT** treat `node_limit_applied = false` as "complete coverage" (other limits may apply upstream)

---

## Generating a Retrieval Graph View

### Programmatic

```python
from ace_lite.retrieval_graph_view import build_retrieval_graph_view

# Build with defaults (limit=50, max_hops=1)
graph = build_retrieval_graph_view(plan_payload)

# Custom boundaries
graph = build_retrieval_graph_view(
    plan_payload,
    limit=100,
    max_hops=2,
    repo="my-repo",
    root="/path/to/repo",
    query="fix auth"
)

# Check truncation
if graph["summary"]["node_limit_applied"]:
    print("Warning: graph is truncated")
    print(graph["warnings"])
```

### Available Functions

| Function | Purpose |
|---|---|
| `build_retrieval_graph_view(plan_payload, *, limit, max_hops, repo, root, query)` | Build a retrieval_graph_view_v1 dict |
| `RETRIEVAL_GRAPH_VIEW_SCHEMA_VERSION` | Constant: `"retrieval_graph_view_v1"` |

---

## Node Sources

The graph is built from four sources (in priority order):

1. **`source_plan.candidate_files`** — files selected by the planner
2. **`source_plan.candidate_chunks`** — symbol-level chunks within selected files
3. **`index.candidate_files`** — files found by the indexer
4. **`repomap.focused_files`** — files in the repository map focus set

---

## Edge Sources

| Edge Kind | Source |
|---|---|
| `file_chunk` | Path-based grouping (chunks belong to files) |
| `neighbor` | Repository neighbor relationships |
| `cochange` | Files that tend to change together |
| `xref` | Cross-reference relationships |
| `scipr` | SCIP symbol references |
| `graph_lookup` | Graph-based retrieval signals |

---

## Relationship to Other Artifacts

| Artifact | Relationship |
|---|---|
| `ContextReport` | Graph = machine-readable subgraph; ContextReport = human summary |
| `source_plan` payload | Graph is derived from source_plan candidates |
| `checkpoint_manifest` | Graph path recorded as optional artifact in Phase 1+ checkpoints |

---

## References

- Module: `src/ace_lite/retrieval_graph_view.py`
- Governance: `docs/maintainers/ADAPTIVE_PROMOTION_GOVERNANCE_2026-03-09.md`
- Evidence taxonomy: `src/ace_lite/source_plan/evidence_confidence.py`
