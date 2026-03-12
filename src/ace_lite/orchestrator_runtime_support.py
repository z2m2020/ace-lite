"""Runtime support helpers for orchestrator plan execution."""

from __future__ import annotations

from typing import Any

from ace_lite.agent_loop.controller import BoundedLoopController
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
) -> StageContractError | None:
    if contract_error is not None:
        return contract_error

    contract_error = orchestrator._execute_stage(
        stage_name="validation",
        repo=repo,
        ctx=ctx,
        registry=registry,
        hook_bus=hook_bus,
        stage_metrics=stage_metrics,
    )
    if contract_error is not None:
        return contract_error

    if not bool(orchestrator._config.agent_loop.enabled):
        return None

    controller = BoundedLoopController(
        enabled=orchestrator._config.agent_loop.enabled,
        max_iterations=orchestrator._config.agent_loop.max_iterations,
        max_focus_paths=orchestrator._config.agent_loop.max_focus_paths,
        query_hint_max_chars=orchestrator._config.agent_loop.query_hint_max_chars,
    )
    current_query = str(query or "")
    pending_action = controller.select_action(
        source_plan_stage=(
            ctx.state.get("source_plan", {})
            if isinstance(ctx.state.get("source_plan"), dict)
            else {}
        ),
        validation_stage=(
            ctx.state.get("validation", {})
            if isinstance(ctx.state.get("validation"), dict)
            else {}
        ),
    )
    if pending_action is None:
        ctx.state["_agent_loop"] = controller.default_summary(final_query=current_query)
        return None

    last_action = dict(pending_action)
    while pending_action is not None and controller.can_continue():
        last_action = dict(pending_action)
        action_type = str(last_action.get("action_type") or "")
        rerun_stages = (
            ["validation"]
            if action_type == "request_validation_retry"
            else ["index", "repomap", "augment", "skills", "source_plan", "validation"]
        )
        current_query = controller.build_incremental_query(
            base_query=current_query,
            action=last_action,
        )
        iteration_index = controller.iteration_count + 1
        iteration_ctx = StageContext(
            query=current_query,
            repo=ctx.repo,
            root=ctx.root,
            state=ctx.state,
        )

        for stage_name in rerun_stages:
            contract_error = orchestrator._execute_stage(
                stage_name=stage_name,
                repo=repo,
                ctx=iteration_ctx,
                registry=registry,
                hook_bus=hook_bus,
                stage_metrics=stage_metrics,
            )
            if contract_error is not None:
                ctx.state["_agent_loop"] = controller.finalize(
                    stop_reason="stage_contract_error",
                    last_action=last_action,
                    final_query=current_query,
                )
                return contract_error
            if stage_metrics:
                stage_metrics[-1].tags["agent_loop_iteration"] = iteration_index
                stage_metrics[-1].tags["agent_loop_action"] = action_type

        controller.record_iteration(
            action=last_action,
            query=current_query,
            rerun_stages=rerun_stages,
            source_plan_stage=(
                ctx.state.get("source_plan", {})
                if isinstance(ctx.state.get("source_plan"), dict)
                else {}
            ),
            validation_stage=(
                ctx.state.get("validation", {})
                if isinstance(ctx.state.get("validation"), dict)
                else {}
            ),
        )
        pending_action = controller.select_action(
            source_plan_stage=(
                ctx.state.get("source_plan", {})
                if isinstance(ctx.state.get("source_plan"), dict)
                else {}
            ),
            validation_stage=(
                ctx.state.get("validation", {})
                if isinstance(ctx.state.get("validation"), dict)
                else {}
            ),
        )
        if pending_action is None:
            ctx.state["_agent_loop"] = controller.finalize(
                stop_reason="completed",
                last_action=last_action,
                final_query=current_query,
            )
            return None

    ctx.state["_agent_loop"] = controller.finalize(
        stop_reason="max_iterations",
        last_action=last_action,
        final_query=current_query,
    )
    return None


__all__ = [
    "run_post_source_plan_runtime",
    "run_pre_source_plan_stages",
    "run_source_plan_stage_with_replay",
]
