"""Lifecycle dispatch runtime helpers for orchestrator plan execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator_runtime_support_types import (
    OrchestratorLifecycleRequest,
    OrchestratorLifecycleResult,
)
from ace_lite.pipeline.types import StageMetric


def execute_orchestrator_lifecycle(
    *,
    orchestrator: Any,
    request: OrchestratorLifecycleRequest,
    iter_lifecycle_descriptors_fn: Callable[[], tuple[Any, ...]],
    run_pre_source_plan_stages_fn: Callable[
        ..., tuple[list[StageMetric], StageContractError | None]
    ],
    run_source_plan_stage_with_replay_fn: Callable[
        ..., tuple[StageContractError | None, dict[str, Any]]
    ],
    run_post_source_plan_runtime_fn: Callable[..., StageContractError | None],
) -> OrchestratorLifecycleResult:
    stage_metrics: list[StageMetric] = []
    contract_error: StageContractError | None = None
    replay_cache_info = orchestrator._default_plan_replay_cache_info(root=request.root_path)

    for descriptor in iter_lifecycle_descriptors_fn():
        if descriptor.name == "pre_source_plan":
            stage_metrics, contract_error = run_pre_source_plan_stages_fn(
                orchestrator=orchestrator,
                repo=request.repo,
                ctx=request.ctx,
                registry=request.registry,
                hook_bus=request.hook_bus,
                descriptor=descriptor,
            )
        elif descriptor.name == "source_plan":
            contract_error, replay_cache_info = run_source_plan_stage_with_replay_fn(
                orchestrator=orchestrator,
                query=request.query,
                repo=request.repo,
                root_path=request.root_path,
                temporal_input=request.temporal_input,
                plugins_loaded=request.plugins_loaded,
                ctx=request.ctx,
                registry=request.registry,
                hook_bus=request.hook_bus,
                stage_metrics=stage_metrics,
                contract_error=contract_error,
                descriptor=descriptor,
            )
        elif descriptor.name == "post_source_plan":
            contract_error = run_post_source_plan_runtime_fn(
                orchestrator=orchestrator,
                query=request.query,
                repo=request.repo,
                ctx=request.ctx,
                registry=request.registry,
                hook_bus=request.hook_bus,
                stage_metrics=stage_metrics,
                contract_error=contract_error,
                descriptor=descriptor,
            )
        else:
            raise KeyError(f"unsupported lifecycle descriptor: {descriptor.name}")

    return OrchestratorLifecycleResult(
        stage_metrics=stage_metrics,
        contract_error=contract_error,
        replay_cache_info=replay_cache_info,
    )
