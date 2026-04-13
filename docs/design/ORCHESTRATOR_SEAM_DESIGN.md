# Orchestrator Seam Design

**Status**: Follow-up design note after PRD-91 Phase 2
**Created**: 2026-04-12
**Updated**: 2026-04-13
**Based on**: GitNexus + Rowboat borrowing studies
**Risk Level**: HIGH - preserve plan payload and stage-contract compatibility

---

## Purpose

This document records the remaining seam-extraction direction for `AceOrchestrator` after PRD-91 Phase 2 landed the first round of contract and payload-builder extraction on `main`.

It is intentionally a design note, not an implementation backlog. The goal is to identify what still belongs in the orchestration shell, what has already been extracted, and which follow-on seams are still worth pursuing without breaking stable contracts.

---

## Current Baseline On `main`

The following seams are already real runtime code, not proposals:

1. `src/ace_lite/orchestrator_payload_builder.py`
- Owns final plan-payload assembly and default validation fallback shaping.

2. `src/ace_lite/orchestrator_contracts.py`
- Owns typed request/response helpers and the `ctx.state` projection used by payload assembly.

3. `src/ace_lite/orchestrator_runtime_*`
- Own runtime preparation, lifecycle/finalization support, replay, and observability helper services.

This document only covers what still looks structurally heavy after those extractions.

---

## Current Hotspots

From the current `src/ace_lite/orchestrator.py` analysis:

### 1. Pipeline Lifecycle Orchestration

**Location**: `AceOrchestrator.plan()`

The `plan()` method orchestrates three phases:
1. `run_orchestrator_preparation()` - setup
2. `run_orchestrator_lifecycle()` - stage execution
3. `run_orchestrator_finalization()` - payload building

### 2. Observability Payload Building

**Location**: `_build_plan_payload()` and the runtime observability support path

Handles:
- `stage_metrics` formatting
- `plugin_action_log` / `plugin_conflicts` aggregation
- `learning_router_rollout_decision` payload building
- `guarded_rollout` payload construction
- Default validation payload generation

### 3. Stage Execution Hooks

**Location**: `_execute_stage()`

Manages:
- Stage logging (debug)
- Plugin runtime execution
- Contract error handling
- `ctx.state` updates for special stages
- Long-term memory observation capture

### 4. Long-term Memory Context

**Location**: `_capture_long_term_stage_observation()`

Captures stage observations for memory persistence.

---

## Landed And Candidate Responsibilities

### Landed: OrchestratorPayloadBuilder

```python
build_default_validation_payload(...)
build_orchestrator_plan_payload(...)
```

This seam is already implemented in `src/ace_lite/orchestrator_payload_builder.py` and should remain outside the main orchestration shell.

### Candidate B: StageLifecycleRunner

```python
class StageLifecycleRunner:
    """Extract stage execution orchestration."""
    
    def __init__(self, orchestrator: AceOrchestrator, registry: StageRegistry):
        self._orchestrator = orchestrator
        self._registry = registry
    
    def run_lifecycle(
        self,
        *,
        query: str,
        repo: str,
        root_path: Path,
        temporal_input: dict,
        plugins_loaded: list[str],
        ctx: StageContext,
        hook_bus: HookBus,
    ) -> LifecycleResult:
        stage_metrics: list[StageMetric] = []
        contract_error: StageContractError | None = None
        
        for stage_name in self._orchestrator.PIPELINE_ORDER:
            error = self._orchestrator._execute_stage(
                stage_name=stage_name,
                repo=repo,
                ctx=ctx,
                registry=self._registry,
                hook_bus=hook_bus,
                stage_metrics=stage_metrics,
            )
            if error is not None:
                contract_error = error
                break
        
        return LifecycleResult(
            stage_metrics=stage_metrics,
            contract_error=contract_error,
        )
```

**Rationale**: the stage loop is still owned indirectly by the shell path and remains a reasonable future extraction target if compatibility coverage stays strong.

### Candidate C: ValidationPayloadFactory

```python
class ValidationPayloadFactory:
    """Extract default validation payload generation."""
    
    def create_disabled_payload(
        self,
        *,
        policy_version: str,
    ) -> dict[str, Any]:
        # Move _default_validation_payload() here
        ...
```

**Rationale**: Phase 2 already moved the default-validation payload shaping out of the shell; this candidate only remains relevant if more validation policy branching accumulates again.

---

## Interface Proposal

