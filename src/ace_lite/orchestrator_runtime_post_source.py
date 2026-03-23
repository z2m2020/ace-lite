"""Post-source runtime helpers for orchestrator plan execution."""

from __future__ import annotations

from typing import Any, Callable

from ace_lite.exceptions import StageContractError
from ace_lite.orchestrator_runtime_support_types import (
    OrchestratorAgentLoopResult,
    OrchestratorLifecycleDescriptor,
)
from ace_lite.pipeline.hooks import HookBus
from ace_lite.pipeline.registry import StageRegistry
from ace_lite.pipeline.types import StageContext, StageMetric
from ace_lite.runtime_stats import build_branch_validation_archive_payload


def execute_post_source_plan_runtime(
    *,
    orchestrator: Any,
    query: str,
    repo: str,
    ctx: StageContext,
    registry: StageRegistry,
    hook_bus: HookBus,
    stage_metrics: list[StageMetric],
    contract_error: StageContractError | None,
    descriptor: OrchestratorLifecycleDescriptor,
    run_stage_sequence_fn: Callable[..., StageContractError | None],
    run_post_source_plan_agent_loop_fn: Callable[..., OrchestratorAgentLoopResult],
) -> StageContractError | None:
    if contract_error is not None:
        return contract_error

    contract_error = run_stage_sequence_fn(
        orchestrator=orchestrator,
        repo=repo,
        ctx=ctx,
        registry=registry,
        hook_bus=hook_bus,
        stage_metrics=stage_metrics,
        stage_names=descriptor.stage_names,
    )
    if contract_error is not None:
        return contract_error

    if not descriptor.runs_agent_loop or not bool(orchestrator._config.agent_loop.enabled):
        return None

    agent_loop_result = run_post_source_plan_agent_loop_fn(
        orchestrator=orchestrator,
        query=query,
        repo=repo,
        ctx=ctx,
        registry=registry,
        hook_bus=hook_bus,
        stage_metrics=stage_metrics,
    )
    if isinstance(agent_loop_result.summary, dict):
        branch_validation_archive = build_branch_validation_archive_payload(
            branch_batch=agent_loop_result.summary.get("branch_batch"),
            branch_selection=agent_loop_result.summary.get("branch_selection"),
        )
        agent_loop_result.summary["branch_validation_archive"] = (
            branch_validation_archive
        )
        ctx.state["_branch_validation_archive"] = branch_validation_archive
    ctx.state["_agent_loop"] = agent_loop_result.summary
    return agent_loop_result.contract_error


def execute_post_source_plan_agent_loop(
    *,
    orchestrator: Any,
    query: str,
    repo: str,
    ctx: StageContext,
    registry: StageRegistry,
    hook_bus: HookBus,
    stage_metrics: list[StageMetric],
    controller_cls: type[Any],
    get_stage_state_fn: Callable[..., dict[str, Any]],
    resolve_agent_loop_rerun_stages_fn: Callable[..., list[str]],
) -> OrchestratorAgentLoopResult:
    controller = controller_cls(
        enabled=orchestrator._config.agent_loop.enabled,
        max_iterations=orchestrator._config.agent_loop.max_iterations,
        max_focus_paths=orchestrator._config.agent_loop.max_focus_paths,
        query_hint_max_chars=orchestrator._config.agent_loop.query_hint_max_chars,
    )
    current_query = str(query or "")
    pending_action = controller.select_action(
        source_plan_stage=get_stage_state_fn(ctx=ctx, stage_name="source_plan"),
        validation_stage=get_stage_state_fn(ctx=ctx, stage_name="validation"),
    )
    if pending_action is None:
        return OrchestratorAgentLoopResult(
            contract_error=None,
            summary=controller.default_summary(final_query=current_query),
            final_query=current_query,
        )

    last_action = dict(pending_action)
    while pending_action is not None and controller.can_continue():
        last_action = dict(pending_action)
        action_type = str(last_action.get("action_type") or "")
        rerun_stages = resolve_agent_loop_rerun_stages_fn(action_type=action_type)
        previous_validation_stage = get_stage_state_fn(ctx=ctx, stage_name="validation")
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
                return OrchestratorAgentLoopResult(
                    contract_error=contract_error,
                    summary=controller.finalize(
                        stop_reason="stage_contract_error",
                        last_action=last_action,
                        final_query=current_query,
                    ),
                    final_query=current_query,
                )
            if stage_metrics:
                stage_metrics[-1].tags["agent_loop_iteration"] = iteration_index
                stage_metrics[-1].tags["agent_loop_action"] = action_type

        controller.record_iteration(
            action=last_action,
            query=current_query,
            rerun_stages=rerun_stages,
            source_plan_stage=get_stage_state_fn(ctx=ctx, stage_name="source_plan"),
            previous_validation_stage=previous_validation_stage,
            validation_stage=get_stage_state_fn(ctx=ctx, stage_name="validation"),
        )
        pending_action = controller.select_action(
            source_plan_stage=get_stage_state_fn(ctx=ctx, stage_name="source_plan"),
            validation_stage=get_stage_state_fn(ctx=ctx, stage_name="validation"),
        )
        if pending_action is None:
            return OrchestratorAgentLoopResult(
                contract_error=None,
                summary=controller.finalize(
                    stop_reason="completed",
                    last_action=last_action,
                    final_query=current_query,
                ),
                final_query=current_query,
            )

    summary = controller.finalize(
        stop_reason="max_iterations",
        last_action=last_action,
        final_query=current_query,
    )
    stage_metrics.append(
        StageMetric(
            stage="agent_loop",
            elapsed_ms=0.0,
            plugins=[],
            tags={
                "stop_reason": str(summary.get("stop_reason") or ""),
                "iteration_count": int(summary.get("iteration_count", 0) or 0),
                "actions_executed": int(summary.get("actions_executed", 0) or 0),
            },
        )
    )
    return OrchestratorAgentLoopResult(
        contract_error=None,
        summary=summary,
        final_query=current_query,
    )
