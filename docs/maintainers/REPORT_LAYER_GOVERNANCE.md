# Report Layer Governance

**Status**: Phase 1 - Advisory
**Owner**: Maintainers
**Last Updated**: 2026-04-12

---

## Purpose

This document defines the clear boundary between **primary execution surfaces** (which drive the pipeline) and **read-only audit surfaces** (which report on outcomes). The goal is to prevent accidental promotion of report-only artifacts into execution gates.

---

## Three-Layer Model

### Layer 1: Primary Execution Surface (source of truth)

| Artifact | Location | Purpose |
|---|---|---|
| `source_plan` payload | Pipeline output | Contains `candidate_files`, `candidate_chunks`, budgets, fingerprints |
| `validation` payload | Post-plan stage | Contains test results, diagnostics, sandbox metadata |
| `memory` signals | Memory provider | Provides hints, preferences, recent issues - treated as signals, not truth |

**Rule**: These artifacts may be used as inputs to downstream stages or CLI/MCP consumers.

### Layer 2: Read-Only Audit Surface (derived, non-authoritative)

| Artifact | Location | Purpose |
|---|---|---|
| `ContextReport` | `src/ace_lite/context_report.py` | Human-readable summary of plan payload (candidates, warnings, confidence breakdown) |
| `retrieval_graph_view` | `src/ace_lite/mcp_server/service.py` | Machine-readable subgraph of candidate relationships |
| `skill catalog` | `src/ace_lite/skills.py` (`build_skill_catalog`) | Human-readable index of available skills |

**Rule**: These artifacts MUST NOT be used as primary routing or gating signals.

### Layer 3: Project沉淀 Surface (documentation context)

| Artifact | Location | Purpose |
|---|---|---|
| `.context/` reports | `.context/*.md` | Research notes, borrowing reports, handoff documents |
| Benchmark reports | `artifacts/benchmark/` | Quality metrics, validation results |
| Checkpoints | `artifacts/validation/*/checkpoint*` | Historical snapshots for regression analysis |

**Rule**: These artifacts are for human consumption and offline analysis only.

---

## Explicitly Forbidden Patterns

### Pattern F1: Report Artifact as Gate

```python
# WRONG - Do not do this
if context_report.warnings:
    raise PipelineError("Cannot proceed due to ContextReport warnings")
```

### Pattern F2: Skill Catalog as Router

```python
# WRONG - Do not do this
skills = load_skill_catalog()
if query in skills.available:
    route_to_skill(query)
```

### Pattern F3: Retrieval Graph as Primary Selector

```python
# WRONG - Do not do this
graph_view = load_retrieval_graph()
primary_candidates = graph_view.filter(query)
```

---

## Allowed Patterns

### Pattern A1: Report as Human-Facing Output

```python
# CORRECT - Write report for human review
write_context_report_markdown(payload, output_path=Path("report.md"))
```

### Pattern A2: Report as Observability

```python
# CORRECT - Log warnings for telemetry
if context_report.warnings:
    logger.warning("ContextReport has %d warnings", len(context_report.warnings))
```

### Pattern A3: Skill Catalog as Discovery Aid

```python
# CORRECT - Display available skills for user
catalog = build_skill_catalog(manifest)
click.echo(catalog)
```

---

## ContextReport Specific Rules

From `docs/maintainers/CONTEXT_REPORT_CONTRACT.md`:

- **Do NOT** use `confidence_breakdown` as a ranking signal
- **Do NOT** use `surprising_connections` as primary routing
- **Do NOT** modify `schema_version` without versioning the contract
- **Do NOT** use ContextReport as a gate during Phase 1

---

## Skill Catalog Specific Rules

- Skills are discovered via `build_skill_manifest()` + `select_skills()` + lazy-load
- Skill catalog is a **read-only projection** of manifest metadata
- Do NOT add hardcoded skill registry or alias resolution

---

## Relationship to GitNexus/Rowboat Borrowing

These rules emerged from borrowing studies:

| Source | Borrowing | Status |
|---|---|---|
| GitNexus | Short, hard agent-facing contracts | Adopted as Layer 2 |
| GitNexus | Auto-write global config | **Rejected** |
| Rowboat | Template stable output | Adopted as Layer 3 |
| Rowboat | Hardcoded skill registry | **Rejected** |

---

## Enforcement

- `pytest -q tests/unit/test_context_report.py` validates ContextReport contract
- `pytest -q tests/unit/test_skills.py` validates skill catalog behavior
- Any PR adding Layer 2 artifacts as execution gates requires maintainer approval

---

## Change Process

To change the classification of any artifact:

1. File a proposal in the `docs/maintainers/` directory
2. Update this document and `CONTEXT_REPORT_CONTRACT.md`
3. Add or update corresponding contract tests
4. Update `skills/cross-project-borrowing-and-adaptation.md` if borrowing-related
