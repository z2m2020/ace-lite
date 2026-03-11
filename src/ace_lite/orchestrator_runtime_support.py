"""Runtime support helpers for orchestrator plan execution."""

from __future__ import annotations

from typing import Any

from ace_lite.exceptions import StageContractError
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import StageRegistry
from ace_lite.pipeline.stage_tags import build_stage_tags
from ace_lite.pipeline.types import StageContext, StageMetric


def run_pre_source_plan_stages(
    *,
    orchestrator: Any,
    repo: str,
    ctx: StageContext,
    registry: StageRegistry,
    hook_bus: HookBus,
) -> tuple[list[StageMetric], StageContractError | None]:
    stage_metrics: list[StageMetric] = []
    contract_error: StageContractError | None = None
    for stage_name in ("memory", "index", "repomap", "augment", "skills"):
        contract_error = orchestrator._execute_stage(
            stage_name=stage_name,
            repo=repo,
            ctx=ctx,
            registry=registry,
            hook_bus=hook_bus,
            stage_metrics=stage_metrics,
        )
        if contract_error is not None:
            break
    return stage_metrics, contract_error


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
) -> tuple[StageContractError | None, dict[str, Any]]:
    replay_cache_info = orchestrator._default_plan_replay_cache_info(root=root_path)
    if contract_error is not None:
        return contract_error, replay_cache_info

    if bool(orchestrator._config.plan_replay_cache.enabled):
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
        if isinstance(cached_source_plan, dict):
            ctx.state[orchestrator.PLAN_REPLAY_STAGE] = cached_source_plan
            stage_tags = build_stage_tags(
                stage_name=orchestrator.PLAN_REPLAY_STAGE,
                output=cached_source_plan,
            )
            stage_tags["plan_replay_cache_hit"] = True
            stage_tags["plan_replay_cache_safe"] = bool(
                replay_cache_info.get("stale_hit_safe", False)
            )
            stage_metrics.append(
                StageMetric(
                    stage=orchestrator.PLAN_REPLAY_STAGE,
                    elapsed_ms=float(replay_cache_info.get("lookup_ms", 0.0) or 0.0),
                    plugins=[],
                    tags=stage_tags,
                )
            )
            return None, replay_cache_info

        contract_error = orchestrator._execute_stage(
            stage_name=orchestrator.PLAN_REPLAY_STAGE,
            repo=repo,
            ctx=ctx,
            registry=registry,
            hook_bus=hook_bus,
            stage_metrics=stage_metrics,
        )
        if contract_error is None:
            replay_cache_info = orchestrator._store_source_plan_replay(
                query=query,
                repo=repo,
                replay_cache_path=replay_cache_path,
                replay_cache_key=replay_cache_key,
                source_plan_stage=ctx.state.get("source_plan", {}),
                replay_cache_info=replay_cache_info,
            )
        else:
            replay_cache_info["reason"] = "stage_contract_error"
        return contract_error, replay_cache_info

    contract_error = orchestrator._execute_stage(
        stage_name=orchestrator.PLAN_REPLAY_STAGE,
        repo=repo,
        ctx=ctx,
        registry=registry,
        hook_bus=hook_bus,
        stage_metrics=stage_metrics,
    )
    return contract_error, replay_cache_info


__all__ = [
    "run_pre_source_plan_stages",
    "run_source_plan_stage_with_replay",
]
