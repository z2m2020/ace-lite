"""Pre-source runtime helpers for orchestrator plan execution."""

from __future__ import annotations

from typing import Any, Callable

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator_runtime_support_types import OrchestratorLifecycleDescriptor
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import StageRegistry
from ace_lite.pipeline.types import StageContext, StageMetric


def execute_pre_source_plan_stages(
    *,
    orchestrator: Any,
    repo: str,
    ctx: StageContext,
    registry: StageRegistry,
    hook_bus: HookBus,
    descriptor: OrchestratorLifecycleDescriptor,
    run_stage_sequence_fn: Callable[..., StageContractError | None],
) -> tuple[list[StageMetric], StageContractError | None]:
    stage_metrics: list[StageMetric] = []
    contract_error = run_stage_sequence_fn(
        orchestrator=orchestrator,
        repo=repo,
        ctx=ctx,
        registry=registry,
        hook_bus=hook_bus,
        stage_metrics=stage_metrics,
        stage_names=descriptor.stage_names,
    )
    return stage_metrics, contract_error
