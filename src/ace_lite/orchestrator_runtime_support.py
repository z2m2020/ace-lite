"""Runtime support helpers for orchestrator plan execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ace_lite.agent_loop.controller import BoundedLoopController
from ace_lite.conventions import load_conventions
from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator_runtime_finalization import (
    execute_orchestrator_finalization,
)
from ace_lite.orchestrator_runtime_lifecycle import (
    execute_orchestrator_lifecycle,
)
from ace_lite.orchestrator_runtime_post_source import (
    execute_post_source_plan_agent_loop,
    execute_post_source_plan_runtime,
)
from ace_lite.orchestrator_runtime_pre_source import (
    execute_pre_source_plan_stages,
)
from ace_lite.orchestrator_runtime_preparation import (
    execute_orchestrator_preparation,
)
from ace_lite.orchestrator_runtime_source_plan import (
    execute_finalize_source_plan_replay,
    execute_prepare_source_plan_replay,
    execute_source_plan_stage_with_replay,
)
from ace_lite.orchestrator_runtime_support_compat import (
    build_orchestrator_runtime_support_compat,
)
from ace_lite.orchestrator_runtime_support_types import (
    ORCHESTRATOR_LIFECYCLE,
    POST_SOURCE_PLAN_LIFECYCLE,
    PRE_SOURCE_PLAN_LIFECYCLE,
    SOURCE_PLAN_LIFECYCLE,
    OrchestratorAgentLoopResult,
    OrchestratorFinalizationDependencies,
    OrchestratorFinalizationResult,
    OrchestratorLifecycleDescriptor,
    OrchestratorLifecycleResult,
    OrchestratorPreparationResult,
    OrchestratorSourcePlanReplayResult,
    get_lifecycle_descriptor,
    iter_lifecycle_descriptors,
)
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import StageRegistry
from ace_lite.pipeline.stage_tags import build_stage_tags
from ace_lite.pipeline.types import StageContext, StageMetric
from ace_lite.schema import validate_context_plan

_RUNTIME_SUPPORT_COMPAT = build_orchestrator_runtime_support_compat(
    pre_stage_names=PRE_SOURCE_PLAN_LIFECYCLE.stage_names,
    source_plan_stage_names=SOURCE_PLAN_LIFECYCLE.stage_names,
    post_stage_names=POST_SOURCE_PLAN_LIFECYCLE.stage_names,
)


def run_orchestrator_lifecycle(
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
) -> OrchestratorLifecycleResult:
    return execute_orchestrator_lifecycle(
        orchestrator=orchestrator,
        query=query,
        repo=repo,
        root_path=root_path,
        temporal_input=temporal_input,
        plugins_loaded=plugins_loaded,
        ctx=ctx,
        registry=registry,
        hook_bus=hook_bus,
        iter_lifecycle_descriptors_fn=iter_lifecycle_descriptors,
        run_pre_source_plan_stages_fn=run_pre_source_plan_stages,
        run_source_plan_stage_with_replay_fn=run_source_plan_stage_with_replay,
        run_post_source_plan_runtime_fn=run_post_source_plan_runtime,
    )


def run_orchestrator_preparation(
    *,
    orchestrator: Any,
    query: str,
    repo: str,
    root: str,
    time_range: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    filters: dict[str, Any] | None = None,
) -> OrchestratorPreparationResult:
    return execute_orchestrator_preparation(
        orchestrator=orchestrator,
        query=query,
        repo=repo,
        root=root,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        filters=filters,
        load_conventions_fn=load_conventions,
    )


def run_orchestrator_finalization(
    *,
    orchestrator: Any,
    query: str,
    repo: str,
    root_path: str,
    conventions: dict[str, Any],
    ctx: StageContext,
    stage_metrics: list[StageMetric],
    plugins_loaded: list[str],
    started_at: datetime,
    total_ms: float,
    contract_error: StageContractError | None,
    replay_cache_info: dict[str, Any],
) -> OrchestratorFinalizationResult:
    return execute_orchestrator_finalization(
        query=query,
        repo=repo,
        root_path=root_path,
        conventions=conventions,
        ctx=ctx,
        stage_metrics=stage_metrics,
        plugins_loaded=plugins_loaded,
        started_at=started_at,
        total_ms=total_ms,
        contract_error=contract_error,
        replay_cache_info=replay_cache_info,
        dependencies=build_orchestrator_finalization_dependencies(
            orchestrator=orchestrator
        ),
        apply_contract_error_to_payload_fn=_apply_contract_error_to_payload,
        validate_context_plan_fn=validate_context_plan,
    )


def build_orchestrator_finalization_dependencies(
    *,
    orchestrator: Any,
) -> OrchestratorFinalizationDependencies:
    def _record_durable_stats(**kwargs: Any) -> dict[str, Any]:
        return orchestrator._runtime_observability_service.record_durable_stats(
            **kwargs,
            learning_router_rollout_decision=(
                orchestrator._last_learning_router_rollout_decision
            ),
        )

    return OrchestratorFinalizationDependencies(
        build_plan_payload=orchestrator._build_plan_payload,
        export_stage_trace=orchestrator._runtime_observability_service.export_stage_trace,
        record_durable_stats=_record_durable_stats,
        runtime_state=orchestrator._runtime_state,
        runtime_manager=orchestrator._runtime_manager,
    )


def run_pre_source_plan_stages(
    *,
    orchestrator: Any,
    repo: str,
    ctx: StageContext,
    registry: StageRegistry,
    hook_bus: HookBus,
    descriptor: OrchestratorLifecycleDescriptor = PRE_SOURCE_PLAN_LIFECYCLE,
) -> tuple[list[StageMetric], StageContractError | None]:
    return execute_pre_source_plan_stages(
        orchestrator=orchestrator,
        repo=repo,
        ctx=ctx,
        registry=registry,
        hook_bus=hook_bus,
        descriptor=descriptor,
        run_stage_sequence_fn=_run_stage_sequence,
    )


def run_source_plan_stage_with_replay(
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
    stage_metrics: list[StageMetric],
    contract_error: StageContractError | None,
    descriptor: OrchestratorLifecycleDescriptor = SOURCE_PLAN_LIFECYCLE,
) -> tuple[StageContractError | None, dict[str, Any]]:
    return execute_source_plan_stage_with_replay(
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
        prepare_source_plan_replay_fn=prepare_source_plan_replay,
        finalize_source_plan_replay_fn=finalize_source_plan_replay,
        build_stage_tags_fn=build_stage_tags,
        run_stage_sequence_fn=_run_stage_sequence,
    )


def prepare_source_plan_replay(
    *,
    orchestrator: Any,
    query: str,
    repo: str,
    root_path: str,
    temporal_input: dict[str, Any],
    plugins_loaded: list[str],
    ctx: StageContext,
) -> OrchestratorSourcePlanReplayResult:
    return execute_prepare_source_plan_replay(
        orchestrator=orchestrator,
        query=query,
        repo=repo,
        root_path=root_path,
        temporal_input=temporal_input,
        plugins_loaded=plugins_loaded,
        ctx=ctx,
    )


def finalize_source_plan_replay(
    *,
    orchestrator: Any,
    query: str,
    repo: str,
    source_plan_stage: Any,
    contract_error: StageContractError | None,
    replay_result: OrchestratorSourcePlanReplayResult,
) -> dict[str, Any]:
    return execute_finalize_source_plan_replay(
        orchestrator=orchestrator,
        query=query,
        repo=repo,
        source_plan_stage=source_plan_stage,
        contract_error=contract_error,
        replay_result=replay_result,
    )


def run_post_source_plan_runtime(
    *,
    orchestrator: Any,
    query: str,
    repo: str,
    ctx: StageContext,
    registry: StageRegistry,
    hook_bus: HookBus,
    stage_metrics: list[StageMetric],
    contract_error: StageContractError | None,
    descriptor: OrchestratorLifecycleDescriptor = POST_SOURCE_PLAN_LIFECYCLE,
) -> StageContractError | None:
    return execute_post_source_plan_runtime(
        orchestrator=orchestrator,
        query=query,
        repo=repo,
        ctx=ctx,
        registry=registry,
        hook_bus=hook_bus,
        stage_metrics=stage_metrics,
        contract_error=contract_error,
        descriptor=descriptor,
        run_stage_sequence_fn=_run_stage_sequence,
        run_post_source_plan_agent_loop_fn=run_post_source_plan_agent_loop,
    )


def run_post_source_plan_agent_loop(
    *,
    orchestrator: Any,
    query: str,
    repo: str,
    ctx: StageContext,
    registry: StageRegistry,
    hook_bus: HookBus,
    stage_metrics: list[StageMetric],
) -> OrchestratorAgentLoopResult:
    return execute_post_source_plan_agent_loop(
        orchestrator=orchestrator,
        query=query,
        repo=repo,
        ctx=ctx,
        registry=registry,
        hook_bus=hook_bus,
        stage_metrics=stage_metrics,
        controller_cls=BoundedLoopController,
        get_stage_state_fn=_get_stage_state,
        resolve_agent_loop_rerun_stages_fn=_resolve_agent_loop_rerun_stages,
    )


_run_stage_sequence = _RUNTIME_SUPPORT_COMPAT.run_stage_sequence
_get_stage_state = _RUNTIME_SUPPORT_COMPAT.get_stage_state
_apply_contract_error_to_payload = _RUNTIME_SUPPORT_COMPAT.apply_contract_error_to_payload


def _resolve_agent_loop_rerun_stages(*, action_type: str) -> list[str]:
    return _RUNTIME_SUPPORT_COMPAT.resolve_agent_loop_rerun_stages(
        action_type=action_type
    )


__all__ = [
    "ORCHESTRATOR_LIFECYCLE",
    "POST_SOURCE_PLAN_LIFECYCLE",
    "PRE_SOURCE_PLAN_LIFECYCLE",
    "SOURCE_PLAN_LIFECYCLE",
    "OrchestratorAgentLoopResult",
    "OrchestratorFinalizationDependencies",
    "OrchestratorFinalizationResult",
    "OrchestratorLifecycleDescriptor",
    "OrchestratorLifecycleResult",
    "OrchestratorPreparationResult",
    "OrchestratorSourcePlanReplayResult",
    "build_orchestrator_finalization_dependencies",
    "finalize_source_plan_replay",
    "get_lifecycle_descriptor",
    "iter_lifecycle_descriptors",
    "prepare_source_plan_replay",
    "run_orchestrator_finalization",
    "run_orchestrator_lifecycle",
    "run_orchestrator_preparation",
    "run_post_source_plan_agent_loop",
    "run_post_source_plan_runtime",
    "run_pre_source_plan_stages",
    "run_source_plan_stage_with_replay",
]
