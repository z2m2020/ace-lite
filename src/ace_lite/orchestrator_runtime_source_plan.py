"""Source-plan replay runtime helpers for orchestrator plan execution."""

from __future__ import annotations

from typing import Any, Callable

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator_runtime_support_types import (
    OrchestratorLifecycleDescriptor,
    OrchestratorSourcePlanReplayResult,
)
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import StageRegistry
from ace_lite.pipeline.types import StageContext, StageMetric


def execute_source_plan_stage_with_replay(
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
    descriptor: OrchestratorLifecycleDescriptor,
    prepare_source_plan_replay_fn: Callable[..., OrchestratorSourcePlanReplayResult],
    finalize_source_plan_replay_fn: Callable[..., dict[str, Any]],
    build_stage_tags_fn: Callable[..., dict[str, Any]],
    run_stage_sequence_fn: Callable[..., StageContractError | None],
) -> tuple[StageContractError | None, dict[str, Any]]:
    replay_result = prepare_source_plan_replay_fn(
        orchestrator=orchestrator,
        query=query,
        repo=repo,
        root_path=root_path,
        temporal_input=temporal_input,
        plugins_loaded=plugins_loaded,
        ctx=ctx,
    )
    replay_cache_info = replay_result.replay_cache_info
    if contract_error is not None:
        return contract_error, replay_cache_info

    stage_name = descriptor.stage_names[0]
    if isinstance(replay_result.cached_source_plan, dict):
        ctx.state[stage_name] = replay_result.cached_source_plan
        stage_tags = build_stage_tags_fn(
            stage_name=stage_name,
            output=replay_result.cached_source_plan,
        )
        stage_tags["plan_replay_cache_hit"] = True
        stage_tags["plan_replay_cache_safe"] = bool(
            replay_cache_info.get("stale_hit_safe", False)
        )
        stage_metrics.append(
            StageMetric(
                stage=stage_name,
                elapsed_ms=float(replay_cache_info.get("lookup_ms", 0.0) or 0.0),
                plugins=[],
                tags=stage_tags,
            )
        )
        return None, replay_cache_info

    contract_error = run_stage_sequence_fn(
        orchestrator=orchestrator,
        repo=repo,
        ctx=ctx,
        registry=registry,
        hook_bus=hook_bus,
        stage_metrics=stage_metrics,
        stage_names=descriptor.stage_names,
    )
    replay_cache_info = finalize_source_plan_replay_fn(
        orchestrator=orchestrator,
        query=query,
        repo=repo,
        source_plan_stage=ctx.state.get(stage_name, {}),
        contract_error=contract_error,
        replay_result=replay_result,
    )
    return contract_error, replay_cache_info


def execute_prepare_source_plan_replay(
    *,
    orchestrator: Any,
    query: str,
    repo: str,
    root_path: str,
    temporal_input: dict[str, Any],
    plugins_loaded: list[str],
    ctx: StageContext,
) -> OrchestratorSourcePlanReplayResult:
    replay_cache_info = orchestrator._default_plan_replay_cache_info(root=root_path)
    if not bool(orchestrator._config.plan_replay_cache.enabled):
        return OrchestratorSourcePlanReplayResult(
            replay_cache_info=replay_cache_info,
            replay_cache_path=None,
            replay_cache_key=None,
            cached_source_plan=None,
            cache_enabled=False,
        )

    replay_cache_key = orchestrator._build_plan_replay_key(
        query=query,
        repo=repo,
        root=root_path,
        temporal_input=temporal_input,
        plugins_loaded=plugins_loaded,
        conventions_hashes=orchestrator._conventions_hashes,
        memory_stage=ctx.state.get("memory", {}),
        index_stage=ctx.state.get("index", {}),
        repomap_stage=ctx.state.get("repomap", {}),
        augment_stage=ctx.state.get("augment", {}),
        skills_stage=ctx.state.get("skills", {}),
    )
    replay_cache_path = orchestrator._resolve_plan_replay_cache_path(root=root_path)
    cached_source_plan, replay_cache_info = orchestrator._load_replayed_source_plan(
        root=root_path,
        replay_cache_path=replay_cache_path,
        replay_cache_key=replay_cache_key,
    )
    return OrchestratorSourcePlanReplayResult(
        replay_cache_info=replay_cache_info,
        replay_cache_path=replay_cache_path,
        replay_cache_key=str(replay_cache_key),
        cached_source_plan=(
            dict(cached_source_plan) if isinstance(cached_source_plan, dict) else None
        ),
        cache_enabled=True,
    )


def execute_finalize_source_plan_replay(
    *,
    orchestrator: Any,
    query: str,
    repo: str,
    source_plan_stage: Any,
    contract_error: StageContractError | None,
    replay_result: OrchestratorSourcePlanReplayResult,
) -> dict[str, Any]:
    replay_cache_info = dict(replay_result.replay_cache_info)
    if not replay_result.cache_enabled:
        return replay_cache_info
    if contract_error is not None:
        replay_cache_info["reason"] = "stage_contract_error"
        return replay_cache_info
    if replay_result.replay_cache_path is None or replay_result.replay_cache_key is None:
        return replay_cache_info
    return orchestrator._store_source_plan_replay(
        query=query,
        repo=repo,
        replay_cache_path=replay_result.replay_cache_path,
        replay_cache_key=replay_result.replay_cache_key,
        source_plan_stage=source_plan_stage,
        replay_cache_info=replay_cache_info,
    )