```python
# New file: src/ace_lite/orchestrator_runner.py

from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass
class OrchestratorPreparation:
    root_path: Path
    conventions: dict[str, Any]
    hook_bus: Any
    plugins_loaded: list[str]
    registry: Any
    temporal_input: dict[str, Any]
    ctx: Any

@dataclass
class LifecycleResult:
    stage_metrics: list[Any]
    contract_error: Any | None
    replay_cache_info: dict[str, Any] | None = None

@dataclass
class FinalizationResult:
    payload: dict[str, Any]


class OrchestratorRunner:
    """
    Shell responsibilities extracted from AceOrchestrator.
    
    This class is responsible for:
    - Preparation orchestration
    - Lifecycle management
    - Finalization orchestration
    
    It does NOT implement stage logic (those remain in stage handlers).
    """
    
    def __init__(self, orchestrator: AceOrchestrator):
        self._orchestrator = orchestrator
    
    def prepare(
        self,
        *,
        query: str,
        repo: str,
        root: str,
        ...
    ) -> OrchestratorPreparation:
        ...
    
    def run_lifecycle(
        self,
        prep: OrchestratorPreparation,
        ...
    ) -> LifecycleResult:
        ...
    
    def finalize(
        self,
        prep: OrchestratorPreparation,
        lifecycle: LifecycleResult,
        ...
    ) -> FinalizationResult:
        ...
    
    def execute(self, *, query: str, repo: str, root: str, ...) -> dict[str, Any]:
        """Convenience method that runs prepare -> lifecycle -> finalize."""
        prep = self.prepare(query=query, repo=repo, root=root, ...)
        lifecycle = self.run_lifecycle(prep=prep, ...)
        finalization = self.finalize(prep=prep, lifecycle=lifecycle, ...)
        return finalization.payload
```

---

## Constraints (Must Preserve)

1. **Pipeline order**: `memory -> index -> repomap -> augment -> skills -> source_plan -> validation`
2. **Public payload contract**: `_build_plan_payload()` output format must remain stable
3. **Guardrails**: `ace_plan_quick` guardrails must not be implicitly removed
4. **Memory search guardrails**: Must remain functional
5. **Stage handlers**: `_run_memory`, `_run_index`, etc. remain in `AceOrchestrator`

---

## Migration Strategy

### Phase 1: Landed baseline (already done on `main`)

1. Extract payload assembly into `orchestrator_payload_builder.py`
2. Extract typed request/response and state projection into `orchestrator_contracts.py`
3. Keep `AceOrchestrator.plan()` as the public shell
4. Add focused contract and payload-builder regression tests

### Phase 2: Future lifecycle-loop extraction

1. Create `StageLifecycleRunner`
2. Move stage loop from `AceOrchestrator` to runner
3. Keep stage handlers in `AceOrchestrator`
4. Add integration tests for lifecycle

### Phase 3: Future preparation extraction

1. Create `OrchestratorPreparation` factory
2. Move `run_orchestrator_preparation()` logic
3. Test preparation in isolation

---

## Test Requirements

Before any new seam extraction beyond the current baseline:

1. Contract regression tests for `_build_plan_payload()` output
2. Stage handler unit tests
3. Integration tests for full pipeline
4. Payload structure assertions

```bash
pytest -q tests/unit/test_orchestrator.py
pytest -q tests/integration/ -k "orchestrator or plan"
```

---

## Relationship to Borrowing Studies

| Source | Borrowing | Status |
|---|---|---|
| GitNexus | Shared analysis core | Adopted in `OrchestratorRunner` design |
| GitNexus | CLI/server shell separation | Informs migration strategy |
| Rowboat | Small, direct tests | Informs test requirements |

---

## When NOT to Proceed

Do NOT proceed with extraction if:

1. Contract regression tests fail
2. Stage handler tests fail
3. Integration tests fail
4. Payload structure changes unexpectedly

---

## Rollback

```bash
git restore -- src/ace_lite/orchestrator.py src/ace_lite/orchestrator_runner.py tests/
```

---

## References

- `src/ace_lite/orchestrator.py` - Current implementation
- `src/ace_lite/orchestrator_payload_builder.py` - Current payload-builder seam
- `src/ace_lite/orchestrator_contracts.py` - Current typed contract and state projection seam
- `src/ace_lite/orchestrator_runtime_support.py` - Existing support functions
- `docs/design/ARCHITECTURE_OVERVIEW.md` - Architecture context
- `docs/design/ORCHESTRATOR_DESIGN.md` - Current runtime-shell contract
- `docs/design/SKILL_CATALOG_DISCOVERABILITY.md` - Related design
- `docs/maintainers/REPORT_LAYER_GOVERNANCE.md` - Layer classification
