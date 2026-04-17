# ContextReport Consumption Contract

**Schema Version**: `context_report_v1`
**Phase**: Phase 1
**Module**: `src/ace_lite/context_report.py`

---

## Overview

`ContextReport` is a read-only, human- and agent-readable audit report derived from an already-computed plan payload. It does **not** call LLM APIs or external services, and does **not** modify the input payload.

**Contract status**: Phase 1 — report-only governance artifact. The `validate_context_report_payload()` guard is available but enforcement is not yet required.

---

## Schema Version

```
context_report_v1
```

The `schema_version` field is required and must equal `context_report_v1`. The schema version must not be changed without a corresponding version bump and migration plan.

---

## Required Fields

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Fixed: `context_report_v1` |
| `query` | string | The original retrieval/query string |
| `repo` | string | Repository identifier |
| `root` | string | Repository root path |
| `summary` | object | Candidate and validation counts (see Summary schema below) |
| `core_nodes` | array | List of retrieved candidate file/chunk nodes |
| `warnings` | array | List of warning strings (may be empty) |

---

## Summary Schema (required sub-object)

| Field | Type | Description |
|---|---|---|
| `candidate_file_count` | int | Number of unique retrieved files |
| `candidate_chunk_count` | int | Number of retrieved chunks |
| `validation_test_count` | int | Number of validation tests found |
| `stage_count` | int | Number of pipeline stages run |
| `degraded_reason_count` | int | Number of degraded/partial signal reasons |
| `has_validation_payload` | bool | Whether a validation payload was present |
| `memory_hit_count` | int | Number of long-term memory hits exposed through `memory.ltm.selected` |
| `memory_abstract_hit_count` | int | Number of memory hits exposed at `abstract` or `overview` level |
| `memory_observation_hit_count` | int | Number of long-term memory hits whose `memory_kind` is `observation` |
| `memory_fact_hit_count` | int | Number of long-term memory hits whose `memory_kind` is `fact` |
| `memory_stale_warning_count` | int | Number of long-term memory hits marked `freshness_state=stale` |

---

## Optional Fields

| Field | Type | Description |
|---|---|---|
| `ok` | bool | Whether the payload represents a successful run (absent/true = success) |
| `surprising_connections` | array | Unexpected cross-module relationships detected |
| `confidence_breakdown` | object | Evidence strength counts by category (EXTRACTED/INFERRED/AMBIGUOUS/UNKNOWN) |
| `memory_summary` | object | Report-only summary of long-term memory layering, stale warnings, and signal counts |
| `knowledge_gaps` | array | Identified gaps in retrieved context |
| `suggested_questions` | array | Agent-generated questions to resolve gaps |
| `inputs` | object | Flags indicating which inputs were available |

---

## Memory Summary Schema

`memory_summary` is optional and report-only. It summarizes what the already-computed plan payload exposed under the `memory` stage. It must not be used as a ranking gate.

| Field | Type | Description |
|---|---|---|
| `count` | int | Top-level `memory.count` when present |
| `ltm_selected_count` | int | Number of selected long-term memory entries reported by `memory.ltm.selected_count` |
| `hit_count` | int | Actual number of entries in `memory.ltm.selected` |
| `abstract_hit_count` | int | Number of entries whose `abstraction_level` is `abstract` or `overview` |
| `observation_hit_count` | int | Number of selected entries with `memory_kind=observation` |
| `fact_hit_count` | int | Number of selected entries with `memory_kind=fact` |
| `stale_warning_count` | int | Number of selected entries with `freshness_state=stale` |
| `feedback_signal_counts` | object | Pass-through summary of long-term memory feedback signals |
| `abstraction_counts` | object | Counts by `abstract` / `overview` / `detail` |

---

## Confidence Breakdown Schema

| Field | Type | Description |
|---|---|---|
| `extracted_count` | int | Chunks with direct evidence (EXTRACTED) |
| `inferred_count` | int | Chunks inferred via graph/semantic signals |
| `ambiguous_count` | int | Chunks with ambiguous evidence |
| `unknown_count` | int | Chunks with no identifiable evidence source |
| `total_count` | int | Total chunks assessed |

**Taxonomy (PRD R8503)**:

| Level | Score | Meaning |
|---|---|---|
| `EXTRACTED` | 1.0 | Direct symbol hit, exact rg hit, SCIP reference |
| `INFERRED` | 0.6–0.9 | cochange, graph_lookup, semantic rerank, memory hint |
| `AMBIGUOUS` | 0.1–0.5 | hint-only, stale memory, fallback ranker |
| `UNKNOWN` | 0.0 | Cannot identify evidence source |

---

## Generating a ContextReport

### CLI (via `ace-lite plan`)

```bash
# Generate a context report as part of the plan pipeline
ace-lite plan --query "fix validation flow" --repo ace-lite --root . --context-report-path artifacts/context-reports/2026-04-11/context_report.md
```

The report is written to the path passed in `--context-report-path`, for example `artifacts/context-reports/YYYY-MM-DD/context_report.md`.

### Programmatic

```python
from ace_lite.context_report import build_context_report_payload, validate_context_report_payload

# Build from plan payload
plan_payload = {...}  # any source_plan output dict
report = build_context_report_payload(plan_payload)

# Validate against schema
validated = validate_context_report_payload(report)

# Render as markdown
from ace_lite.context_report import render_context_report_markdown
md = render_context_report_markdown(validated)
```

### Python API

```python
from ace_lite.context_report import write_context_report_markdown

result = write_context_report_markdown(
    plan_payload,
    output_path=Path("artifacts/context-reports/report.md")
)
# result keys: ok, path, byte_count, schema_version
```

---

## Available Functions (`__all__`)

| Function | Purpose |
|---|---|
| `build_context_report_payload(plan_payload)` | Build a context_report_v1 dict from a plan payload |
| `validate_context_report_payload(payload)` | Validate required keys and types; raises `ValueError` on failure |
| `render_context_report_markdown(payload)` | Render a payload as a Markdown string |
| `write_context_report_markdown(payload, output_path)` | Write markdown report to a file |

---

## Guardrails

### DO

- Use `validate_context_report_payload()` before treating a ContextReport as authoritative
- Handle `ok=false` payloads gracefully (empty/minimal input)
- Check `warnings` array for truncation or missing data signals

### DO NOT

- **Do NOT** build new main-chain logic on top of ContextReport fields without a governance proposal
- **Do NOT** treat the `confidence_breakdown` as a ranking signal — it is strictly report-only
- **Do NOT** use `surprising_connections` as a primary routing mechanism
- **Do NOT** treat `memory_summary` as a ranking or trust oracle; it is an audit surface over already-selected memory
- **Do NOT** modify `schema_version` without versioning the contract and updating consumers
- **Do NOT** use ContextReport as a gate or blocker during Phase 1

---

## Relationship to Other Artifacts

| Artifact | Relationship |
|---|---|
| `source_plan` payload | ContextReport is derived from this; it does not replace it |
| `retrieval_graph_view` | Complementary; ContextReport = human summary, graph = machine-readable subgraph |
| `problem_surface` | PQ-003 surfaces can be joined with ContextReport for evidence gap analysis |
| `checkpoint_manifest` | ContextReport path recorded as optional artifact in Phase 1+ checkpoints |

---

## References

- Module: `src/ace_lite/context_report.py`
- Validation guard: `validate_context_report_payload()` (lines 794–827)
- Evidence confidence taxonomy: `src/ace_lite/source_plan/evidence_confidence.py`
- Governance: `docs/maintainers/ADAPTIVE_PROMOTION_GOVERNANCE_2026-03-09.md`
