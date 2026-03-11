# Xref Ingest (SCIP / Stack Graphs)

ACE-Lite supports protocolized xref ingest through `scip` stage scoring.

## Providers

Use `--scip-provider` (or config `scip_provider`) with one of:

- `auto` (default): tries `scip_lite -> xref_json -> stack_graphs_json`
- `scip_lite`
- `xref_json`
- `stack_graphs_json`

`--scip-generate-fallback/--no-scip-generate-fallback` controls whether ACE-Lite generates local `scip-lite` index when the external ingest source is missing/invalid.

## Expected payload examples

### xref_json

```json
{
  "schema_version": "xref-json-1",
  "edges": [
    {"from": "src/a.py", "to": "src/b.py", "weight": 2}
  ]
}
```

### stack_graphs_json

```json
{
  "schema_version": "stack-graphs-1",
  "graph_edges": [
    {
      "from": {"path": "src/a.py"},
      "to": {"path": "src/b.py"}
    }
  ]
}
```

The loader normalizes edge lists into inbound counts and merges boosts into candidate ranking.
