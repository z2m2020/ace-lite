# Golden Contract Test Maintenance Guide

**Date**: 2026-04-12
**Owner**: ACE-Lite Maintainers
**Related Tasks**: ALH1-0105.T2, ALH1-0105.T3

---

## Overview

Golden contract tests in `tests/integration/test_retrieval_evidence_golden.py` pair
pre-generated JSON fixtures with schema guard validation to catch contract drift
before it reaches production. The test suite verifies that:

1. A deterministic plan payload (`retrieval_evidence_minimal_plan.json`) can be
   consumed by `build_context_report_payload()` and `build_retrieval_graph_view()`
   without exceptions.
2. Both derived payloads pass `validate_context_report_payload()` and
   `validate_retrieval_graph_view_payload()` respectively.
3. Required top-level fields in both outputs remain stable across versions.

---

## Fixture Files

| File | Purpose |
|---|---|
| `tests/fixtures/retrieval_evidence_minimal_plan.json` | Deterministic input plan payload |
| `tests/fixtures/retrieval_evidence_context_report.json` | Expected context_report output |
| `tests/fixtures/retrieval_evidence_retrieval_graph.json` | Expected retrieval_graph output |

---

## When to Regenerate Fixtures

Regenerate fixtures when ANY of these conditions are met:

- A **schema guard** is added, removed, or renamed in `context_report.py` or
  `retrieval_graph_view.py` (e.g., a new required field, a renamed key).
- A **contract field** in `build_context_report_payload()` or
  `build_retrieval_graph_view()` changes value format (even if field name is
  unchanged).
- A new `evidence_confidence` value is introduced in the enum
  (`EXTRACTED`, `INFERRED`, `AMBIGUOUS`, `UNKNOWN`).
- The `schema_version` constant in either module is bumped.

**Do NOT regenerate** just because a default value, internal helper, or
non-contract field changes — only contract output shapes matter.

---

## How to Regenerate Fixtures

### Step 1: Run the generation script

From the repo root:

```bash
python -c "
import json
from ace_lite.context_report import build_context_report_payload
from ace_lite.retrieval_graph_view import build_retrieval_graph_view

plan_payload = json.load(open('tests/fixtures/retrieval_evidence_minimal_plan.json'))
ctx = build_context_report_payload(plan_payload)
rg = build_retrieval_graph_view(plan_payload)

json.dump(plan_payload, open('tests/fixtures/retrieval_evidence_minimal_plan.json','w'), indent=2, sort_keys=True)
json.dump(ctx, open('tests/fixtures/retrieval_evidence_context_report.json','w'), indent=2, sort_keys=True)
json.dump(rg, open('tests/fixtures/retrieval_evidence_retrieval_graph.json','w'), indent=2, sort_keys=True)
print('Fixtures regenerated')
"
```

### Step 2: Run the full golden test suite

```bash
pytest -q tests/integration/test_retrieval_evidence_golden.py
```

All 3 tests must pass. If a test fails, either:
- The contract intentionally changed → update the test assertions to match.
- The fixture was not regenerated correctly → regenerate.

### Step 3: Commit

```bash
git add tests/fixtures/ tests/integration/test_retrieval_evidence_golden.py
git commit -m "tests: regenerate golden fixtures for retrieval evidence contract"
```

---

## Adding New Golden Fixtures

To add a new fixture (e.g., for a new artifact type):

1. Add the deterministic input payload to `tests/fixtures/` with a descriptive name.
2. Use `scripts/build_gap_report.py` or the module's `build_*` function to generate
   the expected output fixtures.
3. Add a new test function in `test_retrieval_evidence_golden.py` following the
   existing pattern: load fixture → validate schema → assert required fields.
4. Run `pytest -q tests/integration/test_retrieval_evidence_golden.py` to confirm
   the new test passes.
5. Commit both the fixture and the test.

---

## Fixture Design Constraints

- **Deterministic only**: Fixtures must be generated from deterministic inputs.
  No timestamps, no random seeds, no real file paths.
- **Minimal payload**: The `minimal_plan` fixture uses the smallest possible
  valid payload that exercises all code paths. Keep it minimal to make
  contract changes obvious.
- **Schema-versioned**: Each fixture output carries `schema_version` as its
  top-level field. When bumping a schema version, regenerate the corresponding
  fixture and update the test assertion.

---

## Relationship to Contract Docs

- **PQ003_EVIDENCE_OVERLAY_CONTRACT.md**: Describes the benchmark evidence overlay
  surface consumed by the freeze trend report.
- **CONTEXT_REPORT_CONTRACT.md**: Describes `context_report_v1` consumption contract.
- **RETRIEVAL_GRAPH_VIEW_CONTRACT.md**: Describes `retrieval_graph_view_v1`
  consumption contract.

These three docs are the **source of truth** for what fields must be stable.
Golden fixtures are the **machine-readable enforcement** of those stability
requirements. When a contract doc is updated, regenerate the corresponding
fixture.

---

## Architecture Golden Seam Rules (2026-04-16)

`tests/unit/test_architecture_golden.py` now also freezes several post-refactor
import/dependency seams that should remain stable unless a deliberate
architecture update is happening:

- `skills.py` -> `skills_catalog.py`
- CLI/MCP skill catalog surfaces -> `skills_contract.py`
- `source_plan.py` -> `context_refine_support.py`
- benchmark trend scripts -> `report_script_support.py`

Update the architecture golden tests whenever these seam imports move, and add a
matching note here explaining why the dependency boundary changed. This keeps
the maintenance guide aligned with the actual golden coverage instead of letting
new support seams drift without ownership.
