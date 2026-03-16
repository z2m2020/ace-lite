"""Lifecycle dispatch runtime helpers for orchestrator plan execution."""

from __future__ import annotations

from typing import Any, Callable

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator_runtime_support_types import OrchestratorLifecycleResult
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import StageRegistry
from ace_lite.pipeline.types import StageContext, StageMetric


def execute_orchestrator_lifecycle(
    *,
    orchestrator: Any,
    query: str,
    repo: str,
    root_path: str,
    temporal_input: dict[str, Any],
    plugins_loaded: list[str],
    ctx: StageContext,
    registry: StageRegistry,
    hook_bus: HookBus,
    iter_lifecycle_descriptors_fn: Callable[[], tuple[Any, ...]],
    run_pre_source_plan_stages_fn: Callable[..., tuple[list[StageMetric], StageContractError | None]],
    run_source_plan_stage_with_replay_fn: Callable[..., tuple[StageContractError | None, dict[str, Any]]],
    run_post_source_plan_runtime_fn: Callable[..., StageContractError | None],
) -> OrchestratorLifecycleResult:
    stage_metrics: list[StageMetric] = []
    contract_error: StageContractError | None = None
    replay_cache_info = orchestrator._default_plan_replay_cache_info(root=root_path)

    for descriptor in iter_lifecycle_descriptors_fn():
        if descriptor.name == "pre_source_plan":
            stage_metrics, contract_error = run_pre_source_plan_stages_fn(
                orchestrator=orchestrator,
                repo=repo,
                ctx=ctx,
                registry=registry,
                hook_bus=hook_bus,
                descriptor=descriptor,
            )
        elif descriptor.name == "source_plan":
            contract_error, replay_cache_info = run_source_plan_stage_with_replay_fn(
                orchestrator=orchestrator,
                query=query,
                repo=repo,
                root_path=root_path,
                temporal_input=temporal_input,
                plugins_loaded=plugins_loaded,
                ctx=ctx,
                registry=registry,
                hook_bus=hook_bus,
                stage_metrics=stage_metrics,
                contract_error=contract_error,
                descriptor=descriptor,
            )
        elif descriptor.name == "post_source_plan":
            contract_error = run_post_source_plan_runtime_fn(
                orchestrator=orchestrator,
                query=query,
                repo=repo,
                ctx=ctx,
                registry=registry,
                hook_bus=hook_bus,
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
